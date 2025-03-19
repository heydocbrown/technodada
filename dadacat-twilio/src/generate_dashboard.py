#!/usr/bin/env python
"""
Script to generate a DadaCat analytics dashboard.
"""
import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add the project root directory to the path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
sys.path.append(str(project_root))

# Add the current directory to the path to import our local modules
sys.path.append(str(current_dir))

# Import our components
from analytics.dashboard import generate_html_dashboard, MetricsDashboard

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file in the project root
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='Generate DadaCat metrics dashboard')
    parser.add_argument('--days', type=int, default=7, help='Number of days to include in the dashboard')
    parser.add_argument('--output', type=str, help='Output path for HTML dashboard')
    parser.add_argument('--namespace', type=str, default=os.getenv('ANALYTICS_NAMESPACE', 'DadaCatTwilio'), 
                       help='CloudWatch namespace')
    parser.add_argument('--region', type=str, default=os.getenv('DYNAMODB_REGION', 'us-east-1'), 
                       help='AWS region')
    parser.add_argument('--json', action='store_true', help='Also generate a JSON file with the dashboard data')
    
    return parser.parse_args()


def main():
    """Main function to generate the dashboard."""
    args = parse_args()
    
    logger.info(f"Generating dashboard for the past {args.days} days...")
    
    try:
        # Generate HTML dashboard
        output_path = generate_html_dashboard(
            days=args.days,
            namespace=args.namespace,
            region=args.region,
            output_path=args.output
        )
        
        logger.info(f"Dashboard HTML generated at: {output_path}")
        
        # Generate JSON if requested
        if args.json:
            dashboard = MetricsDashboard(namespace=args.namespace, region=args.region)
            
            # Generate and save dashboard data
            if args.output:
                # Derive JSON path from HTML path
                json_path = Path(args.output).with_suffix('.json')
            else:
                # Use default path
                current_date = datetime.now().strftime('%Y-%m-%d')
                metrics_dir = Path('./metrics')
                metrics_dir.mkdir(parents=True, exist_ok=True)
                json_path = metrics_dir / f"dashboard_{current_date}.json"
            
            # Save dashboard data
            json_output = dashboard.save_dashboard(days=args.days, file_path=str(json_path))
            logger.info(f"Dashboard JSON data saved to: {json_output}")
        
    except Exception as e:
        logger.error(f"Error generating dashboard: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()