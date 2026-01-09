.PHONY: help test test-watch lint format type-check clean

help:  ## Show this help message
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

test:  ## Run tests with coverage reporting
	pytest --cov=derailed --cov-report=html --cov-report=term-missing $(filter-out $@,$(MAKECMDGOALS))

test-watch:  ## Run tests on file changes
	ptw .

lint:  ## Run linting
	ruff check

tox:
	uv tool install tox --with tox-uv
	tox

format:  ## Format code
	ruff check --select I --fix
	ruff format

type-check:  ## Run type checking
	mypy

clean:  ## Clean up generated files
	rm -rf __pycache__ .pytest_cache .coverage htmlcov
	rm -rf *.egg-info build dist
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
