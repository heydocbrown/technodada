"""
Flask application with DynamoDB persistence for DadaCat Twilio integration.
This builds on app_simple.py by adding persistent conversation storage.
"""
import os
import logging
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
import sys

# Add the project root directory to the path
# This ensures we can import both dada_agents and our local modules
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
sys.path.append(str(project_root))

# Add the current directory to the path to import our local modules
sys.path.append(str(current_dir))

# Import our components
from agent.dadacat_client import DadaCatClient
from conversation.models import Message
from conversation.storage import DynamoDBStorage
from conversation.manager import ConversationManager

# Import analytics components
from analytics.costs import CostTracker
from analytics.engagement import EngagementTracker, UserActivity
from analytics.errors import ErrorTracker, ErrorCategory

# Load environment variables from .env file in the project root
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Initialize components
DYNAMODB_TABLE_NAME = os.getenv('DYNAMODB_TABLE_NAME', 'DadaCatConversations')
DYNAMODB_REGION = os.getenv('DYNAMODB_REGION', 'us-east-1')
MAX_MESSAGES_PER_CONVERSATION = 20

# Initialize DadaCat client
dadacat_client = DadaCatClient()

# Initialize DynamoDB storage and conversation manager
# Check for local DynamoDB endpoint
local_dynamodb_endpoint = os.getenv('AWS_ENDPOINT_URL')
if local_dynamodb_endpoint:
    logger.info(f"Using local DynamoDB at {local_dynamodb_endpoint}")
else:
    logger.info("Using AWS DynamoDB")

# Create storage with optional local endpoint
storage = DynamoDBStorage(
    table_name=DYNAMODB_TABLE_NAME, 
    region=DYNAMODB_REGION,
    endpoint_url=local_dynamodb_endpoint
)
conversation_manager = ConversationManager(storage=storage)

# Initialize rate limiter (disabled by default)
from utils.rate_limiter import RateLimiter
rate_limiter = RateLimiter(
    threshold=int(os.getenv('RATE_LIMITER_THRESHOLD', 20)),    # Show donation prompt every 20 messages by default
    time_window=int(os.getenv('RATE_LIMITER_TIME_WINDOW', 86400)),  # 24 hour window by default
    enabled=os.getenv('RATE_LIMITER_ENABLED', '').lower() in ('true', '1', 'yes'),  # Disabled by default
    donation_url="technodada.org/donate"
)
logger.info(f"Rate limiter initialized (enabled: {rate_limiter.enabled}, threshold: {rate_limiter.threshold})")

# Initialize analytics trackers
ANALYTICS_ENABLED = os.getenv('ANALYTICS_ENABLED', '').lower() in ('true', '1', 'yes')
if ANALYTICS_ENABLED:
    cost_tracker = CostTracker(
        namespace=os.getenv('ANALYTICS_NAMESPACE', 'DadaCatTwilio'),
        region=DYNAMODB_REGION,
        local_file_fallback=True
    )
    
    engagement_tracker = EngagementTracker(
        namespace=os.getenv('ANALYTICS_NAMESPACE', 'DadaCatTwilio'),
        region=DYNAMODB_REGION,
        local_file_fallback=True
    )
    
    error_tracker = ErrorTracker(
        namespace=os.getenv('ANALYTICS_NAMESPACE', 'DadaCatTwilio'),
        region=DYNAMODB_REGION,
        local_file_fallback=True
    )
    
    logger.info("Analytics components initialized")
else:
    logger.info("Analytics disabled (set ANALYTICS_ENABLED=true to enable)")
    cost_tracker = None
    engagement_tracker = None
    error_tracker = None

