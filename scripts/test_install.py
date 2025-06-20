#!/usr/bin/env python3
"""
Test script to verify the package installation and basic functionality.
"""

import sys
import subprocess
import importlib.util
from pathlib import Path

def test_package_installation():
    """Test if the package can be installed and imported."""
    print("🔍 Testing package installation...")
    
    # Test if we can import the main modules
    try:
        # Add src to path for testing
        src_path = Path(__file__).parent.parent / "src"
        sys.path.insert(0, str(src_path))
        
        # Test imports
        print("  ✓ Testing imports...")
        
        # Test basic imports
        import src.server
        print("    ✓ src.server imported successfully")
        
        import src.models.requests
        print("    ✓ src.models.requests imported successfully")
        
        import src.models.responses
        print("    ✓ src.models.responses imported successfully")
        
        import src.utils.config
        print("    ✓ src.utils.config imported successfully")
        
        import src.utils.logger
        print("    ✓ src.utils.logger imported successfully")
        
        import src.core.scraper
        print("    ✓ src.core.scraper imported successfully")
        
        import src.integrations.apollo_client
        print("    ✓ src.integrations.apollo_client imported successfully")
        
        import src.integrations.ai_client
        print("    ✓ src.integrations.ai_client imported successfully")
        
        import src.services.profile_service
        print("    ✓ src.services.profile_service imported successfully")
        
        print("  ✅ All core modules imported successfully!")
        
    except ImportError as e:
        print(f"  ❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        return False
    
    return True

def test_dependencies():
    """Test if required dependencies are available."""
    print("\n🔍 Testing dependencies...")
    
    required_deps = [
        "pydantic",
        "httpx", 
        "beautifulsoup4",
        "loguru",
        "dotenv",
        "aiofiles",
        "tenacity",
    ]
    
    missing_deps = []
    
    for dep in required_deps:
        try:
            if dep == "dotenv":
                import python_dotenv
            elif dep == "beautifulsoup4":
                import bs4
            else:
                __import__(dep)
            print(f"  ✓ {dep} is available")
        except ImportError:
            print(f"  ❌ {dep} is missing")
            missing_deps.append(dep)
    
    if missing_deps:
        print(f"\n❌ Missing dependencies: {', '.join(missing_deps)}")
        print("Run: pip install -e . to install all dependencies")
        return False
    else:
        print("  ✅ All required dependencies are available!")
        return True

def test_configuration():
    """Test configuration loading."""
    print("\n🔍 Testing configuration...")
    
    try:
        # Add src to path
        src_path = Path(__file__).parent.parent / "src"
        sys.path.insert(0, str(src_path))
        
        from src.utils.config import config
        
        print(f"  ✓ Configuration loaded successfully")
        print(f"    - Server name: {config.server_name}")
        print(f"    - Debug mode: {config.debug}")
        print(f"    - Database path: {config.database_path}")
        print(f"    - Cache TTL: {config.cache_ttl}")
        
        # Test API key validation
        missing_keys = config.validate_api_keys()
        if missing_keys:
            print(f"    ⚠️  Missing API keys: {', '.join(missing_keys)}")
        else:
            print("    ✓ All API keys are configured")
        
        print("  ✅ Configuration test passed!")
        return True
        
    except Exception as e:
        print(f"  ❌ Configuration error: {e}")
        return False

def test_models():
    """Test Pydantic models."""
    print("\n🔍 Testing Pydantic models...")
    
    try:
        # Add src to path
        src_path = Path(__file__).parent.parent / "src"
        sys.path.insert(0, str(src_path))
        
        from src.models.requests import SearchProfilesRequest, ExtractProfileRequest
        from src.models.responses import ProfileData, SearchMetadata
        
        # Test request model
        search_request = SearchProfilesRequest(
            query="software engineer",
            num_results=10
        )
        print(f"  ✓ SearchProfilesRequest created: {search_request.query}")
        
        # Test response model
        profile_data = ProfileData(
            profile_url="https://linkedin.com/in/test",
            name="Test User",
            headline="Software Engineer"
        )
        print(f"  ✓ ProfileData created: {profile_data.name}")
        
        print("  ✅ Pydantic models test passed!")
        return True
        
    except Exception as e:
        print(f"  ❌ Models error: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Profile Scraping MCP - Installation Test")
    print("=" * 50)
    
    tests = [
        test_package_installation,
        test_dependencies,
        test_configuration,
        test_models,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        else:
            print()
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The package is ready to use.")
        print("\nNext steps:")
        print("1. Copy .env.example to .env and add your API keys")
        print("2. Run: python scripts/run_server.py --validate-keys")
        print("3. Start the server: python scripts/run_server.py")
        return True
    else:
        print("❌ Some tests failed. Please fix the issues before proceeding.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)