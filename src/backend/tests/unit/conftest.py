"""
Unit test fixtures

Fixtures for unit tests that mock external dependencies.
Unit tests should be fast (< 100ms) and isolated.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j AsyncGraphDatabase driver for unit tests"""
    driver = AsyncMock()
    session = AsyncMock()
    driver.session.return_value.__aenter__.return_value = session
    driver.close = AsyncMock()
    return driver


@pytest.fixture
def mock_neo4j_session():
    """Mock Neo4j async session for unit tests"""
    session = AsyncMock()
    session.run = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for unit tests"""
    client = MagicMock()

    # Mock chat completions
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"extracted": "data"}'

    client.chat.completions.create.return_value = mock_response

    return client


@pytest.fixture
def mock_redis_client():
    """Mock Redis async client for unit tests"""
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.exists = AsyncMock(return_value=0)
    client.expire = AsyncMock(return_value=True)
    client.keys = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_postgres_connection():
    """Mock PostgreSQL async connection for unit tests"""
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.close = AsyncMock()
    return conn


@pytest.fixture
def sample_conversation_state():
    """Sample conversation state data for unit tests"""
    from app.models.conversation import ConversationState, ConfiguratorState

    return ConversationState(
        session_id="test-session-123",
        current_state=ConfiguratorState.POWER_SOURCE_SELECTION,
        language="en",
        conversation_history=[
            {"role": "user", "content": "I need a 500A MIG welder"},
            {"role": "assistant", "content": "I can help you find a power source."}
        ],
        master_parameters={
            "power_source": {
                "process": "MIG (GMAW)",
                "current_output": "500 A",
                "material": "Steel"
            }
        },
        response_json={},
        applicability=None
    )


@pytest.fixture
def sample_selected_product():
    """Sample selected product data for unit tests"""
    return {
        "gin": "0446200880",
        "name": "Aristo 500ix",
        "product_name": "Aristo 500ix",
        "category": "Power Source",
        "description": "500A MIG welding machine",
        "process": "MIG (GMAW)",
        "current_output": "500 A"
    }


@pytest.fixture
def sample_neo4j_products():
    """Sample Neo4j product query results for unit tests"""
    return [
        {
            "gin": "0446200880",
            "name": "Aristo 500ix",
            "process": "MIG (GMAW)",
            "current_output": "500 A",
            "category": "Power Source"
        },
        {
            "gin": "0445100880",
            "name": "Renegade ES 300i",
            "process": "MIG (GMAW)",
            "current_output": "300 A",
            "category": "Power Source"
        }
    ]
