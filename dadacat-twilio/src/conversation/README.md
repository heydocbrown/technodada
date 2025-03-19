# DadaCat Conversation Persistence

This module implements conversation persistence for the DadaCat Twilio integration, allowing users to have stateful conversations with DadaCat via SMS.

## Components

1. **Models** (`models.py`): Data models for conversations and messages
   - `Message`: Represents a single message in a conversation
   - `Conversation`: Represents a full conversation between a user and DadaCat

2. **Storage** (`storage.py`): DynamoDB storage interface
   - Handles saving and retrieving conversations from DynamoDB
   - Supports both AWS DynamoDB and DynamoDB Local for development

3. **Manager** (`manager.py`): Conversation state manager
   - Provides a high-level interface for working with conversations
   - Handles adding messages, retrieving conversation history, and resetting conversations

## DynamoDB Schema

Conversations are stored in DynamoDB with the following schema:

- **Table Name**: `DadaCatConversations` (configurable)
- **Primary Key**: `user_id` (the user's phone number)
- **Attributes**:
  - `user_id`: String - Unique identifier for the user (phone number)
  - `created_at`: String - ISO format timestamp for when the conversation was created
  - `updated_at`: String - ISO format timestamp for when the conversation was last updated
  - `messages`: String - JSON serialized array of message objects
  - `is_active`: Boolean - Whether the conversation is active
  - `metadata`: String (optional) - JSON serialized metadata

## Local Development with DynamoDB Local

For local development, you can use DynamoDB Local to avoid needing AWS credentials:

1. Run DynamoDB Local using Docker:
   ```
   ./scripts/run_dynamodb_local.sh
   ```

2. Set the following environment variables:
   ```
   AWS_ENDPOINT_URL=http://localhost:8000
   AWS_REGION=us-east-1
   AWS_ACCESS_KEY_ID=fakeAccessKeyId
   AWS_SECRET_ACCESS_KEY=fakeSecretAccessKey
   ```

3. Run the application with `app_persistent.py`, which will automatically create the necessary table.

## Production Deployment

For production deployment to AWS:

1. Make sure your AWS credentials are properly configured
2. The application will automatically create the DynamoDB table if it doesn't exist
3. Ensure your IAM policies allow creating and accessing DynamoDB tables

## Usage Example

```python
from conversation.models import Message
from conversation.storage import DynamoDBStorage
from conversation.manager import ConversationManager

# Initialize storage and manager
storage = DynamoDBStorage(table_name='DadaCatConversations')
manager = ConversationManager(storage=storage)

# Add a user message
manager.add_user_message(user_id='+1234567890', content='Hello DadaCat!')

# Add an assistant response
manager.add_assistant_message(user_id='+1234567890', content='meow, human!')

# Get the conversation history
conversation = manager.get_or_create_conversation(user_id='+1234567890')
formatted_history = conversation.get_formatted_history()

# Reset the conversation
manager.reset_conversation(user_id='+1234567890')
```