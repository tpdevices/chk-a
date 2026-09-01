# chk-a Makefile (Loop 6)
# Common developer / operator targets.

PYTHON ?= python3
VENV ?= venv
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest

.PHONY: help install uninstall test lint build dev-install clean

help:
	@echo "Targets:"
	@echo "  dev-install  Create venv + install project with dev deps"
	@echo "  test         Run the test suite (pytest)"
	@echo "  lint         Run black --check and flake8"
	@echo "  build        Build sdist/wheel"
	@echo "  install      Install as a systemd service (sudo ./install.sh)"
	@echo "  uninstall    Remove the systemd service and installed files"
	@echo "  clean        Remove local venv and build artifacts"

dev-install:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m black --check src tests
	$(PYTHON) -m flake8 src

build:
	$(PYTHON) -m build

install:
	sudo ./install.sh

uninstall:
	sudo ./uninstall.sh

clean:
	rm -rf $(VENV) build dist *.egg-info src/*.egg-info .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
