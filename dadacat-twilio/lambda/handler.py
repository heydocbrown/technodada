"""
AWS Lambda function handler for DadaCat Twilio integration.
This handler receives webhook requests from Twilio and queues them for processing.
"""
import json
import logging
import os
import sys
import boto3
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from twilio.twiml.messaging_response import MessagingResponse

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Add the project root directory to the path
# This ensures we can import our local modules
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root.parent))
logger.info(f"Set path to include project root: {project_root}")
logger.info(f"Current directory contents: {os.listdir(current_dir)}")

# Configure asynchronous processing
MESSAGE_PROCESSING_ASYNC = os.environ.get('MESSAGE_PROCESSING_ASYNC', '').lower() in ('true', '1', 'yes')
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL')
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE', 'dadacat-conversations-dev')
DYNAMODB_REGION = os.environ.get('AWS_REGION', 'us-east-2')

# Initialize components
try:
    logger.info("Attempting to import from src...")
    
    # Only import what we need for the webhook handler
    from src.conversation.storage import DynamoDBStorage
    from src.conversation.manager import ConversationManager
    
    # Initialize SQS client for asynchronous processing
    sqs_client = boto3.client('sqs', region_name=DYNAMODB_REGION)
    
    # Initialize DynamoDB storage and conversation manager
    storage = DynamoDBStorage(
        table_name=DYNAMODB_TABLE_NAME, 
        region=DYNAMODB_REGION
    )
    conversation_manager = ConversationManager(storage=storage)
    
    logger.info(f"Async processing mode: {MESSAGE_PROCESSING_ASYNC}")
    logger.info(f"SQS Queue URL: {SQS_QUEUE_URL}")
    
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
            'body': json.dumps({'error': f"Error: {str(e)}"})
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
    
    # Process the request based on processing mode
    if MESSAGE_PROCESSING_ASYNC and SQS_QUEUE_URL:
        # For async processing, queue the message and return immediate response
        return process_message_async(request_data)
    else:
        # For synchronous processing, process the message and return the response
        logger.warning("Async processing disabled or SQS queue URL not configured. Using synchronous processing.")
        response = "Meow? (DadaCat is running in synchronous mode, which is not recommended.)"
        
        twilio_response = MessagingResponse()
        twilio_response.message(response)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/xml'
            },
            'body': str(twilio_response)
        }


def process_message_async(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Queue the message for asynchronous processing and return an immediate response.
    """
    logger.info(f"Processing message asynchronously: {request_data}")
    
    try:
        # Get the message content and sender's phone number
        incoming_message = request_data.get('body', '').strip()
        from_number = request_data.get('from', '')
        
        # Add user message to conversation first
        conversation_manager.add_user_message(
            user_id=from_number,
            content=incoming_message
        )
        
        # Check for admin commands that should be processed immediately
        if incoming_message.lower() in ['reset', 'restart', 'clear']:
            # Reset conversation history
            conversation_manager.reset_conversation(from_number)
            
            # Create TwiML response
            twilio_response = MessagingResponse()
            twilio_response.message("Conversation has been reset. What would you like to talk about?")
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/xml'
                },
                'body': str(twilio_response)
            }
        
        # Queue the message for asynchronous processing
        message_data = {
            'user_id': from_number,
            'message': incoming_message,
            'timestamp': datetime.now().isoformat()
        }
        
        # Send message to SQS
        sqs_client.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(message_data),
            MessageAttributes={
                'MessageType': {
                    'DataType': 'String',
                    'StringValue': 'UserMessage'
                }
            }
        )
        
        logger.info(f"Message from {from_number} queued for processing")
        
        # Create immediate response
        twilio_response = MessagingResponse()
        twilio_response.message("I'm thinking about that... I'll respond in a moment\! 🤔")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/xml'
            },
            'body': str(twilio_response)
        }
    
    except Exception as e:
        logger.error(f"Error queuing message: {str(e)}", exc_info=True)
        
        # Return error response
        twilio_response = MessagingResponse()
        twilio_response.message("Meow? (DadaCat seems to be napping. Please try again later.)")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/xml'
            },
            'body': str(twilio_response)
        }
