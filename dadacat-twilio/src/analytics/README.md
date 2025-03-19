# DadaCat Analytics Components

This directory contains analytics and monitoring components for the DadaCat Twilio integration.

## Overview

The analytics system tracks various metrics related to the DadaCat Twilio integration, including:
- API costs (OpenAI, Twilio)
- User engagement (message counts, conversation duration, etc.)
- Error tracking and categorization
- Response time monitoring

The system supports both CloudWatch for production use and local file-based storage for development.

## Components

### Cost Tracker

The `CostTracker` in `costs.py` tracks API usage costs:
- Tracks individual API calls with estimated costs
- Provides methods to retrieve cost metrics for a time period
- Supports both CloudWatch metrics and local file storage

### Engagement Tracker

The `EngagementTracker` in `engagement.py` monitors user engagement:
- Tracks conversation metrics (message count, duration)
- Records user activities (messages, reset, admin commands)
- Measures response times
- Provides methods to retrieve engagement metrics for analysis

### Error Tracker

The `ErrorTracker` in `errors.py` handles error tracking and analysis:
- Categorizes errors by type and severity
- Records error details and context
- Logs errors to CloudWatch Logs and/or local files
- Provides methods to retrieve error metrics and trends

### Dashboard

The `MetricsDashboard` in `dashboard.py` generates visualizations:
- Creates HTML dashboards with key metrics
- Generates plots for costs, engagement, and errors
- Supports JSON export for further analysis
- Includes standalone dashboard generation script

## Usage

### Configuration

Analytics components are configured through environment variables:
```
# Enable/disable analytics
ANALYTICS_ENABLED=true

# CloudWatch namespace
ANALYTICS_NAMESPACE=DadaCatTwilio

# AWS region for CloudWatch
DYNAMODB_REGION=us-east-1
```

### Dashboard Generation

Generate a metrics dashboard using the provided script:
```bash
python src/generate_dashboard.py --days 7 --output metrics/dashboard.html
```

Options:
- `--days`: Number of days to include (default: 7)
- `--output`: Output path for HTML dashboard
- `--namespace`: CloudWatch namespace
- `--region`: AWS region
- `--json`: Also generate JSON data file

### Admin Commands

The following admin commands are available via SMS:
- `admin:status`: Shows system status including analytics settings
- `admin:analytics_status`: Shows key metrics from the analytics system

## Integration

Analytics components are integrated into the main application in `app_persistent.py`:
- Metrics are collected asynchronously to avoid impacting performance
- Local file fallbacks are used when CloudWatch is unavailable
- Admin commands provide runtime insights into system metrics