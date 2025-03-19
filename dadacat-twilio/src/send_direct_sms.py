"""
Script to send a test SMS message directly from Twilio phone number (bypassing Messaging Service).
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from twilio.rest import Client
import argparse

# Add the parent directory to the path
parent_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(parent_dir))

# Load environment variables from .env file in the parent directory
env_path = parent_dir / ".env"
load_dotenv(dotenv_path=env_path)

def send_direct_sms(to_number, message_body):
    """
    Send an SMS message directly from Twilio phone number (not via Messaging Service).
    
    Args:
        to_number: Recipient's phone number (in E.164 format)
        message_body: Text message content
        
    Returns:
        Twilio message SID if successful
    """
    # Get Twilio credentials from environment variables
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_number = os.getenv('TWILIO_PHONE_NUMBER')
    
    if not account_sid or not auth_token or not from_number:
        raise ValueError("Twilio credentials not found in environment variables.")
    
    # Initialize Twilio client
    client = Client(account_sid, auth_token)
    
    # Send message directly from phone number
    print(f"Sending via phone number: {from_number}")
    message = client.messages.create(
        to=to_number,
        from_=from_number,
        body=message_body
    )
    
    print(f"Message sent! SID: {message.sid}")
    return message.sid

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Send a direct SMS using Twilio (bypassing Messaging Service).")
    parser.add_argument("to_number", help="Recipient's phone number (in E.164 format, e.g., +12223334444)")
    parser.add_argument("message", help="Message content")
    
    args = parser.parse_args()
    
    try:
        send_direct_sms(args.to_number, args.message)
    except Exception as e:
        print(f"Error sending SMS: {str(e)}")
        sys.exit(1)