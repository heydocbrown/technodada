#!/usr/bin/env python
"""
Run all flight check scripts sequentially.
This script executes all verification checks to ensure your environment is ready.
"""
import os
import sys
import subprocess
from pathlib import Path

def run_check(script_name, description):
    """Run a check script and return its success status"""
    script_path = Path(__file__).parent / script_name
    
    print(f"\n{'=' * 60}")
    print(f"Running {description}...")
    print(f"{'=' * 60}\n")
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            check=False,
            capture_output=False
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Error running {script_name}: {str(e)}")
        return False

def main():
    """Run all flight checks"""
    print("🚀 Running all DadaCat Twilio flight checks\n")
    
    # Define checks to run
    checks = [
        ("check_env.py", "Environment Check"),
        ("check_openai.py", "OpenAI API Check"),
        ("check_dadacat.py", "DadaCat Check")
    ]
    
    # Track results
    results = {}
    
    # Run each check
    for script, description in checks:
        success = run_check(script, description)
        results[description] = success
    
    # Display summary
    print("\n" + "=" * 60)
    print("FLIGHT CHECK SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for description, success in results.items():
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{description}: {status}")
        all_passed = all_passed and success
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✨ All checks passed! Your environment is ready for DadaCat Twilio development.")
        return 0
    else:
        print("⚠️  Some checks failed. Please resolve the issues before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(main())