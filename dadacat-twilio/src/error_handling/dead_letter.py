"""
Dead letter queue handler for failed messages.
"""
from typing import Dict, Any, Optional, List, Callable, Tuple
import logging
import json
import time
import uuid
import os
from datetime import datetime
import boto3
from botocore.exceptions import ClientError


class DeadLetterQueue:
    """
    Handler for storing and processing failed messages.
    """
    
    def __init__(self, 
                queue_url: Optional[str] = None, 
                region: str = "us-east-1",
                reprocessor: Optional[Callable[[Dict[str, Any]], bool]] = None,
                max_retry_count: int = 3,
                local_file_path: Optional[str] = None):
        """
        Initialize the dead letter queue handler.
        
        Args:
            queue_url: AWS SQS queue URL (or from environment variable)
            region: AWS region
            reprocessor: Optional function to reprocess messages
            max_retry_count: Maximum number of retry attempts
            local_file_path: Path to local JSON file for DLQ (for development without AWS)
            
        Returns:
            None
            
        Required by:
            None (called during initialization)
        """
        # Get queue URL from env var if not provided
        self.queue_url = queue_url or os.getenv('DLQ_QUEUE_URL')
        self.region = region
        self.reprocessor = reprocessor
        self.max_retry_count = max_retry_count
        self.local_file_path = local_file_path or os.getenv('DLQ_LOCAL_FILE_PATH')
        self.logger = logging.getLogger(__name__)
        
        # Determine mode (AWS SQS or local file)
        self.use_local_mode = not self.queue_url or bool(self.local_file_path)
        
        # Initialize AWS SQS client if using AWS
        if self.queue_url and not self.use_local_mode:
            try:
                self.sqs_client = boto3.client('sqs', region_name=self.region)
                self.logger.info(f"Using AWS SQS for Dead Letter Queue: {self.queue_url}")
            except Exception as e:
                self.logger.warning(f"Failed to initialize AWS SQS client: {str(e)}")
                self.use_local_mode = True
                
        # Set up local file if using local mode
        if self.use_local_mode:
            if not self.local_file_path:
                self.local_file_path = "./local_dlq.json"
            self.logger.info(f"Using local file for Dead Letter Queue: {self.local_file_path}")
            
            # Create the file if it doesn't exist
            if not os.path.exists(self.local_file_path):
                try:
                    with open(self.local_file_path, 'w') as f:
                        json.dump([], f)
                except Exception as e:
                    self.logger.error(f"Failed to create local DLQ file: {str(e)}")
    
    def send_to_dlq(self, message: Dict[str, Any], error_info: Dict[str, Any]) -> bool:
        """
        Send a failed message to the dead letter queue.
        
        Args:
            message: The original message that failed
            error_info: Information about the error
            
        Returns:
            Boolean indicating success or failure
            
        Required by:
            None (called by external components)
            
        Requires:
            - _format_dlq_message
        """
        # Format the message for the DLQ
        dlq_message = self._format_dlq_message(message, error_info)
        
        # Handle based on mode (AWS SQS or local file)
        if self.use_local_mode:
            return self._send_to_local_dlq(dlq_message, error_info)
        else:
            return self._send_to_sqs_dlq(dlq_message, error_info)
    
    def _send_to_sqs_dlq(self, dlq_message: Dict[str, Any], error_info: Dict[str, Any]) -> bool:
        """
        Send message to AWS SQS dead letter queue.
        
        Args:
            dlq_message: Formatted message for the DLQ
            error_info: Information about the error
            
        Returns:
            Boolean indicating success or failure
        """
        if not self.queue_url:
            self.logger.error("SQS queue URL is required for SQS DLQ operations")
            return False
            
        try:
            # Convert to JSON string for SQS
            message_body = json.dumps(dlq_message)
            
            # Send to SQS
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=message_body,
                MessageAttributes={
                    'ErrorType': {
                        'DataType': 'String',
                        'StringValue': error_info.get('error_type', 'unknown')
                    },
                    'Timestamp': {
                        'DataType': 'String',
                        'StringValue': datetime.now().isoformat()
                    }
                }
            )
            
            self.logger.info(f"Sent message to SQS DLQ: {response.get('MessageId')}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending message to SQS DLQ: {str(e)}")
            return False
    
    def _send_to_local_dlq(self, dlq_message: Dict[str, Any], error_info: Dict[str, Any]) -> bool:
        """
        Send message to local file-based dead letter queue.
        
        Args:
            dlq_message: Formatted message for the DLQ
            error_info: Information about the error
            
        Returns:
            Boolean indicating success or failure
        """
        if not self.local_file_path:
            self.logger.error("Local file path is required for local DLQ operations")
            return False
            
        try:
            # Load existing messages
            messages = []
            if os.path.exists(self.local_file_path) and os.path.getsize(self.local_file_path) > 0:
                try:
                    with open(self.local_file_path, 'r') as f:
                        messages = json.load(f)
                except json.JSONDecodeError:
                    self.logger.warning(f"Could not decode JSON in {self.local_file_path}, starting with empty DLQ")
                    messages = []
            
            # Add SQS-like metadata to match AWS format
            dlq_message['sqs_metadata'] = {
                'message_id': dlq_message['message_id'],
                'receipt_handle': dlq_message['message_id'],  # Use same value for simplicity
                'attributes': {
                    'SentTimestamp': str(int(time.time() * 1000))
                },
                'message_attributes': {
                    'ErrorType': {
                        'StringValue': error_info.get('error_type', 'unknown')
                    },
                    'Timestamp': {
                        'StringValue': datetime.now().isoformat()
                    }
                }
            }
            
            # Add the new message
            messages.append(dlq_message)
            
            # Write back to file
            with open(self.local_file_path, 'w') as f:
                json.dump(messages, f, indent=2)
            
            self.logger.info(f"Sent message to local DLQ: {dlq_message['message_id']}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending message to local DLQ: {str(e)}")
            return False
    
    def receive_from_dlq(self, max_messages: int = 10) -> List[Dict[str, Any]]:
        """
        Receive messages from the dead letter queue.
        
        Args:
            max_messages: Maximum number of messages to receive
            
        Returns:
            List of messages from the queue
            
        Required by:
            None (called by external components)
            
        Requires:
            None
        """
        # Handle based on mode (AWS SQS or local file)
        if self.use_local_mode:
            return self._receive_from_local_dlq(max_messages)
        else:
            return self._receive_from_sqs_dlq(max_messages)
            
    def _receive_from_sqs_dlq(self, max_messages: int = 10) -> List[Dict[str, Any]]:
        """
        Receive messages from AWS SQS dead letter queue.
        
        Args:
            max_messages: Maximum number of messages to receive
            
        Returns:
            List of messages from the queue
        """
        if not self.queue_url:
            self.logger.error("SQS queue URL is required for SQS DLQ operations")
            return []
            
        try:
            # Receive messages from SQS
            response = self.sqs_client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=min(max_messages, 10),  # SQS API limits to 10
                AttributeNames=['All'],
                MessageAttributeNames=['All'],
                WaitTimeSeconds=1
            )
            
            # Parse SQS messages
            messages = []
            for msg in response.get('Messages', []):
                try:
                    # Parse the message body as JSON
                    body = json.loads(msg.get('Body', '{}'))
                    
                    # Add SQS metadata
                    body['sqs_metadata'] = {
                        'message_id': msg.get('MessageId'),
                        'receipt_handle': msg.get('ReceiptHandle'),
                        'attributes': msg.get('Attributes', {}),
                        'message_attributes': msg.get('MessageAttributes', {})
                    }
                    
                    messages.append(body)
                    
                except json.JSONDecodeError:
                    self.logger.warning(f"Failed to parse message body: {msg.get('Body')}")
            
            return messages
            
        except Exception as e:
            self.logger.error(f"Error receiving messages from SQS DLQ: {str(e)}")
            return []
    
    def _receive_from_local_dlq(self, max_messages: int = 10) -> List[Dict[str, Any]]:
        """
        Receive messages from local file-based dead letter queue.
        
        Args:
            max_messages: Maximum number of messages to receive
            
        Returns:
            List of messages from the queue
        """
        if not self.local_file_path:
            self.logger.error("Local file path is required for local DLQ operations")
            return []
            
        try:
            # Check if file exists
            if not os.path.exists(self.local_file_path):
                self.logger.warning(f"Local DLQ file does not exist: {self.local_file_path}")
                return []
                
            # Read messages from file
            with open(self.local_file_path, 'r') as f:
                try:
                    messages = json.load(f)
                except json.JSONDecodeError:
                    self.logger.warning(f"Could not decode JSON in {self.local_file_path}")
                    return []
            
            # Return up to max_messages
            return messages[:max_messages]
            
        except Exception as e:
            self.logger.error(f"Error receiving messages from local DLQ: {str(e)}")
            return []
    
    def reprocess_message(self, message_id: str) -> bool:
        """
        Attempt to reprocess a message from the dead letter queue.
        
        Args:
            message_id: ID of the message to reprocess
            
        Returns:
            Boolean indicating success or failure
            
        Required by:
            None (called by external components)
            
        Requires:
            - _get_message
            - _delete_message
        """
        if not self.queue_url:
            self.logger.error("SQS queue URL is required for DLQ operations")
            return False
            
        if not self.reprocessor:
            self.logger.error("Reprocessor function is required for reprocessing messages")
            return False
            
        try:
            # Get the message
            message = self._get_message(message_id)
            if not message:
                self.logger.warning(f"Message {message_id} not found in DLQ")
                return False
                
            # Extract receipt handle
            sqs_metadata = message.get('sqs_metadata', {})
            receipt_handle = sqs_metadata.get('receipt_handle')
            if not receipt_handle:
                self.logger.warning(f"Receipt handle not found for message {message_id}")
                return False
                
            # Extract the original message
            original_message = message.get('original_message', {})
            
            # Check retry count
            retry_info = message.get('retry_info', {})
            retry_count = retry_info.get('count', 0)
            
            if retry_count >= self.max_retry_count:
                self.logger.warning(
                    f"Message {message_id} has reached max retry count ({retry_count}/{self.max_retry_count})"
                )
                return False
                
            # Attempt to reprocess
            success = self.reprocessor(original_message)
            
            if success:
                # If successful, delete from DLQ
                self._delete_message(message_id, receipt_handle)
                self.logger.info(f"Successfully reprocessed message {message_id}")
                return True
            else:
                # Update retry count and send back to DLQ
                retry_info['count'] = retry_count + 1
                retry_info['last_retry'] = datetime.now().isoformat()
                
                # Send updated message back to DLQ
                message['retry_info'] = retry_info
                
                # Delete the original message
                self._delete_message(message_id, receipt_handle)
                
                # Send as a new message (without the SQS metadata)
                del message['sqs_metadata']
                error_info = message.get('error_info', {})
                error_info['retry_failed'] = True
                
                return self.send_to_dlq(original_message, error_info)
                
        except Exception as e:
            self.logger.error(f"Error reprocessing message {message_id}: {str(e)}")
            return False
    
    def purge_queue(self) -> bool:
        """
        Purge all messages from the dead letter queue.
        
        Args:
            None
            
        Returns:
            Boolean indicating success or failure
            
        Required by:
            None (called by external components)
            
        Requires:
            None
        """
        if not self.queue_url:
            self.logger.error("SQS queue URL is required for DLQ operations")
            return False
            
        try:
            # Purge the queue
            self.sqs_client.purge_queue(QueueUrl=self.queue_url)
            self.logger.info(f"Purged DLQ: {self.queue_url}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error purging DLQ: {str(e)}")
            return False
    
    def _format_dlq_message(self, message: Dict[str, Any], error_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format a message for the dead letter queue.
        
        Args:
            message: The original message that failed
            error_info: Information about the error
            
        Returns:
            Formatted message for the queue
            
        Required by:
            - send_to_dlq
            
        Requires:
            None
        """
        # Generate a unique ID for this DLQ message
        message_id = str(uuid.uuid4())
        
        # Current timestamp
        timestamp = datetime.now().isoformat()
        
        # Create DLQ message structure
        dlq_message = {
            'message_id': message_id,
            'timestamp': timestamp,
            'original_message': message,
            'error_info': error_info,
            'retry_info': {
                'count': 0,
                'first_failure': timestamp,
                'last_retry': None
            }
        }
        
        return dlq_message
    
    def _get_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific message from the queue by ID.
        
        Args:
            message_id: ID of the message to get
            
        Returns:
            Message if found, None otherwise
            
        Required by:
            - reprocess_message
            
        Requires:
            None
        """
        if not self.queue_url:
            self.logger.error("SQS queue URL is required for DLQ operations")
            return None
            
        # SQS doesn't support querying by custom attributes efficiently
        # We need to retrieve all messages and filter
        try:
            # Get messages from the queue
            messages = self.receive_from_dlq(max_messages=10)
            
            # Filter for the specific message ID
            # This is not efficient for large queues, but works for small queues
            for message in messages:
                sqs_message_id = message.get('sqs_metadata', {}).get('message_id')
                custom_message_id = message.get('message_id')
                
                if sqs_message_id == message_id or custom_message_id == message_id:
                    return message
                    
            # If we get here, the message was not found
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting message {message_id}: {str(e)}")
            return None
    
    def _delete_message(self, message_id: str, receipt_handle: str) -> bool:
        """
        Delete a message from the queue.
        
        Args:
            message_id: ID of the message to delete
            receipt_handle: Receipt handle of the message
            
        Returns:
            Boolean indicating success or failure
            
        Required by:
            - reprocess_message
            
        Requires:
            None
        """
        if not self.queue_url:
            self.logger.error("SQS queue URL is required for DLQ operations")
            return False
            
        try:
            # Delete the message
            self.sqs_client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle
            )
            
            self.logger.info(f"Deleted message {message_id} from DLQ")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting message {message_id}: {str(e)}")
            return False