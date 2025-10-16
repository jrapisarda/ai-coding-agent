#!/usr/bin/env python
"""Run integration test"""

import subprocess
import sys

if __name__ == '__main__':
    print("Running integration test...")
    result = subprocess.run([sys.executable, 'integration_test.py'], 
                          capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    sys.exit(result.returncode)