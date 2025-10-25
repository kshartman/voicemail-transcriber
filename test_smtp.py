#!/usr/bin/env python3
"""
Test SMTP configuration by sending a test email
Run this to verify SMTP port 587 is working correctly
"""
import os
import sys
import smtplib
from datetime import datetime
from email.message import EmailMessage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_smtp():
    """Test SMTP connection and send a test email"""
    
    # Get SMTP configuration
    smtp_host = os.getenv('SMTP_HOST')
    smtp_port = int(os.getenv('SMTP_PORT', 587))
    smtp_user = os.getenv('SMTP_USERNAME')
    smtp_pass = os.getenv('SMTP_PASSWORD')
    smtp_security = os.getenv('SMTP_SECURITY', 'STARTTLS')
    
    # Get test recipient (use first account's forward_to)
    import json
    accounts = json.loads(os.getenv('ACCOUNTS', '[]'))
    if not accounts:
        print("No accounts configured")
        return False
    
    test_recipient = accounts[0]['forward_to']
    
    print(f"Testing SMTP configuration:")
    print(f"  Host: {smtp_host}")
    print(f"  Port: {smtp_port}")
    print(f"  Security: {smtp_security}")
    print(f"  Username: {smtp_user}")
    print(f"  Recipient: {test_recipient}")
    
    # Create test message
    msg = EmailMessage()
    msg['Subject'] = f'Voicemail Transcriber SMTP Test - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    msg['From'] = smtp_user
    msg['To'] = test_recipient
    msg.set_content(f"""This is a test email from the Voicemail Transcriber service.

SMTP Configuration Test Results:
- Server: {smtp_host}:{smtp_port}
- Security: {smtp_security}
- Authentication: {'Yes' if smtp_user else 'No'}
- Test performed: {datetime.now()}

If you received this email, SMTP on port {smtp_port} is working correctly.
""")
    
    try:
        # Connect to SMTP server
        if smtp_security == 'SSL':
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
        
        print(f"\n✓ Connected to {smtp_host}:{smtp_port}")
        
        # Start TLS if needed
        if smtp_security == 'STARTTLS':
            server.starttls()
            print("✓ STARTTLS successful")
        
        # Authenticate if credentials provided
        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)
            print(f"✓ Authenticated as {smtp_user}")
        
        # Send test email
        server.send_message(msg)
        print(f"✓ Test email sent successfully to {test_recipient}")
        
        server.quit()
        print(f"\n✅ SMTP test completed successfully on port {smtp_port}")
        return True
        
    except Exception as e:
        print(f"\n❌ SMTP test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_smtp()
    sys.exit(0 if success else 1)