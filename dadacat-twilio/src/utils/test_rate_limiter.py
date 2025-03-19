#!/usr/bin/env python
"""
Test script to demonstrate the rate limiter.
"""
import sys
import os
import logging
import time
from pathlib import Path

# Add project root to path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent.parent
sys.path.append(str(project_root))

# Add source directory to path
src_dir = current_dir.parent
sys.path.append(str(src_dir))

# Import rate limiter
from utils.rate_limiter import RateLimiter, with_rate_limit

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test function that will be rate limited
def generate_response(user_id: str, message: str) -> str:
    """Generate a response for a user message"""
    return f"Response to '{message}' from user {user_id}"

# Test function with the decorator
@with_rate_limit(
    RateLimiter(threshold=5, enabled=True, time_window=3600),  # 5 messages per hour
    lambda user_id, message: user_id  # Extract user_id from arguments
)
def generate_response_with_rate_limit(user_id: str, message: str) -> str:
    """Generate a response with rate limiting applied"""
    return generate_response(user_id, message)

def test_rate_limiter_disabled():
    """Test rate limiter when disabled"""
    logger.info("\n=== TESTING RATE LIMITER (DISABLED) ===")
    
    # Create a rate limiter that's disabled
    limiter = RateLimiter(threshold=5, enabled=False)
    
    # Simulate messages from a user
    user_id = "test_user_1"
    for i in range(20):  # Send 20 messages
        # Record the message
        count = limiter.record_message(user_id)
        
        # Check if we should show a donation prompt
        result = limiter.check_rate_limit(user_id)
        
        logger.info(f"Message {i+1} - Count: {count}, Should prompt: {result['should_prompt']}")
        
        # Short delay between messages
        time.sleep(0.1)
    
    # Check final state
    final_result = limiter.check_rate_limit(user_id)
    logger.info(f"Final state: {final_result}")

def test_rate_limiter_enabled():
    """Test rate limiter when enabled"""
    logger.info("\n=== TESTING RATE LIMITER (ENABLED) ===")
    
    # Create a rate limiter that's enabled
    limiter = RateLimiter(threshold=5, enabled=True, time_window=3600)  # 5 messages per hour
    
    # Simulate messages from a user
    user_id = "test_user_2"
    for i in range(20):  # Send 20 messages
        # Record the message
        count = limiter.record_message(user_id)
        
        # Check if we should show a donation prompt
        result = limiter.check_rate_limit(user_id)
        
        logger.info(f"Message {i+1} - Count: {count}, "
                  f"Should prompt: {result['should_prompt']}, "
                  f"Prompt message: {result['prompt_message'] if result['should_prompt'] else 'None'}")
        
        # Short delay between messages
        time.sleep(0.1)
    
    # Reset the counter
    limiter.reset_counter(user_id)
    logger.info("Counter reset")
    
    # Check final state after reset
    final_result = limiter.check_rate_limit(user_id)
    logger.info(f"Final state after reset: {final_result}")

def test_rate_limiter_with_decorator():
    """Test rate limiter using the decorator"""
    logger.info("\n=== TESTING RATE LIMITER WITH DECORATOR ===")
    
    # Simulate messages from a user using the decorated function
    user_id = "test_user_3"
    for i in range(12):  # Send 12 messages
        response, rate_limit_info = generate_response_with_rate_limit(user_id, f"Message {i+1}")
        
        logger.info(f"Message {i+1} - Response: {response}")
        logger.info(f"Rate limit info: {rate_limit_info}")
        
        # If we should show a donation prompt, display it
        if rate_limit_info['should_prompt']:
            logger.info(f"DONATION PROMPT: {rate_limit_info['prompt_message']}")
        
        # Short delay between messages
        time.sleep(0.1)

def test_multiple_users():
    """Test rate limiter with multiple users"""
    logger.info("\n=== TESTING RATE LIMITER WITH MULTIPLE USERS ===")
    
    # Create a rate limiter
    limiter = RateLimiter(threshold=5, enabled=True, time_window=3600)  # 5 messages per hour
    
    # Simulate messages from multiple users
    users = ["user_a", "user_b", "user_c"]
    
    for _ in range(7):  # 7 rounds of messages
        for user_id in users:
            # Record the message
            count = limiter.record_message(user_id)
            
            # Check if we should show a donation prompt
            result = limiter.check_rate_limit(user_id)
            
            logger.info(f"User {user_id} - Count: {count}, "
                      f"Should prompt: {result['should_prompt']}")
            
            # If we should show a donation prompt, display it
            if result['should_prompt']:
                logger.info(f"DONATION PROMPT for {user_id}: {result['prompt_message']}")
            
            # Short delay between messages
            time.sleep(0.1)

def test_enable_disable():
    """Test enabling and disabling the rate limiter"""
    logger.info("\n=== TESTING ENABLING/DISABLING RATE LIMITER ===")
    
    # Create a rate limiter that's initially disabled
    limiter = RateLimiter(threshold=3, enabled=False)
    
    # Simulate some messages while disabled
    user_id = "test_user_4"
    for i in range(4):
        count = limiter.record_message(user_id)
        result = limiter.check_rate_limit(user_id)
        logger.info(f"DISABLED - Message {i+1} - Count: {count}, Should prompt: {result['should_prompt']}")
    
    # Enable the rate limiter
    limiter.enable()
    
    # Simulate more messages while enabled
    for i in range(6):
        count = limiter.record_message(user_id)
        result = limiter.check_rate_limit(user_id)
        logger.info(f"ENABLED - Message {i+1} - Count: {count}, Should prompt: {result['should_prompt']}")
        
        # If we should show a donation prompt, display it
        if result['should_prompt']:
            logger.info(f"DONATION PROMPT: {result['prompt_message']}")
    
    # Disable the rate limiter again
    limiter.disable()
    
    # Simulate more messages after disabling
    for i in range(3):
        count = limiter.record_message(user_id)
        result = limiter.check_rate_limit(user_id)
        logger.info(f"DISABLED AGAIN - Message {i+1} - Count: {count}, Should prompt: {result['should_prompt']}")

if __name__ == "__main__":
    """Run all tests"""
    # Test each scenario
    test_rate_limiter_disabled()
    test_rate_limiter_enabled()
    test_rate_limiter_with_decorator()
    test_multiple_users()
    test_enable_disable()
    
    logger.info("\n=== ALL RATE LIMITER TESTS COMPLETE ===")