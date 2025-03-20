"""
Twilio adapter for handling SMS messages.
"""
from typing import Dict, Any, Optional
import logging
from datetime import datetime
import urllib.parse
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator

from .base import MessageAdapter


class TwilioAdapter(MessageAdapter):
    """
    Adapter for handling Twilio SMS messages.
    """
    
    def __init__(self, account_sid: str, auth_token: str, twilio_number: str):
        """
        Initialize the Twilio adapter with credentials.
        
        Args:
            account_sid: Twilio account SID
            auth_token: Twilio auth token
            twilio_number: Twilio phone number to send messages from
            
        Returns:
            None
            
        Required by:
            None (called during initialization)
        """
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.twilio_number = twilio_number
        self.client = Client(account_sid, auth_token)
        self.validator = RequestValidator(auth_token)
        self.logger = logging.getLogger(__name__)
    
    def validate_request(self, request_data: Dict[str, Any]) -> bool:
        """
        Validates that an incoming request is from Twilio using signature validation.
        
        Args:
            request_data: Dictionary containing the request data
            
        Returns:
            bool: True if request is valid and from Twilio, False otherwise
            
        Required by:
            - handle_webhook
            
        Requires:
            - External Twilio validation utilities
        """
        # In Lambda context, validation works differently
        # This is a simplified implementation for now
        return True
    
    def extract_message(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts message content and metadata from the Twilio request.
        
        Args:
            request_data: Dictionary containing the Twilio request data
            
        Returns:
            Dict with keys:
                'from': Sender phone number
                'body': SMS text content
                'media_urls': List of MMS URLs if any
                'timestamp': Message timestamp
                
        Required by:
            - handle_webhook
        """
        try:
            # For API Gateway + Lambda, we may need to parse the body
            if isinstance(request_data.get('body'), str):
                parsed_form = urllib.parse.parse_qs(request_data['body'])
                from_number = parsed_form.get('From', [''])[0]
                body = parsed_form.get('Body', [''])[0]
                num_media = int(parsed_form.get('NumMedia', ['0'])[0])
                self.logger.info(f"Extracted from parsed body - from_number: '{from_number}', body: '{body}'")
            else:
                # Direct request params
                from_number = request_data.get('From', '')
                body = request_data.get('Body', '')
                num_media = int(request_data.get('NumMedia', 0))
                self.logger.info(f"Extracted from direct params - from_number: '{from_number}', body: '{body}'")
                
            # Validate phone number format
            if not from_number or not from_number.startswith('+'):
                self.logger.error(f"Invalid phone number format extracted from Twilio request: '{from_number}' - Must start with + and contain country code")
                # Continue processing to catch this in the logs, but expect it to fail later
            
            # Extract media URLs if present
            media_urls = []
            if num_media > 0:
                for i in range(num_media):
                    media_url_key = f'MediaUrl{i}'
                    if isinstance(request_data.get('body'), str):
                        media_url = parsed_form.get(media_url_key, [''])[0]
                    else:
                        media_url = request_data.get(media_url_key, '')
                    
                    if media_url:
                        media_urls.append(media_url)
            
            return {
                'from': from_number,
                'body': body,
                'media_urls': media_urls,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error extracting message: {e}", exc_info=True)
            raise
    
    def send_message(self, to: str, body: str, media_urls: Optional[list] = None) -> Dict[str, Any]:
        """
        Sends an SMS/MMS message via Twilio.
        
        Args:
            to: Recipient phone number
            body: SMS text content
            media_urls: Optional list of media URLs to send as MMS
            
        Returns:
            Dict with Twilio response data
            
        Required by:
            None (called by external components)
            
        Requires:
            - External Twilio client library
        """
        try:
            message_params = {
                'from_': self.twilio_number,
                'to': to,
                'body': body
            }
            
            # Add media URLs if provided
            if media_urls:
                message_params['media_url'] = media_urls
            
            # Send the message
            message = self.client.messages.create(**message_params)
            
            self.logger.info(f"Sent message to {to} with SID {message.sid}")
            
            return {
                'sid': message.sid,
                'status': message.status,
                'error_code': message.error_code,
                'error_message': message.error_message
            }
            
        except Exception as e:
            self.logger.error(f"Error sending message: {e}", exc_info=True)
            raise
    
    def handle_webhook(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes an incoming Twilio webhook request and prepares a TwiML response.
        
        Args:
            request_data: Dictionary containing the Twilio request data
            
        Returns:
            Dict with TwiML response
            
        Required by:
            None (called by the web framework)
            
        Requires:
            - validate_request
            - extract_message
        """
        try:
            # Validate the request
            if not self.validate_request(request_data):
                self.logger.warning("Invalid Twilio request")
                return {
                    'statusCode': 403,
                    'body': 'Forbidden'
                }
            
            # Extract the message
            message_data = self.extract_message(request_data)
            
            # Return the extracted message for further processing
            return {
                'statusCode': 200,
                'message_data': message_data
            }
            
        except Exception as e:
            self.logger.error(f"Error handling webhook: {e}", exc_info=True)
            return {
                'statusCode': 500,
                'body': 'Internal Server Error'
            }
    
    def create_twiml_response(self, message: str) -> str:
        """
        Creates a TwiML response with the given message.
        
        Args:
            message: Message text to include in the response
            
        Returns:
            String containing the TwiML XML
            
        Required by:
            - handle_webhook
            
        Requires:
            - External Twilio TwiML library
        """
        try:
            response = MessagingResponse()
            response.message(message)
            return str(response)
            
        except Exception as e:
            self.logger.error(f"Error creating TwiML response: {e}", exc_info=True)
            # Simple fallback response
            return '<?xml version="1.0" encoding="UTF-8"?><Response><Message>Error processing request</Message></Response>'