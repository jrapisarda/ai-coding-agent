#!/bin/bash
# Quick test script for the CLI tool

echo "Testing Study ETL CLI Tool"
echo "=========================="

# Test help
echo "1. Testing help command:"
python -m study_etl.cli --help

# Test validation
echo -e "\n2. Testing validation:"
python -m study_etl.cli validate sample_data/sample_study_data.csv

# Test processing
echo -e "\n3. Testing processing:"
python -m study_etl.cli process sample_data/sample_study_data.csv test_output.json --format json

# Test config generation
echo -e "\n4. Testing config generation:"
python -m study_etl.cli init-config --output test_config.yaml

# Cleanup
rm -f test_output.json test_config.yaml

echo -e "\n✅ All tests completed!"