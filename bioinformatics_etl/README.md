# Study ETL CLI Tool

A robust command-line interface for ETL (Extract, Transform, Load) operations on study data ingestion.

## Features

- **Extract**: Support for CSV, JSON, and Excel file formats
- **Transform**: Data validation, cleaning, and transformation pipelines
- **Load**: Output to multiple formats with schema validation
- **Validation**: Comprehensive data quality checks
- **Logging**: Detailed logging with colored output
- **Configuration**: YAML-based configuration files
- **Error Handling**: Robust error handling and reporting

## Installation

```bash
pip install -r requirements.txt
pip install -e .
```

## Quick Start

```bash
# Basic ETL operation
study-etl process input.csv output.json --config config.yaml

# Validate data only
study-etl validate input.csv --schema schema.json

# Generate sample configuration
study-etl init-config
```

## Configuration

The tool uses YAML configuration files to define:
- Data validation rules
- Transformation pipelines
- Output formats
- Logging settings

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=study_etl

# Run specific test
pytest tests/test_validator.py -v
```

## Development

```bash
# Format code
black study_etl/

# Lint code
flake8 study_etl/
```