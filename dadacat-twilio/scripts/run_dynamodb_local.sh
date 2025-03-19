#!/bin/bash
# Script to run DynamoDB Local using Docker

# Create a data directory if it doesn't exist
mkdir -p ./dynamodb-data

# Run DynamoDB Local in a Docker container
echo "Starting DynamoDB Local on port 8000..."
docker run -d \
    --name dynamodb-local \
    -p 8000:8000 \
    -v "$(pwd)/dynamodb-data:/home/dynamodblocal/data" \
    amazon/dynamodb-local \
    -jar DynamoDBLocal.jar -sharedDb -dbPath /home/dynamodblocal/data/

echo "DynamoDB Local is running. Configure your application with:"
echo "AWS_ENDPOINT_URL=http://localhost:8000"
echo "AWS_REGION=us-east-1"
echo "AWS_ACCESS_KEY_ID=fakeAccessKeyId"
echo "AWS_SECRET_ACCESS_KEY=fakeSecretAccessKey"