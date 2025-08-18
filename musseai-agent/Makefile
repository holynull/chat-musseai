.PHONY: all format lint test tests test_watch integration_tests docker_tests help extended_tests

# Default target executed when no arguments are given to make.
all: help

# Define a variable for the test file path.
TEST_FILE ?= tests/unit_tests/

test:
	python -m pytest $(TEST_FILE)

integration_tests:
	python -m pytest tests/integration_tests 

test_watch:
	python -m ptw --snapshot-update --now . -- -vv tests/unit_tests

test_profile:
	python -m pytest -vv tests/unit_tests/ --profile-svg

extended_tests:
	python -m pytest --only-extended $(TEST_FILE)


######################
# LINTING AND FORMATTING
######################

# Define a variable for Python and notebook files.
PYTHON_FILES=src/
MYPY_CACHE=.mypy_cache
lint format: PYTHON_FILES=.
lint_diff format_diff: PYTHON_FILES=$(shell git diff --name-only --diff-filter=d main | grep -E '\.py$$|\.ipynb$$')
lint_package: PYTHON_FILES=src
lint_tests: PYTHON_FILES=tests
lint_tests: MYPY_CACHE=.mypy_cache_test

lint lint_diff lint_package lint_tests:
	python -m ruff check .
	[ "$(PYTHON_FILES)" = "" ] || python -m ruff format $(PYTHON_FILES) --diff
	[ "$(PYTHON_FILES)" = "" ] || python -m ruff check --select I $(PYTHON_FILES)
	[ "$(PYTHON_FILES)" = "" ] || python -m mypy --strict $(PYTHON_FILES)
	[ "$(PYTHON_FILES)" = "" ] || mkdir -p $(MYPY_CACHE) && python -m mypy --strict $(PYTHON_FILES) --cache-dir $(MYPY_CACHE)

format format_diff:
	ruff format $(PYTHON_FILES)
	ruff check --select I --fix $(PYTHON_FILES)

spell_check:
	codespell --toml pyproject.toml

spell_fix:
	codespell --toml pyproject.toml -w

dev:
	langgraph dev --port 8080  --host 192.168.3.6

PID_FILE := langgraph.pid

start:
	@echo "Starting Langgraph..."
	@nohup langgraph dev --port 8080 > langgraph.log 2>&1 & echo $$! > $(PID_FILE)
	@echo "Langgraph started with PID: $$(cat $(PID_FILE))"

stop:
	@echo "Stopping Langgraph..."
	@if [ -f $(PID_FILE) ]; then \
	    kill $$(cat $(PID_FILE)) && rm $(PID_FILE); \
	    echo "Langgraph stopped."; \
	else \
	    echo "No PID file found. Is Langgraph running?"; \
	fi

build:
# langgraph build -t musseai_agent
	docker build -t musseai-agent .

# Alert Monitor Configuration
MONITOR_PID_FILE := monitor.pid
MONITOR_LOG_FILE := logs/monitor.log
MONITOR_CONFIG_FILE := .env

# Start the alert monitor service
start_monitor:
	@echo "Starting Alert Monitor Service..."
	@if [ -f $(MONITOR_PID_FILE) ]; then \
		echo "Monitor is already running (PID: $$(cat $(MONITOR_PID_FILE)))"; \
		exit 1; \
	fi
	@mkdir -p logs
	@if [ ! -f src/start_monitor.py ]; then \
		echo "Error: start_monitor.py not found"; \
		exit 1; \
	fi
	@chmod +x src/start_monitor.py
	@echo "Starting monitor in background..."
	@nohup python src/start_monitor.py > $(MONITOR_LOG_FILE) 2>&1 & echo $$! > $(MONITOR_PID_FILE)
	@sleep 2
	@if [ -f $(MONITOR_PID_FILE) ] && kill -0 $$(cat $(MONITOR_PID_FILE)) 2>/dev/null; then \
		echo "Alert Monitor started successfully with PID: $$(cat $(MONITOR_PID_FILE))"; \
		echo "Log file: $(MONITOR_LOG_FILE)"; \
	else \
		echo "Failed to start Alert Monitor. Check $(MONITOR_LOG_FILE) for details"; \
		rm -f $(MONITOR_PID_FILE); \
		exit 1; \
	fi


