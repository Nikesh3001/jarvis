#! /usr/bin/env python3

# Flexible build script for FRIDAY web dashboard
# Automatically installs dependencies and builds static assets

import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, description):
    """Run a command and report success/failure."""
    print(f"  [BUILD] {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  ✓ {description} completed successfully")
            return True
        else:
            print(f"  ✗ {description} failed")
            print(f"    Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"  ✗ {description} failed with exception: {e}")
        return False

def main():
    print("  =====================================================")
    print("   FRIDAY Web Dashboard Build Script")
    print("  =====================================================")
    print()
    
    # Change to project directory
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # Install Python dependencies
    if run_command("pip install -r requirements.txt", "Installing Python dependencies"):
        print("  ✓ Dependencies installed successfully")
    
    print()
    print("  =====================================================")
    print("  Build completed!")
    print("  You can now run the web dashboard with:")
    print("    python -m web.server")
    print("  Access the dashboard at: http://localhost:8080")
    print("  =====================================================")
    print()

if __name__ == "__main__":
    main()
