"""
Simple Flask application for DadaCat Twilio integration.
This is a basic implementation to get started with testing.
"""
import os
import logging
from pathlib import Path
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
from agent.history_adapter import ConversationHistoryAdapter

# Load environment variables from .env file in the project root
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Initialize DadaCat client and history adapter
dadacat_client = DadaCatClient()
history_adapter = ConversationHistoryAdapter()

# Simple in-memory conversation storage for testing
# Format: {phone_number: [list of messages]}
conversations = {}

@app.route('/sms', methods=['POST'])
def sms_webhook():
    """
    Handle incoming SMS messages.
    """
    # Get the message content and sender's phone number
    incoming_message = request.values.get('Body', '').strip()
    from_number = request.values.get('From', '')
    
    logger.info(f"Received message from {from_number}: {incoming_message}")
    
    # Check for reset command
    if incoming_message.lower() in ['reset', 'restart', 'clear']:
        if from_number in conversations:
            conversations[from_number] = []
        response_text = "Conversation has been reset. What would you like to talk about?"
    else:
        # Get existing conversation history or create new
        if from_number not in conversations:
            conversations[from_number] = []
            
        # Add user message to history
        conversations[from_number] = history_adapter.add_to_history(
            conversations[from_number], 
            "user", 
            incoming_message
        )
        
        try:
            # Generate response using our DadaCat client
            response_text = dadacat_client.generate_response(
                user_message=incoming_message,
                conversation_history=conversations[from_number],
                user_id=from_number
            )
            
            # Add assistant response to history
            conversations[from_number] = history_adapter.add_to_history(
                conversations[from_number], 
                "assistant", 
                response_text
            )
            
            # Show conversation length for debugging
            conversation_length = len(conversations.get(from_number, []))
            logger.info(f"Conversation with {from_number} now has {conversation_length} messages")
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}", exc_info=True)
            response_text = "Meow? (DadaCat seems to be napping. Please try again later.)"
    
    # Create TwiML response
    twilio_response = MessagingResponse()
    twilio_response.message(response_text)
    
    return Response(str(twilio_response), mimetype='text/xml')

@app.route('/health', methods=['GET'])
def health_check():
    """
    Simple health check endpoint.
    """
    return {'status': 'healthy'}

if __name__ == '__main__':
    # Check if environment variables are set
    if not os.getenv('TWILIO_ACCOUNT_SID') or not os.getenv('TWILIO_AUTH_TOKEN'):
        logger.warning("Twilio credentials not found in environment variables.")
    
    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5001)