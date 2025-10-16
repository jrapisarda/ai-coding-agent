import pandas as pd
import logging
from pathlib import Path
from .validator import DataValidator

logger = logging.getLogger(__name__)


class ETLProcessor:
    def __init__(self, config):
        self.config = config
        self.validator = DataValidator(config.get('validation', {}))
    
    def process(self, input_file, output_file, output_format='csv'):
        try:
            logger.info(f"Starting ETL process: {input_file} -> {output_file}")
            
            # Extract
            df = self._extract(input_file)
            if df is None:
                return None
            
            initial_rows = len(df)
            logger.info(f"Extracted {initial_rows} rows")
            
            # Validate
            is_valid, errors = self.validator.validate_file(input_file)
            if not is_valid:
                logger.error(f"Validation failed: {errors}")
                return None
            
            # Transform
            df = self._transform(df)
            if df is None:
                return None
            
            transformed_rows = len(df)
            logger.info(f"Transformed data: {initial_rows} -> {transformed_rows} rows")
            
            # Load
            success = self._load(df, output_file, output_format)
            if not success:
                return None
            
            logger.info(f"ETL process completed successfully")
            return {
                'rows_processed': transformed_rows,
                'input_file': input_file,
                'output_file': output_file
            }
            
        except Exception as e:
            logger.error(f"ETL process failed: {e}")
            return None
    
    def _extract(self, input_file):
        try:
            file_path = Path(input_file)
            
            if file_path.suffix.lower() == '.csv':
                return pd.read_csv(file_path)
            elif file_path.suffix.lower() == '.json':
                return pd.read_json(file_path)
            elif file_path.suffix.lower() in ['.xls', '.xlsx']:
                return pd.read_excel(file_path)
            else:
                logger.error(f"Unsupported input format: {file_path.suffix}")
                return None
                
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return None
    
    def _transform(self, df):
        try:
            # Basic transformations
            df = df.drop_duplicates()
            logger.info("Removed duplicates")
            
            # Strip whitespace from string columns
            string_columns = df.select_dtypes(include=['object']).columns
            df[string_columns] = df[string_columns].apply(lambda x: x.str.strip())
            logger.info("Stripped whitespace from string columns")
            
            return df
            
        except Exception as e:
            logger.error(f"Transformation failed: {e}")
            return None
    
    def _load(self, df, output_file, output_format):
        try:
            if output_format == 'csv':
                df.to_csv(output_file, index=False)
            elif output_format == 'json':
                df.to_json(output_file, orient='records', indent=2)
            elif output_format == 'excel':
                df.to_excel(output_file, index=False)
            else:
                logger.error(f"Unsupported output format: {output_format}")
                return False
            
            logger.info(f"Data saved to {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Loading failed: {e}")
            return False