"""
A test script to verify the Lambda webhook flow.
This script simulates a Twilio webhook request and tests the Lambda handler and processor.
"""
import os
import json
import time
import boto3
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Import Lambda functions
# Add the path to the Lambda functions
import sys
sys.path.append(str(Path(__file__).resolve().parent / "lambda"))
try:
    from handler import lambda_handler as webhook_handler
    from processor import lambda_handler as processor_handler
    print("Successfully imported Lambda handlers")
except ImportError as e:
    print(f"Error importing Lambda handlers: {e}")
    sys.exit(1)

def simulate_twilio_webhook(phone_number, message):
    """
    Simulate a Twilio webhook request.
    
    Args:
        phone_number: The phone number to use as the sender
        message: The message content
        
    Returns:
        The response from the webhook handler
    """
    # Create a simulated Twilio webhook request
    # This mimics the format that API Gateway would send to the Lambda function
    twilio_request = {
        "body": f"From={phone_number}&Body={message}&NumMedia=0",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded"
        }
    }
    
    print(f"Simulating Twilio webhook request from {phone_number} with message: '{message}'")
    
    # Call the webhook handler
    response = webhook_handler(twilio_request, None)
    
    return response

def process_sqs_message(region_name, queue_url):
    """
    Process messages from the SQS queue.
    
    Args:
        region_name: AWS region name
        queue_url: SQS queue URL
        
    Returns:
        The response from the processor handler
    """
    # Create SQS client
    sqs = boto3.client('sqs', region_name=region_name)
    
    print(f"Retrieving messages from SQS queue: {queue_url}")
    
    # Receive messages from the queue
    response = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=5,
        AttributeNames=['All'],
        MessageAttributeNames=['All']
    )
    
    if 'Messages' not in response or not response['Messages']:
        print("No messages found in the queue")
        return None
    
    print(f"Found {len(response['Messages'])} message(s) in the queue")
    
    # Create the event structure for the processor Lambda
    processor_event = {
        "Records": [
            {
                "body": message['Body'],
                "messageAttributes": message.get('MessageAttributes', {})
            }
            for message in response['Messages']
        ]
    }
    
    # Call the processor handler
    processor_response = processor_handler(processor_event, None)
    
    # Delete the messages from the queue
    for message in response['Messages']:
        sqs.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=message['ReceiptHandle']
        )
    
    return processor_response

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Test the Lambda webhook flow")
    parser.add_argument("--phone", required=True, help="Phone number in E.164 format (e.g., +12223334444)")
    parser.add_argument("--message", required=True, help="Message content")
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-2"), help="AWS region")
    parser.add_argument("--queue", default=os.environ.get("SQS_QUEUE_URL"), help="SQS queue URL")
    
    args = parser.parse_args()
    
    # Check if SQS queue URL is available
    if not args.queue:
        print("ERROR: SQS_QUEUE_URL environment variable is not set")
        sys.exit(1)
    
    # Simulate Twilio webhook
    webhook_response = simulate_twilio_webhook(args.phone, args.message)
    print(f"Webhook response: {json.dumps(webhook_response, indent=2)}")
    
    # Allow time for the message to be available in the queue
    print("Waiting for the message to be available in the queue...")
    time.sleep(2)
    
    # Process the SQS message
    processor_response = process_sqs_message(args.region, args.queue)
    
    if processor_response:
        print(f"Processor response: {json.dumps(processor_response, indent=2)}")
        print("\nTest completed successfully. Check your phone for a response message.")
    else:
        print("Failed to process the SQS message")

if __name__ == "__main__":
    main()