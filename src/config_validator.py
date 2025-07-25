import os
import re
import sys
import json
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class ConfigValidator:
    """Validates and provides configuration from environment variables"""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email address format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_port(port: str) -> bool:
        """Validate port number is in valid range"""
        try:
            port_num = int(port)
            return 1 <= port_num <= 65535
        except ValueError:
            return False
    
    @staticmethod
    def validate_positive_int(value: str) -> bool:
        """Validate positive integer"""
        try:
            return int(value) > 0
        except ValueError:
            return False
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate phone number (10 digits)"""
        # Remove any non-digit characters
        digits_only = re.sub(r'\D', '', phone)
        return len(digits_only) == 10
    
    @staticmethod
    def format_phone(phone: str) -> str:
        """Format phone number as NNN.NNN.NNNN"""
        digits_only = re.sub(r'\D', '', phone)
        if len(digits_only) == 10:
            return f"{digits_only[:3]}.{digits_only[3:6]}.{digits_only[6:]}"
        return phone
    
    @staticmethod
    def mask_email(email: str) -> str:
        """Mask email address for logging"""
        if not email or '@' not in email:
            return email
        parts = email.split('@')
        username = parts[0]
        domain = parts[1]
        # Show first 2 chars of username and domain
        masked_user = username[:2] + '*' * (len(username) - 2) if len(username) > 2 else username
        domain_parts = domain.split('.')
        if len(domain_parts) > 1:
            masked_domain = domain_parts[0][:2] + '*' * (len(domain_parts[0]) - 2) + '.' + '.'.join(domain_parts[1:])
        else:
            masked_domain = domain
        return f"{masked_user}@{masked_domain}"
    
    @staticmethod
    def get_config() -> Dict[str, Any]:
        """Get and validate all configuration from environment"""
        config = {}
        errors = []
        
        # IMAP settings (optional when using ACCOUNTS)
        accounts_json = os.getenv('ACCOUNTS')
        
        imap_host = os.getenv('IMAP_HOST')
        if not imap_host and not accounts_json:
            errors.append("IMAP_HOST is required when not using ACCOUNTS")
        config['imap_host'] = imap_host
        
        imap_username = os.getenv('IMAP_USERNAME')
        if not imap_username and not accounts_json:
            errors.append("IMAP_USERNAME is required when not using ACCOUNTS")
        elif imap_username and not ConfigValidator.validate_email(imap_username):
            logger.warning(f"IMAP_USERNAME '{imap_username}' may not be a valid email format")
        config['imap_username'] = imap_username
        
        imap_password = os.getenv('IMAP_PASSWORD')
        if not imap_password and not accounts_json:
            errors.append("IMAP_PASSWORD is required when not using ACCOUNTS")
        config['imap_password'] = imap_password
        
        imap_port = os.getenv('IMAP_PORT', '993')
        if not ConfigValidator.validate_port(imap_port):
            errors.append(f"IMAP_PORT '{imap_port}' is not a valid port number (1-65535)")
        config['imap_port'] = int(imap_port) if ConfigValidator.validate_port(imap_port) else 993
        
        # IMAP connection security
        imap_security = os.getenv('IMAP_SECURITY', 'SSL').upper()
        if imap_security not in ['SSL', 'STARTTLS']:
            errors.append(f"IMAP_SECURITY must be 'SSL' or 'STARTTLS' (got '{imap_security}')")
        config['imap_security'] = imap_security
        
        # Required SMTP settings
        smtp_host = os.getenv('SMTP_HOST')
        if not smtp_host:
            errors.append("SMTP_HOST is required")
        config['smtp_host'] = smtp_host
        
        # SMTP authentication is now optional
        smtp_username = os.getenv('SMTP_USERNAME', '')
        smtp_password = os.getenv('SMTP_PASSWORD', '')
        
        # If username is provided, password should also be provided
        if smtp_username and not smtp_password:
            errors.append("SMTP_PASSWORD is required when SMTP_USERNAME is provided")
        elif not smtp_username and smtp_password:
            errors.append("SMTP_USERNAME is required when SMTP_PASSWORD is provided")
        
        if smtp_username and not ConfigValidator.validate_email(smtp_username):
            logger.warning(f"SMTP_USERNAME '{smtp_username}' may not be a valid email format")
        
        config['smtp_username'] = smtp_username
        config['smtp_password'] = smtp_password
        
        smtp_port = os.getenv('SMTP_PORT', '587')
        if not ConfigValidator.validate_port(smtp_port):
            errors.append(f"SMTP_PORT '{smtp_port}' is not a valid port number (1-65535)")
        config['smtp_port'] = int(smtp_port) if ConfigValidator.validate_port(smtp_port) else 587
        
        # SMTP connection security
        smtp_security = os.getenv('SMTP_SECURITY', 'STARTTLS').upper()
        if smtp_security not in ['SSL', 'STARTTLS', 'NONE']:
            errors.append(f"SMTP_SECURITY must be 'SSL', 'STARTTLS', or 'NONE' (got '{smtp_security}')")
        config['smtp_security'] = smtp_security
        
        # Account configuration (accounts_json already fetched above)
        if accounts_json:
            # Multiple accounts configuration
            try:
                accounts = json.loads(accounts_json)
                if not isinstance(accounts, list) or not accounts:
                    errors.append("ACCOUNTS must be a non-empty JSON array")
                else:
                    validated_accounts = []
                    for idx, account in enumerate(accounts):
                        if not isinstance(account, dict):
                            errors.append(f"ACCOUNTS[{idx}] must be a JSON object")
                            continue
                        
                        # Validate required fields - some can come from defaults
                        required_fields = ['imap_username', 'imap_password', 'forward_to']
                        for field in required_fields:
                            if field not in account:
                                errors.append(f"ACCOUNTS[{idx}] missing required '{field}' field")
                        
                        # imap_host can come from default but must exist somewhere
                        if 'imap_host' not in account and 'imap_host' not in config:
                            errors.append(f"ACCOUNTS[{idx}] missing 'imap_host' (and no default IMAP_HOST set)")
                        
                        # Validate email addresses
                        if 'imap_username' in account and not ConfigValidator.validate_email(account['imap_username']):
                            logger.warning(f"ACCOUNTS[{idx}] 'imap_username' may not be a valid email format")
                        
                        if 'forward_to' in account and not ConfigValidator.validate_email(account['forward_to']):
                            errors.append(f"ACCOUNTS[{idx}] 'forward_to' '{account['forward_to']}' is not a valid email")
                        
                        # Set defaults - use single account vars as defaults if available
                        account.setdefault('name', f"Account {idx + 1}")
                        
                        # IMAP defaults from single account config if set
                        account.setdefault('imap_host', config.get('imap_host'))
                        account.setdefault('imap_port', config.get('imap_port', 993))
                        account.setdefault('imap_security', config.get('imap_security', 'SSL'))
                        
                        # SMTP defaults always from global SMTP config
                        account.setdefault('smtp_host', config.get('smtp_host'))
                        account.setdefault('smtp_port', config.get('smtp_port'))
                        account.setdefault('smtp_username', config.get('smtp_username'))
                        account.setdefault('smtp_password', config.get('smtp_password'))
                        account.setdefault('smtp_security', config.get('smtp_security'))
                        
                        # Validate optional phone field
                        if 'phone' in account and account['phone']:
                            if not ConfigValidator.validate_phone(account['phone']):
                                errors.append(f"ACCOUNTS[{idx}] 'phone' '{account['phone']}' must be 10 digits")
                            else:
                                account['phone'] = ConfigValidator.format_phone(account['phone'])
                        
                        # Validate ports
                        if 'imap_port' in account and not ConfigValidator.validate_port(str(account['imap_port'])):
                            errors.append(f"ACCOUNTS[{idx}] 'imap_port' must be valid (1-65535)")
                        
                        if not any(f"ACCOUNTS[{idx}]" in e for e in errors):
                            validated_accounts.append(account)
                    
                    config['accounts'] = validated_accounts
            except json.JSONDecodeError as e:
                errors.append(f"ACCOUNTS is not valid JSON: {str(e)}")
        else:
            # Legacy single account configuration
            forward_to = os.getenv('FORWARD_TO')
            if not forward_to:
                errors.append("Either ACCOUNTS or FORWARD_TO is required")
            elif not ConfigValidator.validate_email(forward_to):
                errors.append(f"FORWARD_TO '{forward_to}' is not a valid email address")
            else:
                # Convert to accounts format for consistency
                config['accounts'] = [{
                    'name': 'Primary Account',
                    'imap_host': config['imap_host'],
                    'imap_username': config['imap_username'],
                    'imap_password': config['imap_password'],
                    'imap_port': config['imap_port'],
                    'imap_security': config.get('imap_security', 'SSL'),
                    'smtp_host': config['smtp_host'],
                    'smtp_port': config['smtp_port'],
                    'smtp_username': config.get('smtp_username'),
                    'smtp_password': config.get('smtp_password'),
                    'smtp_security': config.get('smtp_security', 'STARTTLS'),
                    'forward_to': forward_to,
                    'phone': None
                }]
        
        # Optional settings with defaults
        config['archive_folder'] = os.getenv('ARCHIVE_FOLDER', 'Processed')
        
        poll_interval = os.getenv('POLL_INTERVAL', '60')
        if not ConfigValidator.validate_positive_int(poll_interval):
            errors.append(f"POLL_INTERVAL '{poll_interval}' must be a positive integer")
        config['poll_interval'] = int(poll_interval) if ConfigValidator.validate_positive_int(poll_interval) else 60
        
        # Audio processing settings
        config['whisper_language'] = os.getenv('WHISPER_LANGUAGE', 'auto')
        config['whisper_model'] = os.getenv('WHISPER_MODEL', 'medium')
        
        # Size limits
        max_attachment_size = os.getenv('MAX_ATTACHMENT_SIZE_MB', '40')
        if not ConfigValidator.validate_positive_int(max_attachment_size):
            errors.append(f"MAX_ATTACHMENT_SIZE_MB '{max_attachment_size}' must be a positive integer")
        config['max_attachment_size_mb'] = int(max_attachment_size) if ConfigValidator.validate_positive_int(max_attachment_size) else 40
        
        max_attachments = os.getenv('MAX_ATTACHMENTS_PER_EMAIL', '10')
        if not ConfigValidator.validate_positive_int(max_attachments):
            errors.append(f"MAX_ATTACHMENTS_PER_EMAIL '{max_attachments}' must be a positive integer")
        config['max_attachments_per_email'] = int(max_attachments) if ConfigValidator.validate_positive_int(max_attachments) else 10
        
        # Retention policy (in days)
        retention_days = os.getenv('RETENTION_DAYS', '365')  # 1 year default
        if not ConfigValidator.validate_positive_int(retention_days):
            errors.append(f"RETENTION_DAYS '{retention_days}' must be a positive integer")
        config['retention_days'] = int(retention_days) if ConfigValidator.validate_positive_int(retention_days) else 365
        
        # Network retry settings
        config['max_retries'] = int(os.getenv('MAX_RETRIES', '3'))
        config['retry_delay'] = int(os.getenv('RETRY_DELAY_SECONDS', '5'))
        
        # If there are errors, log them and exit
        if errors:
            logger.error("Configuration validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            sys.exit(1)
        
        return config
    
    @staticmethod
    def log_config(config: Dict[str, Any]) -> None:
        """Log configuration (without passwords)"""
        logger.info("Configuration loaded:")
        for key, value in config.items():
            if key == 'accounts' and isinstance(value, list):
                # Mask sensitive data in accounts
                safe_accounts = []
                for acc in value:
                    safe_acc = {
                        'name': acc.get('name', 'Unknown'),
                        'imap_host': acc.get('imap_host'),
                        'imap_username': ConfigValidator.mask_email(acc.get('imap_username', '')),
                        'forward_to': ConfigValidator.mask_email(acc.get('forward_to', '')),
                        'phone': acc.get('phone'),
                    }
                    # Only include non-None values
                    safe_acc = {k: v for k, v in safe_acc.items() if v is not None}
                    safe_accounts.append(safe_acc)
                logger.info(f"  {key}: {safe_accounts}")
            elif 'password' in key.lower():
                logger.info(f"  {key}: ***")
            elif key in ['imap_username', 'smtp_username', 'forward_to']:
                logger.info(f"  {key}: {ConfigValidator.mask_email(value) if value else None}")
            else:
                logger.info(f"  {key}: {value}")