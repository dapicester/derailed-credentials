.PHONY: help test test-unit test-integration test-cli test-performance test-security test-coverage lint format type-check install-dev clean

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $1, $2}'

install-dev:  ## Install development dependencies
	pip install -r requirements-test.txt

test: test-unit test-integration test-cli  ## Run all tests

test-unit:  ## Run unit tests
	pytest test_credentials.py::TestCredentials -v

test-integration:  ## Run integration tests
	pytest test_credentials.py::TestCredentialsIntegration -v

test-cli:  ## Run CLI tests
	pytest test_credentials.py::TestCredentialsCLI -v

test-performance:  ## Run performance tests
	pytest test_performance.py -v -m slow

test-security:  ## Run security tests
	pytest test_security.py -v

test-coverage:  ## Run tests with coverage reporting
	pytest --cov=credentials --cov-report=html --cov-report=term-missing

test-parallel:  ## Run tests in parallel
	pytest -n auto

lint:  ## Run linting
	flake8 credentials.py test_*.py
	isort --check-only credentials.py test_*.py

format:  ## Format code
	black credentials.py test_*.py
	isort credentials.py test_*.py

type-check:  ## Run type checking
	mypy credentials.py

clean:  ## Clean up generated files
	rm -rf __pycache__ .pytest_cache .coverage htmlcov
	rm -rf *.egg-info build dist
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete

benchmark:  ## Run performance benchmarks
	pytest --benchmark-only test_performance.py



