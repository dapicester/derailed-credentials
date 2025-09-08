.PHONY: help test test-watch lint format type-check clean

help:  ## Show this help message
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

test:  ## Run tests with coverage reporting
	pytest --cov=credentials --cov-report=html --cov-report=term-missing

test-watch:  ## Run tests on file changes
	ptw .

lint:  ## Run linting
	flake8 credentials.py test_*.py
	isort --check-only credentials.py test_*.py

format:  ## Format code
	black credentials.py test_*.py
	isort credentials.py test_*.py

type-check:  ## Run type checking
	mypy

clean:  ## Clean up generated files
	rm -rf __pycache__ .pytest_cache .coverage htmlcov
	rm -rf *.egg-info build dist
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
