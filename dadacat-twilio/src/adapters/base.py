"""
Base adapter interface for handling messages from various channels.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class MessageAdapter(ABC):
    """
    Base abstract class for all message channel adapters.
    Provides a common interface for handling messages from different channels.
    """
    
    @abstractmethod
    def validate_request(self, request_data: Dict[str, Any]) -> bool:
        """
        Validates an incoming request from the messaging service.
        
        Args:
            request_data: Dictionary containing the request data
            
        Returns:
            bool: True if request is valid, False otherwise
            
        Required by:
            - handle_webhook
        """
        pass
    
    @abstractmethod
    def extract_message(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts message content and metadata from the request.
        
        Args:
            request_data: Dictionary containing the request data
            
        Returns:
            Dict with keys:
                'from': Sender identifier (e.g., phone number)
                'body': Message text content
                'media_urls': Optional list of media URLs
                'timestamp': Message timestamp
                
        Required by:
            - handle_webhook
        """
        pass
    
    @abstractmethod
    def send_message(self, to: str, body: str, media_urls: Optional[list] = None) -> Dict[str, Any]:
        """
        Sends a message to the specified recipient.
        
        Args:
            to: Recipient identifier (e.g., phone number)
            body: Message text content
            media_urls: Optional list of media URLs to attach
            
        Returns:
            Dict with response data from the messaging service
            
        Required by:
            None (called by external components)
        """
        pass
    
    @abstractmethod
    def handle_webhook(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes an incoming webhook request and prepares a response.
        
        Args:
            request_data: Dictionary containing the request data
            
        Returns:
            Dict with the appropriate response for the messaging service
            
        Required by:
            None (called by the web framework)
            
        Requires:
            - validate_request
            - extract_message
        """
        pass