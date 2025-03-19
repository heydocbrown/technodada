"""
Cost monitoring and tracking.
"""
from typing import Dict, Any, List, Optional
import logging
import os
import json
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError
import threading
from pathlib import Path


class CostTracker:
    """
    Tracker for cost monitoring.
    """
    
    def __init__(self, namespace: str = "DadaCatTwilio", region: str = "us-east-1",
                 local_file_fallback: bool = True, local_file_path: Optional[str] = None):
        """
        Initialize the cost tracker.
        
        Args:
            namespace: CloudWatch namespace
            region: AWS region
            local_file_fallback: Whether to use local file fallback if CloudWatch is unavailable
            local_file_path: Path to local file for metrics (defaults to ./metrics/costs.json)
            
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
                self.local_file_path = Path('./metrics/costs.json')
            
            # Create directory if it doesn't exist
            self.local_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create file if it doesn't exist
            if not self.local_file_path.exists():
                with open(self.local_file_path, 'w') as f:
                    json.dump({
                        "costs": [],
                        "last_updated": datetime.now().isoformat()
                    }, f)
    
    def track_api_cost(self, 
                     api_name: str, 
                     cost_estimate: float,
                     request_count: int = 1,
                     request_tokens: Optional[int] = None) -> bool:
        """
        Track an API cost.
        
        Args:
            api_name: Name of the API (e.g., 'openai', 'twilio')
            cost_estimate: Estimated cost in USD
            request_count: Number of requests
            request_tokens: Optional token count for token-based APIs
            
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
                    'MetricName': 'Cost',
                    'Timestamp': current_time,
                    'Value': cost_estimate,
                    'Unit': 'None',
                    'Dimensions': [
                        {
                            'Name': 'APIName',
                            'Value': api_name
                        }
                    ]
                },
                {
                    'MetricName': 'RequestCount',
                    'Timestamp': current_time,
                    'Value': request_count,
                    'Unit': 'Count',
                    'Dimensions': [
                        {
                            'Name': 'APIName',
                            'Value': api_name
                        }
                    ]
                }
            ]
            
            # Add token count metric if provided
            if request_tokens is not None:
                metrics.append({
                    'MetricName': 'TokenCount',
                    'Timestamp': current_time,
                    'Value': request_tokens,
                    'Unit': 'Count',
                    'Dimensions': [
                        {
                            'Name': 'APIName',
                            'Value': api_name
                        }
                    ]
                })
            
            # Send metrics asynchronously to avoid blocking
            threading.Thread(
                target=self._send_metrics,
                args=(metrics,),
                daemon=True
            ).start()
            
            # Create local record for fallback
            if self.local_file_fallback:
                cost_record = {
                    "timestamp": current_time.isoformat(),
                    "api_name": api_name,
                    "cost_estimate": cost_estimate,
                    "request_count": request_count,
                    "request_tokens": request_tokens
                }
                
                # Save to local file asynchronously
                threading.Thread(
                    target=self._save_to_local_file,
                    args=(cost_record,),
                    daemon=True
                ).start()
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error tracking API cost: {str(e)}", exc_info=True)
            return False
    
    def get_cost_metrics(self, 
                       start_time: datetime, 
                       end_time: Optional[datetime] = None,
                       api_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get cost metrics for a time period.
        
        Args:
            start_time: Start time for the metrics
            end_time: Optional end time (defaults to now)
            api_names: Optional list of specific APIs to retrieve costs for
            
        Returns:
            Dictionary of cost metrics data
            
        Required by:
            None (called by external components)
            
        Requires:
            None
        """
        if end_time is None:
            end_time = datetime.now()
        
        # If CloudWatch is available, use it
        if self.use_cloudwatch:
            try:
                # Build the query parameters
                params = {
                    'Namespace': self.namespace,
                    'MetricName': 'Cost',
                    'StartTime': start_time,
                    'EndTime': end_time,
                    'Period': 3600,  # 1 hour
                    'Statistics': ['Sum', 'Average']
                }
                
                # Add dimensions filter for API names if provided
                if api_names:
                    dimensions = []
                    for api_name in api_names:
                        dimensions.append({
                            'Name': 'APIName',
                            'Value': api_name
                        })
                    params['Dimensions'] = dimensions
                
                # Get metrics from CloudWatch
                response = self.cloudwatch.get_metric_statistics(**params)
                
                # Format the response
                results = {
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'api_names': api_names,
                    'metrics': response['Datapoints'],
                    'source': 'cloudwatch'
                }
                
                return results
            
            except Exception as e:
                self.logger.error(f"Error getting cost metrics from CloudWatch: {str(e)}", exc_info=True)
                # Fall back to local file if enabled
                if not self.local_file_fallback:
                    return {
                        'start_time': start_time.isoformat(),
                        'end_time': end_time.isoformat(),
                        'api_names': api_names,
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
                
                costs = data.get('costs', [])
                
                # Filter by time range
                filtered_costs = []
                for cost in costs:
                    cost_time = datetime.fromisoformat(cost['timestamp'])
                    if start_time <= cost_time <= end_time:
                        # Filter by API name if provided
                        if api_names is None or cost['api_name'] in api_names:
                            filtered_costs.append(cost)
                
                # Calculate summary metrics
                total_cost = sum(c['cost_estimate'] for c in filtered_costs)
                total_requests = sum(c['request_count'] for c in filtered_costs)
                
                # Group by API name
                api_costs = {}
                for cost in filtered_costs:
                    api_name = cost['api_name']
                    if api_name not in api_costs:
                        api_costs[api_name] = {
                            'total_cost': 0,
                            'total_requests': 0,
                            'records': []
                        }
                    
                    api_costs[api_name]['total_cost'] += cost['cost_estimate']
                    api_costs[api_name]['total_requests'] += cost['request_count']
                    api_costs[api_name]['records'].append(cost)
                
                return {
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'api_names': api_names,
                    'total_cost': total_cost,
                    'total_requests': total_requests,
                    'api_costs': api_costs,
                    'source': 'local_file'
                }
            
            except Exception as e:
                self.logger.error(f"Error getting cost metrics from local file: {str(e)}", exc_info=True)
                return {
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'api_names': api_names,
                    'metrics': [],
                    'error': str(e),
                    'source': 'local_file_error'
                }
        
        # If no data sources are available, return empty metrics
        return {
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'api_names': api_names,
            'metrics': [],
            'source': 'no_data_source'
        }
    
    def get_total_cost(self, 
                     start_time: datetime, 
                     end_time: Optional[datetime] = None) -> float:
        """
        Get the total cost for a time period.
        
        Args:
            start_time: Start time for the metrics
            end_time: Optional end time (defaults to now)
            
        Returns:
            Total cost in USD
            
        Required by:
            None (called by external components)
            
        Requires:
            - get_cost_metrics
        """
        # Get cost metrics
        metrics = self.get_cost_metrics(start_time, end_time)
        
        # Extract total cost based on source
        if metrics['source'] == 'cloudwatch':
            # Sum up all the datapoints
            return sum(dp['Sum'] for dp in metrics['metrics']) if metrics['metrics'] else 0.0
        elif metrics['source'] == 'local_file':
            # Return the calculated total
            return metrics.get('total_cost', 0.0)
        else:
            # No data available
            return 0.0
    
    def _send_metrics(self, metrics: List[Dict[str, Any]]) -> bool:
        """
        Send metrics to CloudWatch.
        
        Args:
            metrics: List of metric data dictionaries
            
        Returns:
            Boolean indicating success or failure
            
        Required by:
            - track_api_cost
            
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
            
            self.logger.debug(f"Successfully sent metrics to CloudWatch: {response}")
            return True
        
        except ClientError as e:
            self.logger.error(f"Error sending metrics to CloudWatch: {str(e)}", exc_info=True)
            return False
        
        except Exception as e:
            self.logger.error(f"Unexpected error sending metrics to CloudWatch: {str(e)}", exc_info=True)
            return False
    
    def _save_to_local_file(self, cost_record: Dict[str, Any]) -> bool:
        """
        Save a cost record to the local file.
        
        Args:
            cost_record: Cost record dictionary
            
        Returns:
            Boolean indicating success or failure
            
        Required by:
            - track_api_cost
            
        Requires:
            None
        """
        try:
            # Load existing data
            with open(self.local_file_path, 'r') as f:
                data = json.load(f)
            
            # Add new record
            data['costs'].append(cost_record)
            data['last_updated'] = datetime.now().isoformat()
            
            # Save updated data
            with open(self.local_file_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error saving to local file: {str(e)}", exc_info=True)
            return False