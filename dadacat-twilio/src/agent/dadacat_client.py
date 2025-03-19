"""
Client interface for interacting with the DadaCat AI agent.
"""
from typing import Dict, Any, List, Optional
import logging
import sys
from pathlib import Path
import os

# Add the parent directory to the path to import DadaCat
parent_dir = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(parent_dir))

# Import DadaCat
from dada_agents.dadacat import generate_dada_cat_response

from .history_adapter import ConversationHistoryAdapter

class DadaCatClient:
    """
    Client interface for the DadaCat AI agent.
    Handles conversation management and response generation.
    """
    
    def __init__(self, openai_api_key: Optional[str] = None, model: str = "gpt-4o"):
        """
        Initialize the DadaCat client.
        
        Args:
            openai_api_key: OpenAI API key (defaults to environment variable)
            model: Model to use for generation (default: gpt-4o)
            
        Returns:
            None
            
        Required by:
            None (called during initialization)
        """
        # Set OpenAI API key if provided, otherwise use environment variable
        if openai_api_key:
            os.environ["OPENAI_API_KEY"] = openai_api_key
        
        self.model = model
        self.logger = logging.getLogger(__name__)
        self.history_adapter = ConversationHistoryAdapter()
    
    def generate_response(self, 
                         user_message: str, 
                         conversation_history: Optional[List[Dict[str, Any]]] = None,
                         user_id: Optional[str] = None) -> str:
        """
        Generate a DadaCat response based on the user's message and conversation history.
        
        Args:
            user_message: The user's message text
            conversation_history: List of previous messages in the conversation
            user_id: Unique identifier for the user
            
        Returns:
            String containing the DadaCat response
            
        Required by:
            None (called by external components)
            
        Requires:
            - _prepare_prompt
            - _call_dadacat
        """
        try:
            # Prepare context with conversation history
            context = self.history_adapter.prepare_context(user_message, conversation_history or [])
            
            # Log the request (for debugging)
            self.logger.info(f"Generating response for user {user_id}, message: {user_message}")
            if context.get('has_history', False):
                self.logger.debug(f"With conversation history: {context['conversation_history']}")
            
            # Call DadaCat
            response = self._call_dadacat(user_message, context)
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error generating response: {str(e)}", exc_info=True)
            return self.handle_error("generation_error", str(e))
    
    def _call_dadacat(self, user_message: str, context: Dict[str, Any]) -> str:
        """
        Call the DadaCat generate_dada_cat_response function.
        
        Args:
            user_message: The user's message text
            context: Additional context information
            
        Returns:
            DadaCat response
            
        Required by:
            - generate_response
            
        Requires:
            None (calls external function)
        """
        # Currently DadaCat doesn't use conversation history, so we just pass the user message
        # In a future version, we could enhance DadaCat to support history
        response = generate_dada_cat_response(user_message)
        return response
    
    def handle_error(self, error_type: str, error_message: str) -> str:
        """
        Handle errors gracefully with appropriate fallback responses.
        
        Args:
            error_type: Type of error (e.g., 'api_error', 'timeout', 'rate_limit')
            error_message: Detailed error message
            
        Returns:
            String containing a fallback DadaCat response
            
        Required by:
            - generate_response
            
        Requires:
            None
        """
        self.logger.error(f"Error ({error_type}): {error_message}")
        
        # Map of error types to friendly messages
        error_responses = {
            "api_error": "meow? system purring incorrectly. try again?",
            "timeout": "time stretches like lazy cat... timeout occurred. paws need rest?",
            "rate_limit": "too many pets! rate limited. please wait a moment.",
            "authentication": "who are you? authentication failed. find your whiskers.",
            "generation_error": "dada brain fog... cat lost in thought maze. try simpler query?",
        }
        
        # Get the appropriate response or use a default
        response = error_responses.get(error_type, "Meow? DadaCat is confused.")
        
        return response