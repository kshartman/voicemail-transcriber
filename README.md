# Voicemail Transcriber

A Docker service that monitors an IMAP mailbox, transcribes audio attachments using OpenAI Whisper, and forwards emails with transcriptions.

## Perfect for Voicemail Services

This service works perfectly with voicemail-to-email services like:
- **NumberGarage** and similar services that accept calls, record voicemails, and email audio files
- Services that offer transcription but with poor quality - we use the high-quality OpenAI Whisper model
- Any service that forwards voicemails as email attachments

## Features

- Monitors multiple IMAP accounts with separate credentials
- Detects audio attachments (mp3, mp4, m4a, wav, etc.)
- Transcribes audio using Whisper medium model with GPU acceleration
- Forwards emails with original attachments and transcriptions
- Supports NVIDIA GPU acceleration
- Each account can have different forwarding destinations
- Adds phone numbers to email subjects for easy identification
- Supports SSL/TLS and STARTTLS for both IMAP and SMTP
- Optional SMTP authentication (works with open relays)
- Sends startup notification email when container restarts
- Hourly statistics logging for monitoring activity

## Prerequisites

- Docker and Docker Compose
- NVIDIA GPU with CUDA support (even a GTX 1660 is sufficient - we use a GTX 1660 Super)
- NVIDIA Container Toolkit installed
- NVIDIA drivers installed on host

**GPU Note**: You'll need an NVIDIA card for decent performance. The Whisper medium model provides excellent transcription quality but requires GPU acceleration. We've tested with a GTX 1660 Super which handles voicemail transcriptions perfectly.

## Installation

1. Install NVIDIA Container Toolkit:
```bash
# Remove any existing nvidia-container-toolkit list that might be corrupted
sudo rm -f /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Add the official NVIDIA package repositories
distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
      && curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
      && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
         sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
         sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Update package list and install
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit

# Configure Docker to use the NVIDIA runtime
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

2. Clone and configure:
```bash
cd voicemail-transcriber

# For maintainers with GPG access:
gpg -d .env.gpg > .env

# For new installations:
cp .env.example .env
# Edit .env with your IMAP/SMTP credentials
```

## Configuration

Edit `.env` file with your email settings:

### SMTP Configuration (Required - Shared by All Accounts)
Configure the outgoing mail server used to send all forwarded emails:
- `SMTP_HOST`: Your SMTP server (e.g., smtp.gmail.com)
- `SMTP_PORT`: SMTP port (587 for STARTTLS, 465 for SSL, 25 for open relay)
- `SMTP_USERNAME`: Your SMTP username (optional for open relays)
- `SMTP_PASSWORD`: Your SMTP password (optional for open relays)
- `SMTP_SECURITY`: Use 'SSL', 'STARTTLS', or 'NONE'

### Account Configuration - Choose ONE Method:

#### Option 1: Single Account Mode (Simple)
Monitor one email account using discrete environment variables:
- `IMAP_HOST`: Your IMAP server (e.g., imap.gmail.com)
- `IMAP_USERNAME`: Your email address
- `IMAP_PASSWORD`: Your email password or app-specific password
- `IMAP_PORT`: IMAP port (default: 993)
- `IMAP_SECURITY`: Use 'SSL' or 'STARTTLS'
- `FORWARD_TO`: Email address to forward messages to

#### Option 2: Multiple Accounts Mode (Advanced)
Monitor multiple email accounts using JSON configuration:
- `ACCOUNTS`: JSON array of account configurations

Example for monitoring multiple email accounts:
```bash
ACCOUNTS='[
  {
    "name": "Personal Voicemail",
    "imap_host": "imap.gmail.com",
    "imap_username": "personal.voicemail@gmail.com",
    "imap_password": "app-password-1",
    "forward_to": "me@example.com",
    "phone": "5551234567"
  },
  {
    "name": "Business Voicemail",
    "imap_host": "imap.gmail.com", 
    "imap_username": "business.voicemail@gmail.com",
    "imap_password": "app-password-2",
    "forward_to": "work@example.com",
    "phone": "5559876543"
  }
]'
```

Each account has its own:
- IMAP login credentials (to receive voicemails)
- Forwarding destination 
- Optional phone number that appears in subject as `[555.123.4567]`

**Note**: All accounts share the same SMTP server for sending emails.

## Running

Build and start the service:
```bash
docker-compose up -d --build
```

View logs:
```bash
docker-compose logs -f
```

Stop the service:
```bash
docker-compose down
```

## GPU Verification

Check if GPU is detected:
```bash
docker-compose exec voicemail-transcriber nvidia-smi
```

## Security

This project maintains security-hardened dependencies:
- PyTorch 2.2.0+ (patched for CVE-2024-31580)
- Transformers 4.46.3+ (patched for CVE-2024-11392/11393/11394)

### Note on Base Image Vulnerabilities

This project uses NVIDIA CUDA 12.2.2 base images to maintain compatibility with older NVIDIA graphics cards and their drivers. Many users (including ourselves) run this on older but capable GPUs like the GTX 1660 Super, which require driver versions that don't support the latest CUDA releases.

While newer CUDA base images (12.6+) would reduce the number of reported vulnerabilities, they would break compatibility with these widely-used cards. We've made the conscious decision to prioritize hardware compatibility over achieving a zero-vulnerability scan, as the service typically runs in controlled environments processing voicemail audio files.

## Notes

- The service forwards ALL emails (not just those with audio attachments)
- Processed emails are moved to an archive folder (default: "Processed")
- Audio files supported: mp3, mp4, m4a, wav, ogg, flac, aac, wma, opus
- Transcriptions are added at the top of forwarded emails in a styled box
- Original attachments are preserved in forwarded emails
- Emails older than 1 year are automatically deleted from the archive folder
- The Whisper medium model provides excellent transcription quality
- First run downloads 1.42GB model (cached for subsequent runs)