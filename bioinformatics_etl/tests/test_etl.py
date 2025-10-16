import pytest
import pandas as pd
import tempfile
import os
from study_etl.etl import ETLProcessor


class TestETLProcessor:
    def setup_method(self):
        self.config = {
            'input': {'format': 'csv'},
            'validation': {'required_columns': ['study_id', 'patient_id']},
            'output': {'format': 'csv'}
        }
        self.processor = ETLProcessor(self.config)
    
    def test_process_csv_success(self):
        input_df = pd.DataFrame({
            'study_id': ['S001', 'S002', 'S003'],
            'patient_id': ['P001', 'P002', 'P003'],
            'visit_date': ['2023-01-01', '2023-01-02', '2023-01-03']
        })
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as input_f:
            input_df.to_csv(input_f.name, index=False)
            input_file = input_f.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as output_f:
            output_file = output_f.name
        
        try:
            result = self.processor.process(input_file, output_file, 'csv')
            
            assert result is not None
            assert result['rows_processed'] == 3
            assert os.path.exists(output_file)
            
            output_df = pd.read_csv(output_file)
            assert len(output_df) == 3
            
        finally:
            if os.path.exists(input_file):
                os.unlink(input_file)
            if os.path.exists(output_file):
                os.unlink(output_file)
    
    def test_process_validation_failure(self):
        input_df = pd.DataFrame({
            'study_id': ['S001', 'S002'],
            'visit_date': ['2023-01-01', '2023-01-02']
        })
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as input_f:
            input_df.to_csv(input_f.name, index=False)
            input_file = input_f.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as output_f:
            output_file = output_f.name
        
        try:
            result = self.processor.process(input_file, output_file, 'csv')
            assert result is None
            
        finally:
            if os.path.exists(input_file):
                os.unlink(input_file)
            if os.path.exists(output_file):
                os.unlink(output_file)