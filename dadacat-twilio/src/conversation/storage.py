"""
DynamoDB storage interface for conversation persistence.
"""
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
import json
import os
import boto3
from botocore.exceptions import ClientError

from .models import Conversation, Message


class DynamoDBStorage:
    """
    DynamoDB storage interface for conversation persistence.
    """
    
    def __init__(self, table_name: str, region: str = "us-east-1", endpoint_url: Optional[str] = None):
        """
        Initialize the DynamoDB storage interface.
        
        Args:
            table_name: DynamoDB table name
            region: AWS region
            endpoint_url: Optional custom endpoint URL for local DynamoDB
            
        Returns:
            None
            
        Required by:
            None (called during initialization)
        """
        self.table_name = table_name
        self.region = region
        self.endpoint_url = endpoint_url
        self.logger = logging.getLogger(__name__)
        
        # Get endpoint URL from environment if not provided
        if not endpoint_url:
            self.endpoint_url = os.getenv('AWS_ENDPOINT_URL')
        
        # Initialize DynamoDB resource
        if self.endpoint_url:
            # For local development with DynamoDB Local
            self.logger.info(f"Using local DynamoDB at {self.endpoint_url}")
            self.dynamodb = boto3.resource(
                'dynamodb', 
                region_name=region,
                endpoint_url=self.endpoint_url,
                aws_access_key_id='fakeAccessKeyId',
                aws_secret_access_key='fakeSecretAccessKey'
            )
        else:
            # For production with AWS DynamoDB
            self.logger.info(f"Using AWS DynamoDB in region {region}")
            self.dynamodb = boto3.resource('dynamodb', region_name=region)
            
        # Get the table
        self.table = self.dynamodb.Table(table_name)
    
    def get_conversation(self, user_id: str) -> Optional[Conversation]:
        """
        Retrieve a conversation from DynamoDB by user_id.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            Conversation object if found, None otherwise
            
        Required by:
            None (called by external components)
            
        Requires:
            - _dynamodb_item_to_conversation
        """
        try:
            response = self.table.get_item(Key={'user_id': user_id})
            if 'Item' in response:
                return self._dynamodb_item_to_conversation(response['Item'])
            else:
                self.logger.info(f"No conversation found for user_id: {user_id}")
                return None
        except ClientError as e:
            self.logger.error(f"Error retrieving conversation: {str(e)}")
            return None
    
    def save_conversation(self, conversation: Conversation) -> bool:
        """
        Save a conversation to DynamoDB.
        
        Args:
            conversation: Conversation object to save
            
        Returns:
            Boolean indicating success or failure
            
        Required by:
            None (called by external components)
            
        Requires:
            - _conversation_to_dynamodb_item
        """
        try:
            # Update conversation.updated_at
            conversation.updated_at = datetime.now()
            
            # Convert to DynamoDB item
            item = self._conversation_to_dynamodb_item(conversation)
            
            # Save to DynamoDB
            self.table.put_item(Item=item)
            
            self.logger.info(f"Saved conversation for user_id: {conversation.user_id}")
            return True
        except ClientError as e:
            self.logger.error(f"Error saving conversation: {str(e)}")
            return False
    
    def delete_conversation(self, user_id: str) -> bool:
        """
        Delete a conversation from DynamoDB.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            Boolean indicating success or failure
            
        Required by:
            None (called by external components)
            
        Requires:
            None
        """
        try:
            self.table.delete_item(Key={'user_id': user_id})
            self.logger.info(f"Deleted conversation for user_id: {user_id}")
            return True
        except ClientError as e:
            self.logger.error(f"Error deleting conversation: {str(e)}")
            return False
    
    def list_conversations(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        List conversations from DynamoDB.
        
        Args:
            limit: Maximum number of conversations to return
            
        Returns:
            List of conversation metadata dictionaries
            
        Required by:
            None (called by external components)
            
        Requires:
            None
        """
        try:
            response = self.table.scan(Limit=limit)
            conversations = []
            
            for item in response.get('Items', []):
                # Just return metadata, not full conversation with messages
                conversations.append({
                    'user_id': item.get('user_id'),
                    'created_at': item.get('created_at'),
                    'updated_at': item.get('updated_at'),
                    'message_count': len(json.loads(item.get('messages', '[]'))),
                    'is_active': item.get('is_active', True)
                })
            
            return conversations
        except ClientError as e:
            self.logger.error(f"Error listing conversations: {str(e)}")
            return []
    
    def _dynamodb_item_to_conversation(self, item: Dict[str, Any]) -> Conversation:
        """
        Convert a DynamoDB item to a Conversation object.
        
        Args:
            item: DynamoDB item
            
        Returns:
            Conversation object
            
        Required by:
            - get_conversation
            
        Requires:
            None
        """
        # Parse timestamps
        created_at = datetime.fromisoformat(item.get('created_at'))
        updated_at = datetime.fromisoformat(item.get('updated_at'))
        
        # Parse messages
        messages_json = item.get('messages', '[]')
        messages_data = json.loads(messages_json)
        
        messages = []
        for msg_data in messages_data:
            message = Message(
                content=msg_data.get('content', ''),
                sender=msg_data.get('sender', ''),
                timestamp=datetime.fromisoformat(msg_data.get('timestamp')),
                media_urls=msg_data.get('media_urls'),
                metadata=msg_data.get('metadata')
            )
            messages.append(message)
        
        # Parse metadata
        metadata_json = item.get('metadata', '{}')
        metadata = json.loads(metadata_json) if metadata_json else None
        
        # Create conversation
        conversation = Conversation(
            user_id=item.get('user_id'),
            messages=messages,
            created_at=created_at,
            updated_at=updated_at,
            metadata=metadata,
            is_active=item.get('is_active', True)
        )
        
        return conversation
    
    def _conversation_to_dynamodb_item(self, conversation: Conversation) -> Dict[str, Any]:
        """
        Convert a Conversation object to a DynamoDB item.
        
        Args:
            conversation: Conversation object
            
        Returns:
            DynamoDB item dictionary
            
        Required by:
            - save_conversation
            
        Requires:
            None
        """
        # Convert messages to JSON
        messages_data = []
        for message in conversation.messages:
            msg_dict = {
                'content': message.content,
                'sender': message.sender,
                'timestamp': message.timestamp.isoformat()
            }
            
            if message.media_urls:
                msg_dict['media_urls'] = message.media_urls
                
            if message.metadata:
                msg_dict['metadata'] = message.metadata
                
            messages_data.append(msg_dict)
        
        # Create DynamoDB item
        item = {
            'user_id': conversation.user_id,
            'created_at': conversation.created_at.isoformat(),
            'updated_at': conversation.updated_at.isoformat(),
            'messages': json.dumps(messages_data),
            'is_active': conversation.is_active
        }
        
        # Add metadata if present
        if conversation.metadata:
            item['metadata'] = json.dumps(conversation.metadata)
        
        return item