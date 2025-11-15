"""
Unit tests for ConfigurationService
Tests configuration loading, caching, validation, and error handling
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import threading
import time

from app.services.config.configuration_service import (
    ConfigurationService,
    get_config_service,
    init_config_service,
    _config_service
)


class TestConfigurationService:
    """Test suite for ConfigurationService"""

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory with test configs"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)

            # Create test component_types.json
            component_types = {
                "version": "1.0",
                "component_types": {
                    "power_source": {
                        "class_name": "PowerSource",
                        "display_name": "Power Source",
                        "api_key": "PowerSource",
                        "db_key": "power_source",
                        "neo4j_label": "PowerSource",
                        "icon": "🔋",
                        "state_name": "power_source_selection"
                    },
                    "feeder": {
                        "class_name": "Feeder",
                        "display_name": "Wire Feeder",
                        "api_key": "Feeder",
                        "db_key": "feeder",
                        "state_name": "feeder_selection"
                    }
                }
            }
            (config_dir / "component_types.json").write_text(json.dumps(component_types))

            # Create test llm_config.json
            llm_config = {
                "version": "1.0",
                "models": {
                    "parameter_extraction": {
                        "model": "gpt-4",
                        "temperature": 0.3,
                        "max_tokens": 2000
                    },
                    "translation": {
                        "model": "gpt-3.5-turbo",
                        "temperature": 0.3,
                        "max_tokens": 500
                    }
                }
            }
            (config_dir / "llm_config.json").write_text(json.dumps(llm_config))

            # Create test llm_prompts.json
            llm_prompts = {
                "version": "1.0",
                "prompts": {
                    "parameter_extraction_system": {
                        "prompt": "You are a welding equipment expert."
                    },
                    "translation_system": {
                        "template": "Translate to {language_name}. Context: {context}"
                    }
                }
            }
            (config_dir / "llm_prompts.json").write_text(json.dumps(llm_prompts))

            # Create test state_prompts.json
            state_prompts = {
                "version": "1.0",
                "states": {
                    "power_source_selection": {
                        "icon": "🔋",
                        "step_number": 1,
                        "title": "Power Source Selection",
                        "prompt_simple": "Select a power source"
                    }
                }
            }
            (config_dir / "state_prompts.json").write_text(json.dumps(state_prompts))

            # Create test search_config.json
            search_config = {
                "version": "1.0",
                "fuzzy_matching": {
                    "enabled": True,
                    "score_cutoff": 80,
                    "max_matches": 1
                },
                "search_limits": {
                    "power_source": 10,
                    "default": 10
                }
            }
            (config_dir / "search_config.json").write_text(json.dumps(search_config))

            # Create test cache_config.json
            cache_config = {
                "version": "1.0",
                "redis_session": {
                    "default_ttl_seconds": 3600
                }
            }
            (config_dir / "cache_config.json").write_text(json.dumps(cache_config))

            # Create test error_messages.json
            error_messages = {
                "version": "1.0",
                "error_messages": {
                    "power_source_required": {
                        "code": "ERR_PS_REQUIRED",
                        "icon": "⚠️",
                        "message": "PowerSource selection is mandatory. Please provide your welding requirements or select a specific power source."
                    }
                }
            }
            (config_dir / "error_messages.json").write_text(json.dumps(error_messages))

            # Create test languages.json
            languages = {
                "version": "1.0",
                "supported_languages": [
                    {"code": "en", "name": "English", "is_default": True},
                    {"code": "es", "name": "Spanish", "is_default": False}
                ]
            }
            (config_dir / "languages.json").write_text(json.dumps(languages))

            # Create test welding_processes.json
            welding_processes = {
                "version": "1.0",
                "processes": [
                    {
                        "code": "GMAW",
                        "display_name": "MIG (GMAW)",
                        "short_name": "MIG"
                    }
                ]
            }
            (config_dir / "welding_processes.json").write_text(json.dumps(welding_processes))

            # Create test materials.json
            materials = {
                "version": "1.0",
                "materials": [
                    {
                        "code": "STEEL",
                        "display_name": "Steel"
                    }
                ]
            }
            (config_dir / "materials.json").write_text(json.dumps(materials))

            # Create test cooling_types.json
            cooling_types = {
                "version": "1.0",
                "cooling_types": [
                    {
                        "code": "WATER",
                        "display_name": "Water-cooled"
                    }
                ]
            }
            (config_dir / "cooling_types.json").write_text(json.dumps(cooling_types))

            yield config_dir

    @pytest.fixture
    def config_service(self, temp_config_dir):
        """Create ConfigurationService with temp config directory"""
        service = ConfigurationService(str(temp_config_dir))
        # Clear cache between tests
        service.load_config.cache_clear()
        return service

    # ==================== Basic Loading Tests ====================

    def test_load_valid_config(self, config_service):
        """Test loading a valid configuration file"""
        config = config_service.load_config("component_types")

        assert config is not None
        assert "version" in config
        assert config["version"] == "1.0"
        assert "component_types" in config

    def test_load_nonexistent_config(self, config_service):
        """Test loading a non-existent configuration file"""
        with pytest.raises(FileNotFoundError):
            config_service.load_config("nonexistent_config")

    def test_load_invalid_json(self, temp_config_dir, config_service):
        """Test loading invalid JSON file"""
        # Create invalid JSON file
        invalid_file = temp_config_dir / "invalid.json"
        invalid_file.write_text("{ invalid json }")

        with pytest.raises(json.JSONDecodeError):
            config_service.load_config("invalid")

    # ==================== Caching Tests ====================

    def test_config_caching(self, config_service):
        """Test that configs are cached with LRU cache"""
        # Load config twice
        config1 = config_service.load_config("component_types")
        config2 = config_service.load_config("component_types")

        # Should return same object due to caching
        assert config1 is config2

    def test_cache_reload(self, config_service):
        """Test cache reload functionality"""
        config1 = config_service.load_config("component_types")

        # Reload config (clears cache)
        config2 = config_service.reload_config("component_types")

        # Should load fresh copy
        assert config2 is not None
        assert config2 == config1  # Same content
        # Note: May not be same object after reload

    # ==================== Component Types Tests ====================

    def test_get_component_types(self, config_service):
        """Test getting component types configuration"""
        component_types = config_service.get_component_types()

        assert "component_types" in component_types
        assert "power_source" in component_types["component_types"]
        assert "feeder" in component_types["component_types"]

    def test_get_component_type(self, config_service):
        """Test getting specific component type"""
        power_source = config_service.get_component_type("power_source")

        assert power_source is not None
        assert power_source["api_key"] == "PowerSource"
        assert power_source["display_name"] == "Power Source"
        assert power_source["icon"] == "🔋"

    def test_get_nonexistent_component_type(self, config_service):
        """Test getting non-existent component type"""
        result = config_service.get_component_type("nonexistent")

        assert result is None

    def test_get_component_type_by_api_key(self, config_service):
        """Test getting component type by API key"""
        component = config_service.get_component_type_by_api_key("PowerSource")

        assert component is not None
        assert component["key"] == "power_source"
        assert component["api_key"] == "PowerSource"

    def test_get_component_type_by_invalid_api_key(self, config_service):
        """Test getting component type with invalid API key"""
        component = config_service.get_component_type_by_api_key("InvalidKey")

        assert component is None

    # ==================== LLM Config Tests ====================

    def test_get_llm_config(self, config_service):
        """Test getting LLM configuration"""
        llm_config = config_service.get_llm_config("parameter_extraction")

        assert llm_config["model"] == "gpt-4"
        assert llm_config["temperature"] == 0.3
        assert llm_config["max_tokens"] == 2000

    def test_get_llm_config_with_invalid_purpose(self, config_service):
        """Test getting LLM config with invalid purpose returns defaults"""
        llm_config = config_service.get_llm_config("invalid_purpose")

        # Should return defaults
        assert llm_config["model"] == "gpt-4"
        assert llm_config["temperature"] == 0.3
        assert llm_config["max_tokens"] == 2000

    # ==================== Prompt Tests ====================

    def test_get_prompt(self, config_service):
        """Test getting LLM prompt"""
        prompt = config_service.get_prompt("parameter_extraction_system")

        assert prompt == "You are a welding equipment expert."

    def test_get_prompt_template(self, config_service):
        """Test getting template prompt"""
        prompt = config_service.get_prompt("translation_system")

        assert "Translate to {language_name}" in prompt

    def test_get_nonexistent_prompt(self, config_service):
        """Test getting non-existent prompt raises error"""
        with pytest.raises(KeyError):
            config_service.get_prompt("nonexistent_prompt")

    def test_get_state_prompt_config(self, config_service):
        """Test getting state prompt configuration"""
        state_config = config_service.get_state_prompt_config("power_source_selection")

        assert state_config["icon"] == "🔋"
        assert state_config["step_number"] == 1
        assert state_config["title"] == "Power Source Selection"

    def test_get_nonexistent_state_prompt(self, config_service):
        """Test getting non-existent state prompt raises error"""
        with pytest.raises(KeyError):
            config_service.get_state_prompt_config("nonexistent_state")

    # ==================== Welding Domain Tests ====================

    def test_get_welding_processes(self, config_service):
        """Test getting welding processes"""
        processes = config_service.get_welding_processes()

        assert len(processes) == 1
        assert processes[0]["code"] == "GMAW"
        assert processes[0]["display_name"] == "MIG (GMAW)"

    def test_get_welding_process_names(self, config_service):
        """Test getting welding process display names"""
        names = config_service.get_welding_process_names()

        assert len(names) == 1
        assert "MIG (GMAW)" in names

    def test_get_materials(self, config_service):
        """Test getting materials"""
        materials = config_service.get_materials()

        assert len(materials) == 1
        assert materials[0]["code"] == "STEEL"

    def test_get_material_names(self, config_service):
        """Test getting material display names"""
        names = config_service.get_material_names()

        assert len(names) == 1
        assert "Steel" in names

    def test_get_cooling_types(self, config_service):
        """Test getting cooling types"""
        cooling_types = config_service.get_cooling_types()

        assert len(cooling_types) == 1
        assert cooling_types[0]["code"] == "WATER"

    # ==================== Search Config Tests ====================

    def test_get_search_config(self, config_service):
        """Test getting search configuration"""
        search_config = config_service.get_search_config()

        assert "fuzzy_matching" in search_config
        assert "search_limits" in search_config

    def test_get_fuzzy_match_config(self, config_service):
        """Test getting fuzzy matching configuration"""
        fuzzy_config = config_service.get_fuzzy_match_config()

        assert fuzzy_config["enabled"] is True
        assert fuzzy_config["score_cutoff"] == 80
        assert fuzzy_config["max_matches"] == 1

    def test_get_search_limit(self, config_service):
        """Test getting search limit for component type"""
        limit = config_service.get_search_limit("power_source")

        assert limit == 10

    def test_get_search_limit_default(self, config_service):
        """Test getting default search limit for unknown component"""
        limit = config_service.get_search_limit("unknown_component")

        assert limit == 10

    # ==================== Cache Config Tests ====================

    def test_get_cache_config(self, config_service):
        """Test getting cache configuration"""
        cache_config = config_service.get_cache_config()

        assert "redis_session" in cache_config

    def test_get_session_ttl(self, config_service):
        """Test getting session TTL"""
        ttl = config_service.get_session_ttl()

        assert ttl == 3600

    # ==================== Error Message Tests ====================

    def test_get_error_message(self, config_service):
        """Test getting error message"""
        error = config_service.get_error_message("power_source_required")

        assert error["code"] == "ERR_PS_REQUIRED"
        assert error["icon"] == "⚠️"
        assert "PowerSource selection is mandatory" in error["message"]

    def test_get_nonexistent_error_message(self, config_service):
        """Test getting non-existent error message returns default"""
        error = config_service.get_error_message("nonexistent_error")

        assert error["code"] == "nonexistent_error"
        assert error["icon"] == "⚠️"
        assert error["message"] == "An error occurred"

    # ==================== Language Tests ====================

    def test_get_supported_languages(self, config_service):
        """Test getting supported languages"""
        languages = config_service.get_supported_languages()

        assert len(languages) == 2
        assert languages[0]["code"] == "en"
        assert languages[1]["code"] == "es"

    def test_get_language_codes(self, config_service):
        """Test getting language codes"""
        codes = config_service.get_language_codes()

        assert len(codes) == 2
        assert "en" in codes
        assert "es" in codes

    def test_get_default_language(self, config_service):
        """Test getting default language"""
        default_lang = config_service.get_default_language()

        assert default_lang == "en"

    # ==================== Validation Tests ====================

    def test_validate_config_success(self, config_service):
        """Test config validation for valid file"""
        result = config_service.validate_config("component_types")

        assert result is True

    def test_validate_config_failure(self, config_service):
        """Test config validation for non-existent file"""
        result = config_service.validate_config("nonexistent")

        assert result is False

    # ==================== Singleton Pattern Tests ====================

    def test_singleton_get_config_service(self):
        """Test that get_config_service returns singleton"""
        service1 = get_config_service()
        service2 = get_config_service()

        assert service1 is service2

    def test_singleton_init_config_service(self, temp_config_dir):
        """Test init_config_service creates new singleton"""
        # Clear global singleton
        import app.services.config.configuration_service as config_module
        config_module._config_service = None

        service = init_config_service(str(temp_config_dir))

        assert service is not None
        # Subsequent calls return same instance
        service2 = get_config_service()
        assert service is service2

    # ==================== Thread Safety Tests ====================

    def test_concurrent_config_access(self, config_service):
        """Test concurrent access to configuration service"""
        results = []
        errors = []

        def load_config():
            try:
                config = config_service.load_config("component_types")
                results.append(config)
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=load_config)
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Should have no errors
        assert len(errors) == 0
        assert len(results) == 10

        # All results should be equal due to caching (content-wise)
        first_result = results[0]
        for result in results[1:]:
            assert result == first_result
            # Note: Using == for equality, not 'is' for identity
            # LRU cache guarantees cached results but not necessarily object identity in all threading scenarios

    # ==================== Error Handling Tests ====================

    def test_graceful_degradation_missing_version(self, temp_config_dir):
        """Test handling of config without version field"""
        # Create config without version
        no_version_config = {"data": "test"}
        (temp_config_dir / "no_version.json").write_text(json.dumps(no_version_config))

        service = ConfigurationService(str(temp_config_dir))

        # Should still load, just log warning
        config = service.load_config("no_version")
        assert config is not None
        assert config["data"] == "test"

    def test_config_with_utf8_encoding(self, temp_config_dir):
        """Test loading config with UTF-8 special characters"""
        special_chars_config = {
            "version": "1.0",
            "data": "Español, Français, Deutsch, 中文"
        }
        (temp_config_dir / "utf8_test.json").write_text(
            json.dumps(special_chars_config, ensure_ascii=False),
            encoding="utf-8"
        )

        service = ConfigurationService(str(temp_config_dir))
        config = service.load_config("utf8_test")

        assert config is not None
        assert "Español" in config["data"]


class TestConfigurationServiceIntegration:
    """Integration tests for ConfigurationService with actual config files"""

    @pytest.fixture
    def real_config_service(self):
        """Create ConfigurationService with real config directory"""
        # Use actual config directory from the project
        return ConfigurationService()

    def test_load_all_real_configs(self, real_config_service):
        """Test loading all actual configuration files"""
        configs_to_test = [
            "component_types",
            "llm_config",
            "llm_prompts",
            "state_prompts",
            "welding_processes",
            "materials",
            "cooling_types",
            "search_config",
            "cache_config",
            "error_messages",
            "languages"
        ]

        for config_name in configs_to_test:
            try:
                config = real_config_service.load_config(config_name)
                assert config is not None
                assert "version" in config
            except FileNotFoundError:
                pytest.skip(f"Config file {config_name}.json not found")

    def test_real_component_types_structure(self, real_config_service):
        """Test structure of actual component_types.json"""
        try:
            config = real_config_service.get_component_types()

            assert "component_types" in config

            # Check all expected components exist
            expected_components = [
                "power_source", "feeder", "cooler",
                "interconnector", "torch", "accessories"
            ]

            for component in expected_components:
                assert component in config["component_types"]
                comp_data = config["component_types"][component]

                # Verify required fields
                assert "api_key" in comp_data
                assert "display_name" in comp_data
                assert "state_name" in comp_data
        except FileNotFoundError:
            pytest.skip("component_types.json not found")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
