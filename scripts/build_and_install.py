#!/usr/bin/env python3
"""
Build and installation script for Profile Scraping MCP.
This script handles the build process and provides multiple installation options.
"""

import sys
import subprocess
import os
import shutil
from pathlib import Path

def run_command(cmd, description, check=True):
    """Run a command and handle errors."""
    print(f"🔧 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)
        if result.stdout:
            print(f"   Output: {result.stdout.strip()}")
        if result.stderr and result.returncode != 0:
            print(f"   Error: {result.stderr.strip()}")
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Failed: {e}")
        if e.stdout:
            print(f"   Output: {e.stdout}")
        if e.stderr:
            print(f"   Error: {e.stderr}")
        return False

def clean_build():
    """Clean previous build artifacts."""
    print("🧹 Cleaning previous build artifacts...")
    
    dirs_to_clean = [
        "build",
        "dist", 
        "*.egg-info",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache"
    ]
    
    for pattern in dirs_to_clean:
        if "*" in pattern:
            # Use shell expansion for patterns
            run_command(f"rm -rf {pattern}", f"Removing {pattern}", check=False)
        else:
            path = Path(pattern)
            if path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                    print(f"   ✓ Removed directory: {pattern}")
                else:
                    path.unlink()
                    print(f"   ✓ Removed file: {pattern}")

def check_python_version():
    """Check if Python version is compatible."""
    print("🐍 Checking Python version...")
    
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print(f"   ❌ Python {version.major}.{version.minor} is not supported")
        print("   ℹ️  This package requires Python 3.11 or higher")
        return False
    
    print(f"   ✓ Python {version.major}.{version.minor}.{version.micro} is compatible")
    return True

def install_build_tools():
    """Install required build tools."""
    print("🔨 Installing build tools...")
    
    tools = ["build", "hatchling", "setuptools", "wheel"]
    
    for tool in tools:
        success = run_command(
            f"pip install --upgrade {tool}",
            f"Installing {tool}",
            check=False
        )
        if not success:
            print(f"   ⚠️  Failed to install {tool}, continuing...")

def method_1_hatchling():
    """Installation method 1: Using hatchling build backend."""
    print("\n📦 Method 1: Hatchling build backend")
    
    # Build the package
    success = run_command(
        "python -m build",
        "Building package with hatchling"
    )
    
    if not success:
        print("   ❌ Hatchling build failed")
        return False
    
    # Install the built package
    success = run_command(
        "pip install -e .",
        "Installing package in editable mode"
    )
    
    return success

def method_2_setuptools():
    """Installation method 2: Using setuptools."""
    print("\n📦 Method 2: Setuptools")
    
    success = run_command(
        "python setup.py develop",
        "Installing with setuptools develop mode"
    )
    
    return success

def method_3_requirements():
    """Installation method 3: Direct requirements installation."""
    print("\n📦 Method 3: Direct requirements installation")
    
    # Install requirements
    success = run_command(
        "pip install -r requirements.txt",
        "Installing requirements"
    )
    
    if not success:
        return False
    
    # Add src to Python path via .pth file
    try:
        import site
        site_packages = site.getsitepackages()[0]
        pth_file = Path(site_packages) / "profile-scraping-mcp.pth"
        
        src_path = Path.cwd() / "src"
        with open(pth_file, "w") as f:
            f.write(str(src_path))
        
        print(f"   ✓ Added {src_path} to Python path via {pth_file}")
        return True
        
    except Exception as e:
        print(f"   ⚠️  Could not add to Python path: {e}")
        print("   ℹ️  You may need to manually add src/ to PYTHONPATH")
        return True

def test_installation():
    """Test the installation."""
    print("\n🧪 Testing installation...")
    
    # Run the test script
    test_script = Path("scripts/test_install.py")
    if test_script.exists():
        success = run_command(
            f"python {test_script}",
            "Running installation tests"
        )
        return success
    else:
        print("   ⚠️  Test script not found, skipping tests")
        return True

def main():
    """Main installation process."""
    print("🚀 Profile Scraping MCP - Build and Install")
    print("=" * 50)
    
    # Change to project directory
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    os.chdir(project_dir)
    
    print(f"📁 Working directory: {project_dir}")
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Clean previous builds
    clean_build()
    
    # Install build tools
    install_build_tools()
    
    # Try installation methods in order
    methods = [
        ("Hatchling Build Backend", method_1_hatchling),
        ("Setuptools", method_2_setuptools),
        ("Direct Requirements", method_3_requirements),
    ]
    
    for method_name, method_func in methods:
        print(f"\n🎯 Trying {method_name}...")
        
        if method_func():
            print(f"   ✅ {method_name} succeeded!")
            
            # Test the installation
            if test_installation():
                print("\n🎉 Installation completed successfully!")
                print("\nNext steps:")
                print("1. Copy .env.example to .env and configure your API keys")
                print("2. Run: python scripts/run_server.py --validate-keys")
                print("3. Start the server: python scripts/run_server.py")
                sys.exit(0)
            else:
                print(f"   ⚠️  {method_name} installed but tests failed")
        else:
            print(f"   ❌ {method_name} failed, trying next method...")
    
    print("\n❌ All installation methods failed!")
    print("\nTroubleshooting:")
    print("1. Ensure you have Python 3.11+ installed")
    print("2. Try upgrading pip: pip install --upgrade pip")
    print("3. Install dependencies manually: pip install fastmcp pydantic httpx")
    print("4. Check for system-specific build requirements")
    
    sys.exit(1)

if __name__ == "__main__":
    main()