@app.route('/sms', methods=['POST'])
def sms_webhook():
    """
    Handle incoming SMS messages with DynamoDB persistence.
    """
    # Start timing for response time tracking
    request_start_time = datetime.now()
    
    # Get the message content and sender's phone number
    incoming_message = request.values.get('Body', '').strip()
    from_number = request.values.get('From', '')
    
    logger.info(f"Received message from {from_number}: {incoming_message}")
    
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
    elif incoming_message.lower() == 'admin:analytics_status' and ANALYTICS_ENABLED:
        # Get analytics status (admin command)
        try:
            # Get some basic metrics
            end_time = datetime.now()
            start_time = end_time - timedelta(days=7)  # Last 7 days
            
            # Get cost metrics
            if cost_tracker:
                cost_metrics = cost_tracker.get_cost_metrics(start_time, end_time)
                total_cost = cost_tracker.get_total_cost(start_time, end_time)
            else:
                cost_metrics = {"source": "disabled"}
                total_cost = 0
                
            # Get engagement metrics
            if engagement_tracker:
                engagement_metrics = engagement_tracker.get_engagement_metrics(start_time, end_time)
            else:
                engagement_metrics = {"source": "disabled"}
                
            # Get error metrics
            if error_tracker:
                error_metrics = error_tracker.get_error_metrics(start_time, end_time)
            else:
                error_metrics = {"source": "disabled"}
            
            # Format the response
            status_lines = [
                f"DadaCat Analytics Status (last 7 days):",
                f"- Costs: ${total_cost:.2f} (source: {cost_metrics['source']})",
            ]
            
            # Add engagement metrics if available
            if engagement_metrics['source'] == 'local_file' and 'metrics' in engagement_metrics:
                metrics_data = engagement_metrics['metrics']
                if 'UserActivity' in metrics_data:
                    user_activity = metrics_data['UserActivity']
                    status_lines.append(f"- Total activities: {user_activity.get('count', 0)}")
                    status_lines.append(f"- Unique users: {user_activity.get('unique_users', 0)}")
            else:
                status_lines.append(f"- Engagement metrics source: {engagement_metrics['source']}")
            
            # Add error metrics if available
            if error_metrics['source'] == 'local_file':
                status_lines.append(f"- Total errors: {error_metrics.get('total_errors', 0)}")
            else:
                status_lines.append(f"- Error metrics source: {error_metrics['source']}")
            
            # Track admin command if analytics is enabled
            if engagement_tracker:
                engagement_tracker.track_user_activity(
                    user_id=from_number,
                    activity_type=UserActivity.ADMIN_COMMAND
                )
                
            response_text = "\n".join(status_lines)
            
        except Exception as e:
            logger.error(f"Error getting analytics status: {str(e)}", exc_info=True)
            response_text = "Error getting analytics status"
            
            # Track error if enabled
            if ANALYTICS_ENABLED and error_tracker:
                error_tracker.track_error(
                    error_type="admin_command_error",
                    error_message=f"Error getting analytics status: {str(e)}",
                    category=ErrorCategory.INTERNAL,
                    exception=e
                )
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
    
    return Response(str(twilio_response), mimetype='text/xml')

@app.route('/health', methods=['GET'])
def health_check():
    """
    Simple health check endpoint.
    """
    return {'status': 'healthy', 'persistence': 'dynamodb'}

def create_dynamodb_table():
    """
    Helper function to create the DynamoDB table if it doesn't exist.
    """
    import boto3
    from botocore.exceptions import ClientError
    
    try:
        # Check for local DynamoDB endpoint
        local_endpoint = os.getenv('AWS_ENDPOINT_URL')
        
        # Initialize DynamoDB resource
        if local_endpoint:
            logger.info(f"Creating table in local DynamoDB at {local_endpoint}")
            dynamodb = boto3.resource(
                'dynamodb', 
                region_name=DYNAMODB_REGION,
                endpoint_url=local_endpoint,
                aws_access_key_id='fakeAccessKeyId',
                aws_secret_access_key='fakeSecretAccessKey'
            )
        else:
            logger.info(f"Creating table in AWS DynamoDB in region {DYNAMODB_REGION}")
            dynamodb = boto3.resource('dynamodb', region_name=DYNAMODB_REGION)
        
        # Check if table exists
        try:
            dynamodb.Table(DYNAMODB_TABLE_NAME).table_status
            logger.info(f"DynamoDB table {DYNAMODB_TABLE_NAME} already exists")
            return True
        except ClientError:
            # Table doesn't exist, create it
            table = dynamodb.create_table(
                TableName=DYNAMODB_TABLE_NAME,
                KeySchema=[
                    {
                        'AttributeName': 'user_id',
                        'KeyType': 'HASH'  # Partition key
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'user_id',
                        'AttributeType': 'S'
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            
            # Wait for table to be created
            table.meta.client.get_waiter('table_exists').wait(TableName=DYNAMODB_TABLE_NAME)
            logger.info(f"Created DynamoDB table {DYNAMODB_TABLE_NAME}")
            return True
            
    except Exception as e:
        logger.error(f"Error creating DynamoDB table: {str(e)}")
        return False

if __name__ == '__main__':
    # Check if environment variables are set
    if not os.getenv('TWILIO_ACCOUNT_SID') or not os.getenv('TWILIO_AUTH_TOKEN'):
        logger.warning("Twilio credentials not found in environment variables.")
    
    # Create DynamoDB table in either AWS or local DynamoDB
    try:
        create_dynamodb_table()
    except Exception as e:
        logger.warning(f"Unable to create DynamoDB table: {str(e)}")
        logger.warning("Please make sure DynamoDB is set up correctly before using the application.")
        logger.warning("For local development, you can run DynamoDB Local using the script in scripts/run_dynamodb_local.sh")
    
    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5001)