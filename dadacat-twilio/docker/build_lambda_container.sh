#!/bin/bash
# Build and deploy DadaCat Twilio Docker container for AWS Lambda

set -e  # Exit on any error

# Define variables
PROJECT_ROOT="/Users/docbrown/code/git/technodada"
TWILIO_DIR="$PROJECT_ROOT/dadacat-twilio"
DOCKER_DIR="$TWILIO_DIR/docker"
REGION="us-east-2"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="dadacat-twilio"
IMAGE_TAG="latest"
ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG"

echo "==== Building DadaCat Twilio Lambda Container ===="
echo "Project root: $PROJECT_ROOT"
echo "AWS Account ID: $AWS_ACCOUNT_ID"
echo "AWS Region: $REGION"

cd "$PROJECT_ROOT"

# Create ECR repository if it doesn't exist
echo "Verifying ECR repository exists..."
aws ecr describe-repositories --repository-names "$ECR_REPO" --region "$REGION" > /dev/null 2>&1 || \
  aws ecr create-repository --repository-name "$ECR_REPO" --region "$REGION"

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

# Create a temporary directory for building
BUILD_DIR="/tmp/dadacat-twilio-build"
mkdir -p "$BUILD_DIR"

# Create a modified Dockerfile that copies the DadaCat agent code
cat > "$BUILD_DIR/Dockerfile" << EOF
FROM public.ecr.aws/lambda/python:3.12

