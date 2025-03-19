"""
Simple dashboard for monitoring metrics.
"""
from typing import Dict, Any, List, Optional, Tuple
import logging
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
import io
import base64

from .costs import CostTracker
from .engagement import EngagementTracker
from .errors import ErrorTracker, ErrorCategory


class MetricsDashboard:
    """
    Dashboard for visualizing DadaCat metrics.
    """
    
    def __init__(self, 
                namespace: str = "DadaCatTwilio", 
                region: str = "us-east-1",
                metrics_dir: Optional[str] = None):
        """
        Initialize the dashboard.
        
        Args:
            namespace: CloudWatch namespace
            region: AWS region
            metrics_dir: Directory to store metrics files (defaults to ./metrics)
            
        Returns:
            None
            
        Required by:
            None (called during initialization)
        """
        self.namespace = namespace
        self.region = region
        
        # Set up metrics directory
        if metrics_dir:
            self.metrics_dir = Path(metrics_dir)
        else:
            self.metrics_dir = Path('./metrics')
        
        # Create directory if it doesn't exist
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize logger
        self.logger = logging.getLogger(__name__)
        
        # Initialize trackers
        self.cost_tracker = CostTracker(
            namespace=namespace, 
            region=region,
            local_file_path=str(self.metrics_dir / 'costs.json')
        )
        
        self.engagement_tracker = EngagementTracker(
            namespace=namespace, 
            region=region,
            local_file_path=str(self.metrics_dir / 'engagement.json')
        )
        
        self.error_tracker = ErrorTracker(
            namespace=namespace, 
            region=region,
            local_file_path=str(self.metrics_dir / 'errors.json')
        )
    
    def generate_cost_metrics(self, days: int = 7) -> Dict[str, Any]:
        """
        Generate cost metrics for the dashboard.
        
        Args:
            days: Number of days to include
            
        Returns:
            Dictionary of cost metrics
            
        Required by:
            - generate_dashboard
            
        Requires:
            - cost_tracker.get_cost_metrics
        """
        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        # Get cost metrics
        metrics = self.cost_tracker.get_cost_metrics(
            start_time=start_time,
            end_time=end_time
        )
        
        # Calculate total cost
        total_cost = self.cost_tracker.get_total_cost(
            start_time=start_time,
            end_time=end_time
        )
        
        # Format metrics for dashboard
        if metrics['source'] == 'local_file':
            return {
                'start_time': metrics['start_time'],
                'end_time': metrics['end_time'],
                'total_cost': total_cost,
                'api_costs': metrics.get('api_costs', {}),
                'total_requests': metrics.get('total_requests', 0),
                'source': metrics['source']
            }
        else:
            # Format CloudWatch metrics
            return {
                'start_time': metrics['start_time'],
                'end_time': metrics['end_time'],
                'total_cost': total_cost,
                'metrics': metrics.get('metrics', []),
                'source': metrics['source']
            }
    
    def generate_engagement_metrics(self, days: int = 7) -> Dict[str, Any]:
        """
        Generate engagement metrics for the dashboard.
        
        Args:
            days: Number of days to include
            
        Returns:
            Dictionary of engagement metrics
            
        Required by:
            - generate_dashboard
            
        Requires:
            - engagement_tracker.get_engagement_metrics
        """
        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        # Get engagement metrics
        metrics = self.engagement_tracker.get_engagement_metrics(
            start_time=start_time,
            end_time=end_time
        )
        
        # Format metrics for dashboard
        return {
            'start_time': metrics['start_time'],
            'end_time': metrics['end_time'],
            'metrics': metrics.get('metrics', {}),
            'source': metrics['source']
        }
    
    def generate_error_metrics(self, days: int = 7) -> Dict[str, Any]:
        """
        Generate error metrics for the dashboard.
        
        Args:
            days: Number of days to include
            
        Returns:
            Dictionary of error metrics
            
        Required by:
            - generate_dashboard
            
        Requires:
            - error_tracker.get_error_metrics
        """
        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        # Get error metrics
        metrics = self.error_tracker.get_error_metrics(
            start_time=start_time,
            end_time=end_time
        )
        
        # Format metrics for dashboard
        if metrics['source'] == 'local_file':
            return {
                'start_time': metrics['start_time'],
                'end_time': metrics['end_time'],
                'total_errors': metrics.get('total_errors', 0),
                'error_counts': metrics.get('error_counts', {}),
                'source': metrics['source']
            }
        else:
            return {
                'start_time': metrics['start_time'],
                'end_time': metrics['end_time'],
                'metrics': metrics.get('metrics', []),
                'source': metrics['source']
            }
    
    def generate_dashboard(self, days: int = 7) -> Dict[str, Any]:
        """
        Generate a complete dashboard with all metrics.
        
        Args:
            days: Number of days to include
            
        Returns:
            Dictionary with all dashboard metrics
            
        Required by:
            None (called by external components)
            
        Requires:
            - generate_cost_metrics
            - generate_engagement_metrics
            - generate_error_metrics
        """
        dashboard = {
            'timestamp': datetime.now().isoformat(),
            'period_days': days,
            'costs': self.generate_cost_metrics(days),
            'engagement': self.generate_engagement_metrics(days),
            'errors': self.generate_error_metrics(days)
        }
        
        return dashboard
    
    def plot_metrics(self, days: int = 7) -> Dict[str, str]:
        """
        Generate plots for metrics and return as base64-encoded strings.
        
        Args:
            days: Number of days to include
            
        Returns:
            Dictionary of base64-encoded plot images
            
        Required by:
            None (called by external components)
            
        Requires:
            - generate_dashboard
            - _plot_cost_metrics
            - _plot_engagement_metrics
            - _plot_error_metrics
        """
        # Generate dashboard data
        dashboard = self.generate_dashboard(days)
        
        # Generate plots
        plots = {}
        
        # Plot cost metrics
        cost_plot = self._plot_cost_metrics(dashboard['costs'])
        if cost_plot:
            plots['costs'] = cost_plot
        
        # Plot engagement metrics
        engagement_plots = self._plot_engagement_metrics(dashboard['engagement'])
        if engagement_plots:
            plots.update(engagement_plots)
        
        # Plot error metrics
        error_plot = self._plot_error_metrics(dashboard['errors'])
        if error_plot:
            plots['errors'] = error_plot
        
        return plots
    
    def save_dashboard(self, days: int = 7, file_path: Optional[str] = None) -> str:
        """
        Save dashboard metrics to a file.
        
        Args:
            days: Number of days to include
            file_path: Path to save the dashboard (defaults to ./metrics/dashboard_YYYY-MM-DD.json)
            
        Returns:
            Path to the saved file
            
        Required by:
            None (called by external components)
            
        Requires:
            - generate_dashboard
        """
        # Generate dashboard
        dashboard = self.generate_dashboard(days)
        
        # Determine file path
        if file_path:
            save_path = Path(file_path)
        else:
            current_date = datetime.now().strftime('%Y-%m-%d')
            save_path = self.metrics_dir / f"dashboard_{current_date}.json"
        
        # Save to file
        with open(save_path, 'w') as f:
            json.dump(dashboard, f, indent=2)
        
        return str(save_path)
    
    def _plot_cost_metrics(self, cost_metrics: Dict[str, Any]) -> Optional[str]:
        """
        Plot cost metrics.
        
        Args:
            cost_metrics: Cost metrics from generate_cost_metrics
            
        Returns:
            Base64-encoded plot image or None if plotting fails
            
        Required by:
            - plot_metrics
            
        Requires:
            None
        """
        try:
            # Check if we have data to plot
            if cost_metrics['source'] == 'local_file':
                if not cost_metrics.get('api_costs'):
                    return None
                
                # Extract data for plotting
                api_names = list(cost_metrics['api_costs'].keys())
                costs = [cost_metrics['api_costs'][api]['total_cost'] for api in api_names]
                
                # Create plot
                plt.figure(figsize=(10, 6))
                plt.bar(api_names, costs)
                plt.title('API Costs')
                plt.xlabel('API')
                plt.ylabel('Cost (USD)')
                plt.xticks(rotation=45)
                plt.tight_layout()
                
                # Convert plot to base64
                img_data = io.BytesIO()
                plt.savefig(img_data, format='png')
                plt.close()
                img_data.seek(0)
                
                return base64.b64encode(img_data.getvalue()).decode('utf-8')
            
            elif cost_metrics['source'] == 'cloudwatch':
                if not cost_metrics.get('metrics'):
                    return None
                
                # Convert metrics to dataframe
                df = pd.DataFrame(cost_metrics['metrics'])
                
                # Sort by timestamp
                df = df.sort_values('Timestamp')
                
                # Create plot
                plt.figure(figsize=(10, 6))
                plt.plot(df['Timestamp'], df['Sum'])
                plt.title('API Costs Over Time')
                plt.xlabel('Time')
                plt.ylabel('Cost (USD)')
                plt.xticks(rotation=45)
                plt.tight_layout()
                
                # Convert plot to base64
                img_data = io.BytesIO()
                plt.savefig(img_data, format='png')
                plt.close()
                img_data.seek(0)
                
                return base64.b64encode(img_data.getvalue()).decode('utf-8')
        
        except Exception as e:
            self.logger.error(f"Error plotting cost metrics: {str(e)}", exc_info=True)
            return None
    
    def _plot_engagement_metrics(self, engagement_metrics: Dict[str, Any]) -> Dict[str, str]:
        """
        Plot engagement metrics.
        
        Args:
            engagement_metrics: Engagement metrics from generate_engagement_metrics
            
        Returns:
            Dictionary of base64-encoded plot images
            
        Required by:
            - plot_metrics
            
        Requires:
            None
        """
        plots = {}
        
        try:
            metrics_data = engagement_metrics.get('metrics', {})
            
            # Get message count metrics if available
            if engagement_metrics['source'] == 'local_file':
                
                # Plot message count if available
                if 'ConversationMessageCount' in metrics_data:
                    counts = metrics_data['ConversationMessageCount']
                    
                    plt.figure(figsize=(10, 6))
                    plt.bar(['Average', 'Maximum', 'Total'], 
                           [counts.get('average', 0), counts.get('maximum', 0), counts.get('total', 0)])
                    plt.title('Conversation Message Counts')
                    plt.ylabel('Count')
                    plt.tight_layout()
                    
                    # Convert plot to base64
                    img_data = io.BytesIO()
                    plt.savefig(img_data, format='png')
                    plt.close()
                    img_data.seek(0)
                    
                    plots['message_counts'] = base64.b64encode(img_data.getvalue()).decode('utf-8')
                
                # Plot user activity if available
                if 'UserActivity' in metrics_data:
                    user_activity = metrics_data['UserActivity']
                    
                    if user_activity.get('by_activity_type'):
                        activity_types = list(user_activity['by_activity_type'].keys())
                        activity_counts = list(user_activity['by_activity_type'].values())
                        
                        plt.figure(figsize=(10, 6))
                        plt.bar(activity_types, activity_counts)
                        plt.title('User Activities by Type')
                        plt.xlabel('Activity Type')
                        plt.ylabel('Count')
                        plt.xticks(rotation=45)
                        plt.tight_layout()
                        
                        # Convert plot to base64
                        img_data = io.BytesIO()
                        plt.savefig(img_data, format='png')
                        plt.close()
                        img_data.seek(0)
                        
                        plots['user_activities'] = base64.b64encode(img_data.getvalue()).decode('utf-8')
            
            elif engagement_metrics['source'] == 'cloudwatch':
                # Process CloudWatch metrics if needed
                pass
        
        except Exception as e:
            self.logger.error(f"Error plotting engagement metrics: {str(e)}", exc_info=True)
        
        return plots
    
    def _plot_error_metrics(self, error_metrics: Dict[str, Any]) -> Optional[str]:
        """
        Plot error metrics.
        
        Args:
            error_metrics: Error metrics from generate_error_metrics
            
        Returns:
            Base64-encoded plot image or None if plotting fails
            
        Required by:
            - plot_metrics
            
        Requires:
            None
        """
        try:
            # Check if we have data to plot
            if error_metrics['source'] == 'local_file':
                if not error_metrics.get('error_counts'):
                    return None
                
                # Extract data for plotting
                categories = list(error_metrics['error_counts'].keys())
                counts = [error_metrics['error_counts'][cat]['total'] for cat in categories]
                
                # Create plot
                plt.figure(figsize=(10, 6))
                plt.bar(categories, counts)
                plt.title('Errors by Category')
                plt.xlabel('Category')
                plt.ylabel('Count')
                plt.xticks(rotation=45)
                plt.tight_layout()
                
                # Convert plot to base64
                img_data = io.BytesIO()
                plt.savefig(img_data, format='png')
                plt.close()
                img_data.seek(0)
                
                return base64.b64encode(img_data.getvalue()).decode('utf-8')
            
            elif error_metrics['source'] == 'cloudwatch':
                if not error_metrics.get('metrics'):
                    return None
                
                # Convert metrics to dataframe
                df = pd.DataFrame(error_metrics['metrics'])
                
                # Sort by timestamp
                df = df.sort_values('Timestamp')
                
                # Create plot
                plt.figure(figsize=(10, 6))
                plt.plot(df['Timestamp'], df['Sum'])
                plt.title('Errors Over Time')
                plt.xlabel('Time')
                plt.ylabel('Error Count')
                plt.xticks(rotation=45)
                plt.tight_layout()
                
                # Convert plot to base64
                img_data = io.BytesIO()
                plt.savefig(img_data, format='png')
                plt.close()
                img_data.seek(0)
                
                return base64.b64encode(img_data.getvalue()).decode('utf-8')
        
        except Exception as e:
            self.logger.error(f"Error plotting error metrics: {str(e)}", exc_info=True)
            return None


