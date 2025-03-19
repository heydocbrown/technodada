#!/usr/bin/env python
"""
Flight check script to verify OpenAI API connectivity.
This script tests your OpenAI API key and connectivity.
"""
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

try:
    import openai
    from openai import OpenAI
except ImportError:
    print("Error: OpenAI Python package not found.")
    print("Please install it with: pip install openai")
    sys.exit(1)

# Load environment variables from parent directory's .env file
parent_dir = Path(__file__).resolve().parent.parent.parent
env_path = parent_dir / ".env"

if not env_path.exists():
    print(f"Error: .env file not found at {env_path}")
    print("Please create a .env file with your API keys.")
    sys.exit(1)

load_dotenv(dotenv_path=env_path)

# Check for OpenAI API key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("Error: OPENAI_API_KEY not found in .env file")
    print("Please add your OpenAI API key to the .env file.")
    sys.exit(1)

print("OpenAI API key found.")
print("Testing connection to OpenAI API...")

try:
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    
    # Start timer
    start_time = time.time()
    
    # Test API with a simple request
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'OpenAI API is working!' in one short sentence."}
        ],
        max_tokens=20
    )
    
    # Calculate request time
    elapsed_time = time.time() - start_time
    
    print("\n✅ Connection successful!")
    print(f"Response received in {elapsed_time:.2f} seconds.")
    print(f"Response: {response.choices[0].message.content}")
    print("\nYour OpenAI API key is valid and working correctly.")
    
except Exception as e:
    print("\n❌ Connection failed!")
    print(f"Error: {str(e)}")
    print("\nPlease check your API key and internet connection.")
    sys.exit(1)