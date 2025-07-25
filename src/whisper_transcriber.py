import os
import logging
import tempfile
import torch
import whisper
from typing import Optional

logger = logging.getLogger(__name__)


class WhisperTranscriber:
    def __init__(self, model_size: str = "medium", device: Optional[str] = None, language: str = "auto"):
        self.model_size = model_size
        self.language = language
        
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        logger.info(f"Initializing Whisper {model_size} model on {self.device}")
        
        if self.device == "cuda":
            logger.info(f"CUDA available: {torch.cuda.is_available()}")
            logger.info(f"CUDA device: {torch.cuda.get_device_name(0)}")
        
        try:
            # Use the pre-downloaded model if available
            download_root = os.environ.get('WHISPER_CACHE_DIR', None)
            self.model = whisper.load_model(model_size, device=self.device, download_root=download_root)
            logger.info(f"Whisper model loaded successfully on {self.device}")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise

    def transcribe_audio(self, audio_data: bytes, filename: str) -> str:
        tmp_file_path = None
        try:
            # Create temporary file with secure permissions
            fd, tmp_file_path = tempfile.mkstemp(suffix=os.path.splitext(filename)[1])
            try:
                # Set secure permissions (only owner can read/write)
                os.chmod(tmp_file_path, 0o600)
                # Write audio data
                with os.fdopen(fd, 'wb') as tmp_file:
                    tmp_file.write(audio_data)
            except Exception:
                os.close(fd)
                raise
            
            logger.info(f"Transcribing audio file: {filename}")
            
            # Transcribe audio
            transcribe_kwargs = {
                "fp16": self.device == "cuda",
                "task": "transcribe"
            }
            
            # Only set language if not auto-detect
            if self.language != "auto":
                transcribe_kwargs["language"] = self.language
            
            result = self.model.transcribe(tmp_file_path, **transcribe_kwargs)
            
            transcription = result["text"].strip()
            logger.info(f"Transcription completed for {filename}")
            
            return transcription
            
        except Exception as e:
            logger.error(f"Failed to transcribe audio {filename}: {e}")
            raise
        finally:
            # Clean up temp file
            if tmp_file_path and os.path.exists(tmp_file_path):
                try:
                    os.unlink(tmp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {tmp_file_path}: {e}")

    def get_device_info(self) -> dict:
        info = {
            "device": self.device,
            "model_size": self.model_size
        }
        
        if self.device == "cuda":
            info.update({
                "cuda_available": torch.cuda.is_available(),
                "cuda_device_count": torch.cuda.device_count(),
                "cuda_device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                "cuda_memory_allocated": torch.cuda.memory_allocated(0) if torch.cuda.is_available() else None,
                "cuda_memory_reserved": torch.cuda.memory_reserved(0) if torch.cuda.is_available() else None
            })
        
        return info