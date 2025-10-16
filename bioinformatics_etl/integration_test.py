#!/usr/bin/env python
"""Simple integration test for the CLI tool"""

import subprocess
import sys
import os

def run_command(cmd):
    """Run a command and return success status"""
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(f"Command: {' '.join(cmd)}")
    print(f"Return code: {result.returncode}")
    if result.stdout:
        print(f"Output: {result.stdout}")
    if result.stderr:
        print(f"Errors: {result.stderr}")
    return result.returncode == 0

def main():
    """Run integration tests"""
    print("🧪 Running Study ETL CLI Integration Tests")
    print("=" * 50)
    
    # Test 1: Help command
    print("\n1. Testing help command...")
    cmd1 = [sys.executable, '-m', 'study_etl.cli', '--help']
    success1 = run_command(cmd1)
    
    # Test 2: Validate sample data
    print("\n2. Testing validate command...")
    sample_file = "sample_data/sample_study_data.csv"
    if os.path.exists(sample_file):
        cmd2 = [sys.executable, '-m', 'study_etl.cli', 'validate', sample_file]
        success2 = run_command(cmd2)
    else:
        print(f"❌ Sample file {sample_file} not found")
        success2 = False
    
    # Test 3: Process data
    print("\n3. Testing process command...")
    if os.path.exists(sample_file):
        cmd3 = [sys.executable, '-m', 'study_etl.cli', 'process', sample_file, 'test_output.json', '--format', 'json']
        success3 = run_command(cmd3)
        
        # Clean up
        if os.path.exists('test_output.json'):
            os.remove('test_output.json')
    else:
        print(f"❌ Sample file {sample_file} not found")
        success3 = False
    
    # Test 4: Init config
    print("\n4. Testing init-config command...")
    cmd4 = [sys.executable, '-m', 'study_etl.cli', 'init-config', '--output', 'test_config.yaml']
    success4 = run_command(cmd4)
    
    # Clean up
    if os.path.exists('test_config.yaml'):
        os.remove('test_config.yaml')
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print(f"Help command: {'✅ PASS' if success1 else '❌ FAIL'}")
    print(f"Validate command: {'✅ PASS' if success2 else '❌ FAIL'}")
    print(f"Process command: {'✅ PASS' if success3 else '❌ FAIL'}")
    print(f"Init-config command: {'✅ PASS' if success4 else '❌ FAIL'}")
    
    total_tests = 4
    passed_tests = sum([success1, success2, success3, success4])
    
    print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All integration tests passed!")
        return 0
    else:
        print("❌ Some integration tests failed!")
        return 1

if __name__ == '__main__':
    sys.exit(main())