"""
Error tracking and analysis.
"""
from typing import Dict, Any, List, Optional, Union
import logging
import os
import json
import traceback
import time
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError
import threading
from pathlib import Path
import uuid
from enum import Enum


class ErrorCategory(Enum):
    """
    Enum representing error categories.
    """
    API_ERROR = "api_error"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    INTERNAL = "internal"
    PROCESSING_ERROR = "processing_error"
    UNKNOWN = "unknown"


class ErrorTracker:
    """
    Tracker for error metrics and analysis.
    """
    
    def __init__(self, namespace: str = "DadaCatTwilio", region: str = "us-east-1",
                local_file_fallback: bool = True, local_file_path: Optional[str] = None):
        """
        Initialize the error tracker.
        
        Args:
            namespace: CloudWatch namespace
            region: AWS region
            local_file_fallback: Whether to use local file fallback if CloudWatch is unavailable
            local_file_path: Path to local file for error logs (defaults to ./metrics/errors.json)
            
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
                self.logs_client = boto3.client(
                    'logs',
                    region_name=region,
                    endpoint_url=self.local_endpoint,
                    aws_access_key_id='fakeAccessKeyId',
                    aws_secret_access_key='fakeSecretAccessKey'
                )
            else:
                self.cloudwatch = boto3.client('cloudwatch', region_name=region)
                self.logs_client = boto3.client('logs', region_name=region)
            
            self.use_cloudwatch = True
            
        except Exception as e:
            self.logger.warning(f"Failed to initialize AWS clients: {str(e)}")
            self.use_cloudwatch = False
        
        # Set up local file fallback
        if local_file_fallback:
            if local_file_path:
                self.local_file_path = Path(local_file_path)
            else:
                self.local_file_path = Path('./metrics/errors.json')
            
            # Create directory if it doesn't exist
            self.local_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create file if it doesn't exist
            if not self.local_file_path.exists():
                with open(self.local_file_path, 'w') as f:
                    json.dump({
                        "errors": [],
                        "last_updated": datetime.now().isoformat()
                    }, f)
        
        # Set up log group name
        self.log_group_name = f"/dadacat-twilio/{namespace}/errors"
    
    def track_error(self, 
                   error_type: str, 
                   error_message: str, 
                   category: Union[ErrorCategory, str] = ErrorCategory.UNKNOWN,
                   context: Optional[Dict[str, Any]] = None,
                   exception: Optional[Exception] = None) -> bool:
        """
        Track an error occurrence.
        
        Args:
            error_type: Type of error
            error_message: Error message
            category: Error category
            context: Optional context information
            exception: Optional exception object
            
        Returns:
            Boolean indicating success or failure
            
        Required by:
            None (called by external components)
            
        Requires:
            - _send_metrics
            - _log_error
        """
        try:
            current_time = datetime.now()
            
            # Convert to enum value if string is provided
            if isinstance(category, str):
                try:
                    category = ErrorCategory(category)
                except ValueError:
                    category = ErrorCategory.UNKNOWN
            
            # Add stacktrace if exception is provided
            if exception is not None:
                stack_trace = traceback.format_exception(type(exception), exception, exception.__traceback__)
                if context is None:
                    context = {}
                context['stack_trace'] = stack_trace
            
            # Create metrics data
            metrics = [
                {
                    'MetricName': 'ErrorCount',
                    'Timestamp': current_time,
                    'Value': 1,
                    'Unit': 'Count',
                    'Dimensions': [
                        {
                            'Name': 'ErrorCategory',
                            'Value': category.value
                        },
                        {
                            'Name': 'ErrorType',
                            'Value': error_type
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
            
            # Log error (to CloudWatch Logs or local file)
            threading.Thread(
                target=self._log_error,
                args=(error_type, error_message, category, context),
                daemon=True
            ).start()
            
            # Create local record for fallback
            if self.local_file_fallback:
                error_record = {
                    "id": str(uuid.uuid4()),
                    "timestamp": current_time.isoformat(),
                    "error_type": error_type,
                    "error_message": error_message,
                    "category": category.value,
                    "context": context
                }
                
                # Save to local file asynchronously
                threading.Thread(
                    target=self._save_to_local_file,
                    args=(error_record,),
                    daemon=True
                ).start()
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error in track_error: {str(e)}", exc_info=True)
            return False
    
    def get_error_metrics(self, 
                        start_time: datetime, 
                        end_time: Optional[datetime] = None,
                        categories: Optional[List[Union[ErrorCategory, str]]] = None) -> Dict[str, Any]:
        """
        Get error metrics for a time period.
        
        Args:
            start_time: Start time for the metrics
            end_time: Optional end time (defaults to now)
            categories: Optional list of specific error categories to retrieve
            
        Returns:
            Dictionary of error metrics data
            
        Required by:
            None (called by external components)
            
        Requires:
            None
        """
        if end_time is None:
            end_time = datetime.now()
        
        # Convert string categories to enum values
        category_enums = None
        if categories is not None:
            category_enums = []
            for cat in categories:
                if isinstance(cat, str):
                    try:
                        category_enums.append(ErrorCategory(cat))
                    except ValueError:
                        # Skip invalid categories
                        pass
                else:
                    category_enums.append(cat)
            
            # Convert enums to values for filtering
            categories = [cat.value for cat in category_enums]
        
        # If CloudWatch is available, use it
        if self.use_cloudwatch:
            try:
                # Build the query parameters
                params = {
                    'Namespace': self.namespace,
                    'MetricName': 'ErrorCount',
                    'StartTime': start_time,
                    'EndTime': end_time,
                    'Period': 3600,  # 1 hour
                    'Statistics': ['Sum']
                }
                
                # Add dimensions filter for categories if provided
                if categories:
                    dimensions = []
                    for category in categories:
                        dimensions.append({
                            'Name': 'ErrorCategory',
                            'Value': category
                        })
                    params['Dimensions'] = dimensions
                
                # Get metrics from CloudWatch
                response = self.cloudwatch.get_metric_statistics(**params)
                
                # Format the response
                results = {
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'categories': categories,
                    'metrics': response['Datapoints'],
                    'source': 'cloudwatch'
                }
                
                # Try to get error details from CloudWatch Logs
                if self.use_cloudwatch:
                    try:
                        # Ensure log group exists
                        try:
                            self.logs_client.create_log_group(logGroupName=self.log_group_name)
                        except ClientError as e:
                            # Ignore if log group already exists
                            if 'ResourceAlreadyExistsException' not in str(e):
                                raise
                        
                        # Define query
                        query = f"fields @timestamp, error_type, error_message, category"
                        if categories:
                            category_clause = ' or '.join([f"category = '{cat}'" for cat in categories])
                            query += f" | filter {category_clause}"
                        
                        # Convert times to milliseconds since epoch
                        start_time_ms = int(start_time.timestamp() * 1000)
                        end_time_ms = int(end_time.timestamp() * 1000)
                        
                        # Start query
                        query_response = self.logs_client.start_query(
                            logGroupName=self.log_group_name,
                            startTime=start_time_ms,
                            endTime=end_time_ms,
                            queryString=query
                        )
                        
                        # Get query results (with timeout)
                        query_id = query_response['queryId']
                        query_status = None
                        for _ in range(10):  # try up to 10 times, with a 1-second delay
                            query_result = self.logs_client.get_query_results(queryId=query_id)
                            query_status = query_result['status']
                            
                            if query_status in ['Complete', 'Failed', 'Cancelled']:
                                results['log_entries'] = query_result['results']
                                break
                            
                            # Wait a second before trying again
                            time.sleep(1)
                        
                        # If query didn't complete, log but continue
                        if query_status != 'Complete':
                            self.logger.warning(f"CloudWatch Logs query did not complete: {query_status}")
                    
                    except Exception as e:
                        self.logger.error(f"Error querying CloudWatch Logs: {str(e)}", exc_info=True)
                
                return results
            
            except Exception as e:
                self.logger.error(f"Error getting error metrics from CloudWatch: {str(e)}", exc_info=True)
                # Fall back to local file if enabled
                if not self.local_file_fallback:
                    return {
                        'start_time': start_time.isoformat(),
                        'end_time': end_time.isoformat(),
                        'categories': categories,
                        'metrics': [],
                        'error': str(e),
                        'source': 'cloudwatch_error'
                    }
        
        # Use local file fallback
        if self.local_file_fallback:
            try:
                # Read the local file
                with open(self.local_file_path, 'r') as f:
                    data = json.load(f)
                
                errors = data.get('errors', [])
                
                # Filter by time range
                filtered_errors = []
                for error in errors:
                    error_time = datetime.fromisoformat(error['timestamp'])
                    if start_time <= error_time <= end_time:
                        # Filter by category if provided
                        if categories is None or error['category'] in categories:
                            filtered_errors.append(error)
                
                # Group by category and type
                error_counts = {}
                for error in filtered_errors:
                    category = error['category']
                    error_type = error['error_type']
                    
                    if category not in error_counts:
                        error_counts[category] = {'total': 0, 'by_type': {}}
                    
                    error_counts[category]['total'] += 1
                    
                    if error_type not in error_counts[category]['by_type']:
                        error_counts[category]['by_type'][error_type] = 0
                    
                    error_counts[category]['by_type'][error_type] += 1
                
                return {
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'categories': categories,
                    'total_errors': len(filtered_errors),
                    'error_counts': error_counts,
                    'errors': filtered_errors,
                    'source': 'local_file'
                }
            
            except Exception as e:
                self.logger.error(f"Error getting error metrics from local file: {str(e)}", exc_info=True)
                return {
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'categories': categories,
                    'metrics': [],
                    'error': str(e),
                    'source': 'local_file_error'
                }
        
        # If no data sources are available, return empty metrics
        return {
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'categories': categories,
            'metrics': [],
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
            - track_error
            
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
            
            self.logger.debug(f"Successfully sent error metrics to CloudWatch: {response}")
            return True
        
        except ClientError as e:
            self.logger.error(f"Error sending error metrics to CloudWatch: {str(e)}", exc_info=True)
            return False
        
        except Exception as e:
            self.logger.error(f"Unexpected error sending error metrics to CloudWatch: {str(e)}", exc_info=True)
            return False
    
    def _log_error(self, 
                  error_type: str, 
                  error_message: str, 
                  category: ErrorCategory,
                  context: Optional[Dict[str, Any]]) -> None:
        """
        Log an error to CloudWatch Logs.
        
        Args:
            error_type: Type of error
            error_message: Error message
            category: Error category
            context: Optional context information
            
        Returns:
            None
            
        Required by:
            - track_error
            
        Requires:
            None
        """
        # Prepare log entry
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'error_type': error_type,
            'error_message': error_message,
            'category': category.value
        }
        
        # Add context if provided
        if context:
            # Make sure context is serializable
            serializable_context = {}
            for key, value in context.items():
                try:
                    # Try to serialize the value to check if it's JSON-compatible
                    json.dumps(value)
                    serializable_context[key] = value
                except (TypeError, OverflowError):
                    # If it can't be serialized, convert to string
                    serializable_context[key] = str(value)
            
            log_entry['context'] = serializable_context
        
        # Log to CloudWatch Logs if available
        if self.use_cloudwatch:
            try:
                # Ensure log group exists
                try:
                    self.logs_client.create_log_group(logGroupName=self.log_group_name)
                except ClientError as e:
                    # Ignore if log group already exists
                    if 'ResourceAlreadyExistsException' not in str(e):
                        raise
                
                # Ensure log stream exists (use date-based stream names)
                log_stream_name = datetime.now().strftime('%Y/%m/%d')
                try:
                    self.logs_client.create_log_stream(
                        logGroupName=self.log_group_name,
                        logStreamName=log_stream_name
                    )
                except ClientError as e:
                    # Ignore if stream already exists
                    if 'ResourceAlreadyExistsException' not in str(e):
                        raise
                
                # Put log event
                self.logs_client.put_log_events(
                    logGroupName=self.log_group_name,
                    logStreamName=log_stream_name,
                    logEvents=[
                        {
                            'timestamp': int(datetime.now().timestamp() * 1000),
                            'message': json.dumps(log_entry)
                        }
                    ]
                )
                
                self.logger.debug(f"Successfully logged error to CloudWatch Logs")
            
            except Exception as e:
                self.logger.error(f"Error logging to CloudWatch Logs: {str(e)}", exc_info=True)
        
        # Log to local system logger as well
        log_message = f"ERROR [{category.value}] {error_type}: {error_message}"
        if context:
            log_message += f" | Context: {context}"
        
        self.logger.error(log_message)
    
    def _save_to_local_file(self, error_record: Dict[str, Any]) -> bool:
        """
        Save an error record to the local file.
        
        Args:
            error_record: Error record dictionary
            
        Returns:
            Boolean indicating success or failure
            
        Required by:
            - track_error
            
        Requires:
            None
        """
        try:
            # Load existing data
            with open(self.local_file_path, 'r') as f:
                data = json.load(f)
            
            # Add new record
            if 'errors' not in data:
                data['errors'] = []
            
            data['errors'].append(error_record)
            data['last_updated'] = datetime.now().isoformat()
            
            # Save updated data
            with open(self.local_file_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error saving to local file: {str(e)}", exc_info=True)
            return False