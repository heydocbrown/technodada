"""
AWS Lambda function handler for DadaCat Twilio integration.
This handler integrates with the DadaCat agent and persistent storage.
"""
import json
import logging
import os
import sys
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Add the project root directory to the path
# This ensures we can import both dada_agents and our local modules
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
sys.path.append(str(project_root))
logger.info(f"Set path to include project root: {project_root}")
logger.info(f"Current directory contents: {os.listdir(current_dir)}")

# Debug - print all sys.path entries
logger.info(f"sys.path: {sys.path}")

# Import DadaCat components
try:
    logger.info("Attempting to import from src...")
    from src.agent.dadacat_client import DadaCatClient
    from src.conversation.models import Message
    from src.conversation.storage import DynamoDBStorage
    from src.conversation.manager import ConversationManager
    from src.analytics.costs import CostTracker
    from src.analytics.engagement import EngagementTracker, UserActivity
    from src.analytics.errors import ErrorTracker, ErrorCategory
    from src.utils.rate_limiter import RateLimiter
    from twilio.twiml.messaging_response import MessagingResponse
    
    # Initialize components
    DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE', 'dadacat-conversations-dev')
    DYNAMODB_REGION = os.environ.get('AWS_REGION', 'us-east-2')
    MAX_MESSAGES_PER_CONVERSATION = 20
    
    # Initialize DadaCat client
    dadacat_client = DadaCatClient()
    
    # Initialize DynamoDB storage and conversation manager
    storage = DynamoDBStorage(
        table_name=DYNAMODB_TABLE_NAME, 
        region=DYNAMODB_REGION
    )
    conversation_manager = ConversationManager(storage=storage)
    
    # Initialize rate limiter (disabled by default)
    rate_limiter = RateLimiter(
        threshold=int(os.environ.get('RATE_LIMITER_THRESHOLD', 20)),
        time_window=int(os.environ.get('RATE_LIMITER_TIME_WINDOW', 86400)),
        enabled=os.environ.get('RATE_LIMITER_ENABLED', '').lower() in ('true', '1', 'yes'),
        donation_url="technodada.org/donate"
    )
    logger.info(f"Rate limiter initialized (enabled: {rate_limiter.enabled}, threshold: {rate_limiter.threshold})")
    
    # Initialize analytics trackers
    ANALYTICS_ENABLED = os.environ.get('ANALYTICS_ENABLED', '').lower() in ('true', '1', 'yes')
    if ANALYTICS_ENABLED:
        cost_tracker = CostTracker(
            namespace=os.environ.get('ANALYTICS_NAMESPACE', 'DadaCatTwilio'),
            region=DYNAMODB_REGION,
            local_file_fallback=True
        )
        
        engagement_tracker = EngagementTracker(
            namespace=os.environ.get('ANALYTICS_NAMESPACE', 'DadaCatTwilio'),
            region=DYNAMODB_REGION,
            local_file_fallback=True
        )
        
        error_tracker = ErrorTracker(
            namespace=os.environ.get('ANALYTICS_NAMESPACE', 'DadaCatTwilio'),
            region=DYNAMODB_REGION,
            local_file_fallback=True
        )
        
        logger.info("Analytics components initialized")
    else:
        logger.info("Analytics disabled (set ANALYTICS_ENABLED=true to enable)")
        cost_tracker = None
        engagement_tracker = None
        error_tracker = None
    
except Exception as e:
    logger.error(f"Error initializing components: {str(e)}", exc_info=True)
    # We'll handle this in the lambda_handler if components aren't initialized

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda function handler.
    
    Args:
        event: Lambda event
        context: Lambda context
        
    Returns:
        Dictionary with response data
    """
    try:
        logger.info(f"Processing event: {json.dumps(event)}")
        return process_event(event)
    except Exception as e:
        logger.error(f"Error processing event: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }


def process_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a Lambda event.
    """
    # Extract request data
    request_data = {}
    
    # Check if we have a body in the event
    if 'body' in event:
        # Parse form data
        form_data = event['body']
        parsed_data = urllib.parse.parse_qs(form_data)
        
        # Get message content and sender
        request_data['body'] = parsed_data.get('Body', [''])[0]
        request_data['from'] = parsed_data.get('From', [''])[0]
        logger.info(f"Received message: {request_data['body']} from {request_data['from']}")
    else:
        # For testing direct Lambda invocation
        request_data['body'] = "Test message"
        request_data['from'] = "Test sender"
    
    # Generate response
    response = process_message(request_data)
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/xml'
        },
        'body': response
    }


