"""
Data models for conversation management.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Message:
    """
    Represents a single message in a conversation.
    """
    content: str
    sender: str  # 'user' or 'assistant'
    timestamp: datetime
    media_urls: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Conversation:
    """
    Represents a conversation between a user and DadaCat.
    """
    user_id: str
    messages: List[Message]
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]] = None
    is_active: bool = True
    
    def add_message(self, message: Message) -> None:
        """
        Add a message to the conversation.
        
        Args:
            message: The message to add
            
        Returns:
            None
            
        Required by:
            None (called by external components)
        """
        self.messages.append(message)
        self.updated_at = datetime.now()
    
    def get_formatted_history(self) -> List[Dict[str, str]]:
        """
        Get the conversation history formatted for the OpenAI API.
        
        Args:
            None
            
        Returns:
            List of message dictionaries with 'role' and 'content' keys
            
        Required by:
            None (called by external components)
            
        Requires:
            None
        """
        formatted_history = []
        for message in self.messages:
            role = "user" if message.sender == "user" else "assistant"
            formatted_history.append({
                "role": role,
                "content": message.content
            })
        return formatted_history
    
    def reset(self) -> None:
        """
        Reset the conversation history while maintaining user_id.
        
        Args:
            None
            
        Returns:
            None
            
        Required by:
            None (called by external components)
            
        Requires:
            None
        """
        self.messages = []
        self.updated_at = datetime.now()
    
    def get_first_message_time(self) -> Optional[datetime]:
        """
        Get the timestamp of the first message in the conversation.
        
        Args:
            None
            
        Returns:
            Timestamp of the first message or None if no messages exist
            
        Required by:
            None (called by external components for analytics)
            
        Requires:
            None
        """
        if not self.messages:
            return None
        
        # Sort messages by timestamp and return the earliest
        sorted_messages = sorted(self.messages, key=lambda m: m.timestamp)
        return sorted_messages[0].timestamp