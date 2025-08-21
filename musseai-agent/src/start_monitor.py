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
# sys.path.insert(0, str(Path(__file__).parent / "src"))

from alerts_monitor.monitoring_service_api import AlertMonitoringService
from alerts_monitor.monitor_cli import setup_monitoring_from_env
from loggers import logger
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent
env_file_path = project_root / ".env"

# Load .env file with verbose output for debugging
env_loaded = load_dotenv(env_file_path, verbose=True)

if not env_loaded:
    print(f"Warning: Could not load .env file from {env_file_path}")
    # Try to find .env file in alternative locations
    alternative_paths = [
        Path(__file__).parent / ".env",  # src directory
        Path.cwd() / ".env",  # current working directory
    ]
    
    for alt_path in alternative_paths:
        if alt_path.exists():
            print(f"Found alternative .env file at: {alt_path}")
            load_dotenv(alt_path, verbose=True)
            break
    else:
        print("No .env file found in any expected location")


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
            logger.error(
                f"Failed to start monitor: {result.get('error', 'Unknown error')}"
            )
            sys.exit(1)

    except Exception as e:
        logger.error(f"Monitor startup failed: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        if "service" in locals():
            service.stop()
        logger.info("Monitor service stopped")


if __name__ == "__main__":
    main()
