# Voicemail Transcriber

A Docker service that monitors an IMAP mailbox, transcribes audio attachments using OpenAI Whisper, and forwards emails with transcriptions.

## Features

- Monitors IMAP mailbox for new messages
- Detects audio attachments (mp3, mp4, m4a, wav, etc.)
- Transcribes audio using Whisper medium model with GPU acceleration
- Forwards emails with original attachments and transcriptions
- Supports NVIDIA GPU acceleration (GTX 1660 Super)

## Prerequisites

- Docker and Docker Compose
- NVIDIA GPU with CUDA support
- NVIDIA Container Toolkit installed
- NVIDIA drivers installed on host

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
cp .env.example .env
# Edit .env with your IMAP/SMTP credentials
```

## Configuration

Edit `.env` file with your email settings:

- `IMAP_HOST`: Your IMAP server (e.g., imap.gmail.com)
- `IMAP_USERNAME`: Your email address
- `IMAP_PASSWORD`: Your email password or app-specific password
- `SMTP_HOST`: Your SMTP server (e.g., smtp.gmail.com)
- `SMTP_USERNAME`: Your SMTP username
- `SMTP_PASSWORD`: Your SMTP password
- `FORWARD_TO`: Email address to forward messages to
- `POLL_INTERVAL`: Check interval in seconds (default: 60)

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

## Notes

- The service marks processed emails as read
- Audio files supported: mp3, mp4, m4a, wav, ogg, flac, aac, wma, opus
- Transcriptions are appended to forwarded emails
- Original attachments are preserved in forwarded emails