"""
User engagement metrics tracking.
"""
from typing import Dict, Any, List, Optional, Union
import logging
import os
import json
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError
import threading
from pathlib import Path
import uuid
from enum import Enum


class UserActivity(Enum):
    """
    Enum representing user activity types.
    """
    NEW_CONVERSATION = "new_conversation"
    RESET = "reset"
    MESSAGE = "message"
    ADMIN_COMMAND = "admin_command"
    DONATION_PROMPT = "donation_prompt"


class EngagementTracker:
    """
    Tracker for user engagement metrics.
    """
    
    def __init__(self, namespace: str = "DadaCatTwilio", region: str = "us-east-1",
                 local_file_fallback: bool = True, local_file_path: Optional[str] = None):
        """
        Initialize the engagement tracker.
        
        Args:
            namespace: CloudWatch namespace
            region: AWS region
            local_file_fallback: Whether to use local file fallback if CloudWatch is unavailable
            local_file_path: Path to local file for metrics (defaults to ./metrics/engagement.json)
            
        Returns:
            None
            
        Required by:
            None (called during initialization)
        """
        self.namespace = namespace
        self.region = region
        self.local_file_fallback = local_file_fallback
        
        # Initialize logger
        self.logger = logging.getLogger(__name__)
        
        # Check if we should use local DynamoDB endpoint
        self.local_endpoint = os.getenv('AWS_ENDPOINT_URL')
        
        # Initialize AWS clients
        try:
            if self.local_endpoint:
                self.logger.info(f"Using local AWS endpoint: {self.local_endpoint}")
                self.cloudwatch = boto3.client(
                    'cloudwatch',
                    region_name=region,
                    endpoint_url=self.local_endpoint,
                    aws_access_key_id='fakeAccessKeyId',
                    aws_secret_access_key='fakeSecretAccessKey'
                )
            else:
                self.cloudwatch = boto3.client('cloudwatch', region_name=region)
            self.use_cloudwatch = True
            
        except Exception as e:
            self.logger.warning(f"Failed to initialize CloudWatch client: {str(e)}")
            self.use_cloudwatch = False
        
        # Set up local file fallback
        if local_file_fallback:
            if local_file_path:
                self.local_file_path = Path(local_file_path)
            else:
                self.local_file_path = Path('./metrics/engagement.json')
            
            # Create directory if it doesn't exist
            self.local_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create file if it doesn't exist
            if not self.local_file_path.exists():
                with open(self.local_file_path, 'w') as f:
                    json.dump({
                        "conversations": [],
                        "user_activities": [],
                        "response_times": [],
                        "last_updated": datetime.now().isoformat()
                    }, f)
    
    def track_conversation(self, 
                          user_id: str, 
                          message_count: int, 
                          duration_seconds: float) -> bool:
        """
        Track a conversation engagement.
        
        Args:
            user_id: Unique identifier for the user
            message_count: Number of messages in the conversation
            duration_seconds: Duration of the conversation in seconds
            
        Returns:
            Boolean indicating success or failure
            
        Required by:
            None (called by external components)
            
        Requires:
            - _send_metrics
        """
        try:
            current_time = datetime.now()
            
            # Create metrics data
            metrics = [
                {
                    'MetricName': 'ConversationMessageCount',
                    'Timestamp': current_time,
                    'Value': message_count,
                    'Unit': 'Count',
                    'Dimensions': [
                        {
                            'Name': 'UserId',
                            'Value': user_id
                        }
                    ]
                },
                {
                    'MetricName': 'ConversationDuration',
                    'Timestamp': current_time,
                    'Value': duration_seconds,
                    'Unit': 'Seconds',
                    'Dimensions': [
                        {
                            'Name': 'UserId',
                            'Value': user_id
                        }
                    ]
                }
            ]
            
            # Send metrics asynchronously to avoid blocking
            threading.Thread(
                target=self._send_metrics,
                args=(metrics,),
                daemon=True
            ).start()
            
            # Create local record for fallback
            if self.local_file_fallback:
                conversation_record = {
                    "id": str(uuid.uuid4()),
                    "timestamp": current_time.isoformat(),
                    "user_id": user_id,
                    "message_count": message_count,
                    "duration_seconds": duration_seconds
                }
                
                # Save to local file asynchronously
                threading.Thread(
                    target=self._save_conversation_to_local_file,
                    args=(conversation_record,),
                    daemon=True
                ).start()
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error tracking conversation: {str(e)}", exc_info=True)
            return False
    
    def track_response_time(self, response_time_ms: float) -> bool:
        """
        Track a response time measurement.
        
        Args:
            response_time_ms: Response time in milliseconds
            
        Returns:
            Boolean indicating success or failure
            
        Required by:
            None (called by external components)
            
        Requires:
            - _send_metrics
        """
        try:
            current_time = datetime.now()
            
            # Create metrics data
            metrics = [
                {
                    'MetricName': 'ResponseTime',
                    'Timestamp': current_time,
                    'Value': response_time_ms,
                    'Unit': 'Milliseconds'
                }
            ]
            
            # Send metrics asynchronously to avoid blocking
            threading.Thread(
                target=self._send_metrics,
                args=(metrics,),
                daemon=True
            ).start()
            
            # Create local record for fallback
            if self.local_file_fallback:
                response_time_record = {
                    "id": str(uuid.uuid4()),
                    "timestamp": current_time.isoformat(),
                    "response_time_ms": response_time_ms
                }
                
                # Save to local file asynchronously
                threading.Thread(
                    target=self._save_response_time_to_local_file,
                    args=(response_time_record,),
                    daemon=True
                ).start()
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error tracking response time: {str(e)}", exc_info=True)
            return False
    
    def track_user_activity(self, user_id: str, activity_type: Union[str, UserActivity]) -> bool:
        """
        Track a user activity event.
        
        Args:
            user_id: Unique identifier for the user
            activity_type: Type of activity (e.g., 'new_conversation', 'reset')
            
        Returns:
            Boolean indicating success or failure
            
        Required by:
            None (called by external components)
            
        Requires:
            - _send_metrics
        """
        try:
            current_time = datetime.now()
            
            # Convert to string if it's an enum
            if isinstance(activity_type, UserActivity):
                activity_type_str = activity_type.value
            else:
                activity_type_str = activity_type
            
            # Create metrics data
            metrics = [
                {
                    'MetricName': 'UserActivity',
                    'Timestamp': current_time,
                    'Value': 1,
                    'Unit': 'Count',
                    'Dimensions': [
                        {
                            'Name': 'UserId',
                            'Value': user_id
                        },
                        {
                            'Name': 'ActivityType',
                            'Value': activity_type_str
                        }
                    ]
                }
            ]
            
            # Send metrics asynchronously to avoid blocking
            threading.Thread(
                target=self._send_metrics,
                args=(metrics,),
                daemon=True
            ).start()
            
            # Create local record for fallback
            if self.local_file_fallback:
                activity_record = {
                    "id": str(uuid.uuid4()),
                    "timestamp": current_time.isoformat(),
                    "user_id": user_id,
                    "activity_type": activity_type_str
                }
                
                # Save to local file asynchronously
                threading.Thread(
                    target=self._save_user_activity_to_local_file,
                    args=(activity_record,),
                    daemon=True
                ).start()
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error tracking user activity: {str(e)}", exc_info=True)
            return False
    
    def get_engagement_metrics(self, 
                             start_time: datetime, 
                             end_time: Optional[datetime] = None,
                             metric_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get engagement metrics for a time period.
        
        Args:
            start_time: Start time for the metrics
            end_time: Optional end time (defaults to now)
            metric_names: Optional list of specific metrics to retrieve
            
        Returns:
            Dictionary of metrics data
            
        Required by:
            None (called by external components)
            
        Requires:
            None
        """
        if end_time is None:
            end_time = datetime.now()
        
        # Define default metric names if not provided
        if metric_names is None:
            metric_names = [
                'ConversationMessageCount',
                'ConversationDuration',
                'ResponseTime',
                'UserActivity'
            ]
        
        # If CloudWatch is available, use it
        if self.use_cloudwatch:
            try:
                # Initialize results dictionary
                results = {
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'metrics': {},
                    'source': 'cloudwatch'
                }
                
                # Get metrics for each metric name
                for metric_name in metric_names:
                    # Build the query parameters
                    params = {
                        'Namespace': self.namespace,
                        'MetricName': metric_name,
                        'StartTime': start_time,
                        'EndTime': end_time,
                        'Period': 3600,  # 1 hour
                        'Statistics': ['Sum', 'Average', 'Maximum', 'Minimum']
                    }
                    
                    # Get metrics from CloudWatch
                    response = self.cloudwatch.get_metric_statistics(**params)
                    
                    # Add to results
                    results['metrics'][metric_name] = response['Datapoints']
                
                return results
            
            except Exception as e:
                self.logger.error(f"Error getting engagement metrics from CloudWatch: {str(e)}", exc_info=True)
                # Fall back to local file if enabled
                if not self.local_file_fallback:
                    return {
                        'start_time': start_time.isoformat(),
                        'end_time': end_time.isoformat(),
                        'metrics': {},
                        'error': str(e),
                        'source': 'cloudwatch_error'
                    }
        
        # Use local file fallback
        if self.local_file_fallback:
            try:
                # Read the local file
                with open(self.local_file_path, 'r') as f:
                    data = json.load(f)
                
                # Initialize results
                results = {
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'metrics': {},
                    'source': 'local_file'
                }
                
                # Process conversations data if requested
                if 'ConversationMessageCount' in metric_names or 'ConversationDuration' in metric_names:
                    # Filter conversations by time range
                    filtered_conversations = []
                    for conv in data.get('conversations', []):
                        conv_time = datetime.fromisoformat(conv['timestamp'])
                        if start_time <= conv_time <= end_time:
                            filtered_conversations.append(conv)
                    
                    # Calculate conversation metrics
                    if filtered_conversations:
                        avg_message_count = sum(c['message_count'] for c in filtered_conversations) / len(filtered_conversations)
                        avg_duration = sum(c['duration_seconds'] for c in filtered_conversations) / len(filtered_conversations)
                        max_message_count = max(c['message_count'] for c in filtered_conversations)
                        max_duration = max(c['duration_seconds'] for c in filtered_conversations)
                        
                        # Add to results
                        if 'ConversationMessageCount' in metric_names:
                            results['metrics']['ConversationMessageCount'] = {
                                'count': len(filtered_conversations),
                                'average': avg_message_count,
                                'maximum': max_message_count,
                                'total': sum(c['message_count'] for c in filtered_conversations)
                            }
                        
                        if 'ConversationDuration' in metric_names:
                            results['metrics']['ConversationDuration'] = {
                                'count': len(filtered_conversations),
                                'average': avg_duration,
                                'maximum': max_duration,
                                'total': sum(c['duration_seconds'] for c in filtered_conversations)
                            }
                
                # Process response times data if requested
                if 'ResponseTime' in metric_names:
                    # Filter response times by time range
                    filtered_response_times = []
                    for rt in data.get('response_times', []):
                        rt_time = datetime.fromisoformat(rt['timestamp'])
                        if start_time <= rt_time <= end_time:
                            filtered_response_times.append(rt)
                    
                    # Calculate response time metrics
                    if filtered_response_times:
                        response_times = [rt['response_time_ms'] for rt in filtered_response_times]
                        avg_response_time = sum(response_times) / len(response_times)
                        max_response_time = max(response_times)
                        min_response_time = min(response_times)
                        
                        # Add to results
                        results['metrics']['ResponseTime'] = {
                            'count': len(filtered_response_times),
                            'average': avg_response_time,
                            'maximum': max_response_time,
                            'minimum': min_response_time
                        }
                
                # Process user activities data if requested
                if 'UserActivity' in metric_names:
                    # Filter user activities by time range
                    filtered_activities = []
                    for activity in data.get('user_activities', []):
                        activity_time = datetime.fromisoformat(activity['timestamp'])
                        if start_time <= activity_time <= end_time:
                            filtered_activities.append(activity)
                    
                    # Group by activity type
                    activity_counts = {}
                    for activity in filtered_activities:
                        activity_type = activity['activity_type']
                        if activity_type not in activity_counts:
                            activity_counts[activity_type] = 0
                        activity_counts[activity_type] += 1
                    
                    # Group by user
                    user_counts = {}
                    for activity in filtered_activities:
                        user_id = activity['user_id']
                        if user_id not in user_counts:
                            user_counts[user_id] = 0
                        user_counts[user_id] += 1
                    
                    # Add to results
                    results['metrics']['UserActivity'] = {
                        'count': len(filtered_activities),
                        'by_activity_type': activity_counts,
                        'by_user': user_counts,
                        'unique_users': len(user_counts)
                    }
                
                return results
            
            except Exception as e:
                self.logger.error(f"Error getting engagement metrics from local file: {str(e)}", exc_info=True)
                return {
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'metrics': {},
                    'error': str(e),
                    'source': 'local_file_error'
                }
        
        # If no data sources are available, return empty metrics
        return {
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'metrics': {},
            'source': 'no_data_source'
        }
    
    def _send_metrics(self, metrics: List[Dict[str, Any]]) -> bool:
        """
        Send metrics to CloudWatch.
        
        Args:
            metrics: List of metric data dictionaries
            
        Returns:
            Boolean indicating success or failure
            
        Required by:
            - track_conversation
            - track_response_time
            - track_user_activity
            
        Requires:
            None
        """
        if not self.use_cloudwatch:
            return False
        
        try:
            # Send metrics to CloudWatch
            response = self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=metrics
            )
            
            self.logger.debug(f"Successfully sent engagement metrics to CloudWatch: {response}")
            return True
        
        except ClientError as e:
            self.logger.error(f"Error sending engagement metrics to CloudWatch: {str(e)}", exc_info=True)
            return False
        
        except Exception as e:
            self.logger.error(f"Unexpected error sending engagement metrics to CloudWatch: {str(e)}", exc_info=True)
            return False
    
    def _save_conversation_to_local_file(self, conversation_record: Dict[str, Any]) -> bool:
        """
        Save a conversation record to the local file.
        
        Args:
            conversation_record: Conversation record dictionary
            
        Returns:
            Boolean indicating success or failure
            
        Required by:
            - track_conversation
            
        Requires:
            None
        """
        try:
            # Load existing data
            with open(self.local_file_path, 'r') as f:
                data = json.load(f)
            
            # Add new record
            if 'conversations' not in data:
                data['conversations'] = []
            
            data['conversations'].append(conversation_record)
            data['last_updated'] = datetime.now().isoformat()
            
            # Save updated data
            with open(self.local_file_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error saving conversation to local file: {str(e)}", exc_info=True)
            return False
    
    def _save_response_time_to_local_file(self, response_time_record: Dict[str, Any]) -> bool:
        """
        Save a response time record to the local file.
        
        Args:
            response_time_record: Response time record dictionary
            
        Returns:
            Boolean indicating success or failure
            
        Required by:
            - track_response_time
            
        Requires:
            None
        """
        try:
            # Load existing data
            with open(self.local_file_path, 'r') as f:
                data = json.load(f)
            
            # Add new record
            if 'response_times' not in data:
                data['response_times'] = []
            
            data['response_times'].append(response_time_record)
            data['last_updated'] = datetime.now().isoformat()
            
            # Save updated data
            with open(self.local_file_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error saving response time to local file: {str(e)}", exc_info=True)
            return False
    
    def _save_user_activity_to_local_file(self, activity_record: Dict[str, Any]) -> bool:
        """
        Save a user activity record to the local file.
        
        Args:
            activity_record: User activity record dictionary
            
        Returns:
            Boolean indicating success or failure
            
        Required by:
            - track_user_activity
            
        Requires:
            None
        """
        try:
            # Load existing data
            with open(self.local_file_path, 'r') as f:
                data = json.load(f)
            
            # Add new record
            if 'user_activities' not in data:
                data['user_activities'] = []
            
            data['user_activities'].append(activity_record)
            data['last_updated'] = datetime.now().isoformat()
            
            # Save updated data
            with open(self.local_file_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error saving user activity to local file: {str(e)}", exc_info=True)
            return False