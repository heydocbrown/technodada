#!/usr/bin/env python3
"""
Debug script to diagnose delays in the DadaCat Twilio messaging system.
This script checks Lambda logs, SQS queue settings, and performs timing analysis.
"""
import sys
import os
import json
from datetime import datetime, timedelta
import time
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

# Import AWS utilities
from src.utils.AWS_utils import (
    get_latest_cloudwatch_logs,
    check_sqs_queue_status,
    invoke_lambda_test
)

def print_heading(text):
    """Print a formatted heading."""
    print("\n" + "="*80)
    print(f"  {text}")
    print("="*80)

def print_json(data):
    """Print formatted JSON data."""
    print(json.dumps(data, indent=2, default=str))

def analyze_delays(webhook_logs, processor_logs):
    """
    Analyze logs to find message processing delays.
    
    Args:
        webhook_logs: Logs from the webhook Lambda
        processor_logs: Logs from the processor Lambda
        
    Returns:
        dict: Analysis results with delay information
    """
    print_heading("ANALYZING PROCESSING DELAYS")
    
    webhook_timestamps = {}
    processor_timestamps = {}
    
    # Extract webhook message receipt timestamps
    for log in webhook_logs:
        if "Received message:" in log["message"]:
            # Extract message content and timestamp
            timestamp = datetime.strptime(log["timestamp"], "%Y-%m-%d %H:%M:%S")
            try:
                # Extract message from log entry
                message_part = log["message"].split("Received message: ")[1].split(" from ")[0]
                from_part = log["message"].split(" from ")[1]
                webhook_timestamps[from_part] = {
                    'message': message_part,
                    'received_time': timestamp
                }
                print(f"Webhook received message at {timestamp}: {message_part[:30]}... from {from_part}")
            except (IndexError, KeyError):
                continue
    
    # Extract processor message processing timestamps
    for log in processor_logs:
        if "Processing queued message from " in log["message"]:
            # Extract sender and timestamp
            timestamp = datetime.strptime(log["timestamp"], "%Y-%m-%d %H:%M:%S")
            try:
                # Extract user_id and message from log entry
                parts = log["message"].split("Processing queued message from ")
                if len(parts) < 2:
                    continue
                    
                user_parts = parts[1].split(": ")
                if len(user_parts) < 2:
                    continue
                    
                user_id = user_parts[0]
                message = user_parts[1]
                
                processor_timestamps[user_id] = {
                    'message': message,
                    'processed_time': timestamp
                }
                print(f"Processor handled message at {timestamp}: {message[:30]}... from {user_id}")
            except (IndexError, KeyError):
                continue
        
        # Also look for sending response logs
        elif "Sent message to " in log["message"]:
            timestamp = datetime.strptime(log["timestamp"], "%Y-%m-%d %H:%M:%S")
            try:
                # Extract user_id from log entry
                parts = log["message"].split("Sent message to ")
                if len(parts) < 2:
                    continue
                    
                user_parts = parts[1].split(" with SID ")
                if len(user_parts) < 2:
                    continue
                    
                user_id = user_parts[0]
                sid = user_parts[1]
                
                if user_id in processor_timestamps:
                    processor_timestamps[user_id]['response_time'] = timestamp
                    processor_timestamps[user_id]['message_sid'] = sid
                    print(f"Response sent at {timestamp} to {user_id} with SID {sid}")
            except (IndexError, KeyError):
                continue
    
    # Match webhook and processor timestamps for the same messages
    delays = []
    for user_id, processor_data in processor_timestamps.items():
        if user_id in webhook_timestamps:
            webhook_data = webhook_timestamps[user_id]
            
            # If we have both reception and processing times
            if 'received_time' in webhook_data and 'processed_time' in processor_data:
                queue_delay = (processor_data['processed_time'] - webhook_data['received_time']).total_seconds()
                
                delay_info = {
                    'user_id': user_id,
                    'message': webhook_data['message'],
                    'webhook_time': webhook_data['received_time'],
                    'processor_time': processor_data['processed_time'],
                    'queue_delay_seconds': queue_delay
                }
                
                # If we also have response sent time
                if 'response_time' in processor_data:
                    processing_delay = (processor_data['response_time'] - processor_data['processed_time']).total_seconds()
                    total_delay = (processor_data['response_time'] - webhook_data['received_time']).total_seconds()
                    
                    delay_info.update({
                        'response_time': processor_data['response_time'],
                        'processing_delay_seconds': processing_delay,
                        'total_delay_seconds': total_delay
                    })
                
                delays.append(delay_info)
    
    # Sort by webhook time (most recent first)
    delays.sort(key=lambda x: x['webhook_time'], reverse=True)
    
    # Calculate statistics if we have delays
    stats = {}
    if delays:
        queue_delays = [d['queue_delay_seconds'] for d in delays]
        stats['queue_delay'] = {
            'min': min(queue_delays),
            'max': max(queue_delays),
            'avg': sum(queue_delays) / len(queue_delays)
        }
        
        total_delays = [d.get('total_delay_seconds') for d in delays if 'total_delay_seconds' in d]
        if total_delays:
            stats['total_delay'] = {
                'min': min(total_delays),
                'max': max(total_delays),
                'avg': sum(total_delays) / len(total_delays)
            }
    
    return {
        'delays': delays,
        'stats': stats
    }

