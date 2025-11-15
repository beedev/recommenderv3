"""
Integration tests for configuration system
Tests how different services work together with the configuration
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.services.config.configuration_service import ConfigurationService, get_config_service
from app.services.config.prompt_service import PromptService, get_prompt_service


@pytest.mark.integration
@pytest.mark.config
class TestConfigurationIntegration:
    """Integration tests for configuration system"""

    def test_config_and_prompt_service_integration(self, config_service):
        """Test ConfigurationService and PromptService work together"""
        prompt_service = PromptService(config_service)

        # Test getting component display name
        display_name = prompt_service.get_component_display_name("power_source")
        assert display_name == "Power Source"

        # Test getting component icon
        icon = prompt_service.get_component_icon("power_source")
        assert icon == "🔋"

        # Test getting welding process examples
        processes = prompt_service.get_welding_process_examples()
        assert "MIG (GMAW)" in processes
        assert "TIG (GTAW)" in processes

    def test_config_service_provides_data_for_prompts(self, config_service):
        """Test that ConfigurationService provides all data needed for prompts"""
        prompt_service = PromptService(config_service)

        # Get state prompt config
        state_config = config_service.get_state_prompt_config("power_source_selection")
        assert state_config is not None

        # Render prompt using the config
        result = prompt_service.render_state_prompt("power_source_selection", {})
        assert result is not None
        assert len(result) > 0

    def test_llm_config_integration(self, config_service):
        """Test LLM configuration is correctly provided"""
        # Get LLM config
        llm_config = config_service.get_llm_config("parameter_extraction")

        assert llm_config["model"] == "gpt-4"
        assert llm_config["temperature"] == 0.3
        assert llm_config["max_tokens"] == 2000

        # Get prompt
        prompt = config_service.get_prompt("parameter_extraction_system")
        assert prompt is not None

    def test_error_message_integration(self, config_service):
        """Test error messages work with prompt service"""
        prompt_service = PromptService(config_service)

        # Format error message
        error_msg = prompt_service.format_error_message("power_source_required", "test details")

        assert "⚠️" in error_msg
        assert "PowerSource selection is mandatory" in error_msg

    def test_component_types_complete_workflow(self, config_service):
        """Test complete workflow using component types"""
        # Get all component types
        component_types = config_service.get_component_types()
        assert "component_types" in component_types

        # Get specific component
        power_source = config_service.get_component_type("power_source")
        assert power_source["api_key"] == "PowerSource"

        # Get component by API key
        component = config_service.get_component_type_by_api_key("PowerSource")
        assert component["key"] == "power_source"

    def test_search_config_fuzzy_matching(self, config_service):
        """Test search config provides fuzzy matching settings"""
        search_config = config_service.get_search_config()
        fuzzy_config = config_service.get_fuzzy_match_config()

        assert fuzzy_config["enabled"] is True
        assert fuzzy_config["score_cutoff"] == 80
        assert fuzzy_config["max_matches"] == 1

        # Components enabled for fuzzy matching
        components_enabled = fuzzy_config["components_enabled"]
        assert "power_source" in components_enabled
        assert "feeder" in components_enabled

    def test_multilingual_config_integration(self, config_service):
        """Test multilingual configuration"""
        # Get supported languages
        languages = config_service.get_supported_languages()
        assert len(languages) >= 2

        # Get language codes
        codes = config_service.get_language_codes()
        assert "en" in codes
        assert "es" in codes

        # Get default language
        default_lang = config_service.get_default_language()
        assert default_lang == "en"


@pytest.mark.integration
class TestServiceRefactoringIntegration:
    """Integration tests for refactored services using configuration"""

    @patch('app.services.orchestrator.state_orchestrator.get_config_service')
    def test_orchestrator_uses_config_service(self, mock_get_config, config_service):
        """Test StateByStateOrchestrator uses configuration"""
        mock_get_config.return_value = config_service

        from app.services.orchestrator.state_orchestrator import StateByStateOrchestrator

        # Mock dependencies
        mock_extractor = MagicMock()
        mock_search = MagicMock()
        mock_generator = MagicMock()
        mock_applicability = {}

        # Create orchestrator
        orchestrator = StateByStateOrchestrator(
            mock_extractor,
            mock_search,
            mock_generator,
            mock_applicability
        )

        # Verify config service is accessible
        assert orchestrator.config_service is not None

        # Test getting component API key from state
        api_key = orchestrator._get_component_api_key("power_source_selection")
        assert api_key == "PowerSource"

        # Test getting component name
        component_types = orchestrator.config_service.get_component_types()
        assert "component_types" in component_types

    @patch('app.services.response.message_generator.get_config_service')
    def test_message_generator_uses_config_service(self, mock_get_config, config_service):
        """Test MessageGenerator uses configuration"""
        mock_get_config.return_value = config_service

        from app.services.response.message_generator import MessageGenerator

        # Create message generator
        generator = MessageGenerator()

        # Verify config service is accessible
        assert generator.config_service is not None

        # Test getting component name from state
        component_name = generator._get_component_name("power_source_selection")
        assert component_name == "Power Source"

        # Test error message generation
        error_msg = generator.generate_error_message("power_source_required")
        assert "PowerSource selection is mandatory" in error_msg

    @patch('app.services.neo4j.product_search.get_config_service')
    def test_product_search_uses_config_service(self, mock_get_config, config_service):
        """Test Neo4jProductSearch uses configuration"""
        mock_get_config.return_value = config_service

        from app.services.neo4j.product_search import Neo4jProductSearch

        # Create product search (mock Neo4j connection)
        with patch('app.services.neo4j.product_search.AsyncGraphDatabase.driver'):
            search = Neo4jProductSearch("bolt://localhost", "user", "pass")

            # Verify config service is accessible
            assert search.config_service is not None

            # Test fuzzy match config is loaded
            fuzzy_config = search.config_service.get_fuzzy_match_config()
            assert fuzzy_config["score_cutoff"] == 80

    @patch('app.services.intent.parameter_extractor.get_config_service')
    def test_parameter_extractor_uses_config_service(self, mock_get_config, config_service):
        """Test ParameterExtractor uses configuration"""
        mock_get_config.return_value = config_service

        from app.services.intent.parameter_extractor import ParameterExtractor

        # Create parameter extractor (mock OpenAI)
        with patch('app.services.intent.parameter_extractor.AsyncOpenAI'):
            extractor = ParameterExtractor("fake_api_key")

            # Verify config service is accessible
            assert extractor.config_service is not None

            # Test fuzzy match config is used for product names
            fuzzy_config = extractor.config_service.get_fuzzy_match_config()
            assert "components_enabled" in fuzzy_config

    @patch('app.services.multilingual.translator.get_config_service')
    def test_translator_uses_config_service(self, mock_get_config, config_service):
        """Test MultilingualTranslator uses configuration"""
        mock_get_config.return_value = config_service

        from app.services.multilingual.translator import MultilingualTranslator

        # Create translator
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'fake_key'}):
            translator = MultilingualTranslator()

            # Verify config service is accessible
            assert translator.config_service is not None

            # Test language names are loaded from config
            assert translator.LANGUAGE_NAMES is not None
            assert "en" in translator.LANGUAGE_NAMES
            assert translator.LANGUAGE_NAMES["en"] == "English"


@pytest.mark.integration
@pytest.mark.slow
class TestEndToEndConfigFlow:
    """End-to-end tests for configuration flow"""

    def test_complete_config_loading_flow(self, config_service, prompt_service):
        """Test complete configuration loading and usage flow"""
        # 1. Load component types
        component_types = config_service.get_component_types()
        assert "power_source" in component_types["component_types"]

        # 2. Get component details
        power_source = config_service.get_component_type("power_source")
        assert power_source["display_name"] == "Power Source"

        # 3. Use component in prompt service
        display_name = prompt_service.get_component_display_name("power_source")
        assert display_name == "Power Source"

        # 4. Get LLM configuration
        llm_config = config_service.get_llm_config("parameter_extraction")
        assert llm_config["model"] == "gpt-4"

        # 5. Get prompt template
        prompt = config_service.get_prompt("parameter_extraction_system")
        assert "welding equipment expert" in prompt.lower()

        # 6. Format error message
        error_msg = prompt_service.format_error_message("power_source_required")
        assert "PowerSource selection is mandatory" in error_msg

        # 7. Get welding domain data
        processes = config_service.get_welding_process_names()
        materials = config_service.get_material_names()
        assert len(processes) > 0
        assert len(materials) > 0

        # 8. Use in prompt examples
        process_str = prompt_service.get_welding_process_examples()
        material_str = prompt_service.get_material_examples()
        assert "MIG" in process_str
        assert "Steel" in material_str

    def test_config_caching_across_multiple_calls(self, config_service):
        """Test that configuration caching works across multiple calls"""
        # Load same config multiple times
        config1 = config_service.load_config("component_types")
        config2 = config_service.load_config("component_types")
        config3 = config_service.load_config("component_types")

        # All should return same cached object
        assert config1 is config2
        assert config2 is config3

        # Clear cache and reload
        reloaded = config_service.reload_config("component_types")
        assert reloaded is not None

    def test_multiple_services_share_config(self, config_service):
        """Test that multiple services can share the same config service"""
        prompt_service1 = PromptService(config_service)
        prompt_service2 = PromptService(config_service)

        # Both use same config service
        assert prompt_service1.config_service is prompt_service2.config_service

        # Both get same results
        name1 = prompt_service1.get_component_display_name("power_source")
        name2 = prompt_service2.get_component_display_name("power_source")
        assert name1 == name2

    def test_config_provides_all_required_data(self, config_service):
        """Test that configuration provides all data required by services"""
        # Component types for orchestrator
        component_types = config_service.get_component_types()
        assert "component_types" in component_types

        # LLM config for parameter extractor
        llm_config = config_service.get_llm_config("parameter_extraction")
        assert all(k in llm_config for k in ["model", "temperature", "max_tokens"])

        # Prompts for message generator
        state_config = config_service.get_state_prompt_config("power_source_selection")
        assert all(k in state_config for k in ["icon", "step_number", "title"])

        # Search config for product search
        search_config = config_service.get_search_config()
        assert "fuzzy_matching" in search_config

        # Languages for translator
        languages = config_service.get_supported_languages()
        assert len(languages) > 0

        # Error messages for error handling
        error = config_service.get_error_message("power_source_required")
        assert "message" in error


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
