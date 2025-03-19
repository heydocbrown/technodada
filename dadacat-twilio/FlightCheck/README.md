# DadaCat Twilio FlightCheck

This directory contains scripts to verify your environment setup and dependencies before starting development on the DadaCat Twilio integration.

## Available Flight Checks

1. **Environment Check** (`check_env.py`): Verifies Python version, required packages, and environment variables.

2. **OpenAI API Check** (`check_openai.py`): Tests connectivity to the OpenAI API using your API key.

3. **DadaCat Check** (`check_dadacat.py`): Verifies that the DadaCat agent is functioning properly.

## How to Run

Make sure you're in the conda environment and your `.env` file is set up in the parent `technodada` directory before running these checks.

```bash
# Run the environment check
python FlightCheck/check_env.py

# Test OpenAI API connectivity
python FlightCheck/check_openai.py

# Verify DadaCat functionality
python FlightCheck/check_dadacat.py
```

## What These Checks Validate

- Python version (3.10+ required)
- Required Python packages
- Environment variables in `.env` file
- OpenAI API connectivity
- DadaCat module accessibility and functionality

## Notes

- These checks assume your `.env` file is located in the parent `technodada` directory.
- Additional checks for Twilio and AWS will be added in future phases.
- All scripts will provide clear output about what's working and what needs to be fixed.