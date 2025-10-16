import pytest
import pandas as pd
import tempfile
import os
from study_etl.validator import DataValidator


class TestDataValidator:
    
    def setup_method(self):
        """Setup test configuration"""
        self.config = {
            'required_columns': ['study_id', 'patient_id'],
            'data_types': {
                'visit_date': 'date',
                'age': 'integer'
            }
        }
        self.validator = DataValidator(self.config)
    
    def test_validate_required_columns_success(self):
        """Test validation with all required columns present"""
        # Create test data
        df = pd.DataFrame({
            'study_id': ['S001', 'S002'],
            'patient_id': ['P001', 'P002'],
            'visit_date': ['2023-01-01', '2023-01-02']
        })
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name
        
        try:
            is_valid, errors = self.validator.validate_file(temp_file)
            assert is_valid is True
            assert len(errors) == 0
        finally:
            os.unlink(temp_file)
    
    def test_validate_missing_required_columns(self):
        """Test validation with missing required columns"""
        # Create test data with missing column
        df = pd.DataFrame({
            'study_id': ['S001', 'S002'],
            'visit_date': ['2023-01-01', '2023-01-02']
        })
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name
        
        try:
            is_valid, errors = self.validator.validate_file(temp_file)
            assert is_valid is False
            assert len(errors) > 0
            assert any("Missing required column: patient_id" in error for error in errors)
        finally:
            os.unlink(temp_file)
    
    def test_validate_data_types(self):
        """Test data type validation"""
        # Create test data with invalid data type
        df = pd.DataFrame({
            'study_id': ['S001', 'S002'],
            'patient_id': ['P001', 'P002'],
            'visit_date': ['invalid_date', '2023-01-02'],
            'age': ['not_a_number', '25']
        })
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name
        
        try:
            is_valid, errors = self.validator.validate_file(temp_file)
            assert is_valid is False
            assert len(errors) > 0
        finally:
            os.unlink(temp_file)
    
    def test_load_csv_data(self):
        """Test loading CSV data"""
        df = pd.DataFrame({
            'study_id': ['S001', 'S002'],
            'patient_id': ['P001', 'P002']
        })
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_file = f.name
        
        try:
            loaded_df = self.validator._load_data(temp_file)
            assert loaded_df is not None
            assert len(loaded_df) == 2
            assert list(loaded_df.columns) == ['study_id', 'patient_id']
        finally:
            os.unlink(temp_file)
    
    def test_load_unsupported_format(self):
        """Test loading unsupported file format"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("some text")
            temp_file = f.name
        
        try:
            loaded_df = self.validator._load_data(temp_file)
            assert loaded_df is None
        finally:
            os.unlink(temp_file)