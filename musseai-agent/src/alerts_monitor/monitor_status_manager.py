import asyncio
import json
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
# Monitoring Status Manager
# ========================================

class MonitoringStatusManager:
    """Manages monitoring system status and statistics"""
    
    def __init__(self):
        self.status_data = {
            "total_checks": 0,
            "total_triggered": 0,
            "total_notifications_sent": 0,
            "last_check_time": None,
            "errors_count": 0,
            "uptime_start": datetime.utcnow(),
            "notification_stats": {
                "email": {"sent": 0, "failed": 0},
                "sms": {"sent": 0, "failed": 0},
                "push": {"sent": 0, "failed": 0},
                "webhook": {"sent": 0, "failed": 0}
            }
        }
        self._lock = threading.Lock()
    
    def record_check(self, triggered_count: int = 0):
        """Record a completed alert check"""
        with self._lock:
            self.status_data["total_checks"] += 1
            self.status_data["total_triggered"] += triggered_count
            self.status_data["last_check_time"] = datetime.utcnow().isoformat()
    
    def record_notification(self, method: str, success: bool):
        """Record a notification attempt"""
        with self._lock:
            if method.lower() in self.status_data["notification_stats"]:
                if success:
                    self.status_data["notification_stats"][method.lower()]["sent"] += 1
                    self.status_data["total_notifications_sent"] += 1
                else:
                    self.status_data["notification_stats"][method.lower()]["failed"] += 1
    
    def record_error(self):
        """Record an error occurrence"""
        with self._lock:
            self.status_data["errors_count"] += 1
    
    def get_status(self) -> Dict:
        """Get current status snapshot"""
        with self._lock:
            current_time = datetime.utcnow()
            uptime = current_time - datetime.fromisoformat(
                self.status_data["uptime_start"].isoformat()
            )
            
            return {
                **self.status_data.copy(),
                "uptime_seconds": int(uptime.total_seconds()),
                "uptime_formatted": str(uptime).split(".")[0],  # Remove microseconds
                "current_time": current_time.isoformat()
            }
    
    def get_last_check_time(self) -> Optional[str]:
        """Get the last check timestamp"""
        return self.status_data.get("last_check_time")
    
    def reset_stats(self):
        """Reset statistics (useful for testing)"""
        with self._lock:
            self.status_data.update({
                "total_checks": 0,
                "total_triggered": 0,
                "total_notifications_sent": 0,
                "errors_count": 0,
                "uptime_start": datetime.utcnow(),
                "notification_stats": {
                    "email": {"sent": 0, "failed": 0},
                    "sms": {"sent": 0, "failed": 0},
                    "push": {"sent": 0, "failed": 0},
                    "webhook": {"sent": 0, "failed": 0}
                }
            })