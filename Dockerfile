# CUDA 12.2 + cuDNN runtime (works fine for GTX 1660 / Turing)
FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive

# ---- System deps ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 python3-pip \
    ffmpeg git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# ---- Non-root user ----
# Keep the same user/group you used before so file perms match
RUN groupadd -r whisper && useradd -r -g whisper -u 1000 whisper

# Cache dir where your host bind-mount goes (/srv/whisper-cache)
RUN mkdir -p /home/whisper/.cache/whisper && chown -R whisper:whisper /home/whisper

# ---- App layout ----
WORKDIR /app

# Copy requirements first for layer cache
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy your app code/config
COPY src/ ./src/
COPY config/ ./config/

# Entry point
COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh

# Ensure app files are owned by non-root
RUN chown -R whisper:whisper /app

# Drop privileges
USER whisper

# (No model pre-download here — we rely on the runtime bind mount:
#  /srv/whisper-cache -> /home/whisper/.cache/whisper)

# Keep ENTRYPOINT/CMD behavior the same as your previous image.
# If you had a CMD before (e.g., python -m src.main), keep using it via compose.
