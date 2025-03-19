"""
Rate limiting with donation prompts.
"""
from typing import Dict, Any, Optional, Callable, List, TypeVar, Tuple
import logging
import time
import os
from datetime import datetime, timedelta
from functools import wraps

# Define type for the decorated function
T = TypeVar('T')


class RateLimiter:
    """
    Rate limiter with donation prompts after threshold.
    """
    
    def __init__(self, 
                threshold: int = 5, 
                time_window: int = 86400,  # 24 hours in seconds
                donation_message: Optional[str] = None,
                enabled: bool = False,  # Disabled by default
                donation_url: str = "technodada.org/donate"):
        """
        Initialize the rate limiter.
        
        Args:
            threshold: Number of messages before prompting for donation
            time_window: Time window in seconds for counting messages
            donation_message: Optional custom donation message
            enabled: Whether rate limiting is enabled
            donation_url: URL for donation page
            
        Returns:
            None
            
        Required by:
            None (called during initialization)
        """
        self.threshold = threshold
        self.time_window = time_window
        self.enabled = enabled
        self.donation_url = donation_url
        self.donation_message = donation_message or (
            "You've sent {count} messages today to DadaCat! "
            f"Please consider supporting this service with a donation at {donation_url}"
        )
        self.usage_counts: Dict[str, List[float]] = {}  # user_id -> list of timestamps
        self.logger = logging.getLogger(__name__)
        
        # Check environment variables for enabling/disabling
        env_enabled = os.getenv('RATE_LIMITER_ENABLED', '').lower()
        if env_enabled in ('true', '1', 'yes'):
            self.enabled = True
        elif env_enabled in ('false', '0', 'no'):
            self.enabled = False
            
        if self.enabled:
            self.logger.info("Rate limiter is ENABLED with threshold of "
                           f"{threshold} messages per {time_window/3600:.1f} hours")
        else:
            self.logger.info("Rate limiter is DISABLED")
    
    def check_rate_limit(self, user_id: str) -> Dict[str, Any]:
        """
        Check if a user should receive a donation prompt.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            Dictionary with:
                'should_prompt': Whether to show a donation prompt
                'count': Current message count
                'prompt_message': Donation prompt message if applicable
                'rate_limited': Whether the user is rate limited
                
        Required by:
            None (called by external components)
            
        Requires:
            - _clean_old_timestamps
            - _get_message_count
        """
        # If rate limiting is disabled, return default values
        if not self.enabled:
            return {
                'should_prompt': False,
                'count': 0,
                'prompt_message': None,
                'rate_limited': False
            }
            
        # Clean old timestamps
        self._clean_old_timestamps(user_id)
        
        # Get current count
        count = self._get_message_count(user_id)
        
        # Determine if we should show a donation prompt
        # Show it when count is a multiple of threshold (5, 10, 15, etc.)
        should_prompt = count > 0 and count % self.threshold == 0
        
        # Format the donation message if needed
        prompt_message = None
        if should_prompt:
            prompt_message = self.donation_message.format(count=count)
            
        # Rate limit is not implemented yet - this is just donation prompting
        # We could add actual rate limiting in the future if needed
        rate_limited = False
        
        return {
            'should_prompt': should_prompt,
            'count': count,
            'prompt_message': prompt_message,
            'rate_limited': rate_limited
        }
    
    def record_message(self, user_id: str) -> int:
        """
        Record a message from a user.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            Current message count for the user
            
        Required by:
            None (called by external components)
            
        Requires:
            - _clean_old_timestamps
            - _get_message_count
        """
        # If rate limiting is disabled, return 0
        if not self.enabled:
            return 0
            
        # Clean old timestamps
        self._clean_old_timestamps(user_id)
        
        # Add current timestamp
        if user_id not in self.usage_counts:
            self.usage_counts[user_id] = []
            
        self.usage_counts[user_id].append(time.time())
        
        # Get and return current count
        return self._get_message_count(user_id)
    
    def reset_counter(self, user_id: str) -> bool:
        """
        Reset the message counter for a user.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            Boolean indicating success or failure
            
        Required by:
            None (called by external components)
            
        Requires:
            None
        """
        # If rate limiting is disabled, return True
        if not self.enabled:
            return True
            
        # Reset counter
        if user_id in self.usage_counts:
            self.usage_counts[user_id] = []
            self.logger.info(f"Reset rate limit counter for user {user_id}")
            return True
        
        return False
    
    def _clean_old_timestamps(self, user_id: str) -> None:
        """
        Clean out timestamps that are outside the time window.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            None
            
        Required by:
            - check_rate_limit
            - record_message
            
        Requires:
            None
        """
        if user_id not in self.usage_counts:
            return
            
        current_time = time.time()
        cutoff_time = current_time - self.time_window
        
        # Filter out timestamps older than the cutoff
        old_count = len(self.usage_counts[user_id])
        self.usage_counts[user_id] = [
            ts for ts in self.usage_counts[user_id] if ts >= cutoff_time
        ]
        
        new_count = len(self.usage_counts[user_id])
        if old_count != new_count:
            self.logger.debug(f"Cleaned {old_count - new_count} old timestamps for user {user_id}")
    
    def _get_message_count(self, user_id: str) -> int:
        """
        Get the current message count for a user.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            Current message count for the user
            
        Required by:
            - check_rate_limit
            - record_message
            
        Requires:
            None
        """
        if user_id not in self.usage_counts:
            return 0
            
        return len(self.usage_counts[user_id])
    
    def enable(self) -> None:
        """
        Enable rate limiting.
        
        Args:
            None
            
        Returns:
            None
        """
        self.enabled = True
        self.logger.info("Rate limiter has been ENABLED")
    
    def disable(self) -> None:
        """
        Disable rate limiting.
        
        Args:
            None
            
        Returns:
            None
        """
        self.enabled = False
        self.logger.info("Rate limiter has been DISABLED")


def with_rate_limit(limiter: RateLimiter, user_id_func: Callable[..., str]):
    """
    Decorator for applying rate limiting to a function.
    
    Args:
        limiter: RateLimiter instance
        user_id_func: Function that extracts user_id from the function arguments
        
    Returns:
        Decorated function
        
    Required by:
        None (used as a decorator)
        
    Requires:
        - RateLimiter class
    """
    def decorator(func: Callable[..., T]) -> Callable[..., Tuple[T, Dict[str, Any]]]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Tuple[T, Dict[str, Any]]:
            # If rate limiter is disabled, just call the function
            if not limiter.enabled:
                return func(*args, **kwargs), {'rate_limited': False}
            
            # Extract user_id
            user_id = user_id_func(*args, **kwargs)
            
            # Record the message
            limiter.record_message(user_id)
            
            # Check rate limit
            result = limiter.check_rate_limit(user_id)
            
            # Call the function
            function_result = func(*args, **kwargs)
            
            # Return both the function result and the rate limit info
            return function_result, result
            
        return wrapper
    
    return decorator