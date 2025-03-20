import os
import json
import pathlib
from datetime import datetime, timedelta
from dotenv import load_dotenv
from twilio.rest import Client


def get_recent_twilio_messages(limit=10):
    """
    Retrieve the most recent Twilio messages, including both received and sent.
    
    Args:
        limit (int): Maximum number of messages to retrieve
        
    Returns:
        dict: Dictionary with received and sent messages
    """
    # Get Twilio credentials from environment variables
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    
    if not account_sid or not auth_token:
        return {
            'error': 'Twilio credentials not found in environment variables',
            'received_messages': [],
            'sent_messages': []
        }
    
    client = Client(account_sid, auth_token)
    
    try:
        # Get messages from the last 24 hours
        # Using datetime.now() instead of utcnow() which is deprecated
        date_filter = datetime.now() - timedelta(hours=24)
        
        # Get all messages and separate them by direction
        received_messages = []
        sent_messages = []
        
        # Get all recent messages
        all_messages = client.messages.list(
            date_sent_after=date_filter,
            limit=limit * 2  # Getting more messages since we'll filter them
        )
        
        # Separate messages by direction
        for msg in all_messages:
            message_data = {
                'sid': msg.sid,
                'body': msg.body,
                'from': msg.from_,
                'to': msg.to,
                'date_sent': msg.date_sent.strftime('%Y-%m-%d %H:%M:%S') if msg.date_sent else None,
                'status': msg.status,
                'direction': msg.direction,
                'error_code': msg.error_code,
                'error_message': msg.error_message
            }
            
            # Check if this is an inbound or outbound message
            if msg.direction == 'inbound':
                received_messages.append(message_data)
            elif msg.direction in ['outbound-api', 'outbound-reply', 'outbound']:
                sent_messages.append(message_data)
        
        # Limit the results to the requested number
        received_messages = received_messages[:limit]
        sent_messages = sent_messages[:limit]
        
        return {
            'received_messages': received_messages,
            'sent_messages': sent_messages
        }
        
    except Exception as e:
        return {
            'error': str(e),
            'received_messages': [],
            'sent_messages': []
        }


def get_message_pair(phone_number=None):
    """
    Get the most recent received message and its corresponding response (if any).
    
    Args:
        phone_number (str, optional): Filter messages to a specific phone number
        
    Returns:
        dict: Dictionary with the received message and the corresponding sent message
    """
    messages = get_recent_twilio_messages(limit=20)
    
    if 'error' in messages:
        return {'error': messages['error']}
    
    received = messages['received_messages']
    sent = messages['sent_messages']
    
    # Filter by phone number if provided
    if phone_number:
        received = [msg for msg in received if msg['from'] == phone_number]
        sent = [msg for msg in sent if msg['to'] == phone_number]
    
    if not received:
        return {'error': 'No recent received messages found'}
    
    # Get the most recent received message
    latest_received = sorted(received, key=lambda x: x['date_sent'] if x['date_sent'] else '', reverse=True)[0]
    
    # Find any sent message to the same number after the received message
    response_message = None
    for msg in sent:
        if (msg['to'] == latest_received['from'] and 
            msg['date_sent'] and latest_received['date_sent'] and 
            msg['date_sent'] > latest_received['date_sent']):
            if not response_message or (response_message['date_sent'] and 
                                        msg['date_sent'] > response_message['date_sent']):
                response_message = msg
    
    return {
        'received': latest_received,
        'response': response_message
    }


def send_test_message(to_number, body):
    """
    Send a test message to a specified number.
    
    Args:
        to_number (str): The phone number to send the message to
        body (str): The message content
        
    Returns:
        dict: Information about the sent message
    """
    # Get Twilio credentials from environment variables
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    from_number = os.environ.get('TWILIO_PHONE_NUMBER')
    
    if not account_sid or not auth_token or not from_number:
        return {
            'error': 'Missing Twilio credentials or phone number in environment variables'
        }
    
    client = Client(account_sid, auth_token)
    
    try:
        message = client.messages.create(
            body=body,
            from_=from_number,
            to=to_number
        )
        
        return {
            'sid': message.sid,
            'status': message.status,
            'from': message.from_,
            'to': message.to,
            'body': message.body,
            'date_sent': message.date_sent.strftime('%Y-%m-%d %H:%M:%S') if message.date_sent else None
        }
        
    except Exception as e:
        return {'error': str(e)}


def check_message_status(message_sid):
    """
    Check the status of a specific Twilio message.
    
    Args:
        message_sid (str): The SID of the message to check
        
    Returns:
        dict: Current status information for the message
    """
    # Get Twilio credentials from environment variables
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    
    if not account_sid or not auth_token:
        return {'error': 'Twilio credentials not found in environment variables'}
    
    client = Client(account_sid, auth_token)
    
    try:
        message = client.messages(message_sid).fetch()
        
        return {
            'sid': message.sid,
            'body': message.body,
            'from': message.from_,
            'to': message.to,
            'date_sent': message.date_sent.strftime('%Y-%m-%d %H:%M:%S') if message.date_sent else None,
            'status': message.status,
            'direction': message.direction,
            'error_code': message.error_code,
            'error_message': message.error_message
        }
        
    except Exception as e:
        return {'error': str(e)}


