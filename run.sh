#!/usr/bin/env bash
set -Eeuo pipefail

export PYTHONUNBUFFERED=1
export PYTHONPATH="/app/src:${PYTHONPATH:-}"

mkdir -p /home/whisper/.cache/whisper

python3 - <<'PY' || { echo "[startup] imap_client not importable"; exit 2; }
import sys
try:
    import imap_client
    print("[startup] OK: imap_client import")
except Exception as e:
    sys.stderr.write(f"[startup] ERROR: {e}\n")
    sys.exit(1)
PY

exec python3 -u /app/src/main.py
