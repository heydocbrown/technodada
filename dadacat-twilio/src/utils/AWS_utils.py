import boto3
import time
import os
import sys
import json
import pathlib
from datetime import datetime, timedelta
from dotenv import load_dotenv

def get_latest_cloudwatch_logs(lambda_name, minutes=10, limit=20):
    """
    Retrieve the latest CloudWatch logs for a specified Lambda function.
    
    Args:
        lambda_name (str): Name of the Lambda function
        minutes (int): Number of minutes to look back for logs
        limit (int): Maximum number of log events to retrieve
        
    Returns:
        list: Log events with timestamp, message, and level
    """
    client = boto3.client('logs')
    log_group_name = f"/aws/lambda/{lambda_name}"
    
    # Calculate the start time (N minutes ago)
    start_time = int((datetime.now() - timedelta(minutes=minutes)).timestamp() * 1000)
    end_time = int(datetime.now().timestamp() * 1000)
    
    try:
        # Get the latest log stream
        response = client.describe_log_streams(
            logGroupName=log_group_name,
            orderBy='LastEventTime',
            descending=True,
            limit=1
        )
        
        if not response.get('logStreams'):
            return []
            
        log_stream_name = response['logStreams'][0]['logStreamName']
        
        # Get the log events
        log_events = client.get_log_events(
            logGroupName=log_group_name,
            logStreamName=log_stream_name,
            startTime=start_time,
            endTime=end_time,
            limit=limit,
            startFromHead=False
        )
        
        # Process the log events
        formatted_logs = []
        for event in log_events.get('events', []):
            timestamp = datetime.fromtimestamp(event['timestamp'] / 1000)
            message = event['message'].strip()
            
            # Try to determine log level
            log_level = 'INFO'
            if 'ERROR' in message or 'Exception' in message:
                log_level = 'ERROR'
            elif 'WARNING' in message or 'WARN' in message:
                log_level = 'WARNING'
            elif 'DEBUG' in message:
                log_level = 'DEBUG'
                
            formatted_logs.append({
                'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'level': log_level,
                'message': message
            })
            
        return formatted_logs
        
    except Exception as e:
        print(f"Error retrieving CloudWatch logs: {str(e)}")
        return []


def check_sqs_queue_status(queue_url):
    """
    Check the status of an SQS queue including available messages.
    
    Args:
        queue_url (str): The URL of the SQS queue to check
        
    Returns:
        dict: Information about the queue status
    """
    sqs = boto3.client('sqs')
    
    try:
        # Get queue attributes
        response = sqs.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=[
                'ApproximateNumberOfMessages',
                'ApproximateNumberOfMessagesNotVisible',
                'ApproximateNumberOfMessagesDelayed',
                'CreatedTimestamp',
                'LastModifiedTimestamp',
                'VisibilityTimeout',
                'MaximumMessageSize',
                'MessageRetentionPeriod',
                'DelaySeconds',
                'RedrivePolicy'
            ]
        )
        
        attributes = response.get('Attributes', {})
        
        # Convert timestamp attributes to readable format
        for timestamp_attr in ['CreatedTimestamp', 'LastModifiedTimestamp']:
            if timestamp_attr in attributes:
                timestamp = int(attributes[timestamp_attr])
                attributes[timestamp_attr] = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        
        # Get a sample of messages (without removing them from the queue)
        message_response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=5,
            VisibilityTimeout=5,  # Make messages invisible for just 5 seconds
            WaitTimeSeconds=1,
            AttributeNames=['All'],
            MessageAttributeNames=['All']
        )
        
        # Add sample messages to the result
        sample_messages = []
        for message in message_response.get('Messages', []):
            sample_messages.append({
                'MessageId': message.get('MessageId'),
                'Body': message.get('Body')[:100] + '...' if len(message.get('Body', '')) > 100 else message.get('Body', ''),
                'Attributes': message.get('Attributes'),
                'MessageAttributes': message.get('MessageAttributes')
            })
            
            # Change visibility timeout back to 0 to make message immediately available again
            sqs.change_message_visibility(
                QueueUrl=queue_url,
                ReceiptHandle=message.get('ReceiptHandle'),
                VisibilityTimeout=0
            )
        
        return {
            'QueueAttributes': attributes,
            'SampleMessages': sample_messages
        }
        
    except Exception as e:
        print(f"Error checking SQS queue status: {str(e)}")
        return {'error': str(e)}


def invoke_lambda_test(function_name, payload):
    """
    Directly invoke a Lambda function with a test payload.
    
    Args:
        function_name (str): The name of the Lambda function to invoke
        payload (dict): The JSON payload to send to the function
        
    Returns:
        dict: The response from the Lambda function
    """
    lambda_client = boto3.client('lambda')
    
    try:
        import json
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',  # Synchronous invocation
            Payload=json.dumps(payload)
        )
        
        # Read and parse the response payload
        response_payload = response['Payload'].read().decode('utf-8')
        
        return {
            'StatusCode': response['StatusCode'],
            'ExecutedVersion': response.get('ExecutedVersion'),
            'Payload': json.loads(response_payload) if response_payload else None,
            'FunctionError': response.get('FunctionError')
        }
        
    except Exception as e:
        print(f"Error invoking Lambda function: {str(e)}")
        return {'error': str(e)}


# -------------------- Test Functions --------------------

