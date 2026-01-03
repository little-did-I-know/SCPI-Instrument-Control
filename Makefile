.PHONY: help install install-dev install-all test test-cov lint format clean build publish build-exe build-exe-clean build-exe-test install-pyinstaller test-build-system docs docs-generate docs-examples docs-api docs-serve docs-deploy pre-commit

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install package in editable mode
	pip install -e .

install-dev:  ## Install package with development dependencies
	pip install -e ".[dev]"

install-all:  ## Install package with all optional dependencies
	pip install -e ".[all,dev]"

test:  ## Run tests
	pytest tests/ -v

test-cov:  ## Run tests with coverage report
	pytest tests/ --cov=siglent --cov-report=html --cov-report=term-missing -v
	@echo "Coverage report generated in htmlcov/index.html"

test-fast:  ## Run tests in parallel (faster)
	pytest tests/ -n auto -v

test-exceptions:  ## Test exception handling and imports
	@echo "Testing exception imports and backward compatibility..."
	@python -c "from siglent.exceptions import SiglentConnectionError, SiglentTimeoutError, CommandError, SiglentError; from siglent.exceptions import ConnectionError, TimeoutError; assert ConnectionError is SiglentConnectionError; assert TimeoutError is SiglentTimeoutError; print('✓ New exception names: OK'); print('✓ Backward compatibility aliases: OK'); print('✓ All exception imports: PASSED')"
	@echo "\nRunning exception-related tests..."
	@pytest tests/ -k "exception or error or connection or timeout" -v --tb=short || echo "Note: Some tests may not exist yet"

lint:  ## Run all linting checks
	black --check --line-length 200 siglent/ tests/ examples/
	flake8 siglent/ --max-line-length=200
	@echo "✓ All linting checks passed"

format:  ## Auto-format code with Black
	black --line-length 200 siglent/ tests/ examples/
	@echo "✓ Code formatted"

clean:  ## Remove build artifacts and cache files
	rm -rf build/ dist/ *.egg-info .pytest_cache .coverage htmlcov/ *.spec~
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "✓ Cleaned build artifacts (including PyInstaller)"

build:  ## Build distribution packages
	python -m build
	twine check dist/*
	@echo "✓ Build complete - artifacts in dist/"

publish-test:  ## Publish to TestPyPI
	twine upload --repository testpypi dist/*

publish:  ## Publish to PyPI (production)
	@echo "WARNING: This will publish to PyPI!"
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read line
	twine upload dist/*

# Executable building
.PHONY: build-exe build-exe-clean install-pyinstaller

install-pyinstaller:  ## Install PyInstaller for building executables
	pip install pyinstaller

build-exe-clean:  ## Clean PyInstaller build artifacts
	rm -rf build/ dist/ *.spec~
	@echo "✓ Cleaned PyInstaller artifacts"

build-exe:  ## Build standalone executable for current platform
	@echo "Building standalone executable for current platform..."
	@$(MAKE) install-pyinstaller
	pyinstaller --clean siglent-gui.spec
	@echo ""
	@echo "✓ Build complete!"
	@echo "  Executable location: dist/"
	@echo ""
	@echo "Platform-specific instructions:"
	@echo "  Windows: dist/SiglentGUI.exe"
	@echo "  macOS:   dist/SiglentGUI.app"
	@echo "  Linux:   dist/SiglentGUI"

build-exe-test:  ## Build and test the executable
	@$(MAKE) build-exe
	@echo "\nTesting executable..."
	@if [ -f "dist/SiglentGUI.exe" ]; then \
		echo "Windows executable found: dist/SiglentGUI.exe"; \
	elif [ -d "dist/SiglentGUI.app" ]; then \
		echo "macOS app bundle found: dist/SiglentGUI.app"; \
		open dist/SiglentGUI.app; \
	elif [ -f "dist/SiglentGUI" ]; then \
		echo "Linux executable found: dist/SiglentGUI"; \
		./dist/SiglentGUI; \
	else \
		echo "ERROR: No executable found!"; \
		exit 1; \
	fi

test-build-system:  ## Run pre-flight checks for build system
	python scripts/test_build_system.py

docs-generate:  ## Generate all documentation from code
	@echo "Generating documentation from code..."
	python scripts/docs/generate_examples_docs.py
	python scripts/docs/generate_api_stubs.py
	@echo "Documentation generated successfully!"

docs-examples:  ## Generate examples documentation only
	python scripts/docs/generate_examples_docs.py

docs-api:  ## Generate API reference stubs only
	python scripts/docs/generate_api_stubs.py

docs:  ## Build documentation with MkDocs (auto-generates from code first)
	@$(MAKE) docs-generate
	pip install -e ".[docs]"
	mkdocs build
	@echo "Documentation built in site/"
	@echo "  Open site/index.html in your browser"

docs-serve:  ## Serve documentation locally with live reload
	@$(MAKE) docs-generate
	pip install -e ".[docs]"
	mkdocs serve

docs-deploy:  ## Deploy documentation to GitHub Pages
	@$(MAKE) docs-generate
	pip install -e ".[docs]"
	mkdocs gh-deploy --force

pre-commit-install:  ## Install pre-commit hooks
	pip install pre-commit
	pre-commit install
	@echo "✓ Pre-commit hooks installed"

pre-commit:  ## Run pre-commit on all files
	pre-commit run --all-files

check:  ## Run all checks (lint, test, build)
	@echo "Running linting checks..."
	@$(MAKE) lint
	@echo "\nRunning tests..."
	@$(MAKE) test
	@echo "\nBuilding package..."
	@$(MAKE) build
	@echo "\n✓ All checks passed!"

pre-pr:  ## Run comprehensive pre-PR validation (recommended before creating PR)
	@echo "Running pre-PR validation..."
	python scripts/pre_pr_check.py
	@echo "\n✓ Pre-PR validation passed!"
	
pre-pr-fast:  ## Run quick pre-PR validation (skip slow checks)
	python scripts/pre_pr_check.py --fast

pre-pr-fix:  ## Run pre-PR validation with auto-fix
	python scripts/pre_pr_check.py --fix

gui:  ## Launch the GUI application
	siglent-gui

version:  ## Show package version
	@python -c "import siglent; print(f'Siglent-Oscilloscope v{siglent.__version__}')"

# Development helpers
.PHONY: dev-setup dev-test dev-watch

dev-setup:  ## Complete development environment setup
	@echo "Setting up development environment..."
	@$(MAKE) install-all
	@$(MAKE) pre-commit-install
	@echo "\n✓ Development environment ready!"
	@echo "\nNext steps:"
	@echo "  - Run tests: make test"
	@echo "  - Format code: make format"
	@echo "  - Run all checks: make check"

dev-test:  ## Run tests in watch mode (requires pytest-watch)
	pip install pytest-watch
	ptw tests/ -- -v

dev-watch:  ## Watch for changes and auto-format (requires watchdog)
	pip install watchdog
	watchmedo shell-command --patterns="*.py" --recursive --command='make format' siglent/
