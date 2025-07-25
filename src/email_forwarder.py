import os
import smtplib
import logging
import socket
import html
import time
import email.utils
from email.message import EmailMessage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, List, Tuple
from retry_utils import retry_with_backoff
from config_validator import ConfigValidator

logger = logging.getLogger(__name__)


class EmailForwarder:
    def __init__(self, smtp_host: str, smtp_port: int, username: Optional[str] = None, 
                 password: Optional[str] = None, connection_security: str = 'STARTTLS'):
        """
        Initialize EmailForwarder
        
        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            username: Username for authentication (optional)
            password: Password for authentication (optional)
            connection_security: 'SSL', 'STARTTLS', or 'NONE'
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.connection_security = connection_security.upper()

    def forward_email(self, original_message: EmailMessage, forward_to: str, 
                     transcription: Optional[str] = None, 
                     audio_attachments: Optional[List[Tuple[str, bytes]]] = None,
                     phone_number: Optional[str] = None):
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
            
            # Add phone number to subject if provided
            original_subject = original_message.get('Subject', 'No Subject')
            if phone_number:
                logger.info(f"Adding phone number {phone_number} to subject")
                msg['Subject'] = f"[{phone_number}] Fwd: {original_subject}"
            else:
                logger.info("No phone number provided for subject")
                msg['Subject'] = f"Fwd: {original_subject}"
            
            # Add headers to prevent spam filtering
            msg['X-Mailer'] = 'Voicemail Transcriber 1.0'
            msg['MIME-Version'] = '1.0'
            msg['Message-ID'] = f"<{time.time()}.{os.getpid()}@{socket.getfqdn()}>"
            msg['Date'] = email.utils.formatdate(localtime=True)
            
            # Preserve important headers from original
            if original_message.get('References'):
                msg['References'] = original_message.get('References')
            if original_message.get('In-Reply-To'):
                msg['In-Reply-To'] = original_message.get('In-Reply-To')
            
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
                    # Escape HTML entities to prevent injection
                    escaped_transcription = html.escape(transcription)
                    escaped_subject = html.escape(original_message.get('Subject', 'voicemail'))
                    
                    transcription_html = f"""
                    <div style="border: 1px solid #007acc; background-color: #e6f2ff; padding: 15px; margin: 10px 0; border-radius: 5px;">
                    <h3 style="margin-top: 0; color: #007acc;">🎙️ Audio Transcription</h3>
                    <p style="margin: 10px 0;"><strong>Transcription of {escaped_subject}:</strong></p>
                    <div style="background-color: #fff; padding: 10px; border-radius: 3px; border: 1px solid #ddd;">
                    <p style="white-space: pre-wrap; margin: 0;">{escaped_transcription}</p>
                    </div>
                    </div>
                    """
                
                # Forwarded message header
                html_header = f"""
                <div style="margin: 20px 0;">
                <hr style="border: none; border-top: 2px solid #ccc;">
                <p style="color: #666; margin: 10px 0;"><strong>---------- Forwarded message ----------</strong></p>
                <div style="background-color: #f8f8f8; padding: 10px; border-left: 3px solid #ccc;">
                <p style="margin: 5px 0;"><strong>From:</strong> {html.escape(original_from)}<br>
                <strong>Date:</strong> {html.escape(original_date)}<br>
                <strong>Subject:</strong> {html.escape(original_message.get('Subject', 'No Subject'))}<br>
                <strong>To:</strong> {html.escape(original_message.get('To', 'Unknown'))}</p>
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
            
            # Use retry logic for SMTP operations
            self._send_with_retry(msg, forward_to)
            
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
        if not filename or '.' not in filename:
            return False
        ext = os.path.splitext(filename.lower())[1]
        return ext in audio_extensions

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
    
    @retry_with_backoff(max_attempts=3, initial_delay=2.0, exceptions=(Exception,))
    def _send_with_retry(self, msg, forward_to: str):
        """Send email with retry logic"""
        # Choose the appropriate SMTP class based on connection security
        if self.connection_security == 'SSL':
            logger.info(f"Connecting to SMTP server using SSL on {self.smtp_host}:{self.smtp_port}")
            smtp_class = smtplib.SMTP_SSL
            server = smtp_class(self.smtp_host, self.smtp_port, timeout=30)
        else:
            logger.info(f"Connecting to SMTP server on {self.smtp_host}:{self.smtp_port}")
            server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30)
        
        try:
            logger.info("SMTP connection established")
            
            # Apply STARTTLS if requested
            if self.connection_security == 'STARTTLS':
                logger.info("Starting TLS")
                server.starttls()
            
            # Authenticate if credentials provided
            if self.username and self.password:
                logger.info(f"Logging in as {ConfigValidator.mask_email(self.username)}")
                server.login(self.username, self.password)
                logger.info("Login successful")
            else:
                logger.info("No authentication credentials provided, sending without auth")
            
            # Send the message
            logger.info("Sending message")
            server.send_message(msg)
            logger.info(f"Email forwarded successfully to {ConfigValidator.mask_email(forward_to)}")
            
        finally:
            server.quit()
    
    def test_connection(self) -> bool:
        """Test SMTP connection without sending email"""
        try:
            # Choose the appropriate SMTP class
            if self.connection_security == 'SSL':
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=10)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10)
            
            try:
                # Apply STARTTLS if requested
                if self.connection_security == 'STARTTLS':
                    server.starttls()
                
                # Try to login if credentials provided
                if self.username and self.password:
                    server.login(self.username, self.password)
                
                logger.info("SMTP connection test successful")
                return True
            finally:
                server.quit()
                
        except Exception as e:
            logger.error(f"SMTP connection test failed: {e}")
            return False