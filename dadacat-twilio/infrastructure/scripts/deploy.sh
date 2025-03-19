#!/bin/bash
# Script to deploy the DadaCat Twilio integration

set -e

# Get environment from args or default to dev
ENVIRONMENT=${1:-dev}
STACK_NAME="dadacat-twilio-$ENVIRONMENT"
REGION=${AWS_REGION:-us-east-2}
TEMPLATE_PATH="../template.yaml"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI is not installed"
    exit 1
fi

# Check if SAM CLI is installed
if ! command -v sam &> /dev/null; then
    echo "Error: AWS SAM CLI is not installed"
    exit 1
fi

# Check if environment file exists
ENV_FILE=".env.$ENVIRONMENT"
if [ ! -f "$ENV_FILE" ]; then
    echo "Error: Environment file $ENV_FILE not found"
    exit 1
fi

# Load environment variables
source "$ENV_FILE"

# Validate template
echo "Validating CloudFormation template..."
aws cloudformation validate-template \
    --template-body file://$TEMPLATE_PATH \
    --region $REGION

# Build with SAM
echo "Building with SAM..."
sam build -t $TEMPLATE_PATH

# Deploy with SAM
echo "Deploying stack $STACK_NAME to $ENVIRONMENT environment in $REGION region..."
sam deploy \
    --stack-name $STACK_NAME \
    --parameter-overrides \
        Environment=$ENVIRONMENT \
        OpenAIApiKey=$OPENAI_API_KEY \
        TwilioAccountSid=$TWILIO_ACCOUNT_SID \
        TwilioAuthToken=$TWILIO_AUTH_TOKEN \
        TwilioPhoneNumber=$TWILIO_PHONE_NUMBER \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    --region $REGION \
    --no-fail-on-empty-changeset

# Get outputs
echo "Deployment complete. Fetching stack outputs..."
aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query "Stacks[0].Outputs" \
    --region $REGION \
    --output table

echo "Deployment completed successfully!"