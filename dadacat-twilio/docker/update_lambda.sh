#!/bin/bash
# Update Lambda Docker container with fixes

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

echo "==== Updating DadaCat Twilio Lambda Container ===="
echo "Project root: $PROJECT_ROOT"
echo "AWS Account ID: $AWS_ACCOUNT_ID"
echo "AWS Region: $REGION"

cd "$PROJECT_ROOT"

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

# Create a temporary directory for building
BUILD_DIR="/tmp/dadacat-twilio-update"
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

# Update Lambda functions
WEBHOOK_FUNCTION_NAME="dadacat-twilio-webhook"
PROCESSOR_FUNCTION_NAME="dadacat-twilio-processor"

echo "Updating webhook Lambda function..."
aws lambda update-function-code \
  --function-name "$WEBHOOK_FUNCTION_NAME" \
  --image-uri "$ECR_URI" \
  --region "$REGION"

echo "Updating processor Lambda function..."
aws lambda update-function-code \
  --function-name "$PROCESSOR_FUNCTION_NAME" \
  --image-uri "$ECR_URI" \
  --region "$REGION"

# Wait for functions to become active
echo "Waiting for Lambda functions to become active..."
aws lambda wait function-active \
  --function-name "$WEBHOOK_FUNCTION_NAME" \
  --region "$REGION"
  
aws lambda wait function-active \
  --function-name "$PROCESSOR_FUNCTION_NAME" \
  --region "$REGION"

# Clean up temporary files
echo "Cleaning up temporary files..."
rm -rf "$BUILD_DIR"

echo "DadaCat Twilio Lambda functions updated successfully!"

# Update SQS visibility timeout
echo "Updating SQS queue visibility timeout..."
aws sqs set-queue-attributes \
  --queue-url https://us-east-2.queue.amazonaws.com/446385818049/dadacat-processing-queue-dev \
  --attributes VisibilityTimeout=60,ReceiveMessageWaitTimeSeconds=20 \
  --region us-east-2

echo "SQS queue updated with optimized settings."

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
echo -e "\nNote: To perform a full end-to-end test, send a message to your Twilio phone number."
echo "This update should reduce the delay from 4 minutes to seconds."