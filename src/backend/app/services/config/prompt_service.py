"""
Prompt Service
Handles template rendering for LLM prompts and user messages
"""

import logging
from typing import Dict, Any, List, Optional
from .configuration_service import get_config_service

logger = logging.getLogger(__name__)


class PromptService:
    """
    Service for rendering prompt templates with dynamic data

    Handles:
    - Variable substitution in templates
    - State-specific prompt generation
    - Multi-language support
    - Context-aware formatting
    """

    def __init__(self, config_service=None):
        """
        Initialize PromptService

        Args:
            config_service: ConfigurationService instance (uses global if None)
        """
        self.config_service = config_service or get_config_service()

    def render_template(self, template: str, **variables) -> str:
        """
        Render template with variable substitution

        Args:
            template: Template string with {variable} placeholders
            **variables: Variable values for substitution

        Returns:
            Rendered string
        """
        try:
            return template.format(**variables)
        except KeyError as e:
            logger.error(f"Missing variable in template: {e}")
            logger.error(f"Template: {template[:100]}...")
            logger.error(f"Variables provided: {list(variables.keys())}")
            raise
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            raise

    def render_state_prompt(
        self,
        state_name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Render state-specific prompt with context

        Args:
            state_name: State identifier (e.g., "power_source_selection")
            context: Context variables for template rendering

        Returns:
            Rendered prompt string
        """
        try:
            # Get state configuration
            state_config = self.config_service.get_state_prompt_config(state_name)

            # Get template
            template = state_config.get("prompt_template", "")

            # Prepare default context
            default_context = {
                "step_number": state_config.get("step_number", ""),
                "title": state_config.get("title", ""),
                "icon": state_config.get("icon", ""),
            }

            # Merge with provided context
            render_context = {**default_context, **(context or {})}

            # Render template
            rendered = self.render_template(template, **render_context)

            logger.info(f"Rendered prompt for state: {state_name}")
            return rendered

        except Exception as e:
            logger.error(f"Failed to render state prompt for {state_name}: {e}")
            # Return a fallback prompt
            return f"Please provide information for {state_name.replace('_', ' ')}"

    def render_llm_system_prompt(
        self,
        prompt_key: str,
        **variables
    ) -> str:
        """
        Render LLM system prompt with variables

        Args:
            prompt_key: Prompt identifier from llm_prompts.json
            **variables: Variables for template rendering

        Returns:
            Rendered prompt string
        """
        try:
            prompt_template = self.config_service.get_prompt(prompt_key)
            return self.render_template(prompt_template, **variables)

        except Exception as e:
            logger.error(f"Failed to render LLM prompt {prompt_key}: {e}")
            raise

    def get_component_display_name(self, component_key: str) -> str:
        """
        Get display name for component

        Args:
            component_key: Component key (e.g., "power_source")

        Returns:
            Display name (e.g., "Power Source")
        """
        try:
            component_config = self.config_service.get_component_type(component_key)
            if component_config:
                return component_config.get("display_name", component_key.replace("_", " ").title())
            return component_key.replace("_", " ").title()
        except Exception as e:
            logger.warning(f"Could not get display name for {component_key}: {e}")
            return component_key.replace("_", " ").title()

    def get_component_icon(self, component_key: str) -> str:
        """
        Get emoji icon for component

        Args:
            component_key: Component key

        Returns:
            Emoji icon string
        """
        try:
            component_config = self.config_service.get_component_type(component_key)
            if component_config:
                return component_config.get("icon", "")
            return ""
        except Exception as e:
            logger.warning(f"Could not get icon for {component_key}: {e}")
            return ""

    def format_product_list(
        self,
        products: List[Dict[str, Any]],
        component_key: str,
        max_display: int = 10
    ) -> str:
        """
        Format product list for user display

        Args:
            products: List of product dictionaries
            component_key: Component type key
            max_display: Maximum products to display

        Returns:
            Formatted product list string
        """
        if not products:
            return "No products found."

        component_name = self.get_component_display_name(component_key)
        icon = self.get_component_icon(component_key)

        lines = [f"\n{icon} **Available {component_name}s:**\n"]

        for idx, product in enumerate(products[:max_display], 1):
            name = product.get("name", "Unknown")
            gin = product.get("gin", "")
            description = product.get("description", "")

            line = f"{idx}. **{name}**"
            if gin:
                line += f" (GIN: {gin})"
            if description:
                # Truncate long descriptions
                desc_short = description[:100] + "..." if len(description) > 100 else description
                line += f"\n   {desc_short}"

            lines.append(line)

        if len(products) > max_display:
            lines.append(f"\n... and {len(products) - max_display} more")

        return "\n".join(lines)

    def format_error_message(
        self,
        error_code: str,
        details: Optional[str] = None
    ) -> str:
        """
        Format error message with details

        Args:
            error_code: Error code identifier
            details: Optional additional details

        Returns:
            Formatted error message
        """
        try:
            error_config = self.config_service.get_error_message(error_code)

            icon = error_config.get("icon", "⚠️")
            message = error_config.get("message", "An error occurred")

            # Substitute {details} placeholder if present
            if details and "{details}" in message:
                message = message.replace("{details}", details)

            formatted = f"{icon} {message}"

            # Add suggested actions if available
            suggested_actions = error_config.get("suggested_actions", [])
            if suggested_actions:
                formatted += "\n\n**Suggestions:**"
                for action in suggested_actions:
                    formatted += f"\n- {action}"

            return formatted

        except Exception as e:
            logger.error(f"Failed to format error message {error_code}: {e}")
            return f"⚠️ {details or 'An error occurred'}"

    def get_welding_process_examples(self) -> str:
        """
        Get formatted list of welding processes for prompts

        Returns:
            Comma-separated process names (e.g., "MIG (GMAW), TIG (GTAW), ...")
        """
        try:
            process_names = self.config_service.get_welding_process_names()
            return ", ".join(process_names)
        except Exception as e:
            logger.warning(f"Could not load welding processes: {e}")
            return "MIG, TIG, STICK"  # Fallback

    def get_material_examples(self) -> str:
        """
        Get formatted list of materials for prompts

        Returns:
            Comma-separated material names
        """
        try:
            material_names = self.config_service.get_material_names()
            return ", ".join(material_names)
        except Exception as e:
            logger.warning(f"Could not load materials: {e}")
            return "Steel, Aluminum, Stainless Steel"  # Fallback

    def format_configuration_summary(
        self,
        response_json: Dict[str, Any]
    ) -> str:
        """
        Format complete configuration summary for finalization

        Args:
            response_json: ResponseJSON dict with selected components

        Returns:
            Formatted summary string
        """
        lines = ["📋 **Your Welding Equipment Configuration:**\n"]

        # Component order
        component_order = [
            "PowerSource",
            "Feeder",
            "Cooler",
            "Interconnector",
            "Torch",
            "Accessories"
        ]

        for comp_api_key in component_order:
            if comp_api_key in response_json and response_json[comp_api_key]:
                # Get component config for icon
                comp_config = self.config_service.get_component_type_by_api_key(comp_api_key)
                icon = comp_config.get("icon", "•") if comp_config else "•"
                display_name = comp_config.get("display_name", comp_api_key) if comp_config else comp_api_key

                # Handle Accessories (list) vs single product
                if comp_api_key == "Accessories":
                    accessories = response_json[comp_api_key]
                    if isinstance(accessories, list) and accessories:
                        lines.append(f"{icon} **{display_name}:**")
                        for acc in accessories:
                            if isinstance(acc, dict):
                                lines.append(f"   - {acc.get('product_name', 'Unknown')}")
                            else:
                                lines.append(f"   - {acc}")
                else:
                    product = response_json[comp_api_key]
                    if isinstance(product, dict):
                        product_name = product.get("product_name", "Unknown")
                        lines.append(f"{icon} **{display_name}:** {product_name}")

        return "\n".join(lines)


# Global singleton instance
_prompt_service: Optional[PromptService] = None


def get_prompt_service() -> PromptService:
    """
    Get global PromptService singleton instance

    Returns:
        PromptService instance
    """
    global _prompt_service
    if _prompt_service is None:
        _prompt_service = PromptService()
    return _prompt_service
