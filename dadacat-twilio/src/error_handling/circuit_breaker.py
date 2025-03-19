"""
Circuit breaker implementation for preventing cascade failures.
"""
from typing import Callable, Any, Dict, Optional, TypeVar, Generic
import logging
import time
from enum import Enum
from functools import wraps

# Define type for the function result
T = TypeVar('T')

class CircuitBreakerOpenError(Exception):
    """
    Exception raised when trying to execute a function with an open circuit.
    """
    def __init__(self, circuit_name: str, message: Optional[str] = None):
        self.circuit_name = circuit_name
        self.message = message or f"Circuit '{circuit_name}' is open"
        super().__init__(self.message)


class CircuitState(Enum):
    """
    Enum representing the possible states of a circuit breaker.
    """
    CLOSED = "closed"  # Normal operation, requests flow through
    OPEN = "open"      # Circuit is open, requests fail fast
    HALF_OPEN = "half_open"  # Testing if the circuit can close again


class CircuitBreaker(Generic[T]):
    """
    Circuit breaker implementation to prevent cascade failures.
    """
    
    def __init__(self, 
                failure_threshold: int = 5, 
                recovery_timeout: int = 60, 
                name: str = "default"):
        """
        Initialize the circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening the circuit
            recovery_timeout: Seconds to wait before trying to recover
            name: Name of this circuit breaker
            
        Returns:
            None
            
        Required by:
            None (called during initialization)
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = CircuitState.CLOSED
        self.logger = logging.getLogger(__name__)
    
    def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            Result of the function call
            
        Raises:
            CircuitBreakerOpenError: If the circuit is open
            
        Required by:
            None (called by external components)
            
        Requires:
            - _check_state
            - _handle_success
            - _handle_failure
        """
        # Check if execution is allowed based on circuit state
        if not self._check_state():
            self.logger.warning(f"Circuit '{self.name}' is open, failing fast")
            raise CircuitBreakerOpenError(self.name)
        
        try:
            # Execute the function
            result = func(*args, **kwargs)
            
            # Handle success
            self._handle_success()
            return result
            
        except Exception as e:
            # Handle failure
            self._handle_failure(e)
            
            # Re-raise the original exception
            raise
    
    def _check_state(self) -> bool:
        """
        Check the current state of the circuit breaker and determine if execution is allowed.
        
        Args:
            None
            
        Returns:
            Boolean indicating if execution is allowed
            
        Required by:
            - execute
            
        Requires:
            None
        """
        current_time = time.time()
        
        if self.state == CircuitState.CLOSED:
            # Circuit is closed, allow execution
            return True
            
        elif self.state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if current_time - self.last_failure_time > self.recovery_timeout:
                self.logger.info(f"Circuit '{self.name}' transitioning from OPEN to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                return True
            else:
                # Still within recovery timeout, do not allow execution
                return False
                
        elif self.state == CircuitState.HALF_OPEN:
            # In half-open state, we allow a single execution attempt
            return True
            
        # Shouldn't get here, but just in case
        return False
    
    def _handle_success(self) -> None:
        """
        Handle a successful execution by resetting failure counts.
        
        Args:
            None
            
        Returns:
            None
            
        Required by:
            - execute
            
        Requires:
            None
        """
        if self.state == CircuitState.HALF_OPEN:
            # If we succeed in half-open state, close the circuit
            self.logger.info(f"Circuit '{self.name}' recovered, transitioning from HALF_OPEN to CLOSED")
            self.state = CircuitState.CLOSED
            
        # Reset failure count on success
        self.failure_count = 0
    
    def _handle_failure(self, exception: Exception) -> None:
        """
        Handle a failed execution by incrementing failure counts.
        
        Args:
            exception: The exception that caused the failure
            
        Returns:
            None
            
        Required by:
            - execute
            
        Requires:
            None
        """
        current_time = time.time()
        self.last_failure_time = current_time
        
        if self.state == CircuitState.HALF_OPEN:
            # If we fail in half-open state, reopen the circuit
            self.logger.warning(f"Circuit '{self.name}' failed in HALF_OPEN state, transitioning back to OPEN")
            self.state = CircuitState.OPEN
            
        elif self.state == CircuitState.CLOSED:
            # Increment failure count
            self.failure_count += 1
            self.logger.debug(f"Circuit '{self.name}' failure count: {self.failure_count}/{self.failure_threshold}")
            
            # Check if we've reached the threshold
            if self.failure_count >= self.failure_threshold:
                self.logger.warning(f"Circuit '{self.name}' reached failure threshold, transitioning from CLOSED to OPEN")
                self.state = CircuitState.OPEN
    
    def reset(self) -> None:
        """
        Reset the circuit breaker to its initial state.
        
        Args:
            None
            
        Returns:
            None
            
        Required by:
            None (called by external components)
            
        Requires:
            None
        """
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = CircuitState.CLOSED
        self.logger.info(f"Circuit '{self.name}' manually reset to CLOSED state")
    
    def get_state(self) -> Dict[str, Any]:
        """
        Get the current state of the circuit breaker.
        
        Args:
            None
            
        Returns:
            Dictionary with the current state
            
        Required by:
            None (called by external components)
            
        Requires:
            None
        """
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": self.last_failure_time,
            "recovery_timeout": self.recovery_timeout,
        }


def circuit_breaker(failure_threshold: int = 5, recovery_timeout: int = 60, name: Optional[str] = None):
    """
    Decorator for applying circuit breaker pattern to a function.
    
    Args:
        failure_threshold: Number of failures before opening the circuit
        recovery_timeout: Seconds to wait before trying to recover
        name: Optional name for this circuit breaker
        
    Returns:
        Decorated function
        
    Required by:
        None (used as a decorator)
        
    Requires:
        - CircuitBreaker class
    """
    # Create a circuit breaker instance
    circuit = CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        name=name
    )
    
    def decorator(func):
        # If name wasn't provided, use the function name
        if name is None:
            circuit.name = func.__name__
            
        @wraps(func)
        def wrapper(*args, **kwargs):
            return circuit.execute(func, *args, **kwargs)
            
        # Add circuit reference to the function for introspection
        wrapper.circuit = circuit
        return wrapper
        
    return decorator