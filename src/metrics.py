import time
import logging
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ProcessingMetrics:
    """Metrics for email processing"""
    emails_processed: int = 0
    emails_failed: int = 0
    audio_files_transcribed: int = 0
    transcription_failures: int = 0
    total_processing_time: float = 0.0
    total_transcription_time: float = 0.0
    bytes_processed: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    
    def get_summary(self) -> Dict[str, any]:
        """Get a summary of metrics"""
        runtime = (datetime.now() - self.start_time).total_seconds()
        return {
            "runtime_seconds": runtime,
            "emails_processed": self.emails_processed,
            "emails_failed": self.emails_failed,
            "success_rate": self.emails_processed / max(1, self.emails_processed + self.emails_failed),
            "audio_files_transcribed": self.audio_files_transcribed,
            "transcription_failures": self.transcription_failures,
            "avg_processing_time": self.total_processing_time / max(1, self.emails_processed),
            "avg_transcription_time": self.total_transcription_time / max(1, self.audio_files_transcribed),
            "bytes_processed": self.bytes_processed,
            "emails_per_minute": (self.emails_processed / runtime) * 60 if runtime > 0 else 0
        }
    
    def log_summary(self):
        """Log a summary of metrics"""
        summary = self.get_summary()
        logger.info("=== Processing Metrics ===")
        logger.info(f"Runtime: {summary['runtime_seconds']:.1f} seconds")
        logger.info(f"Emails processed: {summary['emails_processed']} (success rate: {summary['success_rate']:.1%})")
        logger.info(f"Emails failed: {summary['emails_failed']}")
        logger.info(f"Audio files transcribed: {summary['audio_files_transcribed']}")
        logger.info(f"Transcription failures: {summary['transcription_failures']}")
        logger.info(f"Average processing time: {summary['avg_processing_time']:.2f}s per email")
        logger.info(f"Average transcription time: {summary['avg_transcription_time']:.2f}s per file")
        logger.info(f"Total data processed: {summary['bytes_processed'] / 1024 / 1024:.1f} MB")
        logger.info(f"Processing rate: {summary['emails_per_minute']:.1f} emails/minute")


class MetricsCollector:
    """Collects and manages metrics"""
    
    def __init__(self):
        self.metrics = ProcessingMetrics()
        self._processing_start: Optional[float] = None
        self._transcription_start: Optional[float] = None
    
    def start_processing(self):
        """Mark the start of email processing"""
        self._processing_start = time.time()
    
    def end_processing(self, success: bool = True):
        """Mark the end of email processing"""
        if self._processing_start:
            duration = time.time() - self._processing_start
            self.metrics.total_processing_time += duration
            if success:
                self.metrics.emails_processed += 1
            else:
                self.metrics.emails_failed += 1
            self._processing_start = None
    
    def start_transcription(self):
        """Mark the start of audio transcription"""
        self._transcription_start = time.time()
    
    def end_transcription(self, success: bool = True, bytes_processed: int = 0):
        """Mark the end of audio transcription"""
        if self._transcription_start:
            duration = time.time() - self._transcription_start
            self.metrics.total_transcription_time += duration
            if success:
                self.metrics.audio_files_transcribed += 1
                self.metrics.bytes_processed += bytes_processed
            else:
                self.metrics.transcription_failures += 1
            self._transcription_start = None
    
    def get_metrics(self) -> ProcessingMetrics:
        """Get current metrics"""
        return self.metrics
    
    def log_periodic_summary(self, interval_minutes: int = 60):
        """Log summary if enough time has passed"""
        runtime = (datetime.now() - self.metrics.start_time).total_seconds() / 60
        if runtime > 0 and int(runtime) % interval_minutes == 0:
            self.metrics.log_summary()