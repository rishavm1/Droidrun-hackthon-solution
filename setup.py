#!/usr/bin/env python3
"""
Setup script for DroidRun Hackathon Solution
Helps configure the environment and check dependencies
"""

import os
import sys
import subprocess
import shutil

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 7):
        print("❌ Python 3.7 or higher is required")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True

def check_adb():
    """Check if ADB is available"""
    if shutil.which("adb"):
        print("✅ ADB found in PATH")
        return True
    print("❌ ADB not found. Please install Android SDK Platform Tools")
    return False

def install_requirements():
    """Install Python requirements"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Python dependencies installed")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install Python dependencies")
        return False

def setup_env_file():
    """Create .env file from template"""
    if os.path.exists(".env"):
        print("✅ .env file already exists")
        return True
    
    if os.path.exists(".env.example"):
        shutil.copy(".env.example", ".env")
        print("✅ Created .env file from template")
        print("📝 Please edit .env file with your API keys and settings")
        return True
    else:
        print("❌ .env.example template not found")
        return False

def check_android_device():
    """Check if Android device is connected"""
    try:
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        devices = [line for line in result.stdout.split('\n') if '\tdevice' in line]
        if devices:
            print(f"✅ {len(devices)} Android device(s) connected")
            return True
        else:
            print("⚠️  No Android devices connected")
            print("   Please connect your Android device and enable USB debugging")
            return False
    except FileNotFoundError:
        print("❌ ADB not available")
        return False

def main():
    print("🛒 DroidRun Hackathon Solution Setup")
    print("=" * 40)
    
    checks = [
        ("Python Version", check_python_version),
        ("ADB Installation", check_adb),
        ("Python Dependencies", install_requirements),
        ("Environment File", setup_env_file),
        ("Android Device", check_android_device)
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n🔍 Checking {name}...")
        results.append(check_func())
    
    print("\n" + "=" * 40)
    print("📋 Setup Summary:")
    
    for i, (name, _) in enumerate(checks):
        status = "✅ PASS" if results[i] else "❌ FAIL"
        print(f"   {name}: {status}")
    
    if all(results):
        print("\n🎉 Setup completed successfully!")
        print("   You can now run: python main.py")
    else:
        print("\n⚠️  Some checks failed. Please resolve the issues above.")
        print("\n📖 Quick Help:")
        print("   - Install Android SDK Platform Tools for ADB")
        print("   - Connect Android device with USB debugging enabled")
        print("   - Edit .env file with your API keys")

if __name__ == "__main__":
    main()