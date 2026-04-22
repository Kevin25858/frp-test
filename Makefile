.PHONY: build build-web build-desktop build-all test clean deps

# Python virtual environment
VENV = venv
BIN = $(VENV)/bin

# Build directories
BUILD_DIR = bin

# Version info
VERSION = 1.0.0

build-server: $(VENV)
	@echo "Building frp-monitor (server)..."
	@mkdir -p $(BUILD_DIR)
	$(BIN)/pyinstaller --onefile --name frp-monitor --distpath $(BUILD_DIR) \
		--add-data frp_monitor/web/static:frp_monitor/web/static \
		cli/main.py -- --command server
	@echo "Build complete: $(BUILD_DIR)/frp-monitor"

build-web: $(VENV)
	@echo "Building frp-monitor-web..."
	@mkdir -p $(BUILD_DIR)
	$(BIN)/pyinstaller --onefile --name frp-monitor-web --distpath $(BUILD_DIR) \
		cli/web_dashboard.py
	@echo "Build complete: $(BUILD_DIR)/frp-monitor-web"

build-desktop: $(VENV)
	@echo "Building frp-monitor-desktop..."
	@mkdir -p $(BUILD_DIR)
	$(BIN)/pyinstaller --onefile --name frp-monitor-desktop --distpath $(BUILD_DIR) \
		--hidden-import PySimpleGUI \
		cli/desktop.py
	@echo "Build complete: $(BUILD_DIR)/frp-monitor-desktop"

build-all: build-server build-web build-desktop
	@echo "All builds complete"

$(VENV):
	python3 -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements.txt

test: $(VENV)
	@echo "Running tests..."
	$(BIN)/python -m pytest tests/ -v
	@echo "Tests complete"

clean:
	@echo "Cleaning build artifacts..."
	rm -rf $(BUILD_DIR)
	rm -rf build dist
	rm -rf *.spec
	rm -f *.db
	@echo "Clean complete"

deps: $(VENV)
	@echo "Dependencies ready"

.DEFAULT_GOAL := build-all
