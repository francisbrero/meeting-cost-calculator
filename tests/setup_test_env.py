#!/usr/bin/env python3
"""
Setup script to validate test environment and credentials.
Run this before executing the main tests.
"""
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
project_root = Path(__file__).parent.parent
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(env_path)
    print(f"📁 Loaded environment from: {env_path}")
else:
    print(f"⚠️  No .env file found at: {env_path}")
    print("   Create one by copying .env_sample to .env")


def check_credentials():
    """Validate Google credentials file or environment variable."""
    print("🔐 Checking Google Cloud credentials...")
    
    # Try to load from file first (preferred)
    creds_path = os.environ.get('GOOGLE_CREDENTIALS_PATH')
    creds = None
    
    if creds_path:
        creds_file = Path(creds_path)
        if not creds_file.is_absolute():
            creds_file = project_root / creds_path
        
        if creds_file.exists():
            try:
                with open(creds_file, 'r') as f:
                    creds = json.load(f)
                print(f"  ✅ Loaded credentials from: {creds_file}")
            except (json.JSONDecodeError, IOError) as e:
                print(f"  ❌ Error reading credentials file {creds_file}: {e}")
                return False
        else:
            print(f"  ❌ Credentials file not found: {creds_file}")
            print("     Create credentials.json from credentials.json.sample")
            return False
    else:
        # Fallback to environment variable
        creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
        if creds_json:
            try:
                creds = json.loads(creds_json)
                print("  ✅ Using credentials from GOOGLE_CREDENTIALS_JSON environment variable")
            except json.JSONDecodeError:
                print("  ❌ GOOGLE_CREDENTIALS_JSON is not valid JSON")
                return False
        else:
            print("  ❌ No credentials found")
            print("     Set GOOGLE_CREDENTIALS_PATH in .env to point to your credentials.json file")
            print("     Or set GOOGLE_CREDENTIALS_JSON environment variable")
            return False
    
    # Validate credentials structure
    required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
    
    for field in required_fields:
        if field not in creds:
            print(f"  ❌ Missing required field in credentials: {field}")
            return False
    
    if creds.get('type') != 'service_account':
        print(f"  ❌ Credentials type must be 'service_account', got: {creds.get('type')}")
        return False
    
    print(f"     Service account: {creds.get('client_email')}")
    print(f"     Project: {creds.get('project_id')}")
    return True


def check_environment():
    """Check required environment variables."""
    print("\n🌍 Checking environment variables...")
    
    required_vars = {
        'DOMAIN': 'Your Google Workspace domain (e.g., company.com)',
        'GOOGLE_CREDENTIALS_PATH': 'Path to your credentials.json file',
        'TEST_USER_EMAIL': 'Email of a user in your domain for testing'
    }
    
    optional_vars = {
        'DEFAULT_RATE': 'Hourly rate for cost calculation (default: 125)',
        'COST_TAG': 'Tag format for cost annotation (default: [[MEETING_COST]])',
        'INTERNAL_ONLY': 'Skip mixed internal/external meetings (default: true)'
    }
    
    all_good = True
    
    # Check required variables (except GOOGLE_CREDENTIALS_PATH if GOOGLE_CREDENTIALS_JSON is set)
    for var, description in required_vars.items():
        if var == 'GOOGLE_CREDENTIALS_PATH' and os.environ.get('GOOGLE_CREDENTIALS_JSON'):
            # Skip this check if using environment variable method
            continue
            
        value = os.environ.get(var)
        if value:
            print(f"  ✅ {var}: {value}")
        else:
            print(f"  ❌ {var}: Not set - {description}")
            all_good = False
    
    # Check optional variables
    for var, description in optional_vars.items():
        value = os.environ.get(var)
        if value:
            print(f"  ℹ️  {var}: {value}")
        else:
            print(f"  ⚠️  {var}: Using default - {description}")
    
    return all_good


def check_python_dependencies():
    """Check if required Python packages are available."""
    print("\n📦 Checking Python dependencies...")
    
    required_packages = [
        'google-auth',
        'google-auth-httplib2', 
        'google-api-python-client',
        'google-cloud-firestore',
        'python-dotenv'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            # Try importing the package
            if package == 'google-auth':
                import google.auth
            elif package == 'google-auth-httplib2':
                import google.auth.transport.requests
            elif package == 'google-api-python-client':
                import googleapiclient.discovery
            elif package == 'google-cloud-firestore':
                import google.cloud.firestore
            elif package == 'python-dotenv':
                import dotenv
            
            print(f"  ✅ {package}: Available")
            
        except ImportError:
            print(f"  ❌ {package}: Not installed")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n  Install missing packages with:")
        print(f"  pip install {' '.join(missing_packages)}")
        return False
    
    return True


def check_domain_validation():
    """Validate domain configuration."""
    print("\n🌐 Validating domain configuration...")
    
    domain = os.environ.get('DOMAIN')
    test_user = os.environ.get('TEST_USER_EMAIL')
    
    if not domain or not test_user:
        print("  ⚠️  Cannot validate domain (DOMAIN or TEST_USER_EMAIL not set)")
        return True  # Skip validation
    
    if not test_user.endswith(f"@{domain}"):
        print(f"  ❌ TEST_USER_EMAIL ({test_user}) does not match DOMAIN ({domain})")
        print(f"     TEST_USER_EMAIL should end with @{domain}")
        return False
    
    print(f"  ✅ Domain configuration valid")
    print(f"     Domain: {domain}")
    print(f"     Test user: {test_user}")
    
    return True


def print_test_instructions():
    """Print instructions for running tests."""
    print("\n📋 Next Steps - Running Tests:")
    print()
    print("1. Unit Test (No API access needed):")
    print("   cd tests/")
    print("   python3 test_cost_calculation.py")
    print()
    print("2. Integration Test - Cost Calculation Only:")
    print("   cd tests/")
    print("   python3 test_event_annotation.py --calc-only")
    print()
    print("3. Full Integration Test (Will modify calendar events!):")
    print("   cd tests/")
    print("   python3 test_event_annotation.py")
    print()
    print("⚠️  Important Notes:")
    print("   - The full integration test will modify real calendar events")
    print("   - Use a test calendar/user account for safety")
    print("   - Ensure your service account has Domain-Wide Delegation enabled")
    print("   - Required OAuth scopes must be delegated in Admin Console:")
    print("     * https://www.googleapis.com/auth/calendar")
    print("     * https://www.googleapis.com/auth/admin.directory.user.readonly")
    print("   - Setup instructions:")
    print("     1. Copy .env_sample to .env")
    print("     2. Copy credentials.json.sample to credentials.json")
    print("     3. Fill in your actual values in both files")


def main():
    """Run environment validation checks."""
    print("🧪 Meeting Cost Calculator - Test Environment Setup")
    print("=" * 60)
    
    checks = [
        ("Credentials", check_credentials),
        ("Environment Variables", check_environment),
        ("Python Dependencies", check_python_dependencies),
        ("Domain Configuration", check_domain_validation)
    ]
    
    all_passed = True
    
    for check_name, check_func in checks:
        result = check_func()
        all_passed = all_passed and result
    
    print("\n" + "=" * 60)
    
    if all_passed:
        print("✅ All environment checks passed!")
        print_test_instructions()
        return True
    else:
        print("❌ Some environment checks failed.")
        print("   Please fix the issues above before running tests.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)