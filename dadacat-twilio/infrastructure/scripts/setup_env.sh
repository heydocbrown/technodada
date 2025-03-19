#!/bin/bash
# Script to set up environment files for deployment

set -e

# Get environment from args or default to dev
ENVIRONMENT=${1:-dev}
ENV_FILE=".env.$ENVIRONMENT"

echo "Setting up environment file for $ENVIRONMENT"

# Check if file already exists
if [ -f "$ENV_FILE" ]; then
    read -p "File $ENV_FILE already exists. Overwrite? (y/n): " OVERWRITE
    if [[ $OVERWRITE != "y" && $OVERWRITE != "Y" ]]; then
        echo "Aborted."
        exit 0
    fi
fi

# Prompt for required values
read -p "Enter OpenAI API key: " OPENAI_API_KEY
read -p "Enter Twilio Account SID: " TWILIO_ACCOUNT_SID
read -p "Enter Twilio Auth Token: " TWILIO_AUTH_TOKEN
read -p "Enter Twilio Phone Number: " TWILIO_PHONE_NUMBER
read -p "Enter AWS Region (default: us-east-2): " AWS_REGION
AWS_REGION=${AWS_REGION:-us-east-2}

# Create the environment file
cat > $ENV_FILE << EOF
# DadaCat Twilio $ENVIRONMENT environment variables
# Created: $(date)

# AWS
AWS_REGION=$AWS_REGION

# OpenAI
OPENAI_API_KEY=$OPENAI_API_KEY

# Twilio
TWILIO_ACCOUNT_SID=$TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN=$TWILIO_AUTH_TOKEN
TWILIO_PHONE_NUMBER=$TWILIO_PHONE_NUMBER

# Application
LOG_LEVEL=INFO
DONATION_THRESHOLD=5
DONATION_MESSAGE="You've sent {count} messages today to DadaCat! Please consider supporting this service with a donation at example.com/donate"
EOF

echo "Environment file $ENV_FILE created successfully!"
echo "Use ./deploy.sh $ENVIRONMENT to deploy with these settings."