# Stop the alert monitor service
stop_monitor:
	@echo "Stopping Alert Monitor Service..."
	@if [ -f $(MONITOR_PID_FILE) ]; then \
		PID=$$(cat $(MONITOR_PID_FILE)); \
		if kill -0 $$PID 2>/dev/null; then \
			echo "Stopping monitor process (PID: $$PID)..."; \
			kill -TERM $$PID; \
			sleep 3; \
			if kill -0 $$PID 2>/dev/null; then \
				echo "Process still running, forcing termination..."; \
				kill -KILL $$PID; \
				sleep 1; \
			fi; \
			rm -f $(MONITOR_PID_FILE); \
			echo "Alert Monitor stopped successfully"; \
		else \
			echo "Monitor process not running, cleaning up PID file"; \
			rm -f $(MONITOR_PID_FILE); \
		fi; \
	else \
		echo "No PID file found. Monitor may not be running"; \
	fi

# Restart the alert monitor service
restart_monitor: stop_monitor start_monitor

# Check monitor status
status_monitor:
	@echo "Alert Monitor Status:"
	@echo "===================="
	@if [ -f $(MONITOR_PID_FILE) ]; then \
		PID=$$(cat $(MONITOR_PID_FILE)); \
		if kill -0 $$PID 2>/dev/null; then \
			echo "Status: RUNNING"; \
			echo "PID: $$PID"; \
			echo "Uptime: $$(ps -o etime= -p $$PID | tr -d ' ')"; \
			echo "Memory: $$(ps -o rss= -p $$PID | tr -d ' ') KB"; \
			echo "Log file: $(MONITOR_LOG_FILE)"; \
			if [ -f $(MONITOR_LOG_FILE) ]; then \
				echo "Last log entries:"; \
				tail -5 $(MONITOR_LOG_FILE) | sed 's/^/  /'; \
			fi; \
		else \
			echo "Status: STOPPED (PID file exists but process not running)"; \
			echo "Cleaning up stale PID file..."; \
			rm -f $(MONITOR_PID_FILE); \
		fi; \
	else \
		echo "Status: STOPPED"; \
	fi

# View monitor logs
logs_monitor:
	@if [ -f $(MONITOR_LOG_FILE) ]; then \
		echo "Alert Monitor Logs:"; \
		echo "=================="; \
		tail -f $(MONITOR_LOG_FILE); \
	else \
		echo "No log file found at $(MONITOR_LOG_FILE)"; \
	fi

# Follow monitor logs in real-time
logs_monitor_follow:
	@if [ -f $(MONITOR_LOG_FILE) ]; then \
		echo "Following Alert Monitor logs (Ctrl+C to stop):"; \
		echo "================================================"; \
		tail -f $(MONITOR_LOG_FILE); \
	else \
		echo "No log file found at $(MONITOR_LOG_FILE)"; \
		echo "Start the monitor first with: make start_monitor"; \
	fi

# Test monitor configuration
test_monitor_config:
	@echo "Testing Alert Monitor Configuration..."
	@python3 -c "\
import sys; \
sys.path.insert(0, 'src'); \
from alerts_monitor.monitor_cli import setup_monitoring_from_env; \
try: \
    config = setup_monitoring_from_env(); \
    print('✓ Configuration loaded successfully'); \
    print(f'  - Check interval: {config.check_interval_seconds}s'); \
    print(f'  - Max concurrent: {config.max_concurrent_checks}'); \
    print(f'  - Email enabled: {config.enable_email}'); \
    print(f'  - SMS enabled: {config.enable_sms}'); \
    print(f'  - Push enabled: {config.enable_push}'); \
    print(f'  - Webhook enabled: {config.enable_webhook}'); \
except Exception as e: \
    print(f'✗ Configuration error: {e}'); \
    sys.exit(1) \
"

