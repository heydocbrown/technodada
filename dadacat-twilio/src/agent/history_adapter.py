"""
Conversation history adapter for DadaCat.
Provides stateful conversation interactions without modifying the original DadaCat implementation.
"""
from typing import Dict, Any, List, Optional
import logging

class ConversationHistoryAdapter:
    """
    Adapter that manages conversation history for DadaCat without modifying the original implementation.
    """
    
    def __init__(self, max_history_length: int = 10):
        """
        Initialize the conversation history adapter.
        
        Args:
            max_history_length: Maximum number of conversation turns to maintain
            
        Returns:
            None
            
        Required by:
            None (called during initialization)
        """
        self.max_history_length = max_history_length
        self.logger = logging.getLogger(__name__)
    
    def format_history_for_prompt(self, 
                                conversation_history: List[Dict[str, Any]]) -> str:
        """
        Format conversation history into a string suitable for inclusion in the DadaCat prompt.
        
        Args:
            conversation_history: List of conversation messages with 'role' and 'content' keys
            
        Returns:
            Formatted history string
            
        Required by:
            None (called by external components)
            
        Requires:
            None
        """
        if not conversation_history:
            return ""
        
        # Format: "Human: {message}\nDadaCat: {response}\n"
        formatted_history = ""
        for msg in conversation_history:
            role = msg.get('role', '')
            content = msg.get('content', '')
            
            if role.lower() == 'user':
                formatted_history += f"Human: {content}\n"
            elif role.lower() == 'assistant':
                formatted_history += f"DadaCat: {content}\n"
        
        return formatted_history.strip()
    
    def prepare_context(self, 
                      user_message: str, 
                      conversation_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Prepare the full context for a DadaCat request, including conversation history.
        
        Args:
            user_message: Current user message
            conversation_history: Previous conversation history
            
        Returns:
            Dictionary with prepared request context
            
        Required by:
            None (called by external components)
            
        Requires:
            - format_history_for_prompt
        """
        # Get formatted history
        history_str = self.format_history_for_prompt(conversation_history)
        
        # Create context dictionary
        context = {
            'user_message': user_message,
            'conversation_history': history_str,
            'has_history': bool(history_str)
        }
        
        return context
    
    def add_to_history(self, 
                     conversation_history: List[Dict[str, Any]],
                     role: str,
                     content: str) -> List[Dict[str, Any]]:
        """
        Add a new message to the conversation history.
        
        Args:
            conversation_history: Previous conversation history
            role: Role of the message sender ('user' or 'assistant')
            content: Message content
            
        Returns:
            Updated conversation history
            
        Required by:
            None (called by external components)
            
        Requires:
            None
        """
        # Create a new list if None was provided
        if conversation_history is None:
            conversation_history = []
        
        # Create a copy of the conversation history
        updated_history = conversation_history.copy()
        
        # Add the new message
        updated_history.append({
            "role": role,
            "content": content
        })
        
        # Trim history if it's too long
        if len(updated_history) > self.max_history_length * 2:  # *2 for pairs of messages
            updated_history = self.trim_history(updated_history)
            
        return updated_history
    
    def trim_history(self, conversation_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Trim conversation history to the maximum length.
        
        Args:
            conversation_history: Conversation history to trim
            
        Returns:
            Trimmed conversation history
            
        Required by:
            - add_to_history
            
        Requires:
            None
        """
        # If the history is already short enough, return it as is
        max_messages = self.max_history_length * 2  # *2 for pairs of messages
        if len(conversation_history) <= max_messages:
            return conversation_history
        
        # Keep only the most recent messages up to the maximum length
        # We want to keep pairs of user/assistant messages, so we remove 
        # from the beginning of the list
        trimmed_history = conversation_history[-max_messages:]
        
        self.logger.info(f"Trimmed conversation history from {len(conversation_history)} to {len(trimmed_history)} messages")
        
        return trimmed_history