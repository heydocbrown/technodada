#!/bin/bash
# Script to update Lambda functions with dockerized deployment

# Define variables
PROJECT_ROOT="/Users/docbrown/code/git/technodada"
LAMBDA_DIR="$PROJECT_ROOT/dadacat-twilio/lambda"
DOCKER_DIR="$PROJECT_ROOT/dadacat-twilio/docker"
WEBHOOK_FUNCTION="dadacat-twilio-dev-DadaCatTwilioFunction-2HDkiCVhrTcu"
PROCESSOR_FUNCTION="dadacat-twilio-dev-DadaCatProcessingFunction-rS3588H6LuZJ"
REGION="us-east-2"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create Docker directory if it doesn't exist
mkdir -p "$DOCKER_DIR"

# Create Dockerfile for Lambda container
echo "Creating Dockerfile..."
cat > "$DOCKER_DIR/Dockerfile" << 'EOF'
FROM public.ecr.aws/lambda/python:3.12

# Set up environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy requirements first for better caching
COPY requirements.txt ${LAMBDA_TASK_ROOT}/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy Lambda functions
COPY lambda/handler.py ${LAMBDA_TASK_ROOT}/
COPY lambda/processor.py ${LAMBDA_TASK_ROOT}/

# Copy src directory (application code)
COPY src ${LAMBDA_TASK_ROOT}/src/

# Copy dada_agents (the whole module we want to use)
COPY dada_agents ${LAMBDA_TASK_ROOT}/dada_agents/

# Copy .env file for local development and testing
# Note: In production, environment variables should be set in Lambda configuration
COPY .env ${LAMBDA_TASK_ROOT}/.env

# Command can be overridden by providing a different command in the template directly
CMD ["processor.lambda_handler"]
EOF

# Create requirements.txt for Docker
echo "Creating requirements.txt for Docker..."
cat > "$DOCKER_DIR/requirements.txt" << 'EOF'
boto3>=1.34.0
twilio>=9.0.0
openai>=1.12.0
python-dotenv>=1.0.0
requests>=2.31.0
EOF

# Build separate Docker images for webhook and processor
echo "Building Docker images..."

# Build webhook image
echo "Building webhook image..."
WEBHOOK_IMAGE="dadacat-twilio-webhook:latest"

docker build -t "$WEBHOOK_IMAGE" \
  --file "$DOCKER_DIR/Dockerfile" \
  --build-arg FUNCTION_NAME=handler.lambda_handler \
  "$PROJECT_ROOT"

# Build processor image
echo "Building processor image..."
PROCESSOR_IMAGE="dadacat-twilio-processor:latest"

docker build -t "$PROCESSOR_IMAGE" \
  --file "$DOCKER_DIR/Dockerfile" \
  --build-arg FUNCTION_NAME=processor.lambda_handler \
  "$PROJECT_ROOT"

# Create ECR repositories if they don't exist
echo "Setting up ECR repositories..."

# Webhook repository
ECR_WEBHOOK_REPO="dadacat-twilio-webhook"
aws ecr describe-repositories --repository-names "$ECR_WEBHOOK_REPO" --region "$REGION" || \
  aws ecr create-repository --repository-name "$ECR_WEBHOOK_REPO" --region "$REGION"

# Processor repository
ECR_PROCESSOR_REPO="dadacat-twilio-processor"
aws ecr describe-repositories --repository-names "$ECR_PROCESSOR_REPO" --region "$REGION" || \
  aws ecr create-repository --repository-name "$ECR_PROCESSOR_REPO" --region "$REGION"

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

# Tag and push webhook image
echo "Pushing webhook image..."
docker tag "$WEBHOOK_IMAGE" "$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_WEBHOOK_REPO:latest"
docker push "$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_WEBHOOK_REPO:latest"

# Tag and push processor image
echo "Pushing processor image..."
docker tag "$PROCESSOR_IMAGE" "$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_PROCESSOR_REPO:latest"
docker push "$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_PROCESSOR_REPO:latest"

# Update webhook Lambda function
echo "Updating webhook function $WEBHOOK_FUNCTION..."
aws lambda update-function-code \
  --function-name "$WEBHOOK_FUNCTION" \
  --image-uri "$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_WEBHOOK_REPO:latest" \
  --region "$REGION"

# Update processor Lambda function
echo "Updating processor function $PROCESSOR_FUNCTION..."
aws lambda update-function-code \
  --function-name "$PROCESSOR_FUNCTION" \
  --image-uri "$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_PROCESSOR_REPO:latest" \
  --region "$REGION"

echo "Done! Lambda functions have been updated with Docker container images."