def process_message(request_data: Dict[str, Any]) -> str:
    """
    Process an incoming message and return a Twilio-compatible response.
    """
    # Start timing for response time tracking
    request_start_time = datetime.now()
    
    # Get the message content and sender's phone number
    incoming_message = request_data.get('body', '').strip()
    from_number = request_data.get('from', '')
    
    logger.info(f"Processing message from {from_number}: {incoming_message}")
    
    # Track analytics if enabled
    if ANALYTICS_ENABLED and engagement_tracker:
        engagement_tracker.track_user_activity(
            user_id=from_number,
            activity_type=UserActivity.MESSAGE
        )
    
    # Check for admin commands
    if incoming_message.lower() in ['reset', 'restart', 'clear']:
        # Reset conversation history
        conversation_manager.reset_conversation(from_number)
        
        # Also reset rate limiter counter if enabled
        rate_limiter.reset_counter(from_number)
        
        # Track reset action if analytics is enabled
        if ANALYTICS_ENABLED and engagement_tracker:
            engagement_tracker.track_user_activity(
                user_id=from_number,
                activity_type=UserActivity.RESET
            )
        
        response_text = "Conversation has been reset. What would you like to talk about?"
    elif incoming_message.lower() == 'admin:enable_rate_limiter':
        # Enable rate limiter (admin command)
        rate_limiter.enable()
        
        # Track admin command if analytics is enabled
        if ANALYTICS_ENABLED and engagement_tracker:
            engagement_tracker.track_user_activity(
                user_id=from_number,
                activity_type=UserActivity.ADMIN_COMMAND
            )
            
        response_text = "Rate limiter has been ENABLED"
    elif incoming_message.lower() == 'admin:disable_rate_limiter':
        # Disable rate limiter (admin command)
        rate_limiter.disable()
        
        # Track admin command if analytics is enabled
        if ANALYTICS_ENABLED and engagement_tracker:
            engagement_tracker.track_user_activity(
                user_id=from_number,
                activity_type=UserActivity.ADMIN_COMMAND
            )
            
        response_text = "Rate limiter has been DISABLED"
    elif incoming_message.lower() == 'admin:status':
        # Return status information
        status_lines = [
            f"DadaCat Status:",
            f"- Rate limiter: {'ENABLED' if rate_limiter.enabled else 'DISABLED'}",
            f"- Message count: {conversation_manager.get_message_count(from_number)}",
            f"- Threshold: {rate_limiter.threshold} messages",
            f"- Time window: {rate_limiter.time_window/3600:.1f} hours"
        ]
        
        # Add analytics status if enabled
        if ANALYTICS_ENABLED:
            status_lines.append(f"- Analytics: ENABLED")
        else:
            status_lines.append(f"- Analytics: DISABLED")
        
        # Track admin command if analytics is enabled
        if ANALYTICS_ENABLED and engagement_tracker:
            engagement_tracker.track_user_activity(
                user_id=from_number,
                activity_type=UserActivity.ADMIN_COMMAND
            )
        
        response_text = "\n".join(status_lines)
    else:
        try:
            # Add user message to conversation
            conversation_manager.add_user_message(
                user_id=from_number,
                content=incoming_message
            )
            
            # Get conversation history
            conversation = conversation_manager.get_or_create_conversation(from_number)
            formatted_history = conversation.get_formatted_history()
            
            # Record message with rate limiter and check if we should show a donation prompt
            rate_limiter.record_message(from_number)
            rate_limit_result = rate_limiter.check_rate_limit(from_number)
            
            # Log message count
            message_count = conversation_manager.get_message_count(from_number)
            logger.info(f"Current message count for {from_number}: {message_count}")
            
            # Determine if we should add a donation prompt (using rate limiter if enabled)
            donation_prompted = False
            if rate_limit_result['should_prompt']:
                donation_prompt = f"\n\n{rate_limit_result['prompt_message']}"
                logger.info(f"Adding donation prompt from rate limiter at count {rate_limit_result['count']}")
                donation_prompted = True
            else:
                # Fallback to previous logic if rate limiter is disabled
                if message_count > 0 and message_count % 10 == 5:  # We'll hit this at 5, 15, 25, etc.
                    donation_prompt = f"\n\n(DadaCat has now sent you {message_count // 2} messages. " \
                                     "Please consider supporting DadaCat's development by visiting " \
                                     "our donation page at technodada.org/donate)"
                    logger.info(f"Adding donation prompt from message count at count {message_count}")
                    donation_prompted = True
                else:
                    donation_prompt = ""
            
            # Track donation prompt if shown and analytics enabled
            if donation_prompted and ANALYTICS_ENABLED and engagement_tracker:
                engagement_tracker.track_user_activity(
                    user_id=from_number,
                    activity_type=UserActivity.DONATION_PROMPT
                )
            
            # Generate response using our DadaCat client
            response_text = dadacat_client.generate_response(
                user_message=incoming_message,
                conversation_history=formatted_history,
                user_id=from_number
            )
            
            # Track API cost if analytics enabled
            if ANALYTICS_ENABLED and cost_tracker:
                # Estimate cost based on response length (very rough estimate)
                response_length = len(response_text)
                prompt_length = len(incoming_message) + len(formatted_history)
                total_tokens = (prompt_length + response_length) / 4  # rough estimate of tokens
                
                # GPT-4 cost estimate (very approximate)
                # Input: $0.01 per 1K tokens, Output: $0.03 per 1K tokens
                input_cost = (prompt_length / 4) * 0.01 / 1000
                output_cost = (response_length / 4) * 0.03 / 1000
                total_cost = input_cost + output_cost
                
                cost_tracker.track_api_cost(
                    api_name="openai",
                    cost_estimate=total_cost,
                    request_count=1,
                    request_tokens=int(total_tokens)
                )
            
            # Add donation prompt if needed
            if donation_prompt:
                response_text += donation_prompt
            
            # Add assistant response to conversation
            conversation_manager.add_assistant_message(
                user_id=from_number,
                content=response_text
            )
            
            # Show conversation length for debugging
            conversation_length = conversation_manager.get_message_count(from_number)
            logger.info(f"Conversation with {from_number} now has {conversation_length} messages")
            
            # Track conversation metrics if analytics enabled
            if ANALYTICS_ENABLED and engagement_tracker:
                # Calculate conversation duration
                first_message_time = conversation.get_first_message_time()
                last_message_time = datetime.now()
                
                if first_message_time:
                    duration_seconds = (last_message_time - first_message_time).total_seconds()
                    
                    engagement_tracker.track_conversation(
                        user_id=from_number,
                        message_count=conversation_length,
                        duration_seconds=duration_seconds
                    )
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}", exc_info=True)
            response_text = "Meow? (DadaCat seems to be napping. Please try again later.)"
            
            # Track error if analytics enabled
            if ANALYTICS_ENABLED and error_tracker:
                error_tracker.track_error(
                    error_type="response_generation_error",
                    error_message=str(e),
                    category=ErrorCategory.API_ERROR,
                    context={"user_id": from_number, "message": incoming_message},
                    exception=e
                )
    
    # Create TwiML response
    twilio_response = MessagingResponse()
    twilio_response.message(response_text)
    
    # Track Twilio API cost if analytics enabled
    if ANALYTICS_ENABLED and cost_tracker:
        # Estimate Twilio cost (very rough estimate)
        # Standard SMS cost is about $0.0075 per message
        cost_tracker.track_api_cost(
            api_name="twilio",
            cost_estimate=0.0075,
            request_count=1
        )
    
    # Track response time if analytics enabled
    if ANALYTICS_ENABLED and engagement_tracker:
        request_end_time = datetime.now()
        response_time_ms = (request_end_time - request_start_time).total_seconds() * 1000
        
        engagement_tracker.track_response_time(response_time_ms)
    
    return str(twilio_response)