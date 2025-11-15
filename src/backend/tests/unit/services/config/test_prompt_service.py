"""
Unit tests for PromptService
Tests template rendering, prompt generation, and formatting
"""

import pytest
from unittest.mock import MagicMock, patch

from app.services.config.prompt_service import PromptService, get_prompt_service
from app.services.config.configuration_service import ConfigurationService


class TestPromptService:
    """Test suite for PromptService"""

    @pytest.fixture
    def mock_config_service(self):
        """Create mock ConfigurationService"""
        mock = MagicMock(spec=ConfigurationService)

        # Mock component types
        mock.get_component_types.return_value = {
            "component_types": {
                "power_source": {
                    "display_name": "Power Source",
                    "icon": "🔋",
                    "api_key": "PowerSource"
                },
                "feeder": {
                    "display_name": "Wire Feeder",
                    "icon": "🔌",
                    "api_key": "Feeder"
                }
            },
            "finalize_state": {
                "icon": "📋"
            }
        }

        # Mock component type lookup
        mock.get_component_type.return_value = {
            "display_name": "Power Source",
            "icon": "🔋"
        }

        mock.get_component_type_by_api_key.return_value = {
            "display_name": "Power Source",
            "icon": "🔋",
            "api_key": "PowerSource"
        }

        # Mock state prompt config
        mock.get_state_prompt_config.return_value = {
            "icon": "🔋",
            "step_number": 1,
            "title": "Power Source Selection",
            "prompt_template": "Step {step_number}: {title}"
        }

        # Mock welding processes
        mock.get_welding_process_names.return_value = ["MIG (GMAW)", "TIG (GTAW)", "STICK (SMAW)"]

        # Mock materials
        mock.get_material_names.return_value = ["Steel", "Aluminum", "Stainless Steel"]

        # Mock error messages
        mock.get_error_message.return_value = {
            "code": "ERR_TEST",
            "icon": "⚠️",
            "message": "Test error: {details}",
            "suggested_actions": ["Action 1", "Action 2"]
        }

        return mock

    @pytest.fixture
    def prompt_service(self, mock_config_service):
        """Create PromptService with mock config"""
        return PromptService(mock_config_service)

    # ==================== Template Rendering Tests ====================

    def test_render_template_basic(self, prompt_service):
        """Test basic template rendering"""
        template = "Hello {name}, welcome to {place}!"
        result = prompt_service.render_template(template, name="Alice", place="Wonderland")

        assert result == "Hello Alice, welcome to Wonderland!"

    def test_render_template_with_missing_variable(self, prompt_service):
        """Test template rendering with missing variable raises error"""
        template = "Hello {name}, welcome to {place}!"

        with pytest.raises(KeyError):
            prompt_service.render_template(template, name="Alice")

    def test_render_template_with_extra_variables(self, prompt_service):
        """Test template rendering ignores extra variables"""
        template = "Hello {name}!"
        result = prompt_service.render_template(
            template,
            name="Alice",
            extra="unused"
        )

        assert result == "Hello Alice!"

    def test_render_template_empty(self, prompt_service):
        """Test rendering empty template"""
        result = prompt_service.render_template("", test="value")

        assert result == ""

    def test_render_template_no_variables(self, prompt_service):
        """Test rendering template with no variables"""
        template = "Static text with no variables"
        result = prompt_service.render_template(template)

        assert result == template

    # ==================== State Prompt Rendering Tests ====================

    def test_render_state_prompt(self, prompt_service, mock_config_service):
        """Test rendering state-specific prompt"""
        result = prompt_service.render_state_prompt(
            "power_source_selection",
            {"key": "value"}
        )

        assert "Step 1: Power Source Selection" in result

    def test_render_state_prompt_with_context(self, prompt_service, mock_config_service):
        """Test rendering state prompt with custom context"""
        context = {"custom_key": "custom_value"}

        result = prompt_service.render_state_prompt(
            "power_source_selection",
            context
        )

        assert result is not None

    def test_render_state_prompt_invalid_state(self, prompt_service, mock_config_service):
        """Test rendering prompt for invalid state returns fallback"""
        mock_config_service.get_state_prompt_config.side_effect = KeyError("State not found")

        result = prompt_service.render_state_prompt("invalid_state", {})

        assert "invalid state" in result.lower()

    # ==================== LLM System Prompt Tests ====================

    def test_render_llm_system_prompt(self, prompt_service, mock_config_service):
        """Test rendering LLM system prompt"""
        mock_config_service.get_prompt.return_value = "You are a {role} expert in {domain}."

        result = prompt_service.render_llm_system_prompt(
            "test_prompt",
            role="welding",
            domain="equipment"
        )

        assert result == "You are a welding expert in equipment."

    def test_render_llm_system_prompt_missing_key(self, prompt_service, mock_config_service):
        """Test rendering LLM prompt with missing key raises error"""
        mock_config_service.get_prompt.return_value = "Template with {variable}"

        with pytest.raises(Exception):
            prompt_service.render_llm_system_prompt("test_prompt")

    # ==================== Component Display Name Tests ====================

    def test_get_component_display_name(self, prompt_service):
        """Test getting component display name"""
        result = prompt_service.get_component_display_name("power_source")

        assert result == "Power Source"

    def test_get_component_display_name_not_found(self, prompt_service, mock_config_service):
        """Test getting display name for unknown component"""
        mock_config_service.get_component_type.return_value = None

        result = prompt_service.get_component_display_name("unknown_component")

        # Should return title-cased version
        assert result == "Unknown Component"

    def test_get_component_display_name_exception(self, prompt_service, mock_config_service):
        """Test getting display name when exception occurs"""
        mock_config_service.get_component_type.side_effect = Exception("Config error")

        result = prompt_service.get_component_display_name("power_source")

        # Should handle exception gracefully
        assert "Power Source" in result or "power source" in result.lower()

    # ==================== Component Icon Tests ====================

    def test_get_component_icon(self, prompt_service):
        """Test getting component icon"""
        result = prompt_service.get_component_icon("power_source")

        assert result == "🔋"

    def test_get_component_icon_not_found(self, prompt_service, mock_config_service):
        """Test getting icon for unknown component returns empty"""
        mock_config_service.get_component_type.return_value = None

        result = prompt_service.get_component_icon("unknown")

        assert result == ""

    # ==================== Product List Formatting Tests ====================

    def test_format_product_list(self, prompt_service):
        """Test formatting product list"""
        products = [
            {"name": "Product 1", "gin": "GIN001", "description": "Description 1"},
            {"name": "Product 2", "gin": "GIN002", "description": "Description 2"}
        ]

        result = prompt_service.format_product_list(products, "power_source", max_display=10)

        assert "Product 1" in result
        assert "Product 2" in result
        assert "GIN001" in result
        assert "GIN002" in result
        assert "Power Source" in result

    def test_format_product_list_empty(self, prompt_service):
        """Test formatting empty product list"""
        result = prompt_service.format_product_list([], "power_source")

        assert result == "No products found."

    def test_format_product_list_max_display(self, prompt_service):
        """Test formatting product list respects max_display"""
        products = [
            {"name": f"Product {i}", "gin": f"GIN{i:03d}", "description": f"Desc {i}"}
            for i in range(15)
        ]

        result = prompt_service.format_product_list(products, "power_source", max_display=5)

        # Should show only first 5
        assert "Product 0" in result
        assert "Product 4" in result
        assert "Product 5" not in result
        assert "and 10 more" in result

    def test_format_product_list_no_description(self, prompt_service):
        """Test formatting products without descriptions"""
        products = [
            {"name": "Product 1", "gin": "GIN001"},
            {"name": "Product 2", "gin": "GIN002"}
        ]

        result = prompt_service.format_product_list(products, "power_source")

        assert "Product 1" in result
        assert "Product 2" in result

    def test_format_product_list_long_description(self, prompt_service):
        """Test formatting products with long descriptions"""
        products = [
            {
                "name": "Product 1",
                "gin": "GIN001",
                "description": "A" * 150  # Very long description
            }
        ]

        result = prompt_service.format_product_list(products, "power_source")

        assert "Product 1" in result
        # Should be truncated
        assert "..." in result

    # ==================== Error Message Formatting Tests ====================

    def test_format_error_message(self, prompt_service):
        """Test formatting error message"""
        result = prompt_service.format_error_message("test_error", "specific details")

        assert "⚠️" in result
        assert "Test error: specific details" in result

    def test_format_error_message_with_suggestions(self, prompt_service):
        """Test formatting error message includes suggestions"""
        result = prompt_service.format_error_message("test_error", "details")

        assert "Suggestions:" in result
        assert "Action 1" in result
        assert "Action 2" in result

    def test_format_error_message_no_details(self, prompt_service):
        """Test formatting error message without details"""
        result = prompt_service.format_error_message("test_error")

        assert "⚠️" in result
        assert "Test error" in result

    def test_format_error_message_exception(self, prompt_service, mock_config_service):
        """Test formatting error message when config fails"""
        mock_config_service.get_error_message.side_effect = Exception("Config error")

        result = prompt_service.format_error_message("test_error", "details")

        # Should fall back gracefully
        assert "⚠️" in result
        assert "details" in result

    # ==================== Welding Domain Examples Tests ====================

    def test_get_welding_process_examples(self, prompt_service):
        """Test getting welding process examples"""
        result = prompt_service.get_welding_process_examples()

        assert "MIG (GMAW)" in result
        assert "TIG (GTAW)" in result
        assert "STICK (SMAW)" in result
        assert ", " in result  # Should be comma-separated

    def test_get_welding_process_examples_exception(self, prompt_service, mock_config_service):
        """Test getting process examples when config fails"""
        mock_config_service.get_welding_process_names.side_effect = Exception("Config error")

        result = prompt_service.get_welding_process_examples()

        # Should return fallback
        assert "MIG" in result or "TIG" in result or "STICK" in result

    def test_get_material_examples(self, prompt_service):
        """Test getting material examples"""
        result = prompt_service.get_material_examples()

        assert "Steel" in result
        assert "Aluminum" in result
        assert "Stainless Steel" in result
        assert ", " in result

    def test_get_material_examples_exception(self, prompt_service, mock_config_service):
        """Test getting material examples when config fails"""
        mock_config_service.get_material_names.side_effect = Exception("Config error")

        result = prompt_service.get_material_examples()

        # Should return fallback
        assert "Steel" in result or "Aluminum" in result

    # ==================== Configuration Summary Tests ====================

    def test_format_configuration_summary_single_components(self, prompt_service):
        """Test formatting configuration summary with single components"""
        response_json = {
            "PowerSource": {
                "product_name": "Aristo 500ix",
                "gin": "0446200880",
                "name": "Aristo 500ix"
            },
            "Feeder": {
                "product_name": "RobustFeed",
                "gin": "GIN001",
                "name": "RobustFeed"
            }
        }

        result = prompt_service.format_configuration_summary(response_json)

        assert "📋" in result or "Configuration" in result
        assert "Aristo 500ix" in result
        assert "RobustFeed" in result
        # Note: GIN numbers are not included in the summary, only product names

    def test_format_configuration_summary_with_accessories(self, prompt_service):
        """Test formatting summary with multiple accessories"""
        response_json = {
            "PowerSource": {
                "product_name": "Aristo 500ix",
                "gin": "0446200880",
                "name": "Aristo 500ix"
            },
            "Accessories": [
                {"product_name": "Accessory 1", "gin": "ACC001", "name": "Accessory 1"},
                {"product_name": "Accessory 2", "gin": "ACC002", "name": "Accessory 2"}
            ]
        }

        result = prompt_service.format_configuration_summary(response_json)

        assert "Accessory 1" in result
        assert "Accessory 2" in result
        # Note: GIN numbers are not included in the summary, only product names

    def test_format_configuration_summary_empty(self, prompt_service):
        """Test formatting empty configuration summary"""
        result = prompt_service.format_configuration_summary({})

        assert "Configuration" in result

    def test_format_configuration_summary_missing_components(self, prompt_service):
        """Test formatting summary with None/missing components"""
        response_json = {
            "PowerSource": {
                "product_name": "Aristo 500ix",
                "gin": "0446200880",
                "name": "Aristo 500ix"
            },
            "Feeder": None,
            "Cooler": None
        }

        result = prompt_service.format_configuration_summary(response_json)

        assert "Aristo 500ix" in result
        # Should not show None components
        assert result.count("None") == 0

    # ==================== Singleton Pattern Tests ====================

    def test_get_prompt_service_singleton(self):
        """Test that get_prompt_service returns singleton"""
        service1 = get_prompt_service()
        service2 = get_prompt_service()

        assert service1 is service2

    # ==================== Edge Cases ====================

    def test_render_template_with_special_characters(self, prompt_service):
        """Test rendering template with special characters"""
        template = "Wählen Sie {component} für {process}!"
        result = prompt_service.render_template(
            template,
            component="Schweißgerät",
            process="MIG-Schweißen"
        )

        assert "Schweißgerät" in result
        assert "MIG-Schweißen" in result

    def test_format_product_list_unicode_names(self, prompt_service):
        """Test formatting products with unicode characters"""
        products = [
            {"name": "产品 1", "gin": "GIN001", "description": "描述 1"},
            {"name": "製品 2", "gin": "GIN002", "description": "説明 2"}
        ]

        result = prompt_service.format_product_list(products, "power_source")

        assert "产品 1" in result
        assert "製品 2" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
