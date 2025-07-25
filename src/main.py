import os
import time
import logging
import signal
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
from imap_client import IMAPEmailClient
from email_forwarder import EmailForwarder
from whisper_transcriber import WhisperTranscriber
from config_validator import ConfigValidator
from health_check import HealthCheck
from metrics import MetricsCollector

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# Global flag for graceful shutdown
shutdown_requested = False

# Global health check instance
health_check = None


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_requested, health_check
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True
    if health_check:
        health_check.shutdown()


def validate_connections(config):
    """Validate all account connections on startup"""
    logger.info("Validating connections...")
    
    # Test each account's IMAP connection
    for idx, account in enumerate(config['accounts']):
        logger.info(f"Validating {account['name']}...")
        
        # Test IMAP connection
        try:
            imap_client = IMAPEmailClient(
                account['imap_host'], 
                account['imap_username'], 
                account['imap_password'], 
                account['imap_port'],
                account.get('imap_security', 'SSL')
            )
            imap_client.connect()
            imap_client.disconnect()
            logger.info(f"{account['name']}: IMAP connection validated successfully")
        except Exception as e:
            logger.error(f"{account['name']}: IMAP connection validation failed: {e}")
            sys.exit(1)
        
        # Test SMTP connection (if account has custom SMTP settings)
        smtp_host = account.get('smtp_host', config.get('smtp_host'))
        if smtp_host:
            try:
                email_forwarder = EmailForwarder(
                    smtp_host,
                    account.get('smtp_port', config.get('smtp_port', 587)),
                    account.get('smtp_username', config.get('smtp_username')),
                    account.get('smtp_password', config.get('smtp_password')),
                    account.get('smtp_security', config.get('smtp_security', 'STARTTLS'))
                )
                if email_forwarder.test_connection():
                    logger.info(f"{account['name']}: SMTP connection validated successfully")
                else:
                    logger.error(f"{account['name']}: SMTP connection test failed")
                    sys.exit(1)
            except Exception as e:
                logger.error(f"{account['name']}: SMTP configuration validation failed: {e}")
                sys.exit(1)


def clean_old_messages(imap_client, archive_folder, retention_days):
    """Delete messages older than retention period from archive folder"""
    try:
        logger.info(f"Cleaning messages older than {retention_days} days from {archive_folder}")
        imap_client.delete_old_messages(archive_folder, retention_days)
    except Exception as e:
        logger.error(f"Failed to clean old messages: {e}")


