.PHONY: install test lint format clean help

help:
	@echo "Available commands:"
	@echo "  install    Install dependencies and package"
	@echo "  test       Run tests"
	@echo "  lint       Run linting"
	@echo "  format     Format code"
	@echo "  clean      Clean build artifacts"

install:
	pip install -r requirements.txt
	pip install -e .

test:
	pytest

test-coverage:
	pytest --cov=study_etl --cov-report=html

lint:
	flake8 study_etl/ tests/

format:
	black study_etl/ tests/

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf htmlcov/
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete