# DadaCat Error Handling Components

This module provides robust error handling capabilities for the DadaCat Twilio integration, ensuring reliable operation even in the presence of failures.

## Components

1. **Circuit Breaker** (`circuit_breaker.py`): Prevents cascading failures by detecting when a service is consistently failing and "breaking the circuit" to fail fast.

2. **Exponential Backoff** (`backoff.py`): Automatically retries failed operations with increasing delays to handle temporary issues.

3. **Dead Letter Queue** (`dead_letter.py`): Captures and stores failed messages for later inspection and reprocessing.

4. **Admin Notification** (`notifier.py`): Sends alerts to administrators when critical errors occur.

## Usage Examples

### Circuit Breaker

```python
from error_handling.circuit_breaker import circuit_breaker, CircuitBreaker

# Method 1: Using the decorator
@circuit_breaker(failure_threshold=3, recovery_timeout=30, name="openai-api")
def call_openai_api(prompt):
    # This function will be protected by a circuit breaker
    # After 3 failures, the circuit will open for 30 seconds
    return openai.ChatCompletion.create(model="gpt-4", messages=[{"role": "user", "content": prompt}])

# Method 2: Using the class directly
breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30, name="twilio-api")
try:
    result = breaker.execute(twilio_client.messages.create, to=number, from_=from_number, body=message)
except CircuitBreakerOpenError:
    # Handle the case where the circuit is open
    result = fallback_response()
```

### Exponential Backoff

```python
from error_handling.backoff import with_backoff, BackoffStrategy

# Method 1: Using the decorator
@with_backoff(base_delay=0.5, max_delay=30, max_retries=5, retry_exceptions=[RequestException])
def fetch_message_history(user_id):
    # This function will retry up to 5 times with exponential backoff
    return requests.get(f"https://api.example.com/messages/{user_id}")

# Method 2: Using the class directly
strategy = BackoffStrategy(base_delay=0.5, max_delay=30, max_retries=5)
try:
    result = strategy.execute(
        dynamodb.get_item, 
        TableName="Conversations", 
        Key={"user_id": {"S": user_id}},
        retry_exceptions=(ClientError,)
    )
except RetryExhaustedError as e:
    # Handle the case where all retries were exhausted
    result = {}
```

### Dead Letter Queue (with Local Fallback)

```python
from error_handling.dead_letter import DeadLetterQueue

# Production mode with AWS SQS
dlq = DeadLetterQueue(
    queue_url=os.getenv('DLQ_QUEUE_URL'),  # Will use SQS if provided
    region="us-east-1",
    reprocessor=process_message
)

# Local development mode (no AWS required)
dlq = DeadLetterQueue(
    local_file_path="./local_dlq.json",  # Will use local file if no queue_url
    reprocessor=process_message
)

# Send a failed message to the DLQ
dlq.send_to_dlq(
    message=original_message,
    error_info={
        "error_type": "api_error",
        "error_message": str(e),
        "timestamp": datetime.now().isoformat()
    }
)

# Reprocess a message from the DLQ
dlq.reprocess_message(message_id)

# View messages in the DLQ
messages = dlq.receive_from_dlq(max_messages=10)
```

### Admin Notification

```python
from error_handling.notifier import AdminNotifier, ErrorSeverity, NotificationChannel

# For local development, logging-only mode
notifier = AdminNotifier()  # With no parameters, defaults to logging only

# For production with AWS SNS
notifier = AdminNotifier(
    sns_topic_arn=os.getenv('SNS_TOPIC_ARN'),
    channel=NotificationChannel.SNS
)

# Send a notification
notifier.send_notification(
    message="Failed to process message from user",
    details={
        "user_id": "+1XXXXXXXXXX",  # Masked for privacy
        "message_id": "msg_123",
        "error": str(e)
    },
    severity=ErrorSeverity.ERROR,
    error_type="message_processing_error"
)

# Send a health check notification
notifier.send_health_check_notification(
    is_healthy=False,
    details={
        "component": "openai_api",
        "error": "Timeout"
    }
)
```

## Local Development Without AWS

All components support local development without AWS:

1. **Circuit Breaker** and **Exponential Backoff** work locally without any changes.

2. **Dead Letter Queue** can store messages in a local JSON file instead of AWS SQS.

3. **Admin Notification** can log to the console instead of sending to SNS/Email/SMS.

Use the following configuration for local development:

```python
# Initialize components for local development
circuit_breaker = CircuitBreaker(name="local-openai")
backoff_strategy = BackoffStrategy(max_retries=3)
dlq = DeadLetterQueue(local_file_path="./local_dlq.json")
notifier = AdminNotifier()  # Defaults to logging only
```

## Combining Components

These components can be combined to create a comprehensive error handling system:

```python
def process_message(message):
    # Define our circuit breaker for OpenAI API
    openai_breaker = CircuitBreaker(
        failure_threshold=5,
        recovery_timeout=60,
        name="openai-api"
    )
    
    # Define our backoff strategy
    backoff_strategy = BackoffStrategy(
        base_delay=1.0,
        max_delay=30.0,
        max_retries=3
    )
    
    # Initialize DLQ and notifier
    dlq = DeadLetterQueue(
        queue_url=os.getenv('DLQ_QUEUE_URL'),
        local_file_path="./local_dlq.json"  # Fallback if queue_url is not available
    )
    notifier = AdminNotifier(sns_topic_arn=os.getenv('SNS_TOPIC_ARN'))
    
    try:
        # First attempt with circuit breaker
        try:
            # This will fail fast if the circuit is open
            response = openai_breaker.execute(
                backoff_strategy.execute,
                generate_dadacat_response,
                message['content'],
                retry_exceptions=(RequestException, TimeoutError)
            )
            return response
            
        except CircuitBreakerOpenError:
            # Circuit is open, use fallback and notify admin
            notifier.send_notification(
                message="OpenAI API circuit is open",
                details={
                    "circuit_name": "openai-api",
                    "message_content": message['content'][:100]
                },
                severity=ErrorSeverity.WARNING,
                error_type="circuit_breaker_open"
            )
            return "Meow? (DadaCat is taking a catnap. Please try again later.)"
            
    except Exception as e:
        # Send to DLQ
        dlq.send_to_dlq(
            message=message,
            error_info={
                "error_type": "processing_error",
                "error_message": str(e)
            }
        )
        
        # Notify admin of critical error
        notifier.send_notification(
            message="Failed to process message",
            details={
                "error": str(e),
                "user_id": message.get('user_id'),
                "traceback": traceback.format_exc()
            },
            severity=ErrorSeverity.ERROR,
            error_type="message_processing_error"
        )
        
        # Return fallback response
        return "Meow? (DadaCat seems confused. Please try again later.)"
```

## Configuration

These components can be configured via environment variables:

```
# Circuit Breaker defaults
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60

# Backoff defaults
BACKOFF_BASE_DELAY=1.0
BACKOFF_MAX_DELAY=60.0
BACKOFF_MAX_RETRIES=5

# Dead Letter Queue
DLQ_QUEUE_URL=<your-sqs-queue-url>  # Optional, if not provided uses local file
DLQ_LOCAL_FILE_PATH=./local_dlq.json  # For local development

# Admin Notification
SNS_TOPIC_ARN=<your-sns-topic-arn>  # Optional, if not provided uses logging only
```