# Set up environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy requirements
COPY requirements.txt \${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r \${LAMBDA_TASK_ROOT}/requirements.txt

# Copy Lambda functions
COPY lambda/handler.py \${LAMBDA_TASK_ROOT}/
COPY lambda/processor.py \${LAMBDA_TASK_ROOT}/

# Copy source code
COPY src \${LAMBDA_TASK_ROOT}/src/
COPY dada_agents \${LAMBDA_TASK_ROOT}/dada_agents/

# Set environment variables
ENV MESSAGE_PROCESSING_ASYNC=true
ENV ANALYTICS_ENABLED=true

# Command can be overridden by providing a different command in the template directly
CMD ["handler.lambda_handler"]
EOF

# Copy requirements file
cp "$TWILIO_DIR/lambda/requirements.txt" "$BUILD_DIR/requirements.txt"

# Copy lambda functions
mkdir -p "$BUILD_DIR/lambda"
cp "$TWILIO_DIR/lambda/handler.py" "$BUILD_DIR/lambda/"
cp "$TWILIO_DIR/lambda/processor.py" "$BUILD_DIR/lambda/"

# Copy source code
mkdir -p "$BUILD_DIR/src"
cp -r "$TWILIO_DIR/src/"* "$BUILD_DIR/src/"

# Copy DadaCat agent code
mkdir -p "$BUILD_DIR/dada_agents"
cp -r "$PROJECT_ROOT/dada_agents/"* "$BUILD_DIR/dada_agents/"

# Build docker image with buildx for x86_64 architecture
echo "Building Docker image for x86_64 architecture..."
cd "$BUILD_DIR"
docker buildx build \
  --platform linux/amd64 \
  -t "$ECR_REPO:$IMAGE_TAG" \
  -f "Dockerfile" \
  --load \
  .

# Tag and push to ECR
echo "Tagging and pushing to ECR..."
docker tag "$ECR_REPO:$IMAGE_TAG" "$ECR_URI"
docker push "$ECR_URI"

echo "DadaCat Twilio image built and pushed to ECR: $ECR_URI"

# Create/Update Lambda functions for both webhook and processor
echo "Creating/Updating Lambda functions for DadaCat Twilio..."

# Function definitions
WEBHOOK_FUNCTION_NAME="dadacat-twilio-webhook"
PROCESSOR_FUNCTION_NAME="dadacat-twilio-processor"
LAMBDA_ROLE_ARN="arn:aws:iam::$AWS_ACCOUNT_ID:role/dadacat-twilio-dev-DadaCatProcessingFunctionRole-Lj0ssMVecIaK"

# Create or update webhook function
if aws lambda get-function --function-name "$WEBHOOK_FUNCTION_NAME" --region "$REGION" > /dev/null 2>&1; then
  echo "Updating existing webhook Lambda function..."
  aws lambda update-function-code \
    --function-name "$WEBHOOK_FUNCTION_NAME" \
    --image-uri "$ECR_URI" \
    --region "$REGION"
else
  echo "Creating new webhook Lambda function..."
  aws lambda create-function \
    --function-name "$WEBHOOK_FUNCTION_NAME" \
    --package-type Image \
    --code "ImageUri=$ECR_URI" \
    --role "$LAMBDA_ROLE_ARN" \
    --timeout 30 \
    --memory-size 512 \
    --architectures "x86_64" \
    --region "$REGION"
fi

# Create or update processor function with different handler
if aws lambda get-function --function-name "$PROCESSOR_FUNCTION_NAME" --region "$REGION" > /dev/null 2>&1; then
  echo "Updating existing processor Lambda function..."
  aws lambda update-function-code \
    --function-name "$PROCESSOR_FUNCTION_NAME" \
    --image-uri "$ECR_URI" \
    --region "$REGION"
  
  # Update to use processor.lambda_handler
  aws lambda update-function-configuration \
    --function-name "$PROCESSOR_FUNCTION_NAME" \
    --image-config '{"Command": ["processor.lambda_handler"]}' \
    --region "$REGION"
else
  echo "Creating new processor Lambda function..."
  aws lambda create-function \
    --function-name "$PROCESSOR_FUNCTION_NAME" \
    --package-type Image \
    --code "ImageUri=$ECR_URI" \
    --role "$LAMBDA_ROLE_ARN" \
    --timeout 60 \
    --memory-size 1024 \
    --architectures "x86_64" \
    --image-config '{"Command": ["processor.lambda_handler"]}' \
    --region "$REGION"
fi

# Wait for functions to become active
echo "Waiting for Lambda functions to become active..."
aws lambda wait function-active \
  --function-name "$WEBHOOK_FUNCTION_NAME" \
  --region "$REGION"
  
aws lambda wait function-active \
  --function-name "$PROCESSOR_FUNCTION_NAME" \
  --region "$REGION"

# Read environment variables from .env file
echo "Reading environment variables from .env file..."
OPENAI_API_KEY=$(grep OPENAI_API_KEY "$PROJECT_ROOT/.env" | cut -d= -f2)
TWILIO_ACCOUNT_SID=$(grep TWILIO_ACCOUNT_SID "$PROJECT_ROOT/.env" | cut -d= -f2)
TWILIO_AUTH_TOKEN=$(grep TWILIO_AUTH_TOKEN "$PROJECT_ROOT/.env" | cut -d= -f2)
TWILIO_PHONE_NUMBER=$(grep TWILIO_PHONE_NUMBER "$PROJECT_ROOT/.env" | cut -d= -f2)
SQS_QUEUE_URL=$(grep SQS_QUEUE_URL "$PROJECT_ROOT/.env" | cut -d= -f2)
DYNAMODB_TABLE_NAME=$(grep DYNAMODB_TABLE_NAME "$PROJECT_ROOT/.env" | cut -d= -f2)

# Update webhook function configuration
echo "Updating webhook Lambda function configuration..."
aws lambda update-function-configuration \
  --function-name "$WEBHOOK_FUNCTION_NAME" \
  --environment "Variables={OPENAI_API_KEY=$OPENAI_API_KEY,TWILIO_ACCOUNT_SID=$TWILIO_ACCOUNT_SID,TWILIO_AUTH_TOKEN=$TWILIO_AUTH_TOKEN,TWILIO_PHONE_NUMBER=$TWILIO_PHONE_NUMBER,SQS_QUEUE_URL=$SQS_QUEUE_URL,DYNAMODB_TABLE=$DYNAMODB_TABLE_NAME,MESSAGE_PROCESSING_ASYNC=true}" \
  --region "$REGION"

# Update processor function configuration
echo "Updating processor Lambda function configuration..."
aws lambda update-function-configuration \
  --function-name "$PROCESSOR_FUNCTION_NAME" \
  --environment "Variables={OPENAI_API_KEY=$OPENAI_API_KEY,TWILIO_ACCOUNT_SID=$TWILIO_ACCOUNT_SID,TWILIO_AUTH_TOKEN=$TWILIO_AUTH_TOKEN,TWILIO_PHONE_NUMBER=$TWILIO_PHONE_NUMBER,DYNAMODB_TABLE=$DYNAMODB_TABLE_NAME,ANALYTICS_ENABLED=true}" \
  --region "$REGION"

# Clean up temporary files
echo "Cleaning up temporary files..."
rm -rf "$BUILD_DIR"

echo "DadaCat Twilio Lambda functions created/updated successfully!"

# Test the webhook function
echo "Testing the webhook function..."
aws lambda invoke \
  --function-name "$WEBHOOK_FUNCTION_NAME" \
  --payload '{"body": "Body=Hello+DadaCat&From=%2B12345678901"}' \
  --region "$REGION" \
  --cli-binary-format raw-in-base64-out \
  /tmp/webhook-response.json

echo "Webhook response saved to /tmp/webhook-response.json"
cat /tmp/webhook-response.json

# Note on testing the processor
echo -e "\nNote: The processor function is triggered by SQS messages and will process messages asynchronously."
echo "To test the complete flow, send a message to the Twilio phone number configured in your account."