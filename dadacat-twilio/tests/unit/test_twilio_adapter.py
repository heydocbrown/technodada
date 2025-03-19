"""
Unit tests for the Twilio adapter.
"""
import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, Any

from src.adapters.twilio_adapter import TwilioAdapter


def test_init(test_config):
    """Test the initialization of the TwilioAdapter."""
    adapter = TwilioAdapter(
        account_sid=test_config.twilio.account_sid,
        auth_token=test_config.twilio.auth_token,
        twilio_number=test_config.twilio.phone_number
    )
    
    assert adapter.account_sid == test_config.twilio.account_sid
    assert adapter.auth_token == test_config.twilio.auth_token
    assert adapter.twilio_number == test_config.twilio.phone_number


@patch('src.adapters.twilio_adapter.TwilioAdapter.validate_request')
def test_extract_message(mock_validate, twilio_adapter, sample_twilio_request):
    """Test extracting a message from a Twilio request."""
    mock_validate.return_value = True
    
    # This would test the extract_message method once implemented
    pass


@patch('src.adapters.twilio_adapter.TwilioAdapter.extract_message')
@patch('src.adapters.twilio_adapter.TwilioAdapter.validate_request')
def test_handle_webhook(mock_validate, mock_extract, twilio_adapter, sample_twilio_request):
    """Test handling a Twilio webhook request."""
    mock_validate.return_value = True
    mock_extract.return_value = {
        'from': '+12223334444',
        'body': 'Hello DadaCat!',
        'media_urls': [],
        'timestamp': '2025-03-14T12:00:00Z'
    }
    
    # This would test the handle_webhook method once implemented
    pass


@patch('twilio.rest.Client')
def test_send_message(mock_client_class, twilio_adapter):
    """Test sending a message via Twilio."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    mock_message = MagicMock()
    mock_message.sid = 'SM123456789'
    mock_client.messages.create.return_value = mock_message
    
    # This would test the send_message method once implemented
    pass


def test_create_twiml_response(twilio_adapter):
    """Test creating a TwiML response."""
    # This would test the create_twiml_response method once implemented
    pass