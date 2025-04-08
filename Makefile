.PHONY: start_dev
set_proxy:
	export HTTP_PROXY=http://127.0.0.1:7890
	export HTTPS_PROXY=http://127.0.0.1:7890
	export NO_PROXY=localhost,127.0.0.1
start_dev:
	export HTTP_PROXY=http://127.0.0.1:7890
	export HTTPS_PROXY=http://127.0.0.1:7890
	export NO_PROXY=localhost,127.0.0.1
	uvicorn backend.main:app --reload --port 8080 --host 192.168.3.6
.PHONY: start stop format

PID_FILE := uvicorn.pid

start:
	@echo "Starting Uvicorn..."
	@nohup uvicorn backend.main:app --reload --port 8080 > uvicorn.log 2>&1 & echo $$! > $(PID_FILE)
	@echo "Uvicorn started with PID: $$(cat $(PID_FILE))"

stop:
	@echo "Stopping Uvicorn..."
	@if [ -f $(PID_FILE) ]; then \
	    kill $$(cat $(PID_FILE)) && rm $(PID_FILE); \
	    echo "Uvicorn stopped."; \
	else \
	    echo "No PID file found. Is Uvicorn running?"; \
	fi
.PHONY: format
format:
	black .
	isort .