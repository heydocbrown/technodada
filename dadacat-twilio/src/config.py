"""
Configuration management.
"""
import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class TwilioConfig:
    """
    Twilio configuration.
    """
    account_sid: str
    auth_token: str
    phone_number: str


@dataclass
class OpenAIConfig:
    """
    OpenAI configuration.
    """
    api_key: str
    model: str = "gpt-4o"


@dataclass
class AWSConfig:
    """
    AWS configuration.
    """
    region: str = "us-east-1"
    dynamodb_table: str
    sns_topic_arn: str
    sqs_queue_url: str
    lambda_function_name: Optional[str] = None


@dataclass
class AppConfig:
    """
    Application configuration.
    """
    twilio: TwilioConfig
    openai: OpenAIConfig
    aws: AWSConfig
    log_level: int = logging.INFO
    donation_threshold: int = 5
    donation_message: Optional[str] = None
    debug: bool = False


def load_config() -> AppConfig:
    """
    Load configuration from environment variables.
    
    Args:
        None
        
    Returns:
        AppConfig instance
        
    Required by:
        None (called during application initialization)
        
    Requires:
        - _validate_config
    """
    pass


def _validate_config(config: AppConfig) -> bool:
    """
    Validate configuration values.
    
    Args:
        config: AppConfig instance
        
    Returns:
        Boolean indicating if config is valid
        
    Required by:
        - load_config
        
    Requires:
        None
    """
    pass


def get_env_var(name: str, default: Optional[str] = None, required: bool = True) -> str:
    """
    Get an environment variable.
    
    Args:
        name: Environment variable name
        default: Default value if not found
        required: Whether the variable is required
        
    Returns:
        Environment variable value
        
    Raises:
        ValueError: If variable is required but not found
        
    Required by:
        - load_config
        
    Requires:
        None
    """
    pass