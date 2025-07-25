# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a voicemail transcription service that monitors IMAP mailboxes for voicemails, transcribes audio attachments using OpenAI's Whisper model, and forwards the emails with transcriptions. It runs as a Docker container with NVIDIA GPU support.

**Key Features**:
- Monitors multiple IMAP folders with different forwarding rules
- Forwards ALL emails (not just those with audio attachments)
- Audio transcription is an optional enhancement when audio files are detected
- Can add phone numbers to email subjects for easy identification
- Each mailbox can have its own destination email address

## Recent Updates

### Security Updates (July 25, 2025)
- Upgraded PyTorch from 2.1.2 to 2.2.0+ (fixes CVE-2024-31580 heap buffer overflow)
- Upgraded Transformers from 4.37.2 to 4.46.3+ (fixes CVE-2024-11392/11393/11394 RCE vulnerabilities)
- All functionality tested and verified working with updated dependencies

## Key Commands

### Development Commands

```bash
# Build the Docker image
docker compose build

# Start the service
docker compose up -d

# View logs
docker compose logs -f

# Stop the service
docker compose down

# Rebuild and start fresh (IMPORTANT: Use this to reload environment variables)
docker compose down && docker compose up -d

# Access container shell for debugging
docker compose exec voicemail-transcriber bash

# Verify GPU detection
docker compose exec voicemail-transcriber nvidia-smi

# Test CUDA availability
docker compose exec voicemail-transcriber python3 -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"

# Check environment variables in container
docker compose exec voicemail-transcriber printenv | grep -E "(SMTP|IMAP|FORWARD|MAILBOXES)"

# Pretty print mailbox configuration
docker compose exec voicemail-transcriber python3 -c "import os, json; mb = os.getenv('MAILBOXES'); print(json.dumps(json.loads(mb), indent=2) if mb else 'Single mailbox mode')"

# Test SMTP connectivity
docker compose exec voicemail-transcriber python3 -c "import socket; s = socket.socket(); s.settimeout(5); result = s.connect_ex(('nx.bogometer.com', 25)); print('Port 25:', 'open' if result == 0 else f'error {result}')"

# Check health status
docker compose ps

# View metrics in logs
docker compose logs | grep "Processing Metrics"

# Check if health file exists
docker compose exec voicemail-transcriber ls -la /tmp/voicemail_transcriber.healthy
```

### Running Without Docker (for local development)

```bash
# Create virtual environment
python3 -m venv whisper_env
source whisper_env/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python src/main.py
```

## Architecture

The application follows a modular design with four main components:

1. **IMAP Client** (`src/imap_client.py`): Fetches unread emails with audio attachments from IMAP server
2. **Whisper Transcriber** (`src/whisper_transcriber.py`): Transcribes audio using OpenAI Whisper medium model with GPU acceleration
3. **Email Forwarder** (`src/email_forwarder.py`): Creates and sends forwarded emails with transcriptions
4. **Main Loop** (`src/main.py`): Orchestrates the workflow in a continuous polling loop

### Key Design Patterns

- **Error Resilience**: All components handle errors gracefully with retry logic
- **Modular Design**: Each component has a single responsibility and can be tested independently
- **GPU Acceleration**: Configured to use NVIDIA CUDA for faster transcription
- **Docker Containerization**: Runs as non-root user with health checks
- **Input Validation**: All configuration validated on startup
- **Resource Protection**: Size limits prevent memory exhaustion
- **Secure File Handling**: Temporary files created with restricted permissions (0600)
- **Connection Validation**: IMAP/SMTP connections tested before processing begins

### Audio Processing Flow

1. Email fetched from IMAP → Audio attachment extracted to temp file
2. Whisper model loads and transcribes audio file
3. Original email + transcription → New email created and sent via SMTP
4. Original email moved to archive folder (default: 'Processed'), temp files cleaned up

### Multiple Account Processing

The service processes each configured account sequentially:
1. For each account in `ACCOUNTS` array:
   - Connects to the account's IMAP server
   - Authenticates with account credentials
   - Retrieves all messages from INBOX
   - Forwards each to the account-specific `forward_to` address
   - If `phone` is provided, adds `[NNN.NNN.NNNN]` to email subject
   - Moves processed messages to archive folder
   - Disconnects from IMAP server
2. Waits for poll interval before starting next cycle

Example subject line transformations:
- Original: `Voicemail from 555-123-4567`
- With phone: `[555.123.4567] Fwd: Voicemail from 555-123-4567`

Benefits of multiple accounts:
- Monitor voicemail services that provide separate email accounts for each phone line
- Different departments can have isolated voicemail inboxes
- Each account can forward to different recipients
- Phone numbers help identify which line received the voicemail

## Configuration

Configuration is managed through environment variables (see `.env.example`):

### SMTP Settings (Shared by All Accounts)
All forwarded emails are sent through a single SMTP server:
- `SMTP_HOST`, `SMTP_PORT` (default 587)
- `SMTP_USERNAME`, `SMTP_PASSWORD` (optional - leave blank for open relays)
- `SMTP_SECURITY`: Connection security - 'SSL', 'STARTTLS', or 'NONE' (default 'STARTTLS')

### Account Configuration
Choose ONE of these methods:

#### Option 1: Single Account Mode (Simple)
Use discrete environment variables:
- `IMAP_HOST`, `IMAP_USERNAME`, `IMAP_PASSWORD`, `IMAP_PORT` (default 993)
- `IMAP_SECURITY`: 'SSL' or 'STARTTLS' (default 'SSL')
- `FORWARD_TO`: Email address to forward transcribed voicemails (required)

#### Option 2: Multiple Accounts Mode (Advanced)
Use `ACCOUNTS` JSON array to monitor multiple email accounts:
- Each account has its own IMAP credentials but shares the SMTP server above
- Single account IMAP settings (if set) are used as defaults for all accounts
- Account fields:
  - `name`: Display name for the account (optional, defaults to "Account N")
  - `imap_host`: IMAP server (optional if IMAP_HOST is set as default)
  - `imap_username`, `imap_password`: IMAP credentials (required)
  - `imap_port`, `imap_security`: IMAP settings (optional, uses defaults)
  - `forward_to`: Destination email address (required)
  - `phone`: Optional 10-digit phone number that appears in subject as [NNN.NNN.NNNN]

**Default Behavior**: If you set both single account variables and ACCOUNTS array:
- ACCOUNTS array takes precedence for account configuration
- Single account IMAP settings become defaults for accounts that don't specify them
- This reduces repetition when multiple accounts use the same mail server

- `ARCHIVE_FOLDER`: IMAP folder to move processed emails to (default 'Processed')

### Configuration Examples

#### Example 1: Simple single account
```bash
FORWARD_TO=myemail@example.com
```

#### Example 2: Multiple accounts with shared server (using defaults)
```bash
# Set defaults for all Gmail accounts
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_SECURITY=SSL

# Define accounts (they inherit the defaults above)
ACCOUNTS='[
  {
    "imap_username": "personal.voicemail@gmail.com",
    "imap_password": "app-password-1",
    "forward_to": "personal@example.com",
    "phone": "5551234567"
  },
  {
    "imap_username": "business.voicemail@gmail.com",
    "imap_password": "app-password-2", 
    "forward_to": "business@example.com",
    "phone": "5559876543"
  }
]'
```

#### Example 3: Multiple accounts with different servers
```bash
ACCOUNTS='[
  {
    "name": "Sales Voicemail",
    "imap_host": "mail.company.com",
    "imap_username": "sales@company.com",
    "imap_password": "sales-password",
    "forward_to": "sales-team@company.com",
    "phone": "8001234567"
  },
  {
    "name": "Support Voicemail", 
    "imap_host": "mail.company.com",
    "imap_username": "support@company.com",
    "imap_password": "support-password",
    "forward_to": "support-team@company.com",
    "phone": "8009876543"
  }
]'
```

### Processing Settings
- `POLL_INTERVAL`: Seconds between inbox checks (default 60)
- `WHISPER_MODEL`: Whisper model size (default 'medium')
- `WHISPER_LANGUAGE`: Language for transcription or 'auto' for detection (default 'auto')

### Limits and Safety
- `MAX_ATTACHMENT_SIZE_MB`: Maximum TOTAL size of all audio attachments per email in MB (default 40)
  - If exceeded, email is still forwarded but audio transcription is skipped
  - Example: 3 audio files of 15MB each = 45MB total → exceeds 40MB limit
- `MAX_ATTACHMENTS_PER_EMAIL`: Maximum number of audio attachments to process (default 10)
- `RETENTION_DAYS`: Days to keep archived emails (default 365)

### Retry Settings
- `MAX_RETRIES`: Maximum retry attempts for network operations (default 3)
- `RETRY_DELAY_SECONDS`: Initial delay between retries (default 5)

## Important Notes

- **GPU required** - The application expects NVIDIA GPU with CUDA support (tested with GTX 1660 Super)
- **Continuous operation** - Designed to run indefinitely with automatic error recovery
- **Supported audio formats**: mp3, mp4, m4a, wav, ogg, flac, aac, wma, opus
- **HTML preservation**: Emails are forwarded with both plain text and HTML versions maintained
- **First run downloads**: Initial startup downloads 1.42GB Whisper model - be patient
- **Security**: Runs as non-root user 'whisper' in Docker container
- **Health checks**: Docker health check monitors service status
- **Metrics**: Processing metrics logged hourly
- **Graceful shutdown**: Handles SIGTERM/SIGINT for clean shutdown
- **Retention**: Archived emails older than RETENTION_DAYS are automatically deleted

## Common Troubleshooting

### SMTP Connection Issues
1. **Authentication Failed**: Check SMTP_HOST is correct (e.g., nx.bogometer.com not mx.bogometer.com)
2. **Connection Refused**: 
   - Port 25 with STARTTLS is often required instead of 587
   - Environment variables are cached - use `docker compose down && docker compose up -d` to reload
3. **No quotes in .env**: Password values in .env should NOT have quotes - they're included literally

### GPU Setup
1. Install NVIDIA Container Toolkit (see README.md for detailed instructions)
2. Verify GPU access: `docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi`
3. Check GPU memory usage: Whisper medium model uses ~3GB

### Email Processing
- All emails are forwarded (not just those with audio)
- Emails are moved to archive folder after processing (default: 'Processed')
- Failed transcriptions don't stop email forwarding
- Transcriptions are appended in a styled HTML box
- Each mailbox can have different forwarding rules
- Phone numbers in subject help identify which line received the voicemail
- Multiple IMAP folders can be monitored simultaneously

## Port Configuration
- IMAP: 
  - Port 993 with SSL (most common)
  - Port 143 with STARTTLS
- SMTP:
  - Port 25 (STARTTLS or NONE) - often used for open relays
  - Port 587 (STARTTLS) - standard submission port
  - Port 465 (SSL) - SMTP over SSL/TLS
- Use `nmap -p 25,465,587 mail.server.com` to check open ports