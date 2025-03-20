# DadaCat Twilio Docker Deployment

This directory contains the Docker configuration for deploying the DadaCat Twilio service to AWS Lambda.

## Overview

The Docker container includes:

- The AWS Lambda handler and processor functions
- The DadaCat agent from the `dada_agents` module
- The Twilio adapter and conversation management components
- All necessary dependencies

## Local Testing

To build and test the Docker container locally:

```bash
# Build the Docker image
docker build -t dadacat-twilio -f Dockerfile ../..

# Run the container locally for testing
docker run -p 9000:8080 \
  -e OPENAI_API_KEY="your_key_here" \
  -e TWILIO_ACCOUNT_SID="your_sid_here" \
  -e TWILIO_AUTH_TOKEN="your_token_here" \
  -e TWILIO_PHONE_NUMBER="your_phone_here" \
  -e DYNAMODB_TABLE="dadacat-conversations-dev" \
  -e AWS_REGION="us-east-2" \
  dadacat-twilio:latest

# Test the function
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{"body": "Body=Test message&From=%2B15555555555"}'
```

## Deployment

To deploy the Docker container to AWS Lambda:

```bash
# Make the script executable
chmod +x build_and_deploy.sh

# Run the deployment script
./build_and_deploy.sh
```

This will:
1. Build the Docker image
2. Push it to Amazon ECR
3. Update the Lambda functions
4. Test the deployment

## Environment Variables

The following environment variables are used:

- `OPENAI_API_KEY`: Your OpenAI API key
- `TWILIO_ACCOUNT_SID`: Your Twilio account SID
- `TWILIO_AUTH_TOKEN`: Your Twilio auth token
- `TWILIO_PHONE_NUMBER`: Your Twilio phone number
- `DYNAMODB_TABLE`: The DynamoDB table for conversation storage
- `MESSAGE_PROCESSING_ASYNC`: Set to 'true' to use asynchronous processing
- `ANALYTICS_ENABLED`: Set to 'true' to enable analytics
- `ANALYTICS_NAMESPACE`: The namespace for analytics
- `AWS_REGION`: The AWS region
- `RATE_LIMITER_ENABLED`: Set to 'true' to enable rate limiting
- `RATE_LIMITER_THRESHOLD`: The rate limiter threshold
- `RATE_LIMITER_TIME_WINDOW`: The rate limiter time window

## Docker Structure

- `Dockerfile`: The Docker container configuration
- `requirements.txt`: Python dependencies
- `build_and_deploy.sh`: Script to build and deploy the container

## Troubleshooting

If you encounter issues with the deployment:

1. Check that you have Docker installed and running
2. Verify that AWS CLI is configured with appropriate credentials
3. Ensure environment variables are correctly set
4. Check Lambda CloudWatch logs for detailed error messages