def process_emails():
    global health_check, shutdown_requested
    
    # Get and validate configuration
    config = ConfigValidator.get_config()
    ConfigValidator.log_config(config)
    
    # Initialize health check and metrics
    health_check = HealthCheck()
    health_check.startup()
    
    metrics = MetricsCollector()
    
    # Validate connections before starting
    validate_connections(config)
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Initialize Whisper once for all accounts
    whisper = WhisperTranscriber(
        model_size=config['whisper_model'], 
        device="cuda",
        language=config['whisper_language']
    )
    
    logger.info("Starting email processing service...")
    logger.info(f"Monitoring {len(config['accounts'])} account(s)")
    logger.info(f"Whisper device info: {whisper.get_device_info()}")
    logger.info(f"Max attachment size: {config['max_attachment_size_mb']}MB")
    logger.info(f"Max attachments per email: {config['max_attachments_per_email']}")
    logger.info(f"Retention policy: {config['retention_days']} days")
    
    archive_folder = config['archive_folder']
    last_cleanup = datetime.now()
    
    # Mark service as healthy after successful initialization
    health_check.mark_healthy()
    
    while not shutdown_requested:
        # Process each account
        for account in config['accounts']:
            if shutdown_requested:
                break
                
            try:
                logger.info(f"Processing account: {account['name']}")
                
                # Create IMAP client for this account
                imap_client = IMAPEmailClient(
                    account['imap_host'], 
                    account['imap_username'], 
                    account['imap_password'], 
                    account['imap_port'],
                    account.get('imap_security', 'SSL')
                )
                
                # Create SMTP forwarder for this account
                email_forwarder = EmailForwarder(
                    account.get('smtp_host', config.get('smtp_host')),
                    account.get('smtp_port', config.get('smtp_port', 587)),
                    account.get('smtp_username', config.get('smtp_username')),
                    account.get('smtp_password', config.get('smtp_password')),
                    account.get('smtp_security', config.get('smtp_security', 'STARTTLS'))
                )
                
                imap_client.connect()
                
                # Create archive folder if it doesn't exist
                imap_client.create_folder_if_not_exists(archive_folder)
                
                # Select INBOX
                imap_client.select_folder("INBOX")
                
                # Get ALL messages from INBOX
                all_messages = imap_client.get_all_messages()
                logger.info(f"Found {len(all_messages)} messages in {account['name']} INBOX")
                
                forward_to = account['forward_to']
                phone_number = account.get('phone', None)
                masked_forward_to = ConfigValidator.mask_email(forward_to)
                logger.info(f"Account {account['name']}: forward_to={masked_forward_to}, phone={phone_number}")
                
                for msg_id in all_messages:
                    try:
                        metrics.start_processing()
                        message = imap_client.get_message(msg_id)
                        audio_attachments = imap_client.get_audio_attachments(message)
                        
                        # Check size limits
                        total_size = sum(len(data) for _, data in audio_attachments)
                        if total_size > config['max_attachment_size_mb'] * 1024 * 1024:
                            logger.warning(f"Message {msg_id} exceeds size limit ({total_size / 1024 / 1024:.1f}MB), skipping audio processing")
                            audio_attachments = []  # Skip audio processing but still forward
                        
                        if len(audio_attachments) > config['max_attachments_per_email']:
                            logger.warning(f"Message {msg_id} has too many attachments ({len(audio_attachments)}), processing first {config['max_attachments_per_email']}")
                            audio_attachments = audio_attachments[:config['max_attachments_per_email']]
                        
                        transcription = ""
                        if audio_attachments:
                            logger.info(f"Processing {len(audio_attachments)} audio attachments")
                            for filename, audio_data in audio_attachments:
                                try:
                                    metrics.start_transcription()
                                    transcript = whisper.transcribe_audio(audio_data, filename)
                                    metrics.end_transcription(success=True, bytes_processed=len(audio_data))
                                    transcription += f"\n\n--- Transcription of {filename} ---\n{transcript}\n"
                                except Exception as e:
                                    logger.error(f"Failed to transcribe {filename}: {e}")
                                    transcription += f"\n\n--- Failed to transcribe {filename} ---\n"
                                    metrics.end_transcription(success=False)
                        
                        # Forward the email (with or without transcription)
                        email_forwarder.forward_email(
                            message, 
                            forward_to, 
                            transcription if transcription else None,
                            audio_attachments,
                            phone_number
                        )
                        
                        # Move the message to archive folder instead of just marking as read
                        imap_client.move_message(msg_id, archive_folder)
                        logger.info(f"Message {msg_id} processed, forwarded, and moved to {archive_folder}")
                        
                        # Mark successful processing
                        health_check.mark_healthy()
                        metrics.end_processing(success=True)
                        
                    except Exception as e:
                        logger.error(f"Failed to process message {msg_id}: {e}", exc_info=True)
                        health_check.mark_failure()
                        metrics.end_processing(success=False)
            
                # Clean old messages once per day for this account
                if datetime.now() - last_cleanup > timedelta(days=1):
                    clean_old_messages(imap_client, archive_folder, config['retention_days'])
                
                imap_client.disconnect()
                
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                shutdown_requested = True
            except Exception as e:
                logger.error(f"Error processing account {account['name']}: {e}", exc_info=True)
                health_check.mark_failure()
                try:
                    if 'imap_client' in locals():
                        imap_client.disconnect()
                except Exception as disconnect_error:
                    logger.error(f"Failed to disconnect: {disconnect_error}")
        
        # Clean old messages once per day (after all accounts)
        if datetime.now() - last_cleanup > timedelta(days=1):
            last_cleanup = datetime.now()
        
        # Log metrics periodically
        metrics.log_periodic_summary(interval_minutes=60)
        
        if not shutdown_requested:
            logger.debug(f"Sleeping for {config['poll_interval']} seconds...")
            # Use a loop to check for shutdown during sleep
            for _ in range(config['poll_interval']):
                if shutdown_requested:
                    break
                time.sleep(1)
    
    logger.info("Email processing service stopped gracefully")
    
    # Log final metrics
    if 'metrics' in locals():
        logger.info("Final processing metrics:")
        metrics.metrics.log_summary()
    
    if health_check:
        health_check.shutdown()


if __name__ == "__main__":
    process_emails()