# Test Suite for ESAB Welding Equipment Configurator

Comprehensive test suite organized into unit, integration, E2E, and manual tests.

> **Quick Links:**
> - **[Testing Guide](../../docs/testing-guide.md)** - Comprehensive testing best practices
> - **[Manual Tests](manual/README.md)** - Manual test scripts documentation
> - **[Test Results](../test-results/README.md)** - Test results organization

---

## Test Structure

```
tests/
├── conftest.py                  # Global fixtures
├── unit/                        # Unit tests (< 100ms, mocked dependencies)
│   ├── conftest.py             # Unit-specific fixtures
│   ├── models/                 # Model tests
│   ├── api/                    # API tests
│   ├── database/               # Database service tests
│   └── services/               # Service layer tests
│       ├── config/
│       ├── intent/
│       ├── neo4j/
│       ├── orchestrator/
│       ├── response/
│       └── multilingual/
├── integration/                 # Integration tests (< 5s, real services)
│   ├── conftest.py             # Integration fixtures
│   ├── test_api_endpoints.py
│   ├── test_session_management.py
│   ├── test_configurator_flow.py
│   ├── test_multiuser_sessions.py
│   └── test_config_system.py
├── e2e/                        # End-to-end tests (> 5s, full workflows)
│   ├── test_complete_workflow.py
│   └── test_state_transitions.py
└── manual/                     # Manual test scripts (excluded from pytest)
    ├── README.md               # Manual testing guide
    ├── test_local_neo4j.py
    ├── test_explicit_selection.py
    └── test_message_cleanup.py
```

---

## Installation

Install test dependencies:

```bash
cd src/backend

# Install all dependencies (includes test dependencies)
pip install -r requirements.txt
```

**Required packages:**
- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting
- `pytest-mock` - Mocking utilities
- `httpx` - Async HTTP client for API testing
- `fakeredis` - Redis mock for testing

---

## Running Tests

### Quick Start

```bash
# Run all automated tests
pytest

# Run specific test suite
pytest tests/unit -v              # Unit tests only (fast)
pytest tests/integration -v       # Integration tests
pytest tests/e2e -v               # End-to-end tests
```

### Run Specific Tests

```bash
# Run specific test file
pytest tests/unit/models/test_conversation_state.py -v

# Run specific test class
pytest tests/unit/models/test_conversation_state.py::TestConversationState -v

# Run specific test function
pytest tests/unit/models/test_conversation_state.py::test_initialization -v
```

### Run by Marker

```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Skip slow tests
pytest -m "not slow"

# Tests requiring Neo4j
pytest -m requires_neo4j

# Multiple markers
pytest -m "integration and not requires_neo4j"
```

### With Coverage

```bash
# Run with coverage
pytest --cov=app --cov-report=html

# View coverage report
open test-results/coverage/html/index.html  # macOS
xdg-open test-results/coverage/html/index.html  # Linux
start test-results/coverage/html/index.html  # Windows

# Terminal coverage report
pytest --cov=app --cov-report=term-missing
```

### Parallel Execution

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel (auto-detect CPUs)
pytest -n auto

# Best for unit tests only
pytest tests/unit -n auto -v
```

### Verbose Output

```bash
# Verbose output
pytest -v

# Show print statements
pytest -s

# Show detailed failure info
pytest -vv

# Stop on first failure
pytest -x
```

---

## Test Fixtures

### Global Fixtures (`conftest.py`)

Available to all tests:
- `app_config` - Application configuration
- Session management fixtures
- Singleton reset utilities

### Unit Test Fixtures (`unit/conftest.py`)

Mocked dependencies for isolated testing:
- `mock_neo4j_driver` - Mock Neo4j driver
- `mock_neo4j_session` - Mock Neo4j session
- `mock_openai_client` - Mock OpenAI client
- `mock_redis_client` - Mock Redis client
- `mock_postgres_connection` - Mock PostgreSQL connection
- `sample_conversation_state` - Sample ConversationState
- `sample_selected_product` - Sample SelectedProduct
- `sample_neo4j_products` - Sample Neo4j query results

### Integration Test Fixtures (`integration/conftest.py`)

Real service connections for integration testing:
- `api_client` - AsyncClient for API testing
- `integration_test_session_id` - UUID generator
- `sample_api_message_request` - Sample message request
- `sample_api_select_request` - Sample selection request
- `test_session_with_power_source` - Pre-configured test session

---

## Test Markers

Available markers for categorizing tests:

- `@pytest.mark.unit` - Fast unit tests (< 100ms)
- `@pytest.mark.integration` - Integration tests (< 5s)
- `@pytest.mark.e2e` - End-to-end tests (> 5s)
- `@pytest.mark.slow` - Slow tests
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.services` - Service layer tests
- `@pytest.mark.models` - Data model tests
- `@pytest.mark.database` - Database tests
- `@pytest.mark.requires_neo4j` - Requires Neo4j connection
- `@pytest.mark.requires_postgres` - Requires PostgreSQL
- `@pytest.mark.requires_redis` - Requires Redis
- `@pytest.mark.requires_openai` - Requires OpenAI API key

---

## Writing New Tests

