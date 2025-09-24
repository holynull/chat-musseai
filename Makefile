build_musseai_agent:
	@echo "Building AI Agent image..."
	docker build -f musseai-agent/Dockerfile.musseai_agent -t musseai-agent musseai-agent 

build_trading_signal:
	@echo "Building Trading Signal Docker image..."
	docker build -f trading_signal/Dockerfile.trading_signal -t musseai-trading-signal trading_signal

# Build all service images
build_all_services: build_musseai_agent build_trading_signal
	@echo "All Docker images built successfully"