# Clean monitor artifacts
clean_monitor:
	@echo "Cleaning Alert Monitor artifacts..."
	@rm -f $(MONITOR_PID_FILE)
	@rm -f start_monitor.py
	@rm -f $(MONITOR_LOG_FILE)
	@echo "Monitor artifacts cleaned"

# Monitor health check
health_monitor:
	@echo "Alert Monitor Health Check:"
	@echo "=========================="
	@if [ -f $(MONITOR_PID_FILE) ]; then \
		PID=$$(cat $(MONITOR_PID_FILE)); \
		if kill -0 $$PID 2>/dev/null; then \
			echo "✓ Process is running (PID: $$PID)"; \
			if [ -f $(MONITOR_LOG_FILE) ]; then \
				ERROR_COUNT=$$(grep -c "ERROR" $(MONITOR_LOG_FILE) || echo "0"); \
				WARNING_COUNT=$$(grep -c "WARNING" $(MONITOR_LOG_FILE) || echo "0"); \
				if [ $$ERROR_COUNT -eq 0 ]; then \
					echo "✓ No errors in log file"; \
				else \
					echo "⚠ Found $$ERROR_COUNT errors in log file"; \
				fi; \
				if [ $$WARNING_COUNT -eq 0 ]; then \
					echo "✓ No warnings in log file"; \
				else \
					echo "⚠ Found $$WARNING_COUNT warnings in log file"; \
				fi; \
				RECENT_ACTIVITY=$$(tail -10 $(MONITOR_LOG_FILE) | grep -c "$$(date +'%Y-%m-%d')" || echo "0"); \
				if [ $$RECENT_ACTIVITY -gt 0 ]; then \
					echo "✓ Recent activity detected"; \
				else \
					echo "⚠ No recent activity in logs"; \
				fi; \
			else \
				echo "⚠ Log file not found"; \
			fi; \
		else \
			echo "✗ Process not running"; \
		fi; \
	else \
		echo "✗ Monitor not started"; \
	fi

# Create monitor environment template
create_monitor_env:
	@echo "Creating monitor environment template..."
	@if [ ! -f .env.monitor.example ]; then \
		echo "# Alert Monitor Configuration" > .env.monitor.example; \
		echo "ALERT_CHECK_INTERVAL=60" >> .env.monitor.example; \
		echo "ALERT_MAX_CONCURRENT=10" >> .env.monitor.example; \
		echo "ALERT_NOTIFICATION_TIMEOUT=30" >> .env.monitor.example; \
		echo "" >> .env.monitor.example; \
		echo "# Email Notifications" >> .env.monitor.example; \
		echo "ALERT_EMAIL_ENABLED=true" >> .env.monitor.example; \
		echo "ALERT_SMTP_SERVER=smtp.gmail.com" >> .env.monitor.example; \
		echo "ALERT_SMTP_PORT=587" >> .env.monitor.example; \
		echo "ALERT_SMTP_USERNAME=your-email@gmail.com" >> .env.monitor.example; \
		echo "ALERT_SMTP_PASSWORD=your-app-password" >> .env.monitor.example; \
		echo "ALERT_FROM_EMAIL=your-email@gmail.com" >> .env.monitor.example; \
		echo "" >> .env.monitor.example; \
		echo "# SMS Notifications (Twilio)" >> .env.monitor.example; \
		echo "ALERT_SMS_ENABLED=false" >> .env.monitor.example; \
		echo "TWILIO_ACCOUNT_SID=your-twilio-sid" >> .env.monitor.example; \
		echo "TWILIO_AUTH_TOKEN=your-twilio-token" >> .env.monitor.example; \
		echo "TWILIO_FROM_NUMBER=+1234567890" >> .env.monitor.example; \
		echo "" >> .env.monitor.example; \
		echo "# Push Notifications (Firebase)" >> .env.monitor.example; \
		echo "ALERT_PUSH_ENABLED=false" >> .env.monitor.example; \
		echo "FIREBASE_SERVER_KEY=your-firebase-key" >> .env.monitor.example; \
		echo "" >> .env.monitor.example; \
		echo "# Webhook Notifications" >> .env.monitor.example; \
		echo "ALERT_WEBHOOK_ENABLED=true" >> .env.monitor.example; \
		echo "ALERT_WEBHOOK_TIMEOUT=10" >> .env.monitor.example; \
		echo "ALERT_WEBHOOK_RETRIES=2" >> .env.monitor.example; \
		echo "✓ Created .env.monitor.example"; \
		echo "  Copy this file to .env and configure your settings"; \
	else \
		echo "✓ .env.monitor.example already exists"; \
	fi


