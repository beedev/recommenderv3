"""
Integration test fixtures

Fixtures for integration tests that use real services and components.
Integration tests are slower (< 5s) but test actual component interactions.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def api_client():
    """
    HTTP client for API integration testing

    Usage:
        async def test_health_endpoint(api_client):
            response = await api_client.get("/health")
            assert response.status_code == 200
    """
    from app.main import app

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def integration_test_session_id():
    """Generate unique session ID for integration tests"""
    import uuid
    return f"test-session-{uuid.uuid4()}"


@pytest.fixture
def sample_api_message_request():
    """Sample API message request for integration tests"""
    return {
        "message": "I need a 500A MIG welder for steel",
        "language": "en",
        "session_id": None,
        "reset": False
    }


@pytest.fixture
def sample_api_select_request():
    """Sample API select request for integration tests"""
    return {
        "session_id": "test-session-123",
        "component": "PowerSource",
        "gin": "0446200880",
        "language": "en"
    }


@pytest_asyncio.fixture
async def test_session_with_power_source(api_client):
    """
    Create a test session with power source already selected

    Returns session_id for use in subsequent tests
    """
    # Create initial message to select power source
    response = await api_client.post(
        "/api/v1/configurator/message",
        json={
            "message": "I need Aristo 500ix power source",
            "language": "en"
        }
    )

    assert response.status_code == 200
    data = response.json()

    # If products returned, select the first one
    if data.get("products"):
        select_response = await api_client.post(
            "/api/v1/configurator/select",
            json={
                "session_id": data["session_id"],
                "component": "PowerSource",
                "gin": data["products"][0]["gin"],
                "language": "en"
            }
        )
        assert select_response.status_code == 200
        return select_response.json()["session_id"]

    return data["session_id"]


@pytest.fixture
def mock_neo4j_for_integration():
    """
    Mock Neo4j for integration tests where real Neo4j isn't available

    Use this sparingly - prefer using real Neo4j for true integration tests
    """
    from unittest.mock import AsyncMock

    driver = AsyncMock()
    session = AsyncMock()

    # Mock product search results
    async def mock_run(query, **params):
        result = AsyncMock()
        result.data = AsyncMock(return_value=[
            {
                "product": {
                    "gin": "0446200880",
                    "name": "Aristo 500ix",
                    "process": "MIG (GMAW)",
                    "current_output": "500 A"
                }
            }
        ])
        return result

    session.run = mock_run
    driver.session.return_value.__aenter__.return_value = session

    return driver
