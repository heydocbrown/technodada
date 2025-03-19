#!/usr/bin/env python
"""
Flight check script to verify DadaCat functionality.
This script tests the DadaCat agent to ensure it can be properly integrated.
"""
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Add parent directories to path
parent_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(parent_dir))

# Load environment variables
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

# Try to import DadaCat
try:
    from dada_agents.dadacat import generate_dada_cat_response
    print("✅ Successfully imported DadaCat module")
except ImportError as e:
    print(f"❌ Failed to import DadaCat module: {e}")
    print("Please make sure the dada_agents module is available.")
    sys.exit(1)

def test_dadacat():
    """Test DadaCat's response generation"""
    print("\n🔍 Testing DadaCat response generation...")
    
    try:
        # Start timer
        start_time = time.time()
        
        # Generate a response
        response = generate_dada_cat_response("Hello DadaCat, how are you today?")
        
        # Calculate request time
        elapsed_time = time.time() - start_time
        
        print(f"\n✅ DadaCat response generated in {elapsed_time:.2f} seconds.")
        print(f"Response preview: {response[:100]}..." if len(response) > 100 else f"Response: {response}")
        return True
        
    except Exception as e:
        print(f"\n❌ DadaCat response generation failed: {str(e)}")
        print("Please check the DadaCat implementation and API access.")
        return False

def test_integration_potential():
    """Test if DadaCat can be integrated into a Twilio bot"""
    print("\n🔍 Checking DadaCat integration potential...")
    
    # Check if DadaCat function has expected signature
    import inspect
    signature = inspect.signature(generate_dada_cat_response)
    params = signature.parameters
    
    # Check if it accepts a message parameter
    if 'message' in params:
        print("✅ DadaCat function accepts message parameter")
    else:
        print("⚠️ DadaCat function signature may need adjustment for integration")
        
    # Check if it can accept conversation history (optional)
    if 'conversation_history' in params:
        print("✅ DadaCat function supports conversation history")
    else:
        print("⚠️ DadaCat function doesn't explicitly support conversation history")
        print("   We may need to adapt our integration for stateless operation")
    
    return True

def main():
    """Main function to run all checks"""
    print("🚀 Running DadaCat flight check...\n")
    
    dadacat_response_ok = test_dadacat()
    integration_ok = test_integration_potential()
    
    print("\n📋 DadaCat flight check summary:")
    print(f"DadaCat response generation: {'✅ Passed' if dadacat_response_ok else '❌ Failed'}")
    print(f"Integration potential: {'✅ Passed' if integration_ok else '⚠️ Needs adjustment'}")
    
    if dadacat_response_ok:
        print("\n✨ DadaCat is working and ready for integration!")
        return 0
    else:
        print("\n⚠️ There are issues with DadaCat functionality. Please fix before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(main())