def diagnose_queue_settings(queue_status):
    """
    Diagnose SQS queue settings to identify potential delay causes.
    
    Args:
        queue_status: Queue status information from check_sqs_queue_status
        
    Returns:
        dict: Diagnosis results with recommendations
    """
    print_heading("DIAGNOSING QUEUE SETTINGS")
    
    issues = []
    recommendations = []
    
    # Check queue attributes
    attrs = queue_status.get('QueueAttributes', {})
    
    # Check visibility timeout (default is often 30 seconds)
    visibility_timeout = int(attrs.get('VisibilityTimeout', 0))
    print(f"Current VisibilityTimeout: {visibility_timeout} seconds")
    if visibility_timeout > 60:
        issues.append(f"High visibility timeout ({visibility_timeout} seconds)")
        recommendations.append("Reduce visibility timeout to 60 seconds or less")
    
    # Check message retention period
    retention_period = int(attrs.get('MessageRetentionPeriod', 0))
    print(f"Current MessageRetentionPeriod: {retention_period} seconds")
    
    # Check delay seconds
    delay_seconds = int(attrs.get('DelaySeconds', 0))
    print(f"Current DelaySeconds: {delay_seconds} seconds")
    if delay_seconds > 0:
        issues.append(f"Queue has a message delay of {delay_seconds} seconds")
        recommendations.append("Set DelaySeconds to 0 for immediate processing")
    
    # Check receive message wait time (long polling setting)
    wait_time = int(attrs.get('ReceiveMessageWaitTimeSeconds', 0))
    print(f"Current ReceiveMessageWaitTimeSeconds: {wait_time} seconds")
    if wait_time == 0:
        issues.append("Short polling is enabled (ReceiveMessageWaitTimeSeconds = 0)")
        recommendations.append("Enable long polling by setting ReceiveMessageWaitTimeSeconds to 20")
    
    # Check for DLQ configuration
    redrive_policy = attrs.get('RedrivePolicy')
    if redrive_policy:
        try:
            policy = json.loads(redrive_policy)
            max_receive = policy.get('maxReceiveCount', 0)
            print(f"Dead Letter Queue configured with maxReceiveCount: {max_receive}")
        except:
            print("Dead Letter Queue is configured but couldn't parse policy")
    else:
        print("No Dead Letter Queue configured")
    
    return {
        'issues': issues,
        'recommendations': recommendations
    }