# Function to generate an HTML dashboard
def generate_html_dashboard(days: int = 7, 
                          namespace: str = "DadaCatTwilio",
                          region: str = "us-east-1",
                          output_path: Optional[str] = None) -> str:
    """
    Generate an HTML dashboard with metrics.
    
    Args:
        days: Number of days to include
        namespace: CloudWatch namespace
        region: AWS region
        output_path: Path to save the HTML file (defaults to ./metrics/dashboard_YYYY-MM-DD.html)
        
    Returns:
        Path to the generated HTML file
    """
    # Create dashboard
    dashboard = MetricsDashboard(namespace=namespace, region=region)
    
    # Generate metrics
    metrics = dashboard.generate_dashboard(days)
    
    # Generate plots
    plots = dashboard.plot_metrics(days)
    
    # Create HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DadaCat Metrics Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
            .header {{ background-color: #f5f5f5; padding: 15px; margin-bottom: 20px; }}
            .section {{ margin-bottom: 30px; border: 1px solid #ddd; padding: 15px; border-radius: 5px; }}
            .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
            .metric-card {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; }}
            .metric-title {{ font-size: 16px; font-weight: bold; margin-bottom: 10px; }}
            .metric-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
            .plot {{ margin-top: 20px; text-align: center; }}
            .plot img {{ max-width: 100%; height: auto; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>DadaCat Metrics Dashboard</h1>
            <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Showing data for the last {days} days</p>
        </div>
        
        <div class="section">
            <h2>Cost Metrics</h2>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-title">Total Cost</div>
                    <div class="metric-value">${metrics['costs'].get('total_cost', 0):.2f}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Data Source</div>
                    <div class="metric-value">{metrics['costs']['source']}</div>
                </div>
            </div>
            
            {'<div class="plot"><img src="data:image/png;base64,' + plots['costs'] + '" alt="Cost Metrics"></div>' if 'costs' in plots else '<p>No cost data available for plotting</p>'}
        </div>
        
        <div class="section">
            <h2>Engagement Metrics</h2>
            
            {'<div class="plot"><img src="data:image/png;base64,' + plots['message_counts'] + '" alt="Message Counts"></div>' if 'message_counts' in plots else '<p>No message count data available for plotting</p>'}
            
            {'<div class="plot"><img src="data:image/png;base64,' + plots['user_activities'] + '" alt="User Activities"></div>' if 'user_activities' in plots else '<p>No user activity data available for plotting</p>'}
        </div>
        
        <div class="section">
            <h2>Error Metrics</h2>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-title">Total Errors</div>
                    <div class="metric-value">{metrics['errors'].get('total_errors', 0)}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Data Source</div>
                    <div class="metric-value">{metrics['errors']['source']}</div>
                </div>
            </div>
            
            {'<div class="plot"><img src="data:image/png;base64,' + plots['errors'] + '" alt="Error Metrics"></div>' if 'errors' in plots else '<p>No error data available for plotting</p>'}
        </div>
    </body>
    </html>
    """
    
    # Determine output path
    if output_path:
        output_file = Path(output_path)
    else:
        current_date = datetime.now().strftime('%Y-%m-%d')
        metrics_dir = Path('./metrics')
        metrics_dir.mkdir(parents=True, exist_ok=True)
        output_file = metrics_dir / f"dashboard_{current_date}.html"
    
    # Write to file
    with open(output_file, 'w') as f:
        f.write(html)
    
    return str(output_file)


if __name__ == "__main__":
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Generate DadaCat metrics dashboard')
    parser.add_argument('--days', type=int, default=7, help='Number of days to include in the dashboard')
    parser.add_argument('--namespace', type=str, default="DadaCatTwilio", help='CloudWatch namespace')
    parser.add_argument('--region', type=str, default="us-east-1", help='AWS region')
    parser.add_argument('--output', type=str, help='Output path for HTML dashboard')
    args = parser.parse_args()
    
    # Generate dashboard
    output_path = generate_html_dashboard(
        days=args.days,
        namespace=args.namespace,
        region=args.region,
        output_path=args.output
    )
    
    print(f"Dashboard generated at: {output_path}")