### Unit Test Example

```python
# tests/unit/models/test_conversation_state.py
import pytest
from app.models.conversation import ConversationState, ConfiguratorState

@pytest.mark.unit
def test_conversation_state_initialization(sample_conversation_state):
    """Test ConversationState initializes correctly"""
    assert sample_conversation_state.session_id == "test-session-123"
    assert sample_conversation_state.current_state == ConfiguratorState.POWER_SOURCE_SELECTION
    assert sample_conversation_state.language == "en"
```

### Integration Test Example

```python
# tests/integration/test_api_endpoints.py
import pytest

@pytest.mark.integration
@pytest.mark.api
@pytest.mark.asyncio
async def test_message_endpoint_creates_session(api_client):
    """Test POST /message creates new session"""
    response = await api_client.post(
        "/api/v1/configurator/message",
        json={"message": "I need a 500A MIG welder", "language": "en"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
```

### E2E Test Example

```python
# tests/e2e/test_complete_workflow.py
import pytest

@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
async def test_complete_configuration_workflow(api_client):
    """Test complete S1→S7 workflow"""
    # S1: Create session and select power source
    # S2-S7: Select components through workflow
    # Verify final configuration
    pass
```

---

## Test Coverage Goals

| Component | Target Coverage |
|-----------|----------------|
| Models | 90%+ |
| Services | 85%+ |
| API Endpoints | 90%+ |
| Critical Paths | 100% |
| Overall | 80%+ |

---

## Test Results

Test results are stored in `test-results/` directory:

```
test-results/
├── coverage/        # Coverage reports (HTML, XML)
├── reports/         # Test reports (JUnit, HTML)
├── logs/            # Test execution logs
└── artifacts/       # Test artifacts (screenshots, data)
```

See [test-results/README.md](../test-results/README.md) for details.

---

## Manual Tests

Manual test scripts are excluded from automated test runs:

```bash
# Run manual tests directly with Python
cd src/backend
python tests/manual/test_local_neo4j.py
python tests/manual/test_explicit_selection.py
```

See [manual/README.md](manual/README.md) for complete documentation.

---

## CI/CD Integration

### GitHub Actions

```yaml
- name: Run Tests
  run: |
    cd src/backend
    pytest tests/unit tests/integration \
      --cov=app \
      --cov-report=xml:test-results/coverage/coverage.xml \
      --junit-xml=test-results/reports/junit/test-results.xml

- name: Upload Coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./src/backend/test-results/coverage/coverage.xml
```

### Azure Pipelines

```yaml
- script: |
    cd src/backend
    pytest tests/unit tests/integration \
      --cov=app \
      --cov-report=xml:test-results/coverage/coverage.xml \
      --junit-xml=test-results/reports/junit/test-results.xml
  displayName: 'Run Tests'

- task: PublishTestResults@2
  inputs:
    testResultsFormat: 'JUnit'
    testResultsFiles: 'src/backend/test-results/reports/junit/*.xml'
```

---

## Troubleshooting

### Import Errors

```bash
# Set PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest
```

### Missing Dependencies

```bash
# Reinstall test dependencies
pip install -r requirements.txt
```

### Async Test Failures

```bash
# Ensure pytest-asyncio is installed
pip install pytest-asyncio

# Check pytest.ini has asyncio_mode configured
```

### Slow Tests

```bash
# Skip slow tests during development
pytest -m "not slow"

# Run only fast unit tests
pytest tests/unit -v
```

### Service Connection Issues

For integration tests requiring services:

```bash
# Start required services
# - Neo4j: localhost:7687
# - PostgreSQL: localhost:5432
# - Redis: localhost:6379

# Or skip service-dependent tests
pytest -m "not requires_neo4j" -m "not requires_postgres"
```

---

## Best Practices

1. **Test Isolation**: Each test should be independent and not rely on other tests
2. **Use Fixtures**: Reuse common test setup via fixtures
3. **Clear Names**: Test names should describe what they test: `test_<component>_<scenario>_<expected_result>`
4. **Fast Tests**: Keep unit tests fast (< 100ms), mark slow tests with `@pytest.mark.slow`
5. **Mock External Services**: Unit tests should mock all external dependencies
6. **Test Edge Cases**: Test error conditions, boundary values, and edge cases
7. **One Assertion Concept**: Each test should verify one logical concept
8. **AAA Pattern**: Follow Arrange-Act-Assert pattern

---

## Resources

- **[Testing Guide](../../docs/testing-guide.md)** - Comprehensive testing guide
- **[Testing Organization Review](../../docs/testing-organization-review.md)** - Migration details
- **[Pytest Documentation](https://docs.pytest.org/)** - Official pytest docs
- **[Coverage.py](https://coverage.readthedocs.io/)** - Coverage tool docs

---

## Quick Reference

```bash
# Fast development cycle
pytest tests/unit -v -x        # Unit tests, stop on first failure

# Pre-commit checks
pytest tests/unit tests/integration --cov=app

# Full test suite
pytest --cov=app --cov-report=html

# Clean test results
./clean-test-results.sh
```

For more details, see the [Testing Guide](../../docs/testing-guide.md).
