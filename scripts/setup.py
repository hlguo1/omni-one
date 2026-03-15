#!/usr/bin/env python3
"""
Setup script for Omni-One Enterprise AI Platform
"""

import os
import sys
from pathlib import Path

def setup_environment():
    """Set up the development environment"""
    print("🚀 Setting up Omni-One Enterprise AI Platform")
    print("=" * 50)

    # Check Python version
    if sys.version_info < (3, 11):
        print("❌ Python 3.11+ required")
        sys.exit(1)

    print("✅ Python version check passed")

    # Create necessary directories if they don't exist
    dirs = [
        "logs",
        "data",
        "models",
        "temp"
    ]

    for dir_name in dirs:
        Path(dir_name).mkdir(exist_ok=True)
        print(f"📁 Created directory: {dir_name}")

    # Check for required files
    required_files = [
        ".env.example",
        "requirements.txt",
        "src/omni_one/__init__.py"
    ]

    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✅ Found: {file_path}")
        else:
            print(f"❌ Missing: {file_path}")

    print("\n🎯 Setup complete!")
    print("Next steps:")
    print("1. Copy .env.example to .env and configure your API keys")
    print("2. Run: pip install -r requirements.txt")
    print("3. Run: python scripts/demo_enterprise.py")

if __name__ == "__main__":
    setup_environment()