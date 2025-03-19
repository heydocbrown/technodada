#!/usr/bin/env python
"""
Test script to demonstrate the error handling components.
"""
import sys
import os
import logging
import time
import json
import random
from pathlib import Path
import traceback
from typing import Dict, Any

# Add project root to path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent.parent
sys.path.append(str(project_root))

# Add source directory to path
src_dir = current_dir.parent
sys.path.append(str(src_dir))

# Import error handling components
from error_handling.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError, circuit_breaker
from error_handling.backoff import BackoffStrategy, RetryExhaustedError, with_backoff
from error_handling.dead_letter import DeadLetterQueue
from error_handling.notifier import AdminNotifier, ErrorSeverity, NotificationChannel

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create a test function that sometimes fails
def unreliable_function(success_rate: float = 0.7, delay: float = 0.5) -> str:
    """Simulates an unreliable API call that sometimes fails"""
    # Add delay to simulate network latency
    time.sleep(delay)
    
    # Randomly succeed or fail based on success_rate
    if random.random() < success_rate:
        return "Operation succeeded"
    else:
        error_type = random.choice([
            "ConnectionError",
            "TimeoutError",
            "ServerError",
            "AuthenticationError"
        ])
        raise Exception(f"API Error: {error_type}")

def test_circuit_breaker():
    """Test the circuit breaker pattern"""
    logger.info("\n=== TESTING CIRCUIT BREAKER ===")
    
    # Create a circuit breaker with low threshold for demo
    breaker = CircuitBreaker(
        failure_threshold=3,  # Open after 3 failures
        recovery_timeout=5,   # Try to recover after 5 seconds
        name="test-circuit"
    )
    
    # Run several attempts, tracking successes and failures
    results = {"success": 0, "failure": 0, "circuit_open": 0}
    
    for i in range(10):
        try:
            # Use unreliable_function with lower success rate to trigger circuit breaker
            result = breaker.execute(unreliable_function, success_rate=0.3)
            logger.info(f"Attempt {i+1}: SUCCESS - {result}")
            results["success"] += 1
            
        except CircuitBreakerOpenError:
            logger.warning(f"Attempt {i+1}: CIRCUIT OPEN - Failing fast")
            results["circuit_open"] += 1
            
        except Exception as e:
            logger.error(f"Attempt {i+1}: FAILURE - {str(e)}")
            results["failure"] += 1
        
        # Short delay between attempts
        time.sleep(0.5)
    
    logger.info(f"Circuit Breaker Results: {json.dumps(results)}")
    
    # If circuit is open, wait for recovery and try again
    if breaker.state.value == "open":
        logger.info(f"Circuit is open, waiting {breaker.recovery_timeout} seconds for recovery...")
        time.sleep(breaker.recovery_timeout)
        
        try:
            # This should succeed after recovery timeout
            result = breaker.execute(unreliable_function, success_rate=1.0)  # Force success
            logger.info(f"Recovery test: SUCCESS - {result}")
        except Exception as e:
            logger.error(f"Recovery test: FAILURE - {str(e)}")

def test_backoff_strategy():
    """Test the exponential backoff strategy"""
    logger.info("\n=== TESTING BACKOFF STRATEGY ===")
    
    # Create backoff strategy
    strategy = BackoffStrategy(
        base_delay=0.5,   # Start with 0.5s delay
        max_delay=5.0,    # Don't delay more than 5s
        max_retries=4     # Retry up to 4 times
    )
    
    # Try with a very unreliable function
    try:
        result = strategy.execute(
            unreliable_function,
            success_rate=0.2,  # Low success rate
            retry_exceptions=(Exception,)
        )
        logger.info(f"Backoff successful: {result}")
    except RetryExhaustedError as e:
        logger.error(f"All retries exhausted: {e}")
        logger.error(f"Last error was: {e.last_exception}")

def test_dead_letter_queue():
    """Test the dead letter queue"""
    logger.info("\n=== TESTING DEAD LETTER QUEUE ===")
    
    # Create local DLQ
    dlq = DeadLetterQueue(
        local_file_path="./local_dlq.json",
        reprocessor=lambda msg: True  # Simple reprocessor that always succeeds
    )
    
    # Send some test messages to the DLQ
    for i in range(3):
        message = {
            "id": f"msg_{i}",
            "content": f"Test message {i}",
            "timestamp": time.time()
        }
        
        error_info = {
            "error_type": random.choice(["connection_error", "timeout", "validation_error"]),
            "error_message": f"Error processing message {i}"
        }
        
        success = dlq.send_to_dlq(message, error_info)
        logger.info(f"Sent message {i} to DLQ: {'SUCCESS' if success else 'FAILURE'}")
    
    # Retrieve messages from DLQ
    messages = dlq.receive_from_dlq()
    logger.info(f"Retrieved {len(messages)} messages from DLQ")
    
    # Reprocess a message
    if messages:
        message_id = messages[0]['message_id']
        reprocessed = dlq.reprocess_message(message_id)
        logger.info(f"Reprocessed message {message_id}: {'SUCCESS' if reprocessed else 'FAILURE'}")

