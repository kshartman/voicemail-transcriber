import os
import email
import logging
import time
from typing import List, Tuple, Optional
from datetime import datetime
from imapclient import IMAPClient
from email.message import EmailMessage
from retry_utils import retry_with_backoff, RetryableConnection

logger = logging.getLogger(__name__)


class IMAPEmailClient(RetryableConnection):
    def __init__(self, host: str, username: str, password: str, port: int = 993, 
                 connection_security: str = 'SSL', max_retries: int = 3, retry_delay: float = 5.0):
        super().__init__(max_retries, retry_delay)
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.connection_security = connection_security.upper()
        self.client = None

    @retry_with_backoff(max_attempts=3, initial_delay=2.0, exceptions=(Exception,))
    def connect(self):
        try:
            # Use SSL for SSL connections, no SSL for STARTTLS (will upgrade later)
            use_ssl = (self.connection_security == 'SSL')
            self.client = IMAPClient(self.host, port=self.port, use_uid=True, ssl=use_ssl, timeout=30)
            
            # If using STARTTLS, upgrade the connection
            if self.connection_security == 'STARTTLS':
                self.client.starttls()
                logger.debug("STARTTLS upgrade successful")
            
            self.client.login(self.username, self.password)
            logger.debug(f"Connected to IMAP server {self.host}")
            self.reset_retry_counter()
        except Exception as e:
            logger.error(f"Failed to connect to IMAP server: {e}")
            raise

    def disconnect(self):
        if self.client:
            try:
                self.client.logout()
                logger.debug("Disconnected from IMAP server")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
            finally:
                self.client = None

    def select_folder(self, folder: str = "INBOX"):
        if not self.client:
            raise RuntimeError("Not connected to IMAP server")
        self.client.select_folder(folder)

    def get_unread_messages(self) -> List[int]:
        if not self.client:
            raise RuntimeError("Not connected to IMAP server")
        return self.client.search(['UNSEEN'])
    
    def get_all_messages(self) -> List[int]:
        if not self.client:
            raise RuntimeError("Not connected to IMAP server")
        return self.client.search(['ALL'])

    @retry_with_backoff(max_attempts=2, initial_delay=1.0, exceptions=(Exception,))
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
    
    def create_folder_if_not_exists(self, folder_name: str):
        """Create a folder if it doesn't exist"""
        if not self.client:
            raise RuntimeError("Not connected to IMAP server")
        
        try:
            # Check if folder exists
            folders = self.client.list_folders()
            folder_names = [f[2] for f in folders]
            
            if folder_name not in folder_names:
                self.client.create_folder(folder_name)
                logger.info(f"Created folder: {folder_name}")
            else:
                logger.debug(f"Folder already exists: {folder_name}")
        except Exception as e:
            logger.error(f"Error creating folder {folder_name}: {e}")
            raise
    
    @retry_with_backoff(max_attempts=2, initial_delay=1.0, exceptions=(Exception,))
    def move_message(self, msg_id: int, destination_folder: str):
        """Move a message to another folder"""
        if not self.client:
            raise RuntimeError("Not connected to IMAP server")
        
        try:
            # Copy message to destination folder
            self.client.copy([msg_id], destination_folder)
            # Mark original for deletion
            self.client.add_flags([msg_id], ['\\Deleted'])
            # Expunge to actually delete
            self.client.expunge()
            logger.info(f"Moved message {msg_id} to {destination_folder}")
        except Exception as e:
            logger.error(f"Error moving message {msg_id} to {destination_folder}: {e}")
            raise
    
    def delete_old_messages(self, folder: str, retention_days: int):
        """Delete messages older than retention_days from specified folder"""
        if not self.client:
            raise RuntimeError("Not connected to IMAP server")
        
        try:
            self.select_folder(folder)
            
            # Search for messages older than retention period
            # IMAP date format: DD-Mon-YYYY (e.g., 01-Jan-2023)
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            date_str = cutoff_date.strftime("%d-%b-%Y")
            old_messages = self.client.search(['BEFORE', date_str])
            
            if old_messages:
                logger.info(f"Found {len(old_messages)} messages older than {retention_days} days in {folder}")
                # Mark for deletion
                self.client.add_flags(old_messages, ['\\Deleted'])
                # Expunge to actually delete
                self.client.expunge()
                logger.info(f"Deleted {len(old_messages)} old messages from {folder}")
            else:
                logger.debug(f"No messages older than {retention_days} days found in {folder}")
                
        except Exception as e:
            logger.error(f"Error deleting old messages from {folder}: {e}")
            raise