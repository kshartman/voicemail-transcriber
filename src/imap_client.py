import os
import email
import logging
from typing import List, Tuple, Optional
from imapclient import IMAPClient
from email.message import EmailMessage

logger = logging.getLogger(__name__)


class IMAPEmailClient:
    def __init__(self, host: str, username: str, password: str, port: int = 993, use_ssl: bool = True):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.use_ssl = use_ssl
        self.client = None

    def connect(self):
        try:
            self.client = IMAPClient(self.host, port=self.port, use_uid=True, ssl=self.use_ssl)
            self.client.login(self.username, self.password)
            logger.info(f"Connected to IMAP server {self.host}")
        except Exception as e:
            logger.error(f"Failed to connect to IMAP server: {e}")
            raise

    def disconnect(self):
        if self.client:
            try:
                self.client.logout()
                logger.info("Disconnected from IMAP server")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")

    def select_folder(self, folder: str = "INBOX"):
        if not self.client:
            raise RuntimeError("Not connected to IMAP server")
        self.client.select_folder(folder)

    def get_unread_messages(self) -> List[int]:
        if not self.client:
            raise RuntimeError("Not connected to IMAP server")
        return self.client.search(['UNSEEN'])

    def get_message(self, msg_id: int) -> EmailMessage:
        if not self.client:
            raise RuntimeError("Not connected to IMAP server")
        
        raw_message = self.client.fetch([msg_id], ['RFC822'])[msg_id][b'RFC822']
        return email.message_from_bytes(raw_message)

    def mark_as_read(self, msg_id: int):
        if not self.client:
            raise RuntimeError("Not connected to IMAP server")
        self.client.add_flags([msg_id], ['\\Seen'])

    def get_audio_attachments(self, message: EmailMessage) -> List[Tuple[str, bytes]]:
        audio_attachments = []
        audio_extensions = {'.mp3', '.mp4', '.m4a', '.wav', '.ogg', '.flac', '.aac', '.wma', '.opus'}
        
        for part in message.walk():
            if part.get_content_disposition() == 'attachment':
                filename = part.get_filename()
                if filename:
                    ext = os.path.splitext(filename.lower())[1]
                    if ext in audio_extensions or part.get_content_type().startswith('audio/'):
                        content = part.get_payload(decode=True)
                        audio_attachments.append((filename, content))
                        logger.info(f"Found audio attachment: {filename}")
        
        return audio_attachments