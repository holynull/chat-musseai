#!/usr/bin/env python3
"""
Alert Monitor Startup Script
Starts the portfolio alert monitoring service
"""
import sys
import os
import signal
import logging
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from alerts_monitor.monitoring_service_api import AlertMonitoringService
from alerts_monitor.monitor_cli import setup_monitoring_from_env
from loggers import logger

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, shutting down monitor...")
    sys.exit(0)

def main():
    """Main entry point for monitor service"""
    try:
        # Setup signal handlers
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        # Load configuration from environment
        config = setup_monitoring_from_env()

        # Create and start monitoring service
        service = AlertMonitoringService(config)

        logger.info("Starting Alert Monitoring Service...")
        result = service.start()

        if result["success"]:
            logger.info(f"Monitor started successfully: {result['message']}")

            # Keep the process running
            try:
                while True:
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, stopping monitor...")
        else:
            logger.error(f"Failed to start monitor: {result.get('error', 'Unknown error')}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Monitor startup failed: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        if 'service' in locals():
            service.stop()
        logger.info("Monitor service stopped")

if __name__ == "__main__":
    main()
