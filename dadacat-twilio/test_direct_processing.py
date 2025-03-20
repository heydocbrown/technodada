#!/usr/bin/env python3
"""
Direct test script for DadaCat Twilio processing chain.
Bypasses SQS and directly tests processing time.
"""
import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
import boto3
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

# Try to import required modules
try:
    from dada_agents.dadacat import generate_dada_cat_response
    DADACAT_IMPORT_SUCCESS = True
except ImportError:
    print("WARNING: Failed to import DadaCat. Make sure dada_agents is in your PYTHONPATH")
    DADACAT_IMPORT_SUCCESS = False

def print_section(title):
    """Print a section title with formatting."""
    print(f"\n{'=' * 80}")
    print(f" {title}")
    print(f"{'=' * 80}")

def test_openai_api_directly():
    """Test direct OpenAI API call timing."""
    print_section("TESTING OPENAI API DIRECTLY")
    
    if not DADACAT_IMPORT_SUCCESS:
        print("ERROR: DadaCat module could not be imported")
        return
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not found in environment")
        return
    
    test_message = "Hello DadaCat, how are you today?"
    
    print(f"Testing with message: '{test_message}'")
    print(f"API Key found (length: {len(api_key)})")
    
    # Measure time for API call
    start_time = time.time()
    print(f"Starting API call at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
    
    try:
        response = generate_dada_cat_response(test_message, api_key=api_key)
        end_time = time.time()
        
        print(f"API call completed at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
        print(f"Response time: {(end_time - start_time):.2f} seconds")
        
        # Print truncated response
        print(f"Response (truncated): {response[:100]}...")
        
    except Exception as e:
        print(f"ERROR during API call: {str(e)}")

def test_lambda_direct_invoke():
    """Test Lambda functions by direct invocation."""
    print_section("TESTING LAMBDA FUNCTIONS DIRECTLY")
    
    lambda_client = boto3.client('lambda')
    
    # Try both SAM-deployed and manually deployed function names
    processor_lambda_names = [
        os.environ.get('AWS_PROCESSOR_LAMBDA'),
        'dadacat-twilio-processor',
        'dadacat-twilio-dev-DadaCatProcessingFunction-rS3588H6LuZJ'
    ]
    
    # Filter out None values
    processor_lambda_names = [name for name in processor_lambda_names if name]
    
    if not processor_lambda_names:
        print("ERROR: No processor Lambda function names available")
        return
    
    # Test message
    test_message = {
        'user_id': '+15168080548',
        'message': 'Hello DadaCat, test direct invocation',
        'timestamp': datetime.now().isoformat()
    }
    
    for lambda_name in processor_lambda_names:
        print(f"\nTesting processor Lambda: {lambda_name}")
        
        try:
            # Measure time for Lambda invocation
            start_time = time.time()
            print(f"Starting Lambda invocation at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
            
            response = lambda_client.invoke(
                FunctionName=lambda_name,
                InvocationType='RequestResponse',  # Synchronous invocation
                Payload=json.dumps({'Records': [{'body': json.dumps(test_message)}]})
            )
            
            end_time = time.time()
            print(f"Lambda invocation completed at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
            print(f"Invocation time: {(end_time - start_time):.2f} seconds")
            
            # Get and print the response
            payload = response['Payload'].read().decode('utf-8')
            print(f"Response status code: {response['StatusCode']}")
            print(f"Response payload: {payload}")
            
            if 'FunctionError' in response:
                print(f"Function error: {response['FunctionError']}")
            
        except Exception as e:
            print(f"ERROR testing Lambda function {lambda_name}: {str(e)}")

def main():
    """Main function to run the tests."""
    env_path = project_root / '.env'
    if env_path.exists():
        print(f"Loading environment variables from {env_path}")
        load_dotenv(dotenv_path=env_path)
    
    print_section("DADACAT TWILIO PROCESSING TIME TEST")
    
    # Test OpenAI API directly
    test_openai_api_directly()
    
    # Test Lambda functions directly
    test_lambda_direct_invoke()
    
    print_section("RESULTS SUMMARY")
    print("Check the timing results above to identify the source of delays")
    print("If the OpenAI API call takes seconds but the Lambda invocation takes minutes,")
    print("the delay is likely in the Lambda processing pipeline.")
    print("If both tests show similar timing, the delay is elsewhere in the system.")

if __name__ == "__main__":
    main()