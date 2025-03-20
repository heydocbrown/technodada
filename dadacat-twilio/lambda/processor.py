"""
AWS Lambda function handler for asynchronous DadaCat message processing.
This handler processes messages from the queue and sends responses back to the user.
"""
import json
import logging
import os
import sys
import traceback
import boto3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from twilio.rest import Client

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Add the project root directory to the path
# This ensures we can import both dada_agents and our local modules
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root.parent))
logger.info(f"Set path to include project root: {project_root}")
logger.info(f"Current directory contents: {os.listdir(current_dir)}")

# Initialize global variables to avoid reference errors
DADACAT_IMPORT_SUCCESS = False
cost_tracker = None
engagement_tracker = None
error_tracker = None
storage = None
conversation_manager = None

# Import DadaCat components
try:
    logger.info("Attempting to import from src...")
    from src.conversation.models import Message
    from src.conversation.storage import DynamoDBStorage
    from src.conversation.manager import ConversationManager
    from src.analytics.costs import CostTracker
    from src.analytics.engagement import EngagementTracker, UserActivity
    from src.analytics.errors import ErrorTracker, ErrorCategory

    # Try to import DadaCat
    try:
        # Add the Lambda task root to ensure imports work in containerized environment
        lambda_task_root = os.environ.get('LAMBDA_TASK_ROOT', '')
        if lambda_task_root and lambda_task_root not in sys.path:
            sys.path.insert(0, lambda_task_root)
            logger.info(f"Added LAMBDA_TASK_ROOT to sys.path: {lambda_task_root}")
            
        # Log current environment for debugging
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"Python path: {sys.path}")
        
        # Try the direct import from dada_agents module
        from dada_agents.dadacat import generate_dada_cat_response
        logger.info("Successfully imported DadaCat module")
        DADACAT_IMPORT_SUCCESS = True
    except ImportError as e:
        logger.error(f"Failed to import DadaCat module: {e}")
        logger.error(f"Import traceback: {traceback.format_exc()}")
        DADACAT_IMPORT_SUCCESS = False
    except Exception as e:
        logger.error(f"Unexpected error importing DadaCat module: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        DADACAT_IMPORT_SUCCESS = False
    
    # Initialize components
    DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE', 'dadacat-conversations-dev')
    DYNAMODB_REGION = os.environ.get('AWS_REGION', 'us-east-2')
    
    # Twilio configuration
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
    
    # Initialize DynamoDB storage and conversation manager
    storage = DynamoDBStorage(
        table_name=DYNAMODB_TABLE_NAME, 
        region=DYNAMODB_REGION
    )
    conversation_manager = ConversationManager(storage=storage)
    
    # Initialize analytics trackers
    ANALYTICS_ENABLED = os.environ.get('ANALYTICS_ENABLED', '').lower() in ('true', '1', 'yes')
    if ANALYTICS_ENABLED:
        # Lambda container has read-only filesystem, so disable local file fallback
        cost_tracker = CostTracker(
            namespace=os.environ.get('ANALYTICS_NAMESPACE', 'DadaCatTwilio'),
            region=DYNAMODB_REGION,
            local_file_fallback=False  # Changed to False to avoid read-only filesystem errors
        )
        
        engagement_tracker = EngagementTracker(
            namespace=os.environ.get('ANALYTICS_NAMESPACE', 'DadaCatTwilio'),
            region=DYNAMODB_REGION,
            local_file_fallback=False  # Changed to False to avoid read-only filesystem errors
        )
        
        error_tracker = ErrorTracker(
            namespace=os.environ.get('ANALYTICS_NAMESPACE', 'DadaCatTwilio'),
            region=DYNAMODB_REGION,
            local_file_fallback=False  # Changed to False to avoid read-only filesystem errors
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
    AWS Lambda function handler for processing DadaCat messages from SQS.
    
    Args:
        event: Lambda event containing SQS messages
        context: Lambda context
        
    Returns:
        Dictionary with processing results
    """
    logger.info(f"Processing event: {json.dumps(event)}")
    
    # Process each message from SQS
    processed_count = 0
    error_count = 0
    
    if 'Records' in event:
        for record in event['Records']:
            try:
                # Parse the message body
                message_body = json.loads(record['body'])
                logger.info(f"Processing message: {message_body}")
                
                # Validate the message data
                user_id = message_body.get('user_id')
                message = message_body.get('message')
                
                logger.info(f"Received SQS message with user_id='{user_id}', message='{message}'")
                
                if not user_id or not isinstance(user_id, str) or not user_id.startswith('+'):
                    logger.error(f"Invalid phone number format in SQS message: '{user_id}' - Must start with + and contain country code")
                    # Continue processing to catch this in the logs, but expect it to fail later
                
                # Process the message
                process_message(message_body)
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}", exc_info=True)
                error_count += 1
                
                # Track error if analytics enabled
                if ANALYTICS_ENABLED and error_tracker:
                    error_tracker.track_error(
                        error_type="sqs_message_processing_error",
                        error_message=str(e),
                        category=ErrorCategory.PROCESSING_ERROR,
                        context={"record": record},
                        exception=e
                    )
    
    return {
        'processed_count': processed_count,
        'error_count': error_count
    }


def process_message(message_data: Dict[str, Any]) -> None:
    """
    Process a message from the queue and send a response to the user.
    
    Args:
        message_data: Message data from SQS
    """
    # Start timing for response time tracking
    request_start_time = datetime.now()
    
    user_id = message_data.get('user_id')
    incoming_message = message_data.get('message')
    
    logger.info(f"Processing queued message from {user_id}: {incoming_message}")
    
    # Track analytics if enabled
    if ANALYTICS_ENABLED and engagement_tracker:
        engagement_tracker.track_user_activity(
            user_id=user_id,
            activity_type=UserActivity.MESSAGE
        )
    
    try:
        # Get conversation history
        conversation = conversation_manager.get_or_create_conversation(user_id)
        formatted_history = conversation.get_formatted_history()
        
        # Generate response using DadaCat
        logger.info(f"Generating response for {user_id}")
        try:
            if DADACAT_IMPORT_SUCCESS:
                # Use the DadaCat agent
                logger.info("Using DadaCat agent to generate response...")
                try:
                    # Check if OpenAI API key is available
                    openai_api_key = os.environ.get("OPENAI_API_KEY")
                    if not openai_api_key:
                        logger.error("OPENAI_API_KEY environment variable is not set")
                        response_text = "The DadaCat needs an API key to talk. (Missing OpenAI API key)"
                    else:
                        logger.info("OpenAI API key found, length: " + str(len(openai_api_key)))
                        logger.info(f"Calling generate_dada_cat_response with message: '{incoming_message}'")
                        response_text = generate_dada_cat_response(incoming_message, api_key=openai_api_key)
                        logger.info(f"Generated response: '{response_text}'")
                        
                        # Remove "Meow, human!" prefix if present
                        original_length = len(response_text)
                        response_text = response_text.replace("Meow, human! ", "").replace("Meow, human\\! ", "")
                        if len(response_text) != original_length:
                            logger.info("Removed 'Meow, human!' prefix from response")
                except Exception as e:
                    logger.error(f"Error calling generate_dada_cat_response: {str(e)}", exc_info=True)
                    response_text = f"The DadaCat encountered an error: {str(e)}"
            else:
                # Fallback to a hardcoded response (without the meow prefix)
                logger.warning("DadaCat module not available, using fallback response")
                response_text = f"The DadaCat is here, ready to pounce on the bizarre with surreal whiskers of wisdom. In response to '{incoming_message}', I say: time is a cat's cradle woven from paradoxical yarn."
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}", exc_info=True)
            response_text = "Meow? (DadaCat seems to be napping. Please try again later.)"
            
            # Track error if analytics enabled
            if ANALYTICS_ENABLED and error_tracker:
                error_tracker.track_error(
                    error_type="response_generation_error",
                    error_message=str(e),
                    category=ErrorCategory.API_ERROR,
                    context={"user_id": user_id, "message": incoming_message},
                    exception=e
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
        
        # Add assistant response to conversation
        conversation_manager.add_assistant_message(
            user_id=user_id,
            content=response_text
        )
        
        # Show conversation length for debugging
        conversation_length = conversation_manager.get_message_count(user_id)
        logger.info(f"Conversation with {user_id} now has {conversation_length} messages")
        
        # Track conversation metrics if analytics enabled
        if ANALYTICS_ENABLED and engagement_tracker:
            # Calculate conversation duration
            first_message_time = conversation.get_first_message_time()
            last_message_time = datetime.now()
            
            if first_message_time:
                duration_seconds = (last_message_time - first_message_time).total_seconds()
                
                engagement_tracker.track_conversation(
                    user_id=user_id,
                    message_count=conversation_length,
                    duration_seconds=duration_seconds
                )
        
        # Send the response message via Twilio
        logger.info(f"Sending response to {user_id} (EXACT USER ID VALUE IN QUOTES: '{user_id}')")
        # Ensure the recipient phone number is correctly formatted
        recipient = user_id.strip() if user_id else None
        logger.info(f"Formatted recipient phone number: '{recipient}'")
        if not recipient or not recipient.startswith('+'):
            logger.error(f"Invalid phone number format: '{recipient}' - Must start with + and contain country code")
            recipient = None  # Will cause an error in send_twilio_message to be caught and logged
        
        send_twilio_message(recipient, response_text)
        
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
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        
        # Track error if analytics enabled
        if ANALYTICS_ENABLED and error_tracker:
            error_tracker.track_error(
                error_type="message_processing_error",
                error_message=str(e),
                category=ErrorCategory.PROCESSING_ERROR,
                context={"user_id": user_id, "message": incoming_message},
                exception=e
            )
        
        try:
            # Send error message to user
            error_message = "Meow? (DadaCat seems to be napping. Please try again later.)"
            send_twilio_message(user_id, error_message)
        except Exception as send_error:
            logger.error(f"Error sending error message: {str(send_error)}", exc_info=True)


def send_twilio_message(to: str, body: str) -> Dict[str, Any]:
    """
    Send a message via Twilio.
    
    Args:
        to: Recipient phone number
        body: Message content
        
    Returns:
        Dictionary with Twilio response data
    """
    try:
        # Initialize Twilio client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        # Validate phone number format
        if not to or not isinstance(to, str) or not to.startswith('+'):
            error_msg = f"Invalid phone number format: '{to}' - Must start with + and contain country code"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        from_number = TWILIO_PHONE_NUMBER
        logger.info(f"Preparing to send message from '{from_number}' to '{to}'")
        logger.info(f"Message content: '{body}'")
        
        # Send message
        message = client.messages.create(
            from_=from_number,
            to=to,
            body=body
        )
        
        logger.info(f"Successfully sent message to '{to}' with SID {message.sid}")
        logger.info(f"Message status: {message.status}")
        
        return {
            'sid': message.sid,
            'status': message.status
        }
    except Exception as e:
        logger.error(f"Error sending Twilio message to '{to}': {str(e)}", exc_info=True)
        raise
