import asyncio
import json
import logging
import smtplib
import threading
import time
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import traceback
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
import requests
import schedule
from jinja2 import Template

# Import from existing modules
from mysql.db import get_db
from mysql.model import (
    PortfolioAlertModel,
    AlertStatus,
    AlertType,
    NotificationMethod,
    AlertHistoryModel,
)
from loggers import logger
# ========================================
# Monitoring Service API
# ========================================

from alerts_monitor.alert_monitoring_execution import MonitoringConfig, PortfolioAlertMonitor


class AlertMonitoringService:
    """
    High-level service interface for alert monitoring
    
    This class provides a clean API for starting, stopping, and managing
    the alert monitoring system.
    """
    
    def __init__(self, config: Optional[MonitoringConfig] = None):
        """Initialize the monitoring service"""
        self.config = config or MonitoringConfig()
        self.monitor: Optional[PortfolioAlertMonitor] = None
        self.logger = logging.getLogger("alert_monitoring_service")
    
    def start(self) -> Dict:
        """Start the monitoring service"""
        try:
            if self.monitor and self.monitor.is_running:
                return {
                    "success": False,
                    "message": "Monitoring service is already running"
                }
            
            self.monitor = PortfolioAlertMonitor(self.config)
            self.monitor.start_monitoring()
            
            self.logger.info("Alert monitoring service started successfully")
            return {
                "success": True,
                "message": "Alert monitoring service started",
                "config": {
                    "check_interval": self.config.check_interval_seconds,
                    "max_concurrent": self.config.max_concurrent_checks
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to start monitoring service: {e}")
            return {
                "success": False,
                "error": f"Failed to start monitoring: {str(e)}"
            }
    
    def stop(self) -> Dict:
        """Stop the monitoring service"""
        try:
            if not self.monitor or not self.monitor.is_running:
                return {
                    "success": False,
                    "message": "Monitoring service is not running"
                }
            
            self.monitor.stop_monitoring()
            self.logger.info("Alert monitoring service stopped successfully")
            
            return {
                "success": True,
                "message": "Alert monitoring service stopped"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to stop monitoring service: {e}")
            return {
                "success": False,
                "error": f"Failed to stop monitoring: {str(e)}"
            }
    
    def get_status(self) -> Dict:
        """Get monitoring service status"""
        if not self.monitor:
            return {
                "running": False,
                "message": "Monitoring service not initialized"
            }
        
        return self.monitor.get_monitoring_status()
    
    def check_user_alerts(self, user_id: str) -> Dict:
        """Manually trigger alert check for a specific user"""
        if not self.monitor:
            return {
                "success": False,
                "error": "Monitoring service not initialized"
            }
        
        return self.monitor.check_user_alerts(user_id)
    
    def test_notification(self, user_id: str, method: str, alert_type: str = "TEST") -> Dict:
        """Test notification delivery for a user"""
        try:
            if not self.monitor:
                return {
                    "success": False,
                    "error": "Monitoring service not initialized"
                }
            
            # Create test alert data
            test_alert = {
                "alert_id": 99999,
                "user_id": user_id,
                "alert_type": alert_type,
                "alert_name": "Test Notification",
                "notification_methods": [method]
            }
            
            test_trigger_data = {
                "message": f"This is a test {method} notification",
                "current_value": 12345.67,
                "threshold_value": 12000.00,
                "triggered_at": datetime.utcnow().isoformat()
            }
            # Send test notification
            result = self.monitor.notification_sender.send_notification(
                method=method,
                alert=test_alert,
                trigger_data=test_trigger_data
            )
            
            return {
                "success": result.success,
                "method": result.method,
                "message": "Test notification sent successfully" if result.success else "Test notification failed",
                "error": result.error,
                "delivery_timestamp": result.delivery_timestamp.isoformat(),
                "response_data": result.response_data
            }
            
        except Exception as e:
            self.logger.error(f"Test notification failed: {e}")
            return {
                "success": False,
                "error": f"Test notification failed: {str(e)}"
            }
    
    def update_config(self, new_config: MonitoringConfig) -> Dict:
        """Update monitoring configuration (requires restart)"""
        try:
            was_running = self.monitor and self.monitor.is_running
            
            if was_running:
                self.stop()
            
            self.config = new_config
            
            if was_running:
                return self.start()
            else:
                return {
                    "success": True,
                    "message": "Configuration updated (restart required to take effect)"
                }
                
        except Exception as e:
            self.logger.error(f"Failed to update config: {e}")
            return {
                "success": False,
                "error": f"Failed to update configuration: {str(e)}"
            }