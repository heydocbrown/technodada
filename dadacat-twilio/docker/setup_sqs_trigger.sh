#!/bin/bash
# Setup SQS trigger for the DadaCat Twilio processor function

set -e  # Exit on any error

# Define variables
PROJECT_ROOT="/Users/docbrown/code/git/technodada"
REGION="us-east-2"
PROCESSOR_FUNCTION_NAME="dadacat-twilio-processor"

# Read SQS Queue URL from .env file
SQS_QUEUE_URL=$(grep SQS_QUEUE_URL "$PROJECT_ROOT/.env" | cut -d= -f2)
echo "SQS Queue URL: $SQS_QUEUE_URL"

# Extract the SQS queue ARN from the URL
SQS_QUEUE_NAME=$(basename "$SQS_QUEUE_URL")
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
SQS_QUEUE_ARN="arn:aws:sqs:$REGION:$AWS_ACCOUNT_ID:$SQS_QUEUE_NAME"
echo "SQS Queue ARN: $SQS_QUEUE_ARN"

# Check if event source mapping already exists
echo "Checking for existing event source mappings..."
EXISTING_MAPPINGS=$(aws lambda list-event-source-mappings \
  --function-name "$PROCESSOR_FUNCTION_NAME" \
  --event-source-arn "$SQS_QUEUE_ARN" \
  --region "$REGION" \
  --query "EventSourceMappings[*].UUID" \
  --output text)

if [ -n "$EXISTING_MAPPINGS" ]; then
  echo "Existing event source mapping found: $EXISTING_MAPPINGS"
  echo "Deleting existing mapping..."
  
  # Delete existing mappings
  for MAPPING_UUID in $EXISTING_MAPPINGS; do
    aws lambda delete-event-source-mapping \
      --uuid "$MAPPING_UUID" \
      --region "$REGION"
  done
fi

# Create SQS event source mapping
echo "Creating SQS event source mapping..."
aws lambda create-event-source-mapping \
  --function-name "$PROCESSOR_FUNCTION_NAME" \
  --event-source-arn "$SQS_QUEUE_ARN" \
  --batch-size 1 \
  --maximum-batching-window-in-seconds 0 \
  --region "$REGION"

echo "SQS trigger setup complete!"

# Update processor function to add SQS_QUEUE_URL
echo "Updating processor function configuration to add SQS_QUEUE_URL..."
aws lambda update-function-configuration \
  --function-name "$PROCESSOR_FUNCTION_NAME" \
  --environment "Variables={OPENAI_API_KEY=$(grep OPENAI_API_KEY $PROJECT_ROOT/.env | cut -d= -f2),TWILIO_ACCOUNT_SID=$(grep TWILIO_ACCOUNT_SID $PROJECT_ROOT/.env | cut -d= -f2),TWILIO_AUTH_TOKEN=$(grep TWILIO_AUTH_TOKEN $PROJECT_ROOT/.env | cut -d= -f2),TWILIO_PHONE_NUMBER=$(grep TWILIO_PHONE_NUMBER $PROJECT_ROOT/.env | cut -d= -f2),DYNAMODB_TABLE=$(grep DYNAMODB_TABLE_NAME $PROJECT_ROOT/.env | cut -d= -f2),SQS_QUEUE_URL=$SQS_QUEUE_URL,ANALYTICS_ENABLED=true}" \
  --region "$REGION"

echo "Processor function updated with SQS_QUEUE_URL"

# Check CloudWatch logs for the functions
echo -e "\nTo monitor function activity, check CloudWatch logs:"
echo "Webhook logs: aws logs tail /aws/lambda/$PROCESSOR_FUNCTION_NAME --follow"
echo "Processor logs: aws logs tail /aws/lambda/$PROCESSOR_FUNCTION_NAME --follow"

echo -e "\nDadaCat Twilio setup complete! Please test by sending a message to your Twilio phone number."