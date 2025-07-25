import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class HealthCheck:
    """Manages health status for the application"""
    
    def __init__(self, health_file: str = '/tmp/voicemail_transcriber.healthy'):
        self.health_file = health_file
        self.last_successful_process: Optional[datetime] = None
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        self.max_time_without_success = timedelta(minutes=10)
        
    def mark_healthy(self):
        """Mark the service as healthy"""
        try:
            self.last_successful_process = datetime.now()
            self.consecutive_failures = 0
            
            # Write health file
            with open(self.health_file, 'w') as f:
                f.write(f"healthy at {datetime.now().isoformat()}\n")
                f.write(f"consecutive_failures: {self.consecutive_failures}\n")
                
            logger.debug("Health check marked as healthy")
        except Exception as e:
            logger.error(f"Failed to write health file: {e}")
    
    def mark_failure(self):
        """Mark a processing failure"""
        self.consecutive_failures += 1
        logger.warning(f"Processing failure recorded. Consecutive failures: {self.consecutive_failures}")
        
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.mark_unhealthy("Too many consecutive failures")
    
    def mark_unhealthy(self, reason: str):
        """Mark the service as unhealthy"""
        try:
            logger.error(f"Service marked as unhealthy: {reason}")
            if os.path.exists(self.health_file):
                os.remove(self.health_file)
        except Exception as e:
            logger.error(f"Failed to remove health file: {e}")
    
    def check_health(self) -> bool:
        """Check if the service is healthy"""
        # Check if health file exists
        if not os.path.exists(self.health_file):
            return False
        
        # Check consecutive failures
        if self.consecutive_failures >= self.max_consecutive_failures:
            return False
        
        # Check time since last success
        if self.last_successful_process:
            time_since_success = datetime.now() - self.last_successful_process
            if time_since_success > self.max_time_without_success:
                self.mark_unhealthy(f"No successful processing in {time_since_success}")
                return False
        
        return True
    
    def startup(self):
        """Mark service as starting up"""
        try:
            with open(self.health_file, 'w') as f:
                f.write(f"starting up at {datetime.now().isoformat()}\n")
            logger.info("Health check initialized")
        except Exception as e:
            logger.error(f"Failed to initialize health check: {e}")
    
    def shutdown(self):
        """Clean up health file on shutdown"""
        try:
            if os.path.exists(self.health_file):
                os.remove(self.health_file)
            logger.info("Health check cleaned up")
        except Exception as e:
            logger.error(f"Failed to clean up health file: {e}")