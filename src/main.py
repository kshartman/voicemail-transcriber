import os
import time
import logging
import signal
import sys
import socket
import platform
from datetime import datetime, timedelta
from dotenv import load_dotenv
from imap_client import IMAPEmailClient
from email_forwarder import EmailForwarder
from whisper_transcriber import WhisperTranscriber
from config_validator import ConfigValidator
from health_check import HealthCheck
from metrics import MetricsCollector
from email.message import EmailMessage
import smtplib

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


def send_startup_notification(config, device_info):
    """Send email notification when container starts/restarts"""
    try:
        # Get first account's forward_to for notification
        if not config['accounts']:
            logger.warning("No accounts configured for startup notification")
            return
        
        recipient = config['accounts'][0]['forward_to']
        # Get SMTP config from first account or global config
        account = config['accounts'][0]
        smtp_host = account.get('smtp_host', os.getenv('SMTP_HOST'))
        smtp_port = int(account.get('smtp_port', os.getenv('SMTP_PORT', 587)))
        smtp_user = account.get('smtp_username', os.getenv('SMTP_USERNAME'))
        smtp_pass = account.get('smtp_password', os.getenv('SMTP_PASSWORD'))
        smtp_security = account.get('smtp_security', os.getenv('SMTP_SECURITY', 'STARTTLS'))
        
        # Create notification email with proper headers to avoid spam filters
        msg = EmailMessage()
        msg['Subject'] = f'📧 Voicemail Transcriber Started - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
        msg['From'] = smtp_user if smtp_user else 'voicemail@localhost'
        msg['To'] = recipient
        
        # Add proper email headers to avoid spam classification
        import email.utils
        msg['Date'] = email.utils.formatdate(localtime=True)
        msg['Message-ID'] = email.utils.make_msgid(domain=smtp_host if smtp_host else 'localhost')
        msg['X-Mailer'] = 'Voicemail Transcriber 1.0'
        msg['MIME-Version'] = '1.0'
        
        hostname = socket.gethostname()
        
        content = f"""The Voicemail Transcriber service has started successfully.

Service Information:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 Started: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
🖥️  Hostname: {hostname}
🐧 System: {platform.system()} {platform.release()}
📬 SMTP Server: {smtp_host}:{smtp_port} ({smtp_security})
✉️  Monitored Accounts: {len(config['accounts'])}
🎙️  Whisper Model: {config['whisper_model']}
🗣️  Language: {config['whisper_language']}
💾 {device_info}

Monitored Accounts:
"""
        for account in config['accounts']:
            masked_email = ConfigValidator.mask_email(account['imap_username'])
            content += f"  • {account['name']}: {masked_email} → {ConfigValidator.mask_email(account['forward_to'])}"
            if account.get('phone'):
                content += f" [{account['phone']}]"
            content += "\n"
        
        content += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This notification confirms that:
✅ Container started successfully
✅ SMTP on port {smtp_port} is working
✅ All services are initialized
"""
        
        msg.set_content(content)
        
        # Send the notification
        if smtp_security == 'SSL':
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
        
        try:
            if smtp_security == 'STARTTLS':
                server.starttls()
            
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            
            server.send_message(msg)
            logger.info(f"Startup notification sent to {ConfigValidator.mask_email(recipient)}")
        finally:
            server.quit()
            
    except Exception as e:
        logger.error(f"Failed to send startup notification: {e}")
        # Don't fail the startup if notification fails


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
    
    # Track per-account statistics
    account_stats = {}
    for account in config['accounts']:
        account_stats[account['name']] = {
            'messages_checked': 0,
            'messages_processed': 0,
            'messages_with_audio': 0,
            'last_activity': None
        }
    
    # Track last statistics log time
    last_stats_log = datetime.now()
    
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
    
    # Send startup notification email (also tests SMTP on port 587)
    send_startup_notification(config, whisper.get_device_info())
    
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
                logger.debug(f"Processing account: {account['name']}")
                
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
                logger.debug(f"Found {len(all_messages)} messages in {account['name']} INBOX")
                
                # Update statistics
                account_stats[account['name']]['messages_checked'] += len(all_messages)
                
                forward_to = account['forward_to']
                phone_number = account.get('phone', None)
                masked_forward_to = ConfigValidator.mask_email(forward_to)
                logger.debug(f"Account {account['name']}: forward_to={masked_forward_to}, phone={phone_number}")
                
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
                            logger.debug(f"Processing {len(audio_attachments)} audio attachments")
                            account_stats[account['name']]['messages_with_audio'] += 1
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
                        
                        # Update statistics
                        account_stats[account['name']]['messages_processed'] += 1
                        account_stats[account['name']]['last_activity'] = datetime.now()
                        
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
        
        # Log hourly statistics
        if datetime.now() - last_stats_log > timedelta(hours=1):
            logger.info("=== Hourly Statistics ===")
            total_checked = 0
            total_processed = 0
            total_with_audio = 0
            
            for account_name, stats in account_stats.items():
                if stats['messages_checked'] > 0 or stats['messages_processed'] > 0:
                    logger.info(f"{account_name}: checked={stats['messages_checked']}, "
                              f"processed={stats['messages_processed']}, "
                              f"with_audio={stats['messages_with_audio']}")
                    total_checked += stats['messages_checked']
                    total_processed += stats['messages_processed']
                    total_with_audio += stats['messages_with_audio']
                    
                    # Reset hourly stats
                    stats['messages_checked'] = 0
                    stats['messages_processed'] = 0
                    stats['messages_with_audio'] = 0
            
            logger.info(f"Total: checked={total_checked}, processed={total_processed}, "
                      f"with_audio={total_with_audio}")
            
            # Also log metrics summary
            metrics.metrics.log_summary()
            last_stats_log = datetime.now()
        
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