# Interactive monitor setup
setup_monitor:
	@echo "Alert Monitor Interactive Setup"
	@echo "==============================="
	@make create_monitor_env
	@echo ""
	@echo "1. Configure your environment:"
	@echo "   cp .env.monitor.example .env"
	@echo "   # Edit .env with your configuration"
	@echo ""
	@echo "2. Test configuration:"
	@echo "   make test_monitor_config"
	@echo ""
	@echo "3. Start the monitor:"
	@echo "   make start_monitor"
	@echo ""
	@echo "Available commands:"
	@echo "  make start_monitor     - Start the alert monitor"
	@echo "  make stop_monitor      - Stop the alert monitor"
	@echo "  make restart_monitor   - Restart the alert monitor"
	@echo "  make status_monitor    - Check monitor status"
	@echo "  make logs_monitor      - View recent logs"
	@echo "  make logs_monitor_follow - Follow logs in real-time"
	@echo "  make health_monitor    - Run health check"
	@echo "  make clean_monitor     - Clean monitor artifacts"

# Update help target to include monitor commands
help:
	@echo '----'
	@echo 'format                       - run code formatters'
	@echo 'lint                         - run linters'
	@echo 'test                         - run unit tests'
	@echo 'tests                        - run unit tests'
	@echo 'test TEST_FILE=<test_file>   - run all tests in file'
	@echo 'test_watch                   - run unit tests in watch mode'
	@echo ''
	@echo 'LANGGRAPH COMMANDS:'
	@echo 'dev                          - start langgraph dev server'
	@echo 'start                        - start langgraph in background'
	@echo 'stop                         - stop langgraph service'
	@echo 'build                        - build docker image'
	@echo ''
	@echo 'ALERT MONITOR COMMANDS:'
	@echo 'setup_monitor                - interactive monitor setup'
	@echo 'start_monitor                - start alert monitor service'
	@echo 'stop_monitor                 - stop alert monitor service'
	@echo 'restart_monitor              - restart alert monitor service'
	@echo 'status_monitor               - check monitor status'
	@echo 'logs_monitor                 - view monitor logs'
	@echo 'logs_monitor_follow          - follow monitor logs'
	@echo 'health_monitor               - run monitor health check'
	@echo 'test_monitor_config          - test monitor configuration'
	@echo 'clean_monitor                - clean monitor artifacts'
	@echo 'create_monitor_env           - create environment template'

# Update .PHONY to include all monitor targets
.PHONY: all format lint test tests test_watch integration_tests docker_tests help extended_tests \
	dev start stop build \
	start_monitor stop_monitor restart_monitor status_monitor logs_monitor logs_monitor_follow \
	test_monitor_config clean_monitor health_monitor create_monitor_env setup_monitor \
	create_monitor_script

# Monitor service management aliases for convenience
monitor-start: start_monitor
monitor-stop: stop_monitor
monitor-restart: restart_monitor
monitor-status: status_monitor
monitor-logs: logs_monitor
monitor-health: health_monitor
monitor-setup: setup_monitor
