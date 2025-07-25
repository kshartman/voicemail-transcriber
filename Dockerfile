FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r whisper && useradd -r -g whisper -u 1000 whisper

WORKDIR /app

# Install Python dependencies as root
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Create directories for model cache with proper permissions
RUN mkdir -p /home/whisper/.cache && chown -R whisper:whisper /home/whisper

# Pre-download Whisper model as a separate layer (this is the slow part)
# This runs as root to ensure the model is downloaded to a predictable location
ENV WHISPER_CACHE_DIR=/home/whisper/.cache/whisper
RUN python3 -c "import whisper; whisper.load_model('medium', download_root='${WHISPER_CACHE_DIR}')" && \
    chown -R whisper:whisper /home/whisper/.cache

# Copy application files (changes to these won't invalidate the model cache layer)
COPY src/ ./src/
COPY config/ ./config/

# Change ownership of app directory
RUN chown -R whisper:whisper /app

# Switch to non-root user
USER whisper

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python3 -c "import sys; import os; sys.exit(0 if os.path.exists('/tmp/voicemail_transcriber.healthy') else 1)"

CMD ["python3", "src/main.py"]