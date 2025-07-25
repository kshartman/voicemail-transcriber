import time
import logging
from functools import wraps
from typing import Tuple, Type, Union, Callable

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    log_level: int = logging.WARNING
) -> Callable:
    """
    Decorator for retrying functions with exponential backoff.
    
    Args:
        max_attempts: Maximum number of attempts
        initial_delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay after each failure
        exceptions: Tuple of exceptions to catch and retry
        log_level: Logging level for retry messages
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.log(
                            log_level,
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_attempts}): {e}. "
                            f"Retrying in {delay} seconds..."
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
            
            # Re-raise the last exception if all attempts failed
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator


class RetryableConnection:
    """Base class for connections that should be retried on failure"""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 5.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._connection_attempts = 0
    
    def reset_retry_counter(self):
        """Reset the retry counter after successful operation"""
        self._connection_attempts = 0
    
    def should_retry(self) -> bool:
        """Check if we should retry the connection"""
        return self._connection_attempts < self.max_retries
    
    def increment_retry_counter(self):
        """Increment retry counter"""
        self._connection_attempts += 1
    
    def get_retry_delay(self) -> float:
        """Get delay for next retry with exponential backoff"""
        return self.retry_delay * (2 ** (self._connection_attempts - 1))