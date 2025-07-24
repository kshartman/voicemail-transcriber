import os
import logging
import tempfile
import torch
import whisper
from typing import Optional

logger = logging.getLogger(__name__)


class WhisperTranscriber:
    def __init__(self, model_size: str = "medium", device: Optional[str] = None):
        self.model_size = model_size
        
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        logger.info(f"Initializing Whisper {model_size} model on {self.device}")
        
        if self.device == "cuda":
            logger.info(f"CUDA available: {torch.cuda.is_available()}")
            logger.info(f"CUDA device: {torch.cuda.get_device_name(0)}")
        
        try:
            self.model = whisper.load_model(model_size, device=self.device)
            logger.info(f"Whisper model loaded successfully on {self.device}")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise

    def transcribe_audio(self, audio_data: bytes, filename: str) -> str:
        try:
            with tempfile.NamedTemporaryFile(suffix=os.path.splitext(filename)[1], delete=False) as tmp_file:
                tmp_file.write(audio_data)
                tmp_file_path = tmp_file.name
            
            logger.info(f"Transcribing audio file: {filename}")
            
            result = self.model.transcribe(
                tmp_file_path,
                fp16=self.device == "cuda",
                language="en",
                task="transcribe"
            )
            
            transcription = result["text"].strip()
            logger.info(f"Transcription completed for {filename}")
            
            os.unlink(tmp_file_path)
            
            return transcription
            
        except Exception as e:
            logger.error(f"Failed to transcribe audio {filename}: {e}")
            if 'tmp_file_path' in locals() and os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
            raise

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