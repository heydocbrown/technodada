"""
Conversation state manager.
"""
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime

from .models import Conversation, Message
from .storage import DynamoDBStorage


class ConversationManager:
    """
    Manager for conversation state and persistence.
    """
    
    def __init__(self, storage: DynamoDBStorage):
        """
        Initialize the conversation manager.
        
        Args:
            storage: Storage interface for conversation persistence
            
        Returns:
            None
            
        Required by:
            None (called during initialization)
        """
        self.storage = storage
        self.logger = logging.getLogger(__name__)
    
    def get_or_create_conversation(self, user_id: str) -> Conversation:
        """
        Get an existing conversation or create a new one if it doesn't exist.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            Conversation object
            
        Required by:
            None (called by external components)
            
        Requires:
            - storage.get_conversation
            - _create_new_conversation
        """
        # Try to get existing conversation
        conversation = self.storage.get_conversation(user_id)
        
        # If not found, create a new one
        if not conversation:
            self.logger.info(f"Creating new conversation for user_id: {user_id}")
            conversation = self._create_new_conversation(user_id)
            self.storage.save_conversation(conversation)
        
        return conversation
    
    def add_user_message(self, user_id: str, content: str, media_urls: Optional[List[str]] = None) -> Conversation:
        """
        Add a user message to the conversation.
        
        Args:
            user_id: Unique identifier for the user
            content: Message content
            media_urls: Optional list of media URLs
            
        Returns:
            Updated Conversation object
            
        Required by:
            None (called by external components)
            
        Requires:
            - get_or_create_conversation
            - storage.save_conversation
        """
        # Get or create conversation
        conversation = self.get_or_create_conversation(user_id)
        
        # Create message
        message = Message(
            content=content,
            sender="user",
            timestamp=datetime.now(),
            media_urls=media_urls
        )
        
        # Add message to conversation
        conversation.add_message(message)
        
        # Save updated conversation
        self.storage.save_conversation(conversation)
        
        self.logger.info(f"Added user message to conversation for user_id: {user_id}")
        return conversation
    
    def add_assistant_message(self, user_id: str, content: str) -> Conversation:
        """
        Add an assistant (DadaCat) message to the conversation.
        
        Args:
            user_id: Unique identifier for the user
            content: Message content
            
        Returns:
            Updated Conversation object
            
        Required by:
            None (called by external components)
            
        Requires:
            - get_or_create_conversation
            - storage.save_conversation
        """
        # Get or create conversation
        conversation = self.get_or_create_conversation(user_id)
        
        # Create message
        message = Message(
            content=content,
            sender="assistant",
            timestamp=datetime.now()
        )
        
        # Add message to conversation
        conversation.add_message(message)
        
        # Save updated conversation
        self.storage.save_conversation(conversation)
        
        self.logger.info(f"Added assistant message to conversation for user_id: {user_id}")
        return conversation
    
    def reset_conversation(self, user_id: str) -> bool:
        """
        Reset a conversation by clearing its message history.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            Boolean indicating success or failure
            
        Required by:
            None (called by external components)
            
        Requires:
            - get_or_create_conversation
            - storage.save_conversation
        """
        try:
            # Get conversation
            conversation = self.get_or_create_conversation(user_id)
            
            # Reset message history
            conversation.reset()
            
            # Save updated conversation
            success = self.storage.save_conversation(conversation)
            
            if success:
                self.logger.info(f"Reset conversation for user_id: {user_id}")
            
            return success
        except Exception as e:
            self.logger.error(f"Error resetting conversation: {str(e)}")
            return False
    
    def get_message_count(self, user_id: str) -> int:
        """
        Get the number of messages in a conversation.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            Integer count of messages
            
        Required by:
            None (called by external components)
            
        Requires:
            - get_or_create_conversation
        """
        conversation = self.get_or_create_conversation(user_id)
        return len(conversation.messages)
    
    def _create_new_conversation(self, user_id: str) -> Conversation:
        """
        Create a new conversation.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            New Conversation object
            
        Required by:
            - get_or_create_conversation
            
        Requires:
            None
        """
        now = datetime.now()
        return Conversation(
            user_id=user_id,
            messages=[],
            created_at=now,
            updated_at=now,
            is_active=True
        )