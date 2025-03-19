"""
Admin notification system for critical failures.
"""
from typing import Dict, Any, List, Optional, Union
import logging
import json
import time
import os
from datetime import datetime
from enum import Enum
import boto3
from botocore.exceptions import ClientError


class ErrorSeverity(Enum):
    """
    Enum representing error severity levels.
    """
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class NotificationChannel(Enum):
    """
    Enum representing notification channels.
    """
    SNS = "sns"
    EMAIL = "email"
    SMS = "sms"
    SLACK = "slack"
    LOGGING = "logging"  # Local development mode, just logs messages


class AdminNotifier:
    """
    System for sending notifications about errors to administrators.
    """
    
    def __init__(self, 
                sns_topic_arn: Optional[str] = None, 
                region: str = "us-east-1",
                channel: Optional[NotificationChannel] = None,
                admin_email: Optional[str] = None,
                admin_phone: Optional[str] = None,
                slack_webhook_url: Optional[str] = None,
                throttle_period: int = 300):  # 5 minutes
        """
        Initialize the admin notifier.
        
        Args:
            sns_topic_arn: AWS SNS topic ARN (required for SNS channel)
            region: AWS region
            channel: Notification channel to use
            admin_email: Admin email address (required for EMAIL channel)
            admin_phone: Admin phone number (required for SMS channel)
            slack_webhook_url: Slack webhook URL (required for SLACK channel)
            throttle_period: Seconds between similar notifications (prevent alert spam)
            
        Returns:
            None
            
        Required by:
            None (called during initialization)
        """
        self.sns_topic_arn = sns_topic_arn or os.getenv('SNS_TOPIC_ARN')
        self.region = region
        self.admin_email = admin_email or os.getenv('ADMIN_EMAIL')
        self.admin_phone = admin_phone or os.getenv('ADMIN_PHONE')
        self.slack_webhook_url = slack_webhook_url or os.getenv('SLACK_WEBHOOK_URL')
        self.throttle_period = throttle_period
        self.logger = logging.getLogger(__name__)
        
        # Determine channel based on available configurations
        if channel is not None:
            self.channel = channel
        elif self.sns_topic_arn:
            self.channel = NotificationChannel.SNS
        elif self.admin_email:
            self.channel = NotificationChannel.EMAIL
        elif self.admin_phone:
            self.channel = NotificationChannel.SMS
        elif self.slack_webhook_url:
            self.channel = NotificationChannel.SLACK
        else:
            # Default to logging-only mode if no other channels are configured
            self.channel = NotificationChannel.LOGGING
            self.logger.info("No notification channels configured, using logging-only mode")
        
        # Dictionary to store the last notification time for each error type
        # Used to prevent notification flooding
        self.last_notification_time: Dict[str, float] = {}
        
        # Initialize AWS SNS client if using SNS
        if self.channel == NotificationChannel.SNS and self.sns_topic_arn:
            try:
                self.sns_client = boto3.client('sns', region_name=self.region)
                self.logger.info(f"Initialized SNS client for topic: {self.sns_topic_arn}")
            except Exception as e:
                self.logger.warning(f"Failed to initialize SNS client: {str(e)}")
                self.channel = NotificationChannel.LOGGING  # Fall back to logging
    
    def send_notification(self, 
                         message: str, 
                         details: Dict[str, Any], 
                         severity: Union[ErrorSeverity, str] = ErrorSeverity.ERROR,
                         error_type: Optional[str] = None) -> bool:
        """
        Send a notification to administrators.
        
        Args:
            message: Brief message describing the error
            details: Detailed information about the error
            severity: Error severity level
            error_type: Type of error for throttling similar errors
            
        Returns:
            Boolean indicating success or failure
            
        Required by:
            None (called by external components)
            
        Requires:
            - _format_notification
        """
        # Convert string severity to enum if necessary
        if isinstance(severity, str):
            try:
                severity = ErrorSeverity(severity)
            except ValueError:
                self.logger.warning(f"Invalid severity '{severity}', defaulting to ERROR")
                severity = ErrorSeverity.ERROR
        
        # Check if we should throttle this notification
        if error_type and not self._should_send_notification(error_type):
            self.logger.info(f"Throttling notification for error type '{error_type}'")
            return False
        
        # Format the notification
        notification = self._format_notification(message, details, severity)
        
        try:
            # Send based on the selected channel
            if self.channel == NotificationChannel.SNS:
                if not self.sns_topic_arn:
                    self.logger.error("SNS topic ARN is required for SNS notifications")
                    return False
                
                response = self.sns_client.publish(
                    TopicArn=self.sns_topic_arn,
                    Message=json.dumps(notification),
                    Subject=f"DadaCat {severity.value.upper()}: {message[:40]}..."
                )
                
                # Update last notification time
                if error_type:
                    self.last_notification_time[error_type] = time.time()
                
                self.logger.info(f"Sent notification via SNS: {response.get('MessageId')}")
                return True
                
            elif self.channel == NotificationChannel.EMAIL:
                if not self.admin_email:
                    self.logger.error("Admin email is required for EMAIL notifications")
                    return False
                
                # Simplified email sending for demonstration - in production, use SES or similar
                self.logger.info(f"Would send email to {self.admin_email}: {message}")
                
                # Update last notification time
                if error_type:
                    self.last_notification_time[error_type] = time.time()
                
                return True
                
            elif self.channel == NotificationChannel.SMS:
                if not self.admin_phone:
                    self.logger.error("Admin phone number is required for SMS notifications")
                    return False
                
                # Simplified SMS sending for demonstration - in production, use SNS Mobile
                self.logger.info(f"Would send SMS to {self.admin_phone}: {message}")
                
                # Update last notification time
                if error_type:
                    self.last_notification_time[error_type] = time.time()
                
                return True
                
            elif self.channel == NotificationChannel.SLACK:
                if not self.slack_webhook_url:
                    self.logger.error("Slack webhook URL is required for SLACK notifications")
                    return False
                
                # Simplified Slack sending for demonstration
                self.logger.info(f"Would send Slack message: {message}")
                
                # Update last notification time
                if error_type:
                    self.last_notification_time[error_type] = time.time()
                
                return True
                
            elif self.channel == NotificationChannel.LOGGING:
                # Logging-only mode for local development
                log_level = logging.INFO
                if severity == ErrorSeverity.WARNING:
                    log_level = logging.WARNING
                elif severity == ErrorSeverity.ERROR:
                    log_level = logging.ERROR
                elif severity == ErrorSeverity.CRITICAL:
                    log_level = logging.CRITICAL
                    
                # Log the notification
                self.logger.log(log_level, f"NOTIFICATION [{severity.value.upper()}]: {message}")
                self.logger.log(log_level, f"DETAILS: {json.dumps(details, indent=2)}")
                
                # Update last notification time
                if error_type:
                    self.last_notification_time[error_type] = time.time()
                    
                return True
                
            else:
                self.logger.error(f"Unsupported notification channel: {self.channel}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending notification: {str(e)}")
            return False
    
    def send_batch_notifications(self, notifications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Send multiple notifications in a batch.
        
        Args:
            notifications: List of notification dictionaries, each with:
                - message: Brief message describing the error
                - details: Detailed information about the error
                - severity: Error severity level (optional)
                - error_type: Type of error for throttling (optional)
            
        Returns:
            Dictionary with results of each notification
            
        Required by:
            None (called by external components)
            
        Requires:
            - send_notification
        """
        results = {
            'total': len(notifications),
            'success': 0,
            'failure': 0,
            'throttled': 0,
            'failures': []
        }
        
        for idx, notification in enumerate(notifications):
            try:
                success = self.send_notification(
                    message=notification.get('message', 'Unknown error'),
                    details=notification.get('details', {}),
                    severity=notification.get('severity', ErrorSeverity.ERROR),
                    error_type=notification.get('error_type')
                )
                
                if success:
                    results['success'] += 1
                else:
                    # Check if it was throttled
                    error_type = notification.get('error_type')
                    if error_type and error_type in self.last_notification_time:
                        results['throttled'] += 1
                    else:
                        results['failure'] += 1
                        results['failures'].append({
                            'index': idx,
                            'message': notification.get('message', 'Unknown error')
                        })
                        
            except Exception as e:
                results['failure'] += 1
                results['failures'].append({
                    'index': idx,
                    'message': notification.get('message', 'Unknown error'),
                    'error': str(e)
                })
                
        return results
    
    def _format_notification(self, 
                           message: str, 
                           details: Dict[str, Any], 
                           severity: ErrorSeverity) -> Dict[str, Any]:
        """
        Format a notification for sending via SNS.
        
        Args:
            message: Brief message describing the error
            details: Detailed information about the error
            severity: Error severity level
            
        Returns:
            Formatted notification dictionary
            
        Required by:
            - send_notification
            
        Requires:
            None
        """
        # Current timestamp
        timestamp = datetime.now().isoformat()
        
        # Create notification object
        notification = {
            'application': 'DadaCat Twilio',
            'environment': os.getenv('ENVIRONMENT', 'development'),
            'timestamp': timestamp,
            'severity': severity.value,
            'message': message,
            'details': details
        }
        
        # Add AWS request ID if available
        aws_request_id = os.getenv('AWS_REQUEST_ID')
        if aws_request_id:
            notification['aws_request_id'] = aws_request_id
            
        return notification
    
    def _should_send_notification(self, error_type: str) -> bool:
        """
        Determine if we should send a notification based on throttling rules.
        
        Args:
            error_type: Type of error for throttling similar errors
            
        Returns:
            Boolean indicating if notification should be sent
            
        Required by:
            - send_notification
            
        Requires:
            None
        """
        # If no throttling period, always send
        if self.throttle_period <= 0:
            return True
            
        # If this error type hasn't been seen, send
        if error_type not in self.last_notification_time:
            return True
            
        # Check if throttle period has elapsed
        current_time = time.time()
        last_time = self.last_notification_time.get(error_type, 0)
        time_elapsed = current_time - last_time
        
        return time_elapsed >= self.throttle_period
    
    def send_health_check_notification(self, is_healthy: bool, details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send a health check notification.
        
        Args:
            is_healthy: Whether the system is healthy
            details: Optional detailed health information
            
        Returns:
            Boolean indicating success or failure
            
        Required by:
            None (called by health check system)
            
        Requires:
            - send_notification
        """
        if details is None:
            details = {}
            
        # Set severity based on health status
        severity = ErrorSeverity.INFO if is_healthy else ErrorSeverity.ERROR
        
        # Create message
        message = "DadaCat Twilio is healthy" if is_healthy else "DadaCat Twilio health check failed"
        
        # Add health status to details
        details['is_healthy'] = is_healthy
        details['timestamp'] = datetime.now().isoformat()
        
        # Send notification
        return self.send_notification(
            message=message,
            details=details,
            severity=severity,
            error_type="health_check" if not is_healthy else None  # Only throttle failures
        )