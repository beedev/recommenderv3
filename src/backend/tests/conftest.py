"""
Pytest configuration and shared fixtures
Provides common test fixtures for all test modules
"""

import pytest
import pytest_asyncio
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fakeredis import aioredis as fakeredis_aioredis

from app.database import redis_session_storage
from app.services.config.configuration_service import ConfigurationService
from app.services.config.prompt_service import PromptService


@pytest.fixture(scope="session")
def test_config_dir():
    """
    Create temporary config directory with all test configurations
    Session-scoped fixture used across all tests
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)

        # Create comprehensive test configurations
        configs = {
            "component_types.json": {
                "version": "1.0",
                "description": "Test component types",
                "component_types": {
                    "power_source": {
                        "class_name": "PowerSource",
                        "display_name": "Power Source",
                        "display_name_plural": "Power Sources",
                        "api_key": "PowerSource",
                        "db_key": "power_source",
                        "neo4j_label": "PowerSource",
                        "icon": "🔋",
                        "is_mandatory": True,
                        "selection_mode": "single",
                        "state_order": 1,
                        "state_name": "power_source_selection"
                    },
                    "feeder": {
                        "class_name": "Feeder",
                        "display_name": "Wire Feeder",
                        "display_name_plural": "Wire Feeders",
                        "api_key": "Feeder",
                        "db_key": "feeder",
                        "neo4j_label": "Feeder",
                        "icon": "🔌",
                        "is_mandatory": False,
                        "selection_mode": "single",
                        "state_order": 2,
                        "state_name": "feeder_selection"
                    },
                    "accessories": {
                        "class_name": "Accessories",
                        "display_name": "Accessory",
                        "display_name_plural": "Accessories",
                        "api_key": "Accessories",
                        "db_key": "accessories",
                        "icon": "🛠️",
                        "selection_mode": "multiple",
                        "state_order": 6,
                        "state_name": "accessories_selection"
                    }
                },
                "finalize_state": {
                    "icon": "📋",
                    "state_order": 7
                }
            },
            "llm_config.json": {
                "version": "1.0",
                "description": "Test LLM configurations",
                "models": {
                    "parameter_extraction": {
                        "model": "gpt-4",
                        "temperature": 0.3,
                        "max_tokens": 2000,
                        "fallback_model": "gpt-3.5-turbo"
                    },
                    "translation": {
                        "model": "gpt-3.5-turbo",
                        "temperature": 0.3,
                        "max_tokens": 500
                    }
                }
            },
            "llm_prompts.json": {
                "version": "1.0",
                "prompts": {
                    "parameter_extraction_system": {
                        "prompt": "You are a welding equipment expert."
                    },
                    "translation_system": {
                        "template": "Translate to {language_name}. Context: {context}"
                    }
                }
            },
            "state_prompts.json": {
                "version": "1.0",
                "states": {
                    "power_source_selection": {
                        "icon": "🔋",
                        "step_number": 1,
                        "title": "Power Source Selection",
                        "is_required": True,
                        "prompt_simple": "Select a power source",
                        "prompt_template": "Step {step_number}: {title}"
                    }
                }
            },
            "welding_processes.json": {
                "version": "1.0",
                "processes": [
                    {
                        "code": "GMAW",
                        "display_name": "MIG (GMAW)",
                        "short_name": "MIG",
                        "aliases": ["MIG", "GMAW"]
                    },
                    {
                        "code": "GTAW",
                        "display_name": "TIG (GTAW)",
                        "short_name": "TIG",
                        "aliases": ["TIG", "GTAW"]
                    }
                ]
            },
            "materials.json": {
                "version": "1.0",
                "materials": [
                    {"code": "STEEL", "display_name": "Steel"},
                    {"code": "ALUMINUM", "display_name": "Aluminum"}
                ]
            },
            "cooling_types.json": {
                "version": "1.0",
                "cooling_types": [
                    {"code": "WATER", "display_name": "Water-cooled"},
                    {"code": "AIR", "display_name": "Air-cooled"}
                ]
            },
            "search_config.json": {
                "version": "1.0",
                "fuzzy_matching": {
                    "enabled": True,
                    "score_cutoff": 80,
                    "max_matches": 1,
                    "components_enabled": ["power_source", "feeder", "cooler"]
                },
                "search_limits": {
                    "power_source": 10,
                    "feeder": 10,
                    "default": 10
                }
            },
            "cache_config.json": {
                "version": "1.0",
                "redis_session": {
                    "default_ttl_seconds": 3600,
                    "max_ttl_seconds": 86400
                }
            },
            "error_messages.json": {
                "version": "1.0",
                "error_messages": {
                    "power_source_required": {
                        "code": "ERR_PS_REQUIRED",
                        "icon": "⚠️",
                        "message": "PowerSource selection is mandatory. Please provide your welding requirements or select a specific power source.",
                        "severity": "error",
                        "suggested_actions": [
                            "Describe your welding needs (process, amperage, material)",
                            "Select from available power sources",
                            "Get help from a welding specialist"
                        ]
                    },
                    "search_failed": {
                        "code": "ERR_SEARCH_FAIL",
                        "icon": "⚠️",
                        "message": "Search failed",
                        "severity": "error"
                    }
                }
            },
            "languages.json": {
                "version": "1.0",
                "supported_languages": [
                    {
                        "code": "en",
                        "name": "English",
                        "native_name": "English",
                        "is_default": True
                    },
                    {
                        "code": "es",
                        "name": "Spanish",
                        "native_name": "Español",
                        "is_default": False
                    }
                ]
            }
        }

        # Write all config files
        for filename, content in configs.items():
            (config_dir / filename).write_text(
                json.dumps(content, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )

        yield config_dir


@pytest.fixture
def config_service(test_config_dir):
    """
    Create ConfigurationService with test config directory
    Function-scoped fixture, new instance per test
    """
    service = ConfigurationService(str(test_config_dir))
    # Clear cache before each test
    service.load_config.cache_clear()
    return service


@pytest.fixture
def prompt_service(config_service):
    """
    Create PromptService with test configuration
    Function-scoped fixture
    """
    return PromptService(config_service)


@pytest.fixture
def mock_config_service():
    """
    Create mock ConfigurationService for testing
    Useful for unit tests that don't need actual configs
    """
    mock = MagicMock(spec=ConfigurationService)

    # Default mock returns
    mock.get_component_types.return_value = {
        "component_types": {
            "power_source": {
                "display_name": "Power Source",
                "api_key": "PowerSource",
                "icon": "🔋"
            }
        }
    }

    mock.get_llm_config.return_value = {
        "model": "gpt-4",
        "temperature": 0.3,
        "max_tokens": 2000
    }

    mock.get_welding_process_names.return_value = ["MIG (GMAW)", "TIG (GTAW)"]
    mock.get_material_names.return_value = ["Steel", "Aluminum"]

    return mock


@pytest.fixture
def sample_response_json():
    """
    Sample ResponseJSON data for testing
    """
    return {
        "PowerSource": {
            "gin": "0446200880",
            "name": "Aristo 500ix",
            "product_name": "Aristo 500ix",
            "category": "Power Source",
            "description": "500A MIG welding machine"
        },
        "Feeder": {
            "gin": "GIN001",
            "name": "RobustFeed",
            "product_name": "RobustFeed",
            "category": "Feeder"
        },
        "Accessories": [
            {
                "gin": "ACC001",
                "name": "Accessory 1",
                "product_name": "Accessory 1"
            },
            {
                "gin": "ACC002",
                "name": "Accessory 2",
                "product_name": "Accessory 2"
            }
        ]
    }


@pytest.fixture
def sample_master_parameters():
    """
    Sample MasterParameterJSON data for testing
    """
    return {
        "power_source": {
            "process": "MIG (GMAW)",
            "current_output": "500 A",
            "material": "Steel",
            "product_name": "Aristo 500ix"
        },
        "feeder": {
            "cooling_type": "Water-cooled",
            "product_name": "RobustFeed"
        },
        "cooler": {},
        "interconnector": {},
        "torch": {},
        "accessories": {}
    }


@pytest.fixture
def sample_products():
    """
    Sample product list for testing
    """
    return [
        {
            "gin": "0446200880",
            "name": "Aristo 500ix",
            "category": "Power Source",
            "description": "Multiprocess heavy duty synergic and pulse MIG MAG welding machine"
        },
        {
            "gin": "0445100880",
            "name": "Renegade ES 300i",
            "category": "Power Source",
            "description": "Portable inverter dual voltage powersource"
        },
        {
            "gin": "0465350883",
            "name": "Warrior 500i",
            "category": "Power Source",
            "description": "Heavy duty multiprocess powersource"
        }
    ]


@pytest_asyncio.fixture
async def fake_redis_client():
    """Provide a fakeredis asyncio client for Redis-backed tests."""
    client = fakeredis_aioredis.FakeRedis(decode_responses=True)
    try:
        yield client
    finally:
        await client.flushall()
        await client.close()


@pytest_asyncio.fixture
async def redis_storage(fake_redis_client, monkeypatch):
    """Patch global Redis session storage with a fakeredis-backed instance."""
    original_storage = redis_session_storage._redis_session_storage
    original_memory = redis_session_storage._in_memory_session_storage

    storage = redis_session_storage.RedisSessionStorage(fake_redis_client, ttl=120)
    redis_session_storage._redis_session_storage = storage
    redis_session_storage._in_memory_session_storage = None

    try:
        yield storage
    finally:
        redis_session_storage._redis_session_storage = original_storage
        redis_session_storage._in_memory_session_storage = original_memory


# Pytest markers
def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line("markers", "unit: Unit tests for individual components")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "config: Configuration system tests")
    config.addinivalue_line("markers", "services: Service layer tests")


# Auto-use fixtures
@pytest.fixture(autouse=True)
def reset_singletons():
    """
    Reset singleton instances before each test
    Ensures test isolation
    """
    # Reset ConfigurationService singleton
    import app.services.config.configuration_service as config_module
    config_module._config_service = None

    # Reset PromptService singleton
    import app.services.config.prompt_service as prompt_module
    prompt_module._prompt_service = None

    yield

    # Cleanup after test
    config_module._config_service = None
    prompt_module._prompt_service = None
