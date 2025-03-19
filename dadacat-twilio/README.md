# DadaCat Twilio Integration

This project integrates the DadaCat AI agent with Twilio to create an SMS-based interface for interacting with DadaCat.

## Overview

The DadaCat Twilio Integration enables users to interact with the DadaCat AI agent via SMS messages. It leverages AWS services for a scalable, reliable deployment with robust error handling, analytics, and monitoring.

## Features

- Twilio SMS integration
- DadaCat AI agent responses
- Conversation persistence
- Error recovery mechanisms
- Cost and engagement analytics
- Donation prompts for active users
- Extensible design for future channels (WhatsApp, voice)

## Architecture

The application is built with a modular architecture:

- **Adapters**: Channel-specific interfaces for message handling
- **Agent**: DadaCat AI integration
- **Conversation**: State and persistence management
- **Error Handling**: Circuit breakers, retries, and notifications
- **Analytics**: Tracking for engagement, errors, and costs
- **AWS Infrastructure**: Lambda, DynamoDB, SNS, SQS, CloudWatch

## Prerequisites

- Python 3.10+
- AWS account with CLI access
- Twilio account with SMS capabilities
- OpenAI API access

## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables:
   ```bash
   cd infrastructure/scripts
   chmod +x setup_env.sh
   ./setup_env.sh dev  # Replace with desired environment
   ```

## Deployment

To deploy to AWS:

```bash
cd infrastructure/scripts
chmod +x deploy.sh
./deploy.sh dev  # Replace with desired environment
```

## Local Development

There are several Flask applications for different stages of development:

### Simple Flask App (No Persistence)
Run the simplest version with in-memory storage:

```bash
python src/app_simple.py
```

### DynamoDB Persistence App
To run with DynamoDB persistence:

1. Start DynamoDB Local (requires Docker):
   ```bash
   chmod +x scripts/run_dynamodb_local.sh
   ./scripts/run_dynamodb_local.sh
   ```

2. Set local DynamoDB environment variables:
   ```bash
   export AWS_ENDPOINT_URL=http://localhost:8000
   export AWS_REGION=us-east-1
   export AWS_ACCESS_KEY_ID=fakeAccessKeyId
   export AWS_SECRET_ACCESS_KEY=fakeSecretAccessKey
   ```

3. Run the persistent app:
   ```bash
   python src/app_persistent.py
   ```

### Full Application
Run the complete application with all components:

```bash
export FLASK_APP=src/app.py
export FLASK_ENV=development
flask run
```

## Testing

Run the test suite:

```bash
pytest
```

With coverage report:

```bash
pytest --cov=src tests/
```

## Monitoring & Analytics

The CloudWatch dashboard provides metrics for:
- User engagement
- Error rates by type
- API costs

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

[MIT License](LICENSE)