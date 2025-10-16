"""Utility functions for Study ETL"""

import logging
import coloredlogs


def setup_logging(verbose=False, quiet=False):
    """Setup logging configuration"""
    if quiet:
        level = 'ERROR'
    elif verbose:
        level = 'DEBUG'
    else:
        level = 'INFO'
    
    coloredlogs.install(
        level=level,
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def format_error_message(error, row=None, column=None):
    """Format error message with context"""
    msg = str(error)
    if row is not None:
        msg = f"Row {row}: {msg}"
    if column is not None:
        msg = f"Column '{column}': {msg}"
    return msg