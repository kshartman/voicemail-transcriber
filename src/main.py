import os
import time
import logging
from dotenv import load_dotenv
from imap_client import IMAPEmailClient
from email_forwarder import EmailForwarder
from whisper_transcriber import WhisperTranscriber

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()


def process_emails():
    imap_host = os.getenv('IMAP_HOST')
    imap_username = os.getenv('IMAP_USERNAME')
    imap_password = os.getenv('IMAP_PASSWORD')
    imap_port = int(os.getenv('IMAP_PORT', '993'))
    
    smtp_host = os.getenv('SMTP_HOST')
    smtp_username = os.getenv('SMTP_USERNAME')
    smtp_password = os.getenv('SMTP_PASSWORD')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    
    logger.info(f"SMTP Configuration: {smtp_host}:{smtp_port} as {smtp_username}")
    
    forward_to = os.getenv('FORWARD_TO')
    poll_interval = int(os.getenv('POLL_INTERVAL', '60'))
    
    imap_client = IMAPEmailClient(imap_host, imap_username, imap_password, imap_port)
    email_forwarder = EmailForwarder(smtp_host, smtp_port, smtp_username, smtp_password)
    whisper = WhisperTranscriber(model_size="medium", device="cuda")
    
    logger.info("Starting email processing service...")
    logger.info(f"Whisper device info: {whisper.get_device_info()}")
    
    while True:
        try:
            imap_client.connect()
            imap_client.select_folder("INBOX")
            
            unread_messages = imap_client.get_unread_messages()
            logger.info(f"Found {len(unread_messages)} unread messages")
            
            for msg_id in unread_messages:
                try:
                    message = imap_client.get_message(msg_id)
                    audio_attachments = imap_client.get_audio_attachments(message)
                    
                    transcription = ""
                    if audio_attachments:
                        logger.info(f"Processing {len(audio_attachments)} audio attachments")
                        for filename, audio_data in audio_attachments:
                            try:
                                transcript = whisper.transcribe_audio(audio_data, filename)
                                transcription += f"\n\n--- Transcription of {filename} ---\n{transcript}\n"
                            except Exception as e:
                                logger.error(f"Failed to transcribe {filename}: {e}")
                                transcription += f"\n\n--- Failed to transcribe {filename} ---\n"
                    
                    email_forwarder.forward_email(
                        message, 
                        forward_to, 
                        transcription if transcription else None,
                        audio_attachments
                    )
                    
                    imap_client.mark_as_read(msg_id)
                    logger.info(f"Message {msg_id} processed and forwarded")
                    
                except Exception as e:
                    logger.error(f"Failed to process message {msg_id}: {e}")
            
            imap_client.disconnect()
            
        except Exception as e:
            logger.error(f"Error in email processing loop: {e}")
        
        logger.info(f"Sleeping for {poll_interval} seconds...")
        time.sleep(poll_interval)


if __name__ == "__main__":
    process_emails()