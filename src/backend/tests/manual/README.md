# Manual Test Scripts

These scripts are for **manual testing and debugging only**. They are **NOT** run by pytest and are excluded from the automated test suite.

## Overview

Manual test scripts are standalone Python scripts that:
- Test specific features or components interactively
- Require manual inspection of results
- Test against real services (Neo4j, Redis, PostgreSQL, OpenAI)
- Are used for debugging and development
- May require specific environment setup or data

**Why separate from automated tests?**
- They're not suitable for CI/CD pipelines
- They require manual verification
- They may modify production-like data
- They're intended for developer use during development

---

## Available Scripts

### test_local_neo4j.py

**Purpose**: Tests Neo4j connection, product search, and graph queries.

**What it tests**:
- Neo4j connectivity and authentication
- Product search queries
- COMPATIBLE_WITH relationship traversal
- Node property queries

**Requirements**:
- Neo4j running (local or Neo4j Aura)
- Valid NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD in .env
- Product data loaded in Neo4j

**Usage**:
```bash
cd src/backend
source venv/bin/activate  # Windows: venv\Scripts\activate
python tests/manual/test_local_neo4j.py
```

**Expected output**:
- Connection status
- Sample product queries
- Relationship traversal results

**When to use**:
- Verifying Neo4j connection after setup
- Debugging product search queries
- Testing new Cypher queries
- Validating product data structure

---

### test_explicit_selection.py

**Purpose**: Tests explicit product selection flow through the state machine.

**What it tests**:
- Session creation and management
- Product selection via `/api/v1/configurator/select` endpoint
- State transitions after selection
- Component applicability logic
- ResponseJSON updates

**Requirements**:
- Backend server running on http://localhost:8000
- Redis running (for session storage)
- Neo4j with product data
- OpenAI API key configured

**Usage**:
```bash
cd src/backend
source venv/bin/activate  # Windows: venv\Scripts\activate

# Start the backend server first
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# In another terminal:
python tests/manual/test_explicit_selection.py
```

**Expected output**:
- Session ID
- Initial state
- Product search results
- Selection confirmation
- Updated state after selection
- ResponseJSON with selected product

**When to use**:
- Testing product selection flow
- Debugging state transitions
- Validating component applicability
- Testing multi-step workflows
- Verifying session persistence

---

### test_message_cleanup.py

**Purpose**: Tests message generator cleanup and formatting logic.

**What it tests**:
- Message generation templates
- LLM response formatting
- Multilingual message generation
- Response cleanup (removing markdown, formatting)
- Message truncation and sanitization

**Requirements**:
- OpenAI API key configured
- Backend imports available (message generator, translator)

**Usage**:
```bash
cd src/backend
source venv/bin/activate  # Windows: venv\Scripts\activate
python tests/manual/test_message_cleanup.py
```

**Expected output**:
- Sample generated messages
- Before/after cleanup comparison
- Formatting validation results
- Multilingual output samples

**When to use**:
- Testing message generation changes
- Debugging LLM output formatting
- Validating cleanup logic
- Testing multilingual support
- Inspecting actual LLM responses

---

## Running Manual Tests

### Prerequisites

**Environment Setup**:
```bash
# 1. Ensure .env file is configured
cd src/backend
cp .env.example .env
# Edit .env with your credentials

# 2. Activate virtual environment
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies (if not already done)
pip install -r requirements.txt
```

**Required Services**:
- **Neo4j**: Running on configured NEO4J_URI (local or Aura)
- **Redis**: Running on localhost:6379 (optional but recommended)
- **PostgreSQL**: Running on localhost:5432 (optional for most tests)
- **OpenAI API**: Valid OPENAI_API_KEY configured

**Verify Services**:
```bash
# Neo4j
cypher-shell -a bolt://localhost:7687 -u neo4j -p your_password "RETURN 1;"

# Redis
redis-cli ping

# PostgreSQL
psql -U postgres -d pconfig -c "SELECT 1;"
```

### Running Individual Scripts

**Pattern**:
```bash
cd src/backend
source venv/bin/activate
python tests/manual/script_name.py
```

**With debugging**:
```bash
# Run with verbose output
python -v tests/manual/script_name.py

# Run with debugger
python -m pdb tests/manual/script_name.py
```

### Common Issues

**ImportError: No module named 'app'**
```bash
# Solution: Ensure you're in src/backend directory
cd src/backend
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python tests/manual/script_name.py
```

**Connection Errors**
```bash
# Solution: Verify services are running and .env is configured
# Check .env file:
cat .env | grep NEO4J
cat .env | grep REDIS
cat .env | grep OPENAI

# Test connections individually (see Verify Services above)
```

