#!/usr/bin/env python
"""
Flight check script to verify environment setup.
This script checks for required environment variables and Python packages.
"""
import os
import sys
import importlib.util
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from parent directory's .env file
parent_dir = Path(__file__).resolve().parent.parent.parent
env_path = parent_dir / ".env"

if not env_path.exists():
    print(f"Error: .env file not found at {env_path}")
    print("Please create a .env file with your API keys.")
    sys.exit(1)

print(f"Found .env file at: {env_path}")
load_dotenv(dotenv_path=env_path)

# Define required environment variables
required_env_vars = {
    "OPENAI_API_KEY": "OpenAI API key",
    # These will be needed later but are commented out now
    # "TWILIO_ACCOUNT_SID": "Twilio Account SID",
    # "TWILIO_AUTH_TOKEN": "Twilio Auth Token",
    # "TWILIO_PHONE_NUMBER": "Twilio Phone Number",
}

# Define required Python packages with their import names
# Format: (pip_package_name, import_module_name)
required_packages = [
    ("openai", "openai"),
    ("flask", "flask"),
    ("python-dotenv", "dotenv"),
    ("requests", "requests"),
    # These will be needed later but are commented out now
    # ("twilio", "twilio"),
    # ("boto3", "boto3"),
]

def check_env_variables():
    """Check for required environment variables"""
    print("\n🔍 Checking environment variables...")
    missing_vars = []
    
    for var, description in required_env_vars.items():
        value = os.getenv(var)
        if not value:
            missing_vars.append(f"- {var} ({description})")
            print(f"❌ {var}: Not found")
        else:
            masked_value = value[:4] + "*" * (len(value) - 8) + value[-4:] if len(value) > 8 else "****"
            print(f"✅ {var}: {masked_value}")
    
    if missing_vars:
        print("\n⚠️  Missing environment variables:")
        for var in missing_vars:
            print(var)
        print("\nPlease add these to your .env file.")
    
    return len(missing_vars) == 0

def check_python_packages():
    """Check for required Python packages"""
    print("\n🔍 Checking Python packages...")
    missing_packages = []
    
    for pip_name, import_name in required_packages:
        try:
            # First attempt: try to import the module directly
            module = importlib.import_module(import_name)
            
            # Try to get the version
            try:
                # Some packages use __version__, others use VERSION
                version = getattr(module, '__version__', getattr(module, 'VERSION', 'Unknown version'))
                print(f"✅ {pip_name}: {version}")
            except AttributeError:
                # Attempt with pkg_resources
                try:
                    import pkg_resources
                    version = pkg_resources.get_distribution(pip_name).version
                    print(f"✅ {pip_name}: {version}")
                except (pkg_resources.DistributionNotFound, ImportError):
                    print(f"✅ {pip_name}: Installed (version unknown)")
        except ImportError:
            # If import fails, check with importlib as fallback
            spec = importlib.util.find_spec(import_name)
            if spec is None:
                missing_packages.append(pip_name)
                print(f"❌ {pip_name}: Not installed")
            else:
                print(f"✅ {pip_name}: Installed (version unknown)")
    
    if missing_packages:
        print("\n⚠️  Missing Python packages:")
        for package in missing_packages:
            print(f"- {package}")
        print("\nPlease install these packages with:")
        print(f"pip install {' '.join(missing_packages)}")
    
    return len(missing_packages) == 0

def check_python_version():
    """Check Python version"""
    print("\n🔍 Checking Python version...")
    python_version = sys.version.split()[0]
    print(f"Python version: {python_version}")
    
    # Check if Python version is 3.10 or higher
    major, minor = map(int, python_version.split('.')[:2])
    if major >= 3 and minor >= 10:
        print("✅ Python version is 3.10 or higher")
        return True
    else:
        print("❌ Python version is lower than 3.10")
        print("Please use Python 3.10 or higher for this project.")
        return False

def main():
    """Main function to run all checks"""
    print("🚀 Running environment flight check...\n")
    
    python_version_ok = check_python_version()
    env_vars_ok = check_env_variables()
    packages_ok = check_python_packages()
    
    print("\n📋 Flight check summary:")
    print(f"Python version check: {'✅ Passed' if python_version_ok else '❌ Failed'}")
    print(f"Environment variables: {'✅ Passed' if env_vars_ok else '❌ Failed'}")
    print(f"Python packages: {'✅ Passed' if packages_ok else '❌ Failed'}")
    
    if python_version_ok and env_vars_ok and packages_ok:
        print("\n✨ All checks passed! You're ready to proceed with development.")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please fix the issues above before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(main())