def diagnose_lambda_settings(webhook_name, processor_name):
    """
    Check Lambda function settings that could cause delays.
    
    Args:
        webhook_name: Name of the webhook Lambda function
        processor_name: Name of the processor Lambda function
        
    Returns:
        dict: Diagnosis results with recommendations
    """
    print_heading("DIAGNOSING LAMBDA SETTINGS")
    
    import boto3
    
    lambda_client = boto3.client('lambda')
    issues = []
    recommendations = []
    
    try:
        # Get SQS event source mapping details
        print("Checking SQS event source mapping...")
        event_source_mappings = lambda_client.list_event_source_mappings(
            FunctionName=processor_name
        )
        
        for mapping in event_source_mappings.get('EventSourceMappings', []):
            if 'sqs' in mapping.get('EventSourceArn', '').lower():
                # Found SQS mapping
                batch_size = mapping.get('BatchSize', 0)
                batch_window = mapping.get('MaximumBatchingWindowInSeconds', 0)
                
                print(f"SQS BatchSize: {batch_size}")
                print(f"SQS MaximumBatchingWindowInSeconds: {batch_window}")
                
                if batch_window > 0:
                    issues.append(f"Batching window is set to {batch_window} seconds")
                    recommendations.append("Set MaximumBatchingWindowInSeconds to 0 for immediate processing")
                
                if batch_size > 1:
                    print("NOTE: BatchSize > 1 means Lambda waits to collect multiple messages before processing")
    except Exception as e:
        print(f"Error checking Lambda settings: {str(e)}")
    
    # Get Lambda configurations
    try:
        webhook_config = lambda_client.get_function_configuration(FunctionName=webhook_name)
        processor_config = lambda_client.get_function_configuration(FunctionName=processor_name)
        
        # Check for cold start issues - memory size affects cold start time
        webhook_memory = webhook_config.get('MemorySize', 0)
        processor_memory = processor_config.get('MemorySize', 0)
        
        print(f"Webhook Lambda memory: {webhook_memory} MB")
        print(f"Processor Lambda memory: {processor_memory} MB")
        
        if processor_memory < 1024:
            issues.append(f"Processor Lambda has limited memory ({processor_memory} MB)")
            recommendations.append("Increase processor Lambda memory to 1024 MB or higher")
        
        # Check timeout settings
        webhook_timeout = webhook_config.get('Timeout', 0)
        processor_timeout = processor_config.get('Timeout', 0)
        
        print(f"Webhook Lambda timeout: {webhook_timeout} seconds")
        print(f"Processor Lambda timeout: {processor_timeout} seconds")
        
        if processor_timeout < 60:
            issues.append(f"Processor Lambda has short timeout ({processor_timeout} seconds)")
            recommendations.append("Increase processor Lambda timeout to at least 60 seconds")
        
    except Exception as e:
        print(f"Error checking Lambda configurations: {str(e)}")
    
    return {
        'issues': issues,
        'recommendations': recommendations
    }

