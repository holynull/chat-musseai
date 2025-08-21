import logging
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Optional
from alerts_monitor.types import MonitoringConfig,  NotificationResult
import requests
from jinja2 import Template

# Import from existing modules
from mysql.model import (
    NotificationMethod,
)

# ========================================
# Notification Sender
# ========================================

class NotificationSender:
    """Handles sending notifications through various channels"""
    
    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.logger = logging.getLogger("notification_sender")
        
        # Email templates
        self.email_template = Template("""
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .header { background-color: #f8f9fa; padding: 20px; border-radius: 5px; }
        .alert-info { background-color: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0; }
        .details { background-color: #f8f9fa; padding: 15px; border-radius: 5px; }
        .footer { margin-top: 30px; font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class="header">
        <h2>🚨 Portfolio Alert: {{ alert_name }}</h2>
        <p><strong>Alert Type:</strong> {{ alert_type }}</p>
        <p><strong>Triggered:</strong> {{ triggered_at }}</p>
    </div>
    
    <div class="alert-info">
        <h3>Alert Message</h3>
        <p>{{ message }}</p>
    </div>
    
    <div class="details">
        <h3>Details</h3>
        <p><strong>Current Value:</strong> {{ current_value }}</p>
        <p><strong>Threshold Value:</strong> {{ threshold_value }}</p>
        <p><strong>User ID:</strong> {{ user_id }}</p>
    </div>
    
    <div class="footer">
        <p>This is an automated alert from your Portfolio Monitoring System.</p>
        <p>To manage your alerts, please log in to your account.</p>
    </div>
</body>
</html>
        """)
        
        self.sms_template = Template(
            "🚨 ALERT: {{ alert_name }}\n"
            "{{ message }}\n"
            "Current: {{ current_value }}\n"
            "Threshold: {{ threshold_value }}\n"
            "Time: {{ triggered_at }}"
        )
    
    def send_notification(self, method: str, alert: Dict, trigger_data: Dict) -> NotificationResult:
        """Send notification using specified method"""
        try:
            if method == NotificationMethod.EMAIL.value and self.config.enable_email:
                return self._send_email(alert, trigger_data)
            elif method == NotificationMethod.SMS.value and self.config.enable_sms:
                return self._send_sms(alert, trigger_data)
            elif method == NotificationMethod.PUSH.value and self.config.enable_push:
                return self._send_push(alert, trigger_data)
            elif method == NotificationMethod.WEBHOOK.value and self.config.enable_webhook:
                return self._send_webhook(alert, trigger_data)
            else:
                return NotificationResult(
                    method=method,
                    success=False,
                    error=f"Notification method {method} is not enabled or supported"
                )
                
        except Exception as e:
            self.logger.error(f"Notification send failed ({method}): {e}")
            return NotificationResult(
                method=method,
                success=False,
                error=str(e)
            )
    
    def _send_email(self, alert: Dict, trigger_data: Dict) -> NotificationResult:
        """Send email notification"""
        try:
            # Render email content
            html_content = self.email_template.render(
                alert_name=alert["alert_name"],
                alert_type=alert["alert_type"],
                message=trigger_data["message"],
                current_value=trigger_data.get("current_value", "N/A"),
                threshold_value=trigger_data.get("threshold_value", "N/A"),
                triggered_at=trigger_data["triggered_at"],
                user_id=alert["user_id"]
            )
            
            # Create email message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Portfolio Alert: {alert['alert_name']}"
            msg['From'] = self.config.from_email
            msg['To'] = self._get_user_email(alert["user_id"])  # Would need user email lookup
            
            # Add HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                server.starttls()
                server.login(self.config.smtp_username, self.config.smtp_password)
                server.send_message(msg)
            
            self.logger.info(f"Email sent successfully for alert {alert['alert_id']}")
            return NotificationResult(
                method=NotificationMethod.EMAIL.value,
                success=True,
                response_data={"recipient": msg['To']}
            )
            
        except Exception as e:
            self.logger.error(f"Email send failed: {e}")
            return NotificationResult(
                method=NotificationMethod.EMAIL.value,
                success=False,
                error=str(e)
            )
    
    def _send_sms(self, alert: Dict, trigger_data: Dict) -> NotificationResult:
        """Send SMS notification using Twilio"""
        try:
            from twilio.rest import Client
            
            # Initialize Twilio client
            client = Client(self.config.twilio_account_sid, self.config.twilio_auth_token)
            
            # Render SMS content
            sms_content = self.sms_template.render(
                alert_name=alert["alert_name"],
                message=trigger_data["message"],
                current_value=trigger_data.get("current_value", "N/A"),
                threshold_value=trigger_data.get("threshold_value", "N/A"),
                triggered_at=datetime.fromisoformat(trigger_data["triggered_at"]).strftime("%H:%M")
            )
            
            # Get user phone number
            user_phone = self._get_user_phone(alert["user_id"])
            
            # Send SMS
            message = client.messages.create(
                body=sms_content,
                from_=self.config.twilio_from_number,
                to=user_phone
            )
            
            self.logger.info(f"SMS sent successfully for alert {alert['alert_id']}")
            return NotificationResult(
                method=NotificationMethod.SMS.value,
                success=True,
                response_data={
                    "message_sid": message.sid,
                    "recipient": user_phone
                }
            )
            
        except Exception as e:
            self.logger.error(f"SMS send failed: {e}")
            return NotificationResult(
                method=NotificationMethod.SMS.value,
                success=False,
                error=str(e)
            )
    
    def _send_push(self, alert: Dict, trigger_data: Dict) -> NotificationResult:
        """Send push notification using Firebase"""
        try:
            # Firebase Cloud Messaging payload
            fcm_payload = {
                "to": f"/topics/user_{alert['user_id']}",  # Topic-based messaging
                "notification": {
                    "title": f"Portfolio Alert: {alert['alert_name']}",
                    "body": trigger_data["message"],
                    "icon": "alert_icon",
                    "sound": "default"
                },
                "data": {
                    "alert_id": str(alert["alert_id"]),
                    "alert_type": alert["alert_type"],
                    "current_value": str(trigger_data.get("current_value", "")),
                    "threshold_value": str(trigger_data.get("threshold_value", "")),
                    "triggered_at": trigger_data["triggered_at"],
                    "click_action": "FLUTTER_NOTIFICATION_CLICK"
                }
            }
            
            headers = {
                "Authorization": f"key={self.config.firebase_server_key}",
                "Content-Type": "application/json"
            }
            
            # Send push notification
            response = requests.post(
                "https://fcm.googleapis.com/fcm/send",
                json=fcm_payload,
                headers=headers,
                timeout=self.config.notification_timeout_seconds
            )
            
            if response.status_code == 200:
                self.logger.info(f"Push notification sent successfully for alert {alert['alert_id']}")
                return NotificationResult(
                    method=NotificationMethod.PUSH.value,
                    success=True,
                    response_data=response.json()
                )
            else:
                raise Exception(f"FCM returned status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.logger.error(f"Push notification send failed: {e}")
            return NotificationResult(
                method=NotificationMethod.PUSH.value,
                success=False,
                error=str(e)
            )
    
    def _send_webhook(self, alert: Dict, trigger_data: Dict) -> NotificationResult:
        """Send webhook notification"""
        try:
            # Get webhook URL for user (would be stored in user preferences)
            webhook_url = self._get_user_webhook_url(alert["user_id"])
            
            if not webhook_url:
                raise Exception("No webhook URL configured for user")
            
            # Prepare webhook payload
            webhook_payload = {
                "event": "alert_triggered",
                "timestamp": trigger_data["triggered_at"],
                "alert": {
                    "id": alert["alert_id"],
                    "name": alert["alert_name"],
                    "type": alert["alert_type"],
                    "user_id": alert["user_id"]
                },
                "trigger_data": {
                    "message": trigger_data["message"],
                    "current_value": trigger_data.get("current_value"),
                    "threshold_value": trigger_data.get("threshold_value"),
                    "triggered_at": trigger_data["triggered_at"]
                }
            }
            
            # Send webhook with retries
            for attempt in range(self.config.webhook_retries + 1):
                try:
                    response = requests.post(
                        webhook_url,
                        json=webhook_payload,
                        timeout=self.config.webhook_timeout,
                        headers={"Content-Type": "application/json"}
                    )
                    
                    if response.status_code in [200, 201, 202]:
                        self.logger.info(f"Webhook sent successfully for alert {alert['alert_id']}")
                        return NotificationResult(
                            method=NotificationMethod.WEBHOOK.value,
                            success=True,
                            response_data={
                                "status_code": response.status_code,
                                "webhook_url": webhook_url,
                                "attempt": attempt + 1
                            }
                        )
                    else:
                        if attempt == self.config.webhook_retries:
                            raise Exception(f"Webhook failed with status {response.status_code}")
                        time.sleep(2 ** attempt)  # Exponential backoff
                        
                except requests.exceptions.Timeout:
                    if attempt == self.config.webhook_retries:
                        raise Exception("Webhook request timed out")
                    time.sleep(2 ** attempt)
                    
        except Exception as e:
            self.logger.error(f"Webhook send failed: {e}")
            return NotificationResult(
                method=NotificationMethod.WEBHOOK.value,
                success=False,
                error=str(e)
            )
    
    def _get_user_email(self, user_id: str) -> str:
        """Get user's email address from database or configuration"""
        # In production, this would query user preferences/profile
        # For now, return a placeholder or configured email
        return f"{user_id}@example.com"
    
    def _get_user_phone(self, user_id: str) -> str:
        """Get user's phone number from database"""
        # In production, this would query user preferences/profile
        # For now, return a placeholder
        return "+1234567890"
    
    def _get_user_webhook_url(self, user_id: str) -> Optional[str]:
        """Get user's webhook URL from database"""
        # In production, this would query user preferences
        # For now, return None or a test URL
        return None