**Backend Not Running (for test_explicit_selection.py)**
```bash
# Solution: Start backend in separate terminal
cd src/backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Why Manual Tests Are Excluded from Pytest

**Pytest Configuration** (`pytest.ini`):
```ini
testpaths = tests/unit tests/integration tests/e2e
norecursedirs = .git .tox dist build *.egg venv htmlcov .pytest_cache manual
```

**Reasons for exclusion**:

1. **Real Service Dependencies**
   - Manual tests connect to real Neo4j, Redis, OpenAI
   - Automated tests should use mocks or test databases
   - Manual tests may modify data

2. **Manual Verification Required**
   - Results need human inspection
   - No automated assertions
   - Interactive debugging intended

3. **Not Suitable for CI/CD**
   - Require specific environment setup
   - May take significant time
   - May incur API costs (OpenAI)

4. **Development/Debugging Focus**
   - Used during feature development
   - Help understand system behavior
   - Test specific scenarios interactively

---

## Automated Test Suite

For **automated testing**, use the main test suite:

```bash
# Run all automated tests
pytest

# Run only unit tests (fast)
pytest tests/unit -v

# Run only integration tests
pytest tests/integration -v

# Run with coverage
pytest tests/unit tests/integration --cov=app --cov-report=html
```

See the main [Testing Guide](../../docs/testing-guide.md) for automated testing patterns.

---

## Adding New Manual Tests

### When to Create Manual Tests

Create manual test scripts when:
- Testing against real external services
- Debugging complex workflows
- Exploring API behavior interactively
- Need to inspect results visually
- Testing scenarios that are hard to automate

### Guidelines

**File naming**: `test_<feature_name>.py`

**Structure**:
```python
"""
Manual test script for <feature>

Purpose: <what this tests>
Requirements: <services/setup needed>
Usage: python tests/manual/test_<feature>.py
"""

import asyncio
from app.services.some_service import SomeService

async def test_feature():
    """Test description"""
    # Setup
    service = SomeService()

    # Execute
    result = await service.do_something()

    # Output (no assertions)
    print(f"Result: {result}")
    print("✅ Test completed - verify results above")

if __name__ == "__main__":
    asyncio.run(test_feature())
```

**Best practices**:
- Add clear docstring explaining purpose
- List requirements in comments
- Use print statements for output
- Include usage instructions
- Don't use pytest assertions (not run by pytest)
- Clean up resources (close connections)

### Updating Documentation

When adding a new manual test:
1. Add script to this README
2. Document purpose, requirements, usage
3. Explain when to use it
4. Include expected output

---

## Comparison: Manual vs Automated Tests

| Aspect | Manual Tests | Automated Tests |
|--------|--------------|-----------------|
| **Location** | `tests/manual/` | `tests/unit/`, `tests/integration/`, `tests/e2e/` |
| **Run by** | Developer manually | Pytest automatically |
| **Purpose** | Debugging, exploration | Validation, regression prevention |
| **Dependencies** | Real services | Mocked or test services |
| **Assertions** | Manual verification | Automated assertions |
| **CI/CD** | Not included | Run on every commit |
| **Execution** | `python tests/manual/script.py` | `pytest tests/` |
| **Output** | Print statements | Pass/fail status |
| **When** | During development | Always (pre-commit, CI) |

---

## Getting Help

**For manual test issues**:
1. Verify all required services are running
2. Check .env configuration
3. Review script docstring for requirements
4. Check backend logs if testing API endpoints

**For automated testing**:
- See [Testing Guide](../../docs/testing-guide.md)
- See [Test Organization Review](../../../docs/testing-organization-review.md)
- Run: `pytest --help` for options

**Environment issues**:
- Verify virtual environment is activated
- Check PYTHONPATH includes src/backend
- Ensure dependencies are installed: `pip install -r requirements.txt`

---

## Quick Reference

**Run manual test**:
```bash
cd src/backend
source venv/bin/activate
python tests/manual/test_local_neo4j.py
```

**Run automated tests** (excludes manual/):
```bash
pytest
```

**List available manual tests**:
```bash
ls tests/manual/test_*.py
```

**Check pytest configuration**:
```bash
cat pytest.ini | grep -A2 "norecursedirs"
# Output should include "manual"
```

---

## Next Steps

After running manual tests:
1. Fix any issues discovered
2. Consider adding automated tests for the validated behavior
3. Update integration tests if workflow changes
4. Document any new findings in relevant docs

For comprehensive testing:
1. Run manual tests for interactive validation
2. Run unit tests for fast feedback: `pytest tests/unit`
3. Run integration tests for workflow validation: `pytest tests/integration`
4. Review coverage report: `open htmlcov/index.html`
