import smtplib
import logging
import socket
from email.message import EmailMessage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


class EmailForwarder:
    def __init__(self, smtp_host: str, smtp_port: int, username: str, password: str, use_tls: bool = True):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.use_tls = use_tls

    def forward_email(self, original_message: EmailMessage, forward_to: str, 
                     transcription: Optional[str] = None, 
                     audio_attachments: Optional[List[Tuple[str, bytes]]] = None):
        try:
            # Check if we have attachments to determine structure
            has_attachments = False
            for part in original_message.walk():
                if part.get_content_disposition() == 'attachment':
                    has_attachments = True
                    break
            
            if has_attachments or audio_attachments:
                # Mixed for attachments with alternative inside for text/html
                msg = MIMEMultipart('mixed')
                body_part = MIMEMultipart('alternative')
            else:
                # Just alternative for text/html without attachments
                msg = MIMEMultipart('alternative')
                body_part = msg
            
            msg['From'] = self.username
            msg['To'] = forward_to
            msg['Subject'] = f"Fwd: {original_message.get('Subject', 'No Subject')}"
            
            original_from = original_message.get('From', 'Unknown')
            original_date = original_message.get('Date', 'Unknown')
            
            # Get both plain text and HTML versions
            plain_body = self._get_body_text(original_message)
            html_body = self._get_body_html(original_message)
            
            # Build plain text version
            plain_parts = []
            
            # Add transcription first if available
            if transcription:
                plain_parts.extend([
                    "---------- Audio Transcription ----------",
                    "",
                    f"--- Transcription of {original_message.get('Subject', 'voicemail')} ---",
                    transcription,
                    "",
                    "---------- End Transcription ----------",
                    ""
                ])
            
            # Then add forwarded message
            plain_parts.extend([
                f"---------- Forwarded message ----------",
                f"From: {original_from}",
                f"Date: {original_date}",
                f"Subject: {original_message.get('Subject', 'No Subject')}",
                f"To: {original_message.get('To', 'Unknown')}",
                "",
                plain_body
            ])
            
            plain_text = "\n".join(plain_parts)
            body_part.attach(MIMEText(plain_text, 'plain'))
            
            # Build HTML version if original had HTML
            if html_body:
                # Transcription section first if available
                transcription_html = ""
                if transcription:
                    transcription_html = f"""
                    <div style="border: 1px solid #007acc; background-color: #e6f2ff; padding: 15px; margin: 10px 0; border-radius: 5px;">
                    <h3 style="margin-top: 0; color: #007acc;">🎙️ Audio Transcription</h3>
                    <p style="margin: 10px 0;"><strong>Transcription of {original_message.get('Subject', 'voicemail')}:</strong></p>
                    <div style="background-color: #fff; padding: 10px; border-radius: 3px; border: 1px solid #ddd;">
                    <p style="white-space: pre-wrap; margin: 0;">{transcription}</p>
                    </div>
                    </div>
                    """
                
                # Forwarded message header
                html_header = f"""
                <div style="margin: 20px 0;">
                <hr style="border: none; border-top: 2px solid #ccc;">
                <p style="color: #666; margin: 10px 0;"><strong>---------- Forwarded message ----------</strong></p>
                <div style="background-color: #f8f8f8; padding: 10px; border-left: 3px solid #ccc;">
                <p style="margin: 5px 0;"><strong>From:</strong> {original_from}<br>
                <strong>Date:</strong> {original_date}<br>
                <strong>Subject:</strong> {original_message.get('Subject', 'No Subject')}<br>
                <strong>To:</strong> {original_message.get('To', 'Unknown')}</p>
                </div>
                </div>
                """
                
                # Wrap original HTML body to preserve its formatting
                wrapped_html_body = f"""
                <div style="margin: 10px 0;">
                {html_body}
                </div>
                """
                
                full_html = f"{transcription_html}{html_header}{wrapped_html_body}"
                body_part.attach(MIMEText(full_html, 'html'))
            
            # If we used a separate body part, attach it to the main message
            if body_part != msg:
                msg.attach(body_part)
            
            for part in original_message.walk():
                if part.get_content_disposition() == 'attachment':
                    filename = part.get_filename()
                    if filename and not self._is_audio_file(filename):
                        attachment = MIMEBase('application', 'octet-stream')
                        attachment.set_payload(part.get_payload(decode=True))
                        encoders.encode_base64(attachment)
                        attachment.add_header('Content-Disposition', f'attachment; filename= {filename}')
                        msg.attach(attachment)
            
            if audio_attachments:
                for filename, content in audio_attachments:
                    attachment = MIMEBase('application', 'octet-stream')
                    attachment.set_payload(content)
                    encoders.encode_base64(attachment)
                    attachment.add_header('Content-Disposition', f'attachment; filename= {filename}')
                    msg.attach(attachment)
            
            logger.info(f"Connecting to SMTP server {self.smtp_host}:{self.smtp_port}")
            
            # Test connection first
            try:
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.settimeout(5)
                result = test_socket.connect_ex((self.smtp_host, self.smtp_port))
                test_socket.close()
                logger.info(f"Socket test to {self.smtp_host}:{self.smtp_port} result: {result}")
            except Exception as sock_e:
                logger.error(f"Socket test failed: {sock_e}")
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                logger.info("SMTP connection established")
                if self.use_tls:
                    logger.info("Starting TLS")
                    server.starttls()
                logger.info(f"Logging in as {self.username}")
                server.login(self.username, self.password)
                logger.info("Login successful, sending message")
                server.send_message(msg)
                
            logger.info(f"Email forwarded successfully to {forward_to}")
            
        except Exception as e:
            logger.error(f"Failed to forward email to {self.smtp_host}:{self.smtp_port} - {e}")
            raise

    def _get_body_text(self, message: EmailMessage) -> str:
        body = ""
        
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
                    except Exception:
                        continue
        else:
            try:
                body = message.get_payload(decode=True).decode('utf-8', errors='ignore')
            except Exception:
                body = str(message.get_payload())
        
        return body

    def _is_audio_file(self, filename: str) -> bool:
        audio_extensions = {'.mp3', '.mp4', '.m4a', '.wav', '.ogg', '.flac', '.aac', '.wma', '.opus'}
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        return f'.{ext}' in audio_extensions

    def _get_body_html(self, message: EmailMessage) -> str:
        html = ""
        
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == "text/html":
                    try:
                        html = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
                    except Exception:
                        continue
        else:
            if message.get_content_type() == "text/html":
                try:
                    html = message.get_payload(decode=True).decode('utf-8', errors='ignore')
                except Exception:
                    html = ""
        
        return html