def test_admin_notifier():
    """Test the admin notifier"""
    logger.info("\n=== TESTING ADMIN NOTIFIER ===")
    
    # Create notifier in logging-only mode
    notifier = AdminNotifier()
    
    # Send notifications with different severity levels
    severities = [
        ErrorSeverity.INFO,
        ErrorSeverity.WARNING,
        ErrorSeverity.ERROR,
        ErrorSeverity.CRITICAL
    ]
    
    for severity in severities:
        success = notifier.send_notification(
            message=f"Test notification with {severity.value} severity",
            details={
                "test_id": f"test_{severity.value}",
                "timestamp": time.time(),
                "sample_data": {"key1": "value1", "key2": 42}
            },
            severity=severity,
            error_type=f"test_{severity.value}"
        )
        logger.info(f"Sent {severity.value} notification: {'SUCCESS' if success else 'FAILURE'}")
    
    # Test health check notification
    notifier.send_health_check_notification(
        is_healthy=True,
        details={"components_checked": 4, "all_operational": True}
    )

def test_combined_error_handling():
    """Test all error handling components working together"""
    logger.info("\n=== TESTING COMBINED ERROR HANDLING ===")
    
    # Initialize components
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=5, name="api-circuit")
    strategy = BackoffStrategy(base_delay=0.5, max_delay=5.0, max_retries=3)
    dlq = DeadLetterQueue(local_file_path="./local_dlq.json")
    notifier = AdminNotifier()
    
    # Test function that uses all components
    def process_message(message: Dict[str, Any]) -> str:
        try:
            # Try with circuit breaker + backoff
            try:
                # This will try up to 3 times with backoff and will trip the circuit after 3 failures
                result = breaker.execute(
                    strategy.execute,
                    unreliable_function,
                    success_rate=0.3,  # Very unreliable
                    retry_exceptions=(Exception,)
                )
                return result
                
            except CircuitBreakerOpenError:
                # Circuit is open, notify admin and use fallback
                notifier.send_notification(
                    message="API circuit is open - too many failures",
                    details={
                        "circuit_name": breaker.name,
                        "failure_count": breaker.failure_count,
                        "message": str(message)
                    },
                    severity=ErrorSeverity.ERROR,
                    error_type="circuit_breaker_open"
                )
                return "FALLBACK: Circuit breaker is open"
                
        except Exception as e:
            # Final error handler - log, notify, and send to DLQ
            error_info = {
                "error_type": "processing_error",
                "error_message": str(e),
                "traceback": traceback.format_exc()
            }
            
            # Send to DLQ
            dlq.send_to_dlq(message, error_info)
            
            # Notify admin
            notifier.send_notification(
                message="Failed to process message after all retries",
                details={
                    "error": str(e),
                    "message": str(message)
                },
                severity=ErrorSeverity.ERROR
            )
            
            # Return fallback response
            return "FALLBACK: All error handling failed"
    
    # Process several messages
    for i in range(5):
        message = {
            "id": f"test_msg_{i}",
            "content": f"Test message {i}",
            "timestamp": time.time()
        }
        
        result = process_message(message)
        logger.info(f"Message {i} result: {result}")
        
        # Short delay between attempts
        time.sleep(0.5)
        
    # Wait for circuit recovery and try again
    if breaker.state.value == "open":
        logger.info(f"Circuit is open, waiting {breaker.recovery_timeout} seconds for recovery...")
        time.sleep(breaker.recovery_timeout + 1)
        
        # Process one more message after recovery timeout
        message = {
            "id": "recovery_test",
            "content": "Recovery test message",
            "timestamp": time.time()
        }
        
        result = process_message(message)
        logger.info(f"Recovery test result: {result}")

if __name__ == "__main__":
    """Run all tests"""
    # Test each component individually
    test_circuit_breaker()
    test_backoff_strategy()
    test_dead_letter_queue()
    test_admin_notifier()
    
    # Test all components working together
    test_combined_error_handling()
    
    logger.info("\n=== ALL ERROR HANDLING TESTS COMPLETE ===")