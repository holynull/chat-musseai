"""
Portfolio Alert Monitoring Execution Module

This module provides real-time monitoring and notification execution for portfolio alerts.
It includes scheduled checking, notification delivery, and status management.
"""

import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from alerts_monitor.alert_conditions import check_alert_conditions
from alerts_monitor.monitor_status_manager import MonitoringStatusManager
from alerts_monitor.notification_sender import NotificationSender
from alerts_monitor.types import MonitoringConfig, AlertCheckResult, NotificationResult
import schedule
from alerts_monitor.utils.cmc import getLatestQuote
import json

# Import from existing modules
from mysql.db import get_db
from mysql.model import (
    PortfolioAlertModel,
    AlertStatus,
    AlertType,
    NotificationMethod,
    AlertHistoryModel,
    PortfolioSourceModel,
    PositionModel,
    AssetModel,
)


# ========================================
# Alert Monitoring Engine
# ========================================


class PortfolioAlertMonitor:
    """
    Main monitoring engine for portfolio alerts

    This class handles the execution of alert monitoring, including:
    - Scheduled checking of alert conditions
    - Notification delivery
    - Status tracking and history management
    """

    def __init__(self, config: MonitoringConfig):
        """Initialize the alert monitor with configuration"""
        self.config = config
        self.is_running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        self.executor = ThreadPoolExecutor(max_workers=config.max_concurrent_checks)
        self.notification_sender = NotificationSender(config)
        self.status_manager = MonitoringStatusManager()
        self._setup_logging()

    def _setup_logging(self):
        """Setup monitoring specific logging"""
        self.monitor_logger = logging.getLogger("portfolio_alert_monitor")
        self.monitor_logger.setLevel(os.getenv("PORTFOLIO_ALERT_MONITOR_LEVEL", "INFO"))

        # Create handler if it doesn't exist
        if not self.monitor_logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.monitor_logger.addHandler(handler)

    def start_monitoring(self):
        """Start the alert monitoring system"""
        if self.is_running:
            self.monitor_logger.warning("Monitor is already running")
            return

        self.is_running = True
        self.monitor_logger.info("Starting Portfolio Alert Monitor")

        # Schedule periodic checks
        schedule.every(self.config.check_interval_seconds).seconds.do(
            self._run_scheduled_check
        )

        # Start scheduler thread
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop, daemon=True, name="AlertScheduler"
        )
        self.scheduler_thread.start()

        self.monitor_logger.info(
            f"Alert monitoring started with {self.config.check_interval_seconds}s interval"
        )

    def stop_monitoring(self):
        """Stop the alert monitoring system"""
        if not self.is_running:
            self.monitor_logger.warning("Monitor is not running")
            return

        self.is_running = False
        schedule.clear()

        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)

        self.executor.shutdown(wait=True)
        self.monitor_logger.info("Portfolio Alert Monitor stopped")

    def _scheduler_loop(self):
        """Main scheduler loop running in separate thread"""
        self.monitor_logger.info("Alert scheduler loop started")

        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                self.monitor_logger.error(f"Scheduler loop error: {e}")
                time.sleep(5)  # Wait before retrying

        self.monitor_logger.info("Alert scheduler loop stopped")

    def _run_scheduled_check(self):
        """Execute scheduled alert checking"""
        try:
            self.monitor_logger.info("Starting scheduled alert check")
            start_time = time.time()

            # Get all active alerts
            active_alerts = self._get_active_alerts()
            if not active_alerts:
                self.monitor_logger.info("No active alerts to check")
                return

            self.monitor_logger.info(f"Checking {len(active_alerts)} active alerts")

            # NEW: Pre-fetch all required asset prices
            all_symbols = self._get_unique_symbols_from_alerts(active_alerts)
            # all_symbols = [
            #     # Top 10 by market cap
            #     "BTC",
            #     "ETH",
            #     "BNB",
            #     "XRP",
            #     "SOL",
            #     "ADA",
            #     "DOGE",
            #     "AVAX",
            #     "TRX",
            #     "DOT",
            #     # DeFi tokens
            #     "LINK",
            #     "UNI",
            #     "AAVE",
            #     "SUSHI",
            #     "COMP",
            #     "MKR",
            #     "CRV",
            #     "1INCH",
            #     # Layer 2 & Scaling
            #     "MATIC",
            #     "OP",
            #     "ARB",
            #     "LRC",
            #     "IMX",
            #     # Meme coins (popular)
            #     "SHIB",
            #     "PEPE",
            #     "FLOKI",
            #     "BONK",
            #     # Infrastructure & Utilities
            #     "ATOM",
            #     "NEAR",
            #     "ALGO",
            #     "VET",
            #     "FTM",
            #     "HBAR",
            #     # Gaming & NFT
            #     "SAND",
            #     "MANA",
            #     "AXS",
            #     "ENJ",
            #     "GALA",
            #     # Stablecoins (for reference)
            #     "USDT",
            #     "USDC",
            #     "BUSD",
            #     "DAI",
            #     # Newer projects
            #     "APT",
            #     "SUI",
            #     "OP",
            #     "ARB",
            #     "LDO",
            #     "RPL",
            #     # Pattener
            #     "SWFTC",
            # ]
            global_price_data = self._fetch_batch_prices(all_symbols)

            # Check alerts concurrently with pre-fetched prices
            check_results = self._check_alerts_batch(active_alerts, global_price_data)

            # Process triggered alerts
            triggered_count = 0
            for result in check_results:
                if result.triggered:
                    triggered_count += 1
                    self._handle_triggered_alert(result)

                # Update check timestamp
                self._update_alert_check_timestamp(result.alert_id)

            duration = time.time() - start_time
            self.monitor_logger.info(
                f"Alert check completed: {triggered_count}/{len(active_alerts)} triggered in {duration:.2f}s"
            )

        except Exception as e:
            self.monitor_logger.error(f"Scheduled check failed: {e}")
            self.monitor_logger.error(f"Scheduled alert check error: {e}")

    def _get_unique_symbols_from_alerts(self, alerts: List[Dict]) -> List[str]:
        """Extract unique asset symbols from all alerts"""
        symbols = set()

        try:
            for alert in alerts:
                user_id = alert["user_id"]

                # Get user's portfolio positions to find all symbols
                with get_db() as db:

                    user_positions = (
                        db.query(AssetModel.symbol)
                        .join(
                            PositionModel, PositionModel.asset_id == AssetModel.asset_id
                        )
                        .join(
                            PortfolioSourceModel,
                            PortfolioSourceModel.source_id == PositionModel.source_id,
                        )
                        .filter(PortfolioSourceModel.user_id == user_id)
                        .filter(
                            PositionModel.quantity > 0
                        )  # Only positions with actual holdings
                        .distinct()
                        .all()
                    )

                    for (symbol,) in user_positions:
                        symbols.add(symbol)

        except Exception as e:
            self.monitor_logger.error(f"Error extracting symbols from alerts: {e}")

        return list(symbols)

    def _fetch_batch_prices(self, symbols: List[str]) -> Dict:
        """Fetch prices for all symbols in one CMC API call"""
        if not symbols:
            return {}

        try:

            # Join symbols with comma for batch API call
            symbols_str = ",".join(symbols)
            self.monitor_logger.info(
                f"Fetching batch prices for symbols: {symbols_str}"
            )

            # Single API call to get all prices
            quote_response = getLatestQuote(symbols_str, logger=self.monitor_logger)

            if not isinstance(quote_response, str):
                self.monitor_logger.error(f"Invalid CMC API response: {quote_response}")
                return {}

            quote_data = json.loads(quote_response)

            # Parse and structure price data
            price_data = {}
            if "data" in quote_data:
                for symbol in symbols:
                    symbol_upper = symbol.upper()
                    if (
                        symbol_upper in quote_data["data"]
                        and len(quote_data["data"][symbol_upper]) > 0
                    ):

                        token_data = quote_data["data"][symbol_upper][0]
                        price = token_data["quote"]["USD"]["price"]

                        price_data[symbol] = {
                            "price": float(price),
                            "timestamp": datetime.utcnow().isoformat(),
                            "source": "CMC_API_BATCH",
                            "symbol": symbol,
                            # Additional market data from CMC
                            "market_cap": token_data["quote"]["USD"].get("market_cap"),
                            "volume_24h": token_data["quote"]["USD"].get("volume_24h"),
                            "percent_change_24h": token_data["quote"]["USD"].get(
                                "percent_change_24h"
                            ),
                        }

            self.monitor_logger.info(
                f"Successfully fetched prices for {len(price_data)} symbols"
            )
            return price_data

        except Exception as e:
            self.monitor_logger.error(f"Error fetching batch prices: {e}")
            return {}

    def _check_alerts_batch(
        self, alerts: List[Dict], global_price_data: Dict = None
    ) -> List[AlertCheckResult]:
        """Check multiple alerts concurrently with pre-fetched price data"""
        results = []

        # Submit all alert checks to thread pool
        future_to_alert = {
            self.executor.submit(
                self._check_single_alert, alert, global_price_data
            ): alert
            for alert in alerts
        }

        # Collect results as they complete
        for future in as_completed(future_to_alert, timeout=60):
            alert = future_to_alert[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                self.monitor_logger.error(
                    f"Alert check failed for {alert['alert_id']}: {e}"
                )
                results.append(
                    AlertCheckResult(
                        alert_id=alert["alert_id"],
                        user_id=alert["user_id"],
                        triggered=False,
                        error=str(e),
                    )
                )

        return results

    def _check_single_alert(
        self, alert: Dict, global_price_data: Dict = None
    ) -> AlertCheckResult:
        """Check a single alert condition with optional pre-fetched price data"""
        try:
            # Pass global price data to the alert checking function
            check_result = check_alert_conditions(
                user_id=alert["user_id"],
                portfolio_summary=None,  # Will be fetched inside with optimized price data
                latest_prices=global_price_data,  # Pass pre-fetched prices
                alert_id=str(alert["alert_id"]),
                logger=self.monitor_logger,
            )

            if isinstance(check_result, dict) and "error" not in check_result:
                triggered_alerts = check_result.get("triggered_alerts", [])
                if triggered_alerts:
                    # Alert was triggered
                    trigger_data = triggered_alerts[0]
                    return AlertCheckResult(
                        alert_id=alert["alert_id"],
                        user_id=alert["user_id"],
                        triggered=True,
                        current_value=trigger_data.get("current_value"),
                        threshold_value=trigger_data.get("threshold_value"),
                        message=trigger_data.get("trigger_message", "Alert triggered"),
                    )
                else:
                    # Alert not triggered
                    return AlertCheckResult(
                        alert_id=alert["alert_id"],
                        user_id=alert["user_id"],
                        triggered=False,
                        message="Conditions not met",
                    )
            else:
                # Error in checking
                error_msg = (
                    check_result.get("error", "Unknown error")
                    if isinstance(check_result, dict)
                    else str(check_result)
                )
                return AlertCheckResult(
                    alert_id=alert["alert_id"],
                    user_id=alert["user_id"],
                    triggered=False,
                    error=error_msg,
                )

        except Exception as e:
            return AlertCheckResult(
                alert_id=alert["alert_id"],
                user_id=alert["user_id"],
                triggered=False,
                error=f"Check execution failed: {str(e)}",
            )

    def _get_active_alerts(self) -> List[Dict]:
        """Retrieve all active alerts from database"""
        try:
            with get_db() as db:
                active_alerts = (
                    db.query(PortfolioAlertModel)
                    .filter(PortfolioAlertModel.status == AlertStatus.ACTIVE)
                    .all()
                )

                return [
                    {
                        "alert_id": alert.alert_id,
                        "user_id": alert.user_id,
                        "alert_type": alert.alert_type.value,
                        "alert_name": alert.alert_name,
                        "conditions": alert.conditions,
                        "notification_methods": alert.notification_methods,
                        "last_checked_at": alert.last_checked_at,
                    }
                    for alert in active_alerts
                ]
        except Exception as e:
            self.monitor_logger.error(f"Failed to get active alerts: {e}")
            return []

    def _handle_triggered_alert(self, result: AlertCheckResult):
        """Handle a triggered alert by sending notifications and updating status"""
        try:
            # Get full alert details
            alert_details = self._get_alert_details(result.alert_id)
            if not alert_details:
                self.monitor_logger.error(
                    f"Could not get details for alert {result.alert_id}"
                )
                return

            # Send notifications
            notification_results = self._send_notifications(alert_details, result)

            # Update alert status and history
            self._update_triggered_alert(result, notification_results)

            # Log successful trigger handling
            self.monitor_logger.info(
                f"Alert {result.alert_id} triggered and processed: {result.message}"
            )

        except Exception as e:
            self.monitor_logger.error(
                f"Failed to handle triggered alert {result.alert_id}: {e}"
            )

    def _get_alert_details(self, alert_id: int) -> Optional[Dict]:
        """Get complete alert details from database"""
        try:
            with get_db() as db:
                alert = (
                    db.query(PortfolioAlertModel)
                    .filter(PortfolioAlertModel.alert_id == alert_id)
                    .first()
                )

                if alert:
                    return {
                        "alert_id": alert.alert_id,
                        "user_id": alert.user_id,
                        "alert_type": alert.alert_type.value,
                        "alert_name": alert.alert_name,
                        "conditions": alert.conditions,
                        "notification_methods": alert.notification_methods,
                        "status": alert.status.value,
                    }
                return None
        except Exception as e:
            self.monitor_logger.error(f"Failed to get alert details: {e}")
            return None

    def _send_notifications(
        self, alert: Dict, result: AlertCheckResult
    ) -> List[NotificationResult]:
        """Send notifications for triggered alert"""
        notification_results = []

        for method in alert["notification_methods"]:
            try:
                notification_result = self.notification_sender.send_notification(
                    method=method,
                    alert=alert,
                    trigger_data={
                        "current_value": result.current_value,
                        "threshold_value": result.threshold_value,
                        "message": result.message,
                        "triggered_at": result.check_timestamp.isoformat(),
                    },
                )
                notification_results.append(notification_result)

            except Exception as e:
                self.monitor_logger.error(f"Notification failed ({method}): {e}")
                notification_results.append(
                    NotificationResult(method=method, success=False, error=str(e))
                )

        return notification_results

    def _update_triggered_alert(
        self, result: AlertCheckResult, notifications: List[NotificationResult]
    ):
        """Update alert status and create history record"""
        try:
            with get_db() as db:
                # Update alert record
                alert = (
                    db.query(PortfolioAlertModel)
                    .filter(PortfolioAlertModel.alert_id == result.alert_id)
                    .first()
                )

                if alert:
                    alert.status = AlertStatus.TRIGGERED
                    alert.last_triggered_at = result.check_timestamp
                    alert.trigger_count = (alert.trigger_count or 0) + 1

                    # Create history record
                    history = AlertHistoryModel(
                        alert_id=result.alert_id,
                        triggered_at=result.check_timestamp,
                        trigger_value={
                            "current_value": result.current_value,
                            "threshold_value": result.threshold_value,
                        },
                        message=result.message,
                        notification_sent=any(n.success for n in notifications),
                    )

                    db.add(history)
                    db.commit()

                    self.monitor_logger.info(
                        f"Updated alert {result.alert_id} status and created history"
                    )

        except Exception as e:
            self.monitor_logger.error(f"Failed to update triggered alert: {e}")

    def _update_alert_check_timestamp(self, alert_id: int):
        """Update the last_checked_at timestamp for an alert"""
        try:
            with get_db() as db:
                alert = (
                    db.query(PortfolioAlertModel)
                    .filter(PortfolioAlertModel.alert_id == alert_id)
                    .first()
                )

                if alert:
                    alert.last_checked_at = datetime.utcnow()
                    db.commit()

        except Exception as e:
            self.monitor_logger.error(f"Failed to update check timestamp: {e}")

    # def check_user_alerts(self, user_id: str) -> Dict:
    #     """Manually trigger alert check for a specific user"""
    #     try:
    #         self.monitor_logger.info(f"Manual alert check for user {user_id}")

    #         with get_db() as db:
    #             user_alerts = (
    #                 db.query(PortfolioAlertModel)
    #                 .filter(
    #                     PortfolioAlertModel.user_id == user_id,
    #                     PortfolioAlertModel.status == AlertStatus.ACTIVE,
    #                 )
    #                 .all()
    #             )

    #             alerts_data = [
    #                 {
    #                     "alert_id": alert.alert_id,
    #                     "user_id": alert.user_id,
    #                     "alert_type": alert.alert_type.value,
    #                     "alert_name": alert.alert_name,
    #                     "conditions": alert.conditions,
    #                     "notification_methods": alert.notification_methods,
    #                 }
    #                 for alert in user_alerts
    #             ]

    #             if not alerts_data:
    #                 return {
    #                     "success": True,
    #                     "message": f"No active alerts found for user {user_id}",
    #                     "alerts_checked": 0,
    #                     "alerts_triggered": 0,
    #                 }

    #             # Check alerts
    #             results = self._check_alerts_batch(alerts_data)

    #             # Process triggered alerts
    #             triggered_count = 0
    #             for result in results:
    #                 if result.triggered:
    #                     triggered_count += 1
    #                     self._handle_triggered_alert(result)

    #                 self._update_alert_check_timestamp(result.alert_id)

    #             return {
    #                 "success": True,
    #                 "message": f"Checked {len(results)} alerts for user {user_id}",
    #                 "alerts_checked": len(results),
    #                 "alerts_triggered": triggered_count,
    #                 "check_timestamp": datetime.utcnow().isoformat(),
    #             }

    #     except Exception as e:
    #         self.monitor_logger.error(f"Manual user alert check failed: {e}")
    #         return {"success": False, "error": f"Failed to check user alerts: {str(e)}"}

    def get_monitoring_status(self) -> Dict:
        """Get current monitoring system status"""
        return {
            "is_running": self.is_running,
            "config": {
                "check_interval_seconds": self.config.check_interval_seconds,
                "max_concurrent_checks": self.config.max_concurrent_checks,
                "enabled_notifications": {
                    "email": self.config.enable_email,
                    "sms": self.config.enable_sms,
                    "push": self.config.enable_push,
                    "webhook": self.config.enable_webhook,
                },
            },
            "status": self.status_manager.get_status(),
            "last_check": self.status_manager.get_last_check_time(),
        }
