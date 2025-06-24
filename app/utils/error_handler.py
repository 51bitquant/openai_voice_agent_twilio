"""
Error handling utilities
Unified error handling and retry mechanisms
"""
import asyncio
import logging
from functools import wraps
from typing import Callable, Any, Optional, Type, Union
import traceback

logger = logging.getLogger(__name__)


class RetryableError(Exception):
    """Retryable error"""
    pass


class CriticalError(Exception):
    """Critical error that should not be retried"""
    pass


def async_retry(max_attempts: int = 3,
                delay: float = 1.0,
                backoff: float = 2.0,
                exceptions: tuple = (Exception,)):
    """
    Async retry decorator
    
    Args:
        max_attempts: Maximum retry attempts
        delay: Initial delay
        backoff: Backoff multiplier
        exceptions: Exception types to retry
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    # Check if it's a critical error
                    if isinstance(e, CriticalError):
                        logger.error(f"Critical error in {func.__name__}: {e}")
                        raise

                    # Last attempt, no more retries
                    if attempt == max_attempts - 1:
                        break

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}. "
                        f"Retrying in {current_delay}s..."
                    )

                    await asyncio.sleep(current_delay)
                    current_delay *= backoff

            # All retries failed
            logger.error(f"All {max_attempts} attempts failed for {func.__name__}")
            raise last_exception

        return wrapper

    return decorator


def handle_websocket_error(func: Callable) -> Callable:
    """WebSocket error handling decorator"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ConnectionError as e:
            logger.error(f"WebSocket connection error in {func.__name__}: {e}")
            raise RetryableError(f"Connection error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            raise

    return wrapper


def log_performance(func: Callable) -> Callable:
    """Performance monitoring decorator"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        import time
        start_time = time.time()

        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time

            if execution_time > 1.0:  # Log warning if over 1 second
                logger.warning(f"{func.__name__} took {execution_time:.2f}s to execute")
            else:
                logger.debug(f"{func.__name__} executed in {execution_time:.3f}s")

            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} failed after {execution_time:.3f}s: {e}")
            raise

    return wrapper


class ErrorCollector:
    """Error collector"""

    def __init__(self, max_errors: int = 100):
        self.max_errors = max_errors
        self.errors: list = []
        self.error_counts: dict = {}

    def add_error(self, error: Exception, context: str = ""):
        """Add error record"""
        error_info = {
            "timestamp": asyncio.get_event_loop().time(),
            "error_type": type(error).__name__,
            "message": str(error),
            "context": context,
            "traceback": traceback.format_exc()
        }

        # Add to error list
        self.errors.append(error_info)

        # Maintain maximum error count
        if len(self.errors) > self.max_errors:
            self.errors.pop(0)

        # Count error occurrences
        error_key = f"{error_info['error_type']}:{error_info['context']}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1

    def get_error_summary(self) -> dict:
        """Get error summary"""
        return {
            "total_errors": len(self.errors),
            "error_counts": self.error_counts,
            "recent_errors": self.errors[-5:] if self.errors else []
        }


# Global error collector
error_collector = ErrorCollector()