# -------------------- Test Functions --------------------

def _print_json(data):
    """Helper function to print formatted JSON."""
    print(json.dumps(data, indent=2, default=str))

def test_recent_messages(limit=5):
    """
    Test function to retrieve recent Twilio messages.
    
    Args:
        limit (int): Maximum number of messages to retrieve
        
    Returns:
        dict: Dictionary with received and sent messages
    """
    print("\n===== Testing Recent Twilio Messages =====")
    
    # Verify Twilio credentials are available
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    
    if not account_sid or not auth_token:
        print("ERROR: Twilio credentials not found in environment variables")
        return None
    
    # Get masked account SID for output
    masked_sid = account_sid[:4] + "****" + account_sid[-4:] if len(account_sid) > 8 else "****"
    print(f"Using Twilio Account SID: {masked_sid}")
    
    messages = get_recent_twilio_messages(limit=limit)
    
    if 'error' in messages:
        print(f"Error: {messages['error']}")
        return messages
    
    # Print received messages
    print(f"\n----- Recent Received Messages ({len(messages['received_messages'])}) -----")
    if messages['received_messages']:
        for i, msg in enumerate(messages['received_messages']):
            print(f"\nMessage {i+1}:")
            _print_json(msg)
    else:
        print("No received messages found.")
    
    # Print sent messages
    print(f"\n----- Recent Sent Messages ({len(messages['sent_messages'])}) -----")
    if messages['sent_messages']:
        for i, msg in enumerate(messages['sent_messages']):
            print(f"\nMessage {i+1}:")
            _print_json(msg)
    else:
        print("No sent messages found.")
    
    return messages

def test_message_pair(phone_number=None):
    """
    Test function to retrieve the most recent message pair.
    
    Args:
        phone_number (str, optional): Filter messages to a specific phone number
        
    Returns:
        dict: Dictionary with the received message and the corresponding sent message
    """
    print("\n===== Testing Message Pair Retrieval =====")
    
    # Verify Twilio credentials are available
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    
    if not account_sid or not auth_token:
        print("ERROR: Twilio credentials not found in environment variables")
        return None
    
    if phone_number:
        print(f"Filtering for phone number: {phone_number}")
    
    pair = get_message_pair(phone_number)
    
    if 'error' in pair:
        print(f"Error: {pair['error']}")
        return pair
    
    # Print received message
    print("\n----- Received Message -----")
    if pair.get('received'):
        _print_json(pair['received'])
    else:
        print("No received message found.")
    
    # Print response message
    print("\n----- Response Message -----")
    if pair.get('response'):
        _print_json(pair['response'])
    else:
        print("No response message found.")
    
    return pair

def test_message_status(message_sid=None):
    """
    Test function to check the status of a specific Twilio message.
    
    Args:
        message_sid (str, optional): The SID of the message to check
        
    Returns:
        dict: Current status information for the message
    """
    print("\n===== Testing Message Status Check =====")
    
    # Verify Twilio credentials are available
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    
    if not account_sid or not auth_token:
        print("ERROR: Twilio credentials not found in environment variables")
        return None
    
    # If no message SID provided, try to get one from a recent message
    if not message_sid:
        print("No message SID provided. Attempting to get one from recent messages...")
        messages = get_recent_twilio_messages(limit=1)
        
        if 'error' in messages:
            print(f"Error getting recent messages: {messages['error']}")
            return None
        
        if messages['received_messages']:
            message_sid = messages['received_messages'][0]['sid']
            print(f"Using message SID from recent received message: {message_sid}")
        elif messages['sent_messages']:
            message_sid = messages['sent_messages'][0]['sid']
            print(f"Using message SID from recent sent message: {message_sid}")
        else:
            print("No recent messages found to get a message SID from.")
            return None
    
    status = check_message_status(message_sid)
    
    if 'error' in status:
        print(f"Error: {status['error']}")
    else:
        print(f"Status information for message {message_sid}:")
        _print_json(status)
    
    return status

if __name__ == "__main__":
    # This will only execute when this script is run directly
    import sys
    
    # Load environment variables from .env file in project root
    env_path = pathlib.Path(__file__).parents[3] / '.env'
    if env_path.exists():
        print(f"Loading environment variables from {env_path}")
        load_dotenv(dotenv_path=env_path)
    else:
        print(f"Warning: .env file not found at {env_path}")
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        test_name = sys.argv[1]
        if test_name == "recent":
            print("Running test_recent_messages...")
            test_recent_messages(limit=5)
        elif test_name == "pair":
            print("Running test_message_pair...")
            test_message_pair()
        elif test_name == "status":
            # Check for message SID argument
            if len(sys.argv) > 2:
                message_sid = sys.argv[2]
                print(f"Running test_message_status for message {message_sid}...")
                test_message_status(message_sid)
            else:
                print("Running test_message_status for most recent message...")
                test_message_status()
        else:
            print(f"Unknown test: {test_name}")
            print("Available tests: recent, pair, status")
    else:
        # Default to testing recent messages
        print("Running test_recent_messages...")
        test_recent_messages(limit=5)
