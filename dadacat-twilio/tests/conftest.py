"""
Test configuration fixtures.
"""
import os
import pytest
from typing import Dict, Any, Generator

import boto3
from moto import mock_dynamodb, mock_sns, mock_sqs

from src.config import AppConfig, TwilioConfig, OpenAIConfig, AWSConfig
from src.adapters.twilio_adapter import TwilioAdapter
from src.agent.dadacat_client import DadaCatClient
from src.conversation.manager import ConversationManager
from src.conversation.storage import DynamoDBStorage
from src.utils.rate_limiter import RateLimiter


@pytest.fixture
def test_config() -> AppConfig:
    """
    Fixture providing a test configuration.
    
    Returns:
        AppConfig instance for testing
    """
    return AppConfig(
        twilio=TwilioConfig(
            account_sid="test_account_sid",
            auth_token="test_auth_token",
            phone_number="+15555555555"
        ),
        openai=OpenAIConfig(
            api_key="test_api_key",
            model="gpt-3.5-turbo"  # Use cheaper model for tests
        ),
        aws=AWSConfig(
            region="us-east-1",
            dynamodb_table="test-dadacat-conversations",
            sns_topic_arn="arn:aws:sns:us-east-1:123456789012:test-dadacat-notifications",
            sqs_queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-dadacat-dlq"
        ),
        log_level=20,  # INFO
        donation_threshold=5,
        debug=True
    )


@pytest.fixture
def mock_dynamodb_table(test_config: AppConfig) -> Generator:
    """
    Fixture providing a mocked DynamoDB table.
    
    Args:
        test_config: Test configuration
        
    Yields:
        None
    """
    with mock_dynamodb():
        # Create the mock table
        dynamodb = boto3.resource('dynamodb', region_name=test_config.aws.region)
        table = dynamodb.create_table(
            TableName=test_config.aws.dynamodb_table,
            KeySchema=[
                {'AttributeName': 'user_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'user_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        yield table
        # No need to delete as moto will clean up


@pytest.fixture
def mock_sns_topic(test_config: AppConfig) -> Generator:
    """
    Fixture providing a mocked SNS topic.
    
    Args:
        test_config: Test configuration
        
    Yields:
        SNS client
    """
    with mock_sns():
        sns = boto3.client('sns', region_name=test_config.aws.region)
        sns.create_topic(Name="test-dadacat-notifications")
        yield sns


@pytest.fixture
def mock_sqs_queue(test_config: AppConfig) -> Generator:
    """
    Fixture providing a mocked SQS queue.
    
    Args:
        test_config: Test configuration
        
    Yields:
        SQS client
    """
    with mock_sqs():
        sqs = boto3.client('sqs', region_name=test_config.aws.region)
        sqs.create_queue(QueueName="test-dadacat-dlq")
        yield sqs


@pytest.fixture
def twilio_adapter(test_config: AppConfig) -> TwilioAdapter:
    """
    Fixture providing a TwilioAdapter instance.
    
    Args:
        test_config: Test configuration
        
    Returns:
        TwilioAdapter instance
    """
    return TwilioAdapter(
        account_sid=test_config.twilio.account_sid,
        auth_token=test_config.twilio.auth_token,
        twilio_number=test_config.twilio.phone_number
    )


@pytest.fixture
def dadacat_client(test_config: AppConfig) -> DadaCatClient:
    """
    Fixture providing a DadaCatClient instance.
    
    Args:
        test_config: Test configuration
        
    Returns:
        DadaCatClient instance
    """
    return DadaCatClient(
        openai_api_key=test_config.openai.api_key,
        model=test_config.openai.model
    )


@pytest.fixture
def dynamodb_storage(test_config: AppConfig, mock_dynamodb_table) -> DynamoDBStorage:
    """
    Fixture providing a DynamoDBStorage instance.
    
    Args:
        test_config: Test configuration
        mock_dynamodb_table: Mocked DynamoDB table
        
    Returns:
        DynamoDBStorage instance
    """
    return DynamoDBStorage(
        table_name=test_config.aws.dynamodb_table,
        region=test_config.aws.region
    )


@pytest.fixture
def conversation_manager(dynamodb_storage: DynamoDBStorage) -> ConversationManager:
    """
    Fixture providing a ConversationManager instance.
    
    Args:
        dynamodb_storage: DynamoDB storage instance
        
    Returns:
        ConversationManager instance
    """
    return ConversationManager(storage=dynamodb_storage)


@pytest.fixture
def rate_limiter(test_config: AppConfig) -> RateLimiter:
    """
    Fixture providing a RateLimiter instance.
    
    Args:
        test_config: Test configuration
        
    Returns:
        RateLimiter instance
    """
    return RateLimiter(
        threshold=test_config.donation_threshold,
        donation_message=test_config.donation_message
    )


@pytest.fixture
def sample_twilio_request() -> Dict[str, Any]:
    """
    Fixture providing a sample Twilio webhook request.
    
    Returns:
        Dictionary with sample request data
    """
    return {
        'MessageSid': 'SM123456789',
        'From': '+12223334444',
        'To': '+15555555555',
        'Body': 'Hello DadaCat!',
        'NumMedia': '0'
    }