"""
Exponential backoff retry mechanism.
"""
from typing import Callable, Any, Type, Tuple, Optional, List, TypeVar, Union
import logging
import time
import random
from functools import wraps

# Define type for the function result
T = TypeVar('T')

class RetryExhaustedError(Exception):
    """
    Exception raised when all retry attempts have been exhausted.
    """
    def __init__(self, attempts: int, last_exception: Exception):
        self.attempts = attempts
        self.last_exception = last_exception
        message = f"All {attempts} retry attempts exhausted. Last error: {str(last_exception)}"
        super().__init__(message)


class BackoffStrategy:
    """
    Exponential backoff strategy for retrying operations.
    """
    
    def __init__(self, 
                base_delay: float = 1.0, 
                max_delay: float = 60.0, 
                max_retries: int = 5,
                jitter: bool = True):
        """
        Initialize the backoff strategy.
        
        Args:
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            max_retries: Maximum number of retries
            jitter: Whether to add random jitter to delays
            
        Returns:
            None
            
        Required by:
            None (called during initialization)
        """
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.jitter = jitter
        self.logger = logging.getLogger(__name__)
    
    def execute(self, 
               func: Callable[..., T], 
               *args, 
               retry_exceptions: Tuple[Type[Exception], ...] = (Exception,),
               on_retry: Optional[Callable[[int, Exception, float], None]] = None,
               **kwargs) -> T:
        """
        Execute a function with exponential backoff retries.
        
        Args:
            func: Function to execute
            *args: Arguments to pass to the function
            retry_exceptions: Tuple of exception types to retry on
            on_retry: Optional callback function called before each retry
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            Result of the function call
            
        Raises:
            Exception: If all retries fail
            
        Required by:
            None (called by external components)
            
        Requires:
            - _calculate_delay
        """
        last_exception = None
        
        # Attempt the operation up to max_retries + 1 times (initial + retries)
        for attempt in range(self.max_retries + 1):
            try:
                # Execute the function
                return func(*args, **kwargs)
                
            except retry_exceptions as e:
                last_exception = e
                
                # If this is the last attempt, re-raise the exception
                if attempt >= self.max_retries:
                    self.logger.error(f"All {self.max_retries} retry attempts exhausted. Last error: {str(e)}")
                    raise RetryExhaustedError(attempts=attempt+1, last_exception=e) from e
                
                # Calculate delay for next retry
                delay = self._calculate_delay(attempt)
                
                # Log the retry attempt
                self.logger.warning(
                    f"Attempt {attempt+1}/{self.max_retries+1} failed with error: {str(e)}. "
                    f"Retrying in {delay:.2f} seconds."
                )
                
                # Call the on_retry callback if provided
                if on_retry:
                    on_retry(attempt, e, delay)
                
                # Wait before retry
                time.sleep(delay)
    
    def _calculate_delay(self, retry_count: int) -> float:
        """
        Calculate the delay for a retry attempt.
        
        Args:
            retry_count: Current retry attempt number
            
        Returns:
            Delay in seconds
            
        Required by:
            - execute
            
        Requires:
            None
        """
        # Calculate exponential delay: base_delay * 2^retry_count
        delay = self.base_delay * (2 ** retry_count)
        
        # Apply jitter if enabled (adds randomness to prevent thundering herd)
        if self.jitter:
            # Add random jitter between -25% and +25%
            jitter_factor = random.uniform(0.75, 1.25)
            delay = delay * jitter_factor
        
        # Cap at max_delay
        delay = min(delay, self.max_delay)
        
        return delay


def with_backoff(base_delay: float = 1.0, 
                max_delay: float = 60.0, 
                max_retries: int = 5,
                jitter: bool = True, 
                retry_exceptions: Optional[List[Type[Exception]]] = None):
    """
    Decorator for applying exponential backoff to a function.
    
    Args:
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        max_retries: Maximum number of retries
        jitter: Whether to add random jitter to delays
        retry_exceptions: List of exception types to retry on
        
    Returns:
        Decorated function
        
    Required by:
        None (used as a decorator)
        
    Requires:
        - BackoffStrategy class
    """
    # Create backoff strategy
    strategy = BackoffStrategy(
        base_delay=base_delay,
        max_delay=max_delay,
        max_retries=max_retries,
        jitter=jitter
    )
    
    # Default retry exceptions if not specified
    if retry_exceptions is None:
        retry_exceptions = [Exception]
        
    # Convert to tuple for isinstance checking
    retry_exceptions_tuple = tuple(retry_exceptions)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return strategy.execute(
                func, 
                *args, 
                retry_exceptions=retry_exceptions_tuple,
                **kwargs
            )
        
        # Add strategy reference to the function for introspection
        wrapper.strategy = strategy
        return wrapper
        
    return decorator