def main():
    """Main function to run the diagnostics."""
    # Load environment variables
    env_path = project_root / '.env'
    if env_path.exists():
        print(f"Loading environment variables from {env_path}")
        load_dotenv(dotenv_path=env_path)
    
    # Get Lambda function names from environment
    webhook_lambda = os.environ.get('AWS_LAMBDA_FUNCTION')
    processor_lambda = os.environ.get('AWS_PROCESSOR_LAMBDA')
    
    if not webhook_lambda or not processor_lambda:
        print("ERROR: Lambda function names not found in environment")
        print("Please make sure AWS_LAMBDA_FUNCTION and AWS_PROCESSOR_LAMBDA are set in .env file")
        return
    
    # Get SQS queue URL from environment
    queue_url = os.environ.get('SQS_QUEUE_URL')
    if not queue_url:
        print("ERROR: SQS queue URL not found in environment")
        print("Please make sure SQS_QUEUE_URL is set in .env file")
        return
    
    print_heading(f"DADACAT TWILIO DELAY DIAGNOSTICS")
    print(f"Webhook Lambda: {webhook_lambda}")
    print(f"Processor Lambda: {processor_lambda}")
    print(f"SQS Queue: {queue_url}")
    
    # Get Lambda logs (look back 120 minutes with higher limit for better analysis)
    print("\nFetching Lambda logs (past 120 minutes)...")
    webhook_logs = get_latest_cloudwatch_logs(webhook_lambda, minutes=120, limit=50)
    processor_logs = get_latest_cloudwatch_logs(processor_lambda, minutes=120, limit=50)
    
    # Check SQS queue status
    print("\nChecking SQS queue status...")
    queue_status = check_sqs_queue_status(queue_url)
    
    # Analyze delays
    delay_analysis = analyze_delays(webhook_logs, processor_logs)
    
    # Diagnose settings
    queue_diagnosis = diagnose_queue_settings(queue_status)
    lambda_diagnosis = diagnose_lambda_settings(webhook_lambda, processor_lambda)
    
    # Print findings
    print_heading("FINDINGS AND RECOMMENDATIONS")
    
    # Print delay statistics
    print("\n== Message Processing Delays ==")
    if delay_analysis['delays']:
        print(f"Found {len(delay_analysis['delays'])} matched webhook/processor message pairs")
        
        if 'queue_delay' in delay_analysis['stats']:
            queue_stats = delay_analysis['stats']['queue_delay']
            print(f"Queue delay (webhook to processor):")
            print(f"  Min: {queue_stats['min']:.2f} seconds")
            print(f"  Max: {queue_stats['max']:.2f} seconds")
            print(f"  Avg: {queue_stats['avg']:.2f} seconds")
        
        if 'total_delay' in delay_analysis['stats']:
            total_stats = delay_analysis['stats']['total_delay']
            print(f"Total delay (webhook to response):")
            print(f"  Min: {total_stats['min']:.2f} seconds")
            print(f"  Max: {total_stats['max']:.2f} seconds")
            print(f"  Avg: {total_stats['avg']:.2f} seconds")
        
        # Print details of most recent messages
        print("\nMost recent message delays:")
        for delay in delay_analysis['delays'][:3]:
            print(f"- Message: {delay['message'][:30]}...")
            print(f"  Webhook received: {delay['webhook_time']}")
            print(f"  Processor handled: {delay['processor_time']}")
            print(f"  Queue delay: {delay['queue_delay_seconds']:.2f} seconds")
            if 'response_time' in delay:
                print(f"  Response sent: {delay['response_time']}")
                print(f"  Total delay: {delay['total_delay_seconds']:.2f} seconds")
            print()
    else:
        print("No matching webhook/processor message pairs found in logs")
    
    # Print identified issues
    print("\n== Identified Issues ==")
    all_issues = queue_diagnosis['issues'] + lambda_diagnosis['issues']
    if all_issues:
        for i, issue in enumerate(all_issues, 1):
            print(f"{i}. {issue}")
    else:
        print("No significant issues identified")
    
    # Print recommendations
    print("\n== Recommendations ==")
    all_recommendations = queue_diagnosis['recommendations'] + lambda_diagnosis['recommendations']
    if all_recommendations:
        for i, rec in enumerate(all_recommendations, 1):
            print(f"{i}. {rec}")
    else:
        print("No specific recommendations")
    
    # Additional suggestions
    print("\n== Additional Suggestions ==")
    print("1. Check for any cold start issues by monitoring Lambda initialization times")
    print("2. Verify there are no permission issues with accessing OpenAI API")
    print("3. Monitor OpenAI API response times to identify potential external delays")
    print("4. Consider implementing a warm-up mechanism to avoid cold starts")
    print("5. Implement better logging with timestamps at critical points")

if __name__ == "__main__":
    main()