"""Configuration management for Study ETL"""

import yaml
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration loading and validation"""
    
    DEFAULT_CONFIG = {
        'etl': {
            'input': {
                'format': 'csv',
                'encoding': 'utf-8',
                'delimiter': ',',
                'header': True
            },
            'validation': {
                'enabled': True,
                'required_columns': ['study_id', 'patient_id'],
                'data_types': {}
            },
            'output': {
                'format': 'csv',
                'encoding': 'utf-8'
            }
        },
        'logging': {
            'level': 'INFO',
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        }
    }
    
    def __init__(self, config_path=None):
        """Initialize configuration manager"""
        self.config = self.DEFAULT_CONFIG.copy()
        
        if config_path:
            self.load_config(config_path)
    
    def load_config(self, config_path):
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    self._merge_config(self.config, user_config)
            logger.info(f"Configuration loaded from {config_path}")
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
    
    def _merge_config(self, base, update):
        """Recursively merge configuration dictionaries"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def get_etl_config(self):
        """Get ETL configuration"""
        return self.config.get('etl', {})
    
    def get_validation_config(self):
        """Get validation configuration"""
        etl_config = self.get_etl_config()
        return etl_config.get('validation', {})
    
    def get_logging_config(self):
        """Get logging configuration"""
        return self.config.get('logging', {})