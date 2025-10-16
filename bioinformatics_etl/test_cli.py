#!/usr/bin/env python
"""Test the CLI functionality"""

import subprocess
import sys
import os

def test_cli_help():
    """Test CLI help command"""
    result = subprocess.run([sys.executable, '-m', 'study_etl.cli', '--help'], 
                          capture_output=True, text=True)
    print("Help command output:")
    print(result.stdout)
    print("Help command errors:", result.stderr)
    return result.returncode == 0

def test_cli_validate():
    """Test CLI validate command"""
    sample_file = "sample_data/sample_study_data.csv"
    if os.path.exists(sample_file):
        result = subprocess.run([sys.executable, '-m', 'study_etl.cli', 'validate', sample_file], 
                              capture_output=True, text=True)
        print("Validate command output:")
        print(result.stdout)
        print("Validate command errors:", result.stderr)
        return result.returncode == 0
    else:
        print(f"Sample file {sample_file} not found")
        return False

def test_cli_process():
    """Test CLI process command"""
    input_file = "sample_data/sample_study_data.csv"
    output_file = "test_output.json"
    
    if os.path.exists(input_file):
        # Clean up any existing output file
        if os.path.exists(output_file):
            os.remove(output_file)
            
        result = subprocess.run([
            sys.executable, '-m', 'study_etl.cli', 'process', 
            input_file, output_file, '--format', 'json'
        ], capture_output=True, text=True)
        
        print("Process command output:")
        print(result.stdout)
        print("Process command errors:", result.stderr)
        
        # Check if output file was created
        success = os.path.exists(output_file)
        if success:
            print(f"Output file created: {output_file}")
            # Clean up
            os.remove(output_file)
        
        return result.returncode == 0 and success
    else:
        print(f"Input file {input_file} not found")
        return False

if __name__ == '__main__':
    print("Testing Study ETL CLI...")
    
    print("\n1. Testing help command:")
    help_ok = test_cli_help()
    
    print("\n2. Testing validate command:")
    validate_ok = test_cli_validate()
    
    print("\n3. Testing process command:")
    process_ok = test_cli_process()
    
    print(f"\nResults:")
    print(f"Help command: {'✅ PASS' if help_ok else '❌ FAIL'}")
    print(f"Validate command: {'✅ PASS' if validate_ok else '❌ FAIL'}")
    print(f"Process command: {'✅ PASS' if process_ok else '❌ FAIL'}")
    
    if all([help_ok, validate_ok, process_ok]):
        print("\n🎉 All CLI tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)