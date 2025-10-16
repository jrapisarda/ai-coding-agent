import pandas as pd
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class DataValidator:
    def __init__(self, config):
        self.config = config
        self.schema = None
        self._load_schema()
    
    def _load_schema(self):
        schema_file = self.config.get('schema_file')
        if schema_file and Path(schema_file).exists():
            try:
                with open(schema_file, 'r') as f:
                    self.schema = json.load(f)
                logger.info(f"Schema loaded from {schema_file}")
            except Exception as e:
                logger.warning(f"Failed to load schema from {schema_file}: {e}")
    
    def validate_file(self, file_path):
        try:
            df = self._load_data(file_path)
            if df is None:
                return False, ["Failed to load data file"]
            
            errors = []
            errors.extend(self._validate_required_columns(df))
            errors.extend(self._validate_data_types(df))
            
            is_valid = len(errors) == 0
            if is_valid:
                logger.info(f"Validation passed for {file_path}")
            else:
                logger.warning(f"Validation failed for {file_path} with {len(errors)} errors")
            
            return is_valid, errors
            
        except Exception as e:
            logger.error(f"Validation error for {file_path}: {e}")
            return False, [str(e)]
    
    def _load_data(self, file_path):
        try:
            file_path = Path(file_path)
            
            if file_path.suffix.lower() == '.csv':
                return pd.read_csv(file_path)
            elif file_path.suffix.lower() == '.json':
                return pd.read_json(file_path)
            elif file_path.suffix.lower() in ['.xls', '.xlsx']:
                return pd.read_excel(file_path)
            else:
                logger.error(f"Unsupported file format: {file_path.suffix}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to load data from {file_path}: {e}")
            return None
    
    def _validate_required_columns(self, df):
        errors = []
        required_columns = self.config.get('required_columns', [])
        
        for col in required_columns:
            if col not in df.columns:
                errors.append(f"Missing required column: {col}")
            elif df[col].isnull().all():
                errors.append(f"Required column '{col}' has no data")
        
        return errors
    
    def _validate_data_types(self, df):
        errors = []
        data_types = self.config.get('data_types', {})
        
        for column, expected_type in data_types.items():
            if column not in df.columns:
                continue
            
            try:
                if expected_type == 'date':
                    pd.to_datetime(df[column])
                elif expected_type == 'numeric':
                    pd.to_numeric(df[column])
                elif expected_type == 'integer':
                    pd.to_numeric(df[column], downcast='integer')
            except Exception:
                errors.append(f"Column '{column}' should be of type {expected_type}")
        
        return errors