# chk-a Makefile
# Developer and operator targets for both local development and GitHub Releases installation

PYTHON ?= python3
VENV ?= venv
PIP := $(VENV)/bin/pip
REPO := tpdevices/chk-a

.PHONY: help dev-install test lint build install uninstall clean version status logs upgrade release-dry-run

help:
	@echo "Targets:"
	@echo "  dev-install      Create venv + install project with dev deps (local dev)"
	@echo "  test             Run the test suite (pytest)"
	@echo "  lint             Run black --check and flake8"
	@echo "  build            Build sdist/wheel"
	@echo "  install          Install from local source (sudo ./install.sh)"
	@echo "  install-github   Install from GitHub Releases (sudo ./install.sh [version])"
	@echo "  uninstall        Remove the systemd service and installed files"
	@echo "  clean            Remove local venv and build artifacts"
	@echo "  version          Show installed version"
	@echo "  status           Show systemd service status"
	@echo "  logs             Follow journalctl logs"
	@echo "  upgrade          Upgrade to specific version (sudo make upgrade VERSION=v1.0.1)"
	@echo "  release-dry-run  Test release workflow locally (creates test tag)"

# Local development
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

# Installation from local source
install:
	sudo ./install.sh

# Installation from GitHub Releases
install-github:
	@echo "Usage: sudo ./install.sh [version]"
	@echo "  Example: sudo ./install.sh v1.0.0"
	@echo "  Default: latest release"

# Systemd service management
uninstall:
	sudo ./uninstall.sh

version:
	@/opt/chk-a/.venv/bin/chk-a --version 2>/dev/null || echo "Not installed or not in PATH"

status:
	systemctl status chk-a

logs:
	journalctl -u chk-a -f

upgrade:
	@if [ -z "$(VERSION)" ]; then \
		echo "Usage: sudo make upgrade VERSION=v1.0.1"; \
		exit 1; \
	fi
	sudo ./install.sh $(VERSION)

# Release workflow testing
release-dry-run:
	git tag -d v0.0.0-test 2>/dev/null || true
	git tag v0.0.0-test
	git push origin v0.0.0-test
	@echo "Check GitHub Actions: https://github.com/$(REPO)/actions"
	@echo "Then clean up: git tag -d v0.0.0-test && git push origin :refs/tags/v0.0.0-test"

# Cleanup
clean:
	rm -rf $(VENV) build dist *.egg-info src/*.egg-info .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true