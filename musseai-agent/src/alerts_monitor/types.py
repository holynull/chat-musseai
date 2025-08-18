"""
Alert monitoring data models and configuration classes
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


@dataclass
class MonitoringConfig:
    """Configuration for the alert monitoring system"""
    
    check_interval_seconds: int = 60  # Default check every minute
    max_concurrent_checks: int = 10
    notification_timeout_seconds: int = 30
    retry_attempts: int = 3
    retry_delay_seconds: int = 5
    enable_email: bool = True
    enable_sms: bool = False
    enable_push: bool = False
    enable_webhook: bool = True
    
    # Email configuration
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    from_email: str = ""
    
    # SMS configuration (Twilio)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    
    # Push notification configuration (Firebase)
    firebase_server_key: str = ""
    
    # Webhook configuration
    webhook_timeout: int = 10
    webhook_retries: int = 2


@dataclass
class AlertCheckResult:
    """Result of an alert condition check"""
    
    alert_id: int
    user_id: str
    triggered: bool = False
    current_value: Optional[float] = None
    threshold_value: Optional[float] = None
    message: str = ""
    error: Optional[str] = None
    check_timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class NotificationResult:
    """Result of a notification delivery attempt"""
    
    method: str
    success: bool
    error: Optional[str] = None
    delivery_timestamp: datetime = field(default_factory=datetime.utcnow)
    response_data: Optional[Dict] = None
