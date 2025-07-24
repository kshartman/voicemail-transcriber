# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a voicemail transcription service that monitors an IMAP inbox for voicemails, transcribes audio attachments using OpenAI's Whisper model, and forwards the emails with transcriptions. It runs as a Docker container with NVIDIA GPU support.

**Important**: This service forwards ALL emails (not just those with audio attachments). Audio transcription is an optional enhancement when audio files are detected.

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
docker compose exec voicemail-transcriber printenv | grep -E "(SMTP|IMAP|FORWARD)"

# Test SMTP connectivity
docker compose exec voicemail-transcriber python3 -c "import socket; s = socket.socket(); s.settimeout(5); result = s.connect_ex(('nx.bogometer.com', 25)); print('Port 25:', 'open' if result == 0 else f'error {result}')"
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

- **Error Resilience**: All components handle errors gracefully to ensure continuous operation
- **Modular Design**: Each component has a single responsibility and can be tested independently
- **GPU Acceleration**: Configured to use NVIDIA CUDA for faster transcription
- **Docker Containerization**: Ensures consistent deployment across environments

### Audio Processing Flow

1. Email fetched from IMAP → Audio attachment extracted to temp file
2. Whisper model loads and transcribes audio file
3. Original email + transcription → New email created and sent via SMTP
4. Original email marked as read, temp files cleaned up

## Configuration

Configuration is managed through environment variables (see `.env.example`):
- IMAP settings: host, username, password, port (default 993)
- SMTP settings: host, username, password, port (default 587)
- FORWARD_TO: Email address to forward transcribed voicemails
- POLL_INTERVAL: Seconds between inbox checks (default 60)

## Important Notes

- **No test suite exists** - Be careful when making changes
- **GPU required** - The application expects NVIDIA GPU with CUDA support (tested with GTX 1660 Super)
- **Continuous operation** - Designed to run indefinitely with automatic error recovery
- **Supported audio formats**: mp3, mp4, m4a, wav, ogg, flac, aac, wma, opus
- **HTML preservation**: Emails are forwarded with both plain text and HTML versions maintained
- **First run downloads**: Initial startup downloads 1.42GB Whisper model - be patient

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
- Emails are marked as read after processing
- Failed transcriptions don't stop email forwarding
- Transcriptions are appended in a styled HTML box

## Port Configuration
- IMAP: Usually 993 (SSL/TLS)
- SMTP: Port 25 (STARTTLS) or 587 (STARTTLS) or 465 (SSL/TLS)
- Use `nmap -p 25,465,587 mail.server.com` to check open ports