def _print_json(data):
    """Helper function to print formatted JSON."""
    print(json.dumps(data, indent=2, default=str))

def test_cloudwatch_logs(handler_lambda=None, processor_lambda=None, minutes=60, limit=10):
    """
    Test function to retrieve CloudWatch logs for Lambda functions.
    
    Args:
        handler_lambda (str): Name of the handler Lambda function
        processor_lambda (str): Name of the processor Lambda function
        minutes (int): Number of minutes to look back for logs
        limit (int): Maximum number of log events to retrieve
        
    Returns:
        tuple: (handler_logs, processor_logs)
    """
    print("\n===== Testing CloudWatch Logs =====")
    
    # Get Lambda function names from parameters or environment
    handler_lambda = handler_lambda or os.environ.get('AWS_LAMBDA_FUNCTION')
    processor_lambda = processor_lambda or os.environ.get('AWS_PROCESSOR_LAMBDA')
    
    if not handler_lambda:
        print("ERROR: No handler Lambda function name provided")
        return None, None
        
    print(f"\n----- Handler Lambda Logs ({handler_lambda}) -----")
    handler_logs = get_latest_cloudwatch_logs(
        lambda_name=handler_lambda,
        minutes=minutes, 
        limit=limit
    )
    _print_json(handler_logs)
    
    if processor_lambda:
        print(f"\n----- Processor Lambda Logs ({processor_lambda}) -----")
        processor_logs = get_latest_cloudwatch_logs(
            lambda_name=processor_lambda,
            minutes=minutes, 
            limit=limit
        )
        _print_json(processor_logs)
    else:
        print("Skipping processor logs - no processor Lambda function name provided")
        processor_logs = None
    
    return handler_logs, processor_logs

def test_sqs_queue(queue_url=None):
    """
    Test function to check SQS queue status.
    
    Args:
        queue_url (str): URL of the SQS queue to check
        
    Returns:
        dict: Queue status information
    """
    print("\n===== Testing SQS Queue Status =====")
    
    # Get SQS queue URL from parameter or environment
    queue_url = queue_url or os.environ.get('SQS_QUEUE_URL')
    
    if not queue_url:
        print("ERROR: No SQS queue URL provided")
        return None
    
    print(f"Using SQS queue URL: {queue_url}")
    queue_status = check_sqs_queue_status(queue_url)
    _print_json(queue_status)
    
    return queue_status

if __name__ == "__main__":
    # This will only execute when this script is run directly
    
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
        
        if test_name == "logs":
            # Get Lambda function name from arguments or environment variable
            if len(sys.argv) > 2:
                lambda_name = sys.argv[2]
            else:
                # Default to the webhook handler Lambda
                lambda_name = os.environ.get('AWS_LAMBDA_FUNCTION')
                if not lambda_name:
                    print("ERROR: No Lambda function name provided or found in environment")
                    sys.exit(1)
            
            minutes = int(sys.argv[3]) if len(sys.argv) > 3 else 60
            limit = int(sys.argv[4]) if len(sys.argv) > 4 else 20
            
            print(f"Running test_cloudwatch_logs for function {lambda_name}...")
            test_cloudwatch_logs(lambda_name, None, minutes, limit)
            
        elif test_name == "sqs":
            # Get SQS queue URL from arguments or environment variable
            if len(sys.argv) > 2:
                queue_url = sys.argv[2]
            else:
                queue_url = os.environ.get('SQS_QUEUE_URL')
                if not queue_url:
                    print("ERROR: No SQS queue URL provided or found in environment")
                    sys.exit(1)
            
            print(f"Running test_sqs_queue for queue {queue_url}...")
            test_sqs_queue(queue_url)
            
        elif test_name == "both":
            # Test both Lambda functions
            webhook_lambda = os.environ.get('AWS_LAMBDA_FUNCTION')
            processor_lambda = os.environ.get('AWS_PROCESSOR_LAMBDA')
            
            if not webhook_lambda:
                print("ERROR: Webhook Lambda function name not found in environment (AWS_LAMBDA_FUNCTION)")
                sys.exit(1)
                
            if not processor_lambda:
                print("WARNING: Processor Lambda function name not found in environment (AWS_PROCESSOR_LAMBDA)")
                processor_lambda = None
            
            minutes = int(sys.argv[2]) if len(sys.argv) > 2 else 60
            limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
            
            print(f"Testing Webhook Lambda: {webhook_lambda}")
            if processor_lambda:
                print(f"Testing Processor Lambda: {processor_lambda}")
            test_cloudwatch_logs(webhook_lambda, processor_lambda, minutes, limit)
            
            queue_url = os.environ.get('SQS_QUEUE_URL')
            if queue_url:
                print("\nTesting SQS queue...")
                test_sqs_queue(queue_url)
            else:
                print("\nWARNING: SQS queue URL not found in environment (SQS_QUEUE_URL)")
            
        else:
            print(f"Unknown test: {test_name}")
            print("Available tests: logs, sqs, both")
    else:
        print("AWS Utilities Test Module")
        print("------------------------")
        print("Usage: python AWS_utils.py <test_name> [arguments]")
        print("Available tests:")
        print("  logs [lambda_name] [minutes] [limit]  - Test CloudWatch logs retrieval")
        print("  sqs [queue_url]                      - Test SQS queue status")
        print("  both [minutes] [limit]               - Test both Lambda functions and SQS queue")
