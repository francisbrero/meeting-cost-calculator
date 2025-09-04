# Test Suite Overview

Quick reference for the Meeting Cost Calculator test suite.

## Files

- **`test.md`** - Detailed test documentation and setup instructions
- **`setup_test_env.py`** - Environment validation script (run this first)
- **`test_cost_calculation.py`** - Unit tests for cost calculation logic
- **`test_event_annotation.py`** - Integration tests for calendar event annotation

## Quick Start

1. **Setup Configuration**:
   ```bash
   # From project root
   cp .env_sample .env
   cp credentials.json.sample credentials.json
   # Edit both files with your values
   ```

2. **Validate Environment**:
   ```bash
   cd tests/
   python3 setup_test_env.py
   ```

3. **Run Unit Tests**:
   ```bash
   python3 test_cost_calculation.py
   ```

4. **Test With Real Calendar (Safe)**:
   ```bash
   python3 test_event_annotation.py --calc-only
   ```

5. **Full Integration Test** (modifies events):
   ```bash
   python3 test_event_annotation.py
   ```

## Configuration

The tests now use `.env` files and separate credentials files for better security:
- `.env` - Configuration variables
- `credentials.json` - Google Cloud service account JSON key

See `test.md` for detailed setup instructions.