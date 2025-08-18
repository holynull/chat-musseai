# ========================================
# CLI and Utility Functions
# ========================================

from alerts_monitor.alert_monitoring_execution import MonitoringConfig


def create_default_config() -> MonitoringConfig:
    """Create a default monitoring configuration"""
    return MonitoringConfig(
        check_interval_seconds=60,  # Check every minute
        max_concurrent_checks=10,
        notification_timeout_seconds=30,
        retry_attempts=3,
        enable_email=True,
        enable_webhook=True,
        enable_sms=False,  # Disabled by default (requires Twilio setup)
        enable_push=False  # Disabled by default (requires Firebase setup)
    )


def setup_monitoring_from_env() -> MonitoringConfig:
    """Create monitoring configuration from environment variables"""
    import os
    
    return MonitoringConfig(
        check_interval_seconds=int(os.getenv("ALERT_CHECK_INTERVAL", "60")),
        max_concurrent_checks=int(os.getenv("ALERT_MAX_CONCURRENT", "10")),
        notification_timeout_seconds=int(os.getenv("ALERT_NOTIFICATION_TIMEOUT", "30")),
        
        # Email configuration
        enable_email=os.getenv("ALERT_EMAIL_ENABLED", "true").lower() == "true",
        smtp_server=os.getenv("ALERT_SMTP_SERVER", "smtp.gmail.com"),
        smtp_port=int(os.getenv("ALERT_SMTP_PORT", "587")),
        smtp_username=os.getenv("ALERT_SMTP_USERNAME", ""),
        smtp_password=os.getenv("ALERT_SMTP_PASSWORD", ""),
        from_email=os.getenv("ALERT_FROM_EMAIL", ""),
        
        # SMS configuration
        enable_sms=os.getenv("ALERT_SMS_ENABLED", "false").lower() == "true",
        twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
        twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
        twilio_from_number=os.getenv("TWILIO_FROM_NUMBER", ""),
        
        # Push notification configuration
        enable_push=os.getenv("ALERT_PUSH_ENABLED", "false").lower() == "true",
        firebase_server_key=os.getenv("FIREBASE_SERVER_KEY", ""),
        
        # Webhook configuration
        enable_webhook=os.getenv("ALERT_WEBHOOK_ENABLED", "true").lower() == "true",
        webhook_timeout=int(os.getenv("ALERT_WEBHOOK_TIMEOUT", "10")),
        webhook_retries=int(os.getenv("ALERT_WEBHOOK_RETRIES", "2"))
    )