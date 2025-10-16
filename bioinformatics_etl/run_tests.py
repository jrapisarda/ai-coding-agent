#!/usr/bin/env python
"""Run all tests including CLI tests"""

import subprocess
import sys
import os

def run_unit_tests():
    """Run unit tests with pytest"""
    print("Running unit tests...")
    result = subprocess.run([sys.executable, '-m', 'pytest', '-v'], 
                          capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)
    return result.returncode == 0

def run_cli_tests():
    """Run CLI integration tests"""
    print("\nRunning CLI tests...")
    result = subprocess.run([sys.executable, 'test_cli.py'], 
                          capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)
    return result.returncode == 0

def check_installation():
    """Check if package can be imported"""
    try:
        import study_etl
        print("✅ Package import successful")
        return True
    except ImportError as e:
        print(f"❌ Package import failed: {e}")
        return False

if __name__ == '__main__':
    print("Running comprehensive test suite...")
    
    # Check basic import
    import_ok = check_installation()
    
    # Run unit tests
    unit_tests_ok = run_unit_tests()
    
    # Run CLI tests
    cli_tests_ok = run_cli_tests()
    
    print(f"\nSummary:")
    print(f"Package import: {'✅ PASS' if import_ok else '❌ FAIL'}")
    print(f"Unit tests: {'✅ PASS' if unit_tests_ok else '❌ FAIL'}")
    print(f"CLI tests: {'✅ PASS' if cli_tests_ok else '❌ FAIL'}")
    
    if all([import_ok, unit_tests_ok, cli_tests_ok]):
        print("\n🎉 All tests passed! The Study ETL CLI tool is ready to use.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Please check the output above.")
        sys.exit(1)