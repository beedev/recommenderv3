"""
Configuration Service
Centralized configuration management with caching and validation
"""

import json
import os
from functools import lru_cache
from typing import Dict, List, Any, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigurationService:
    """
    Centralized service for loading and caching application configurations

    Loads configurations from JSON files in the config directory with:
    - LRU caching for performance
    - Validation support
    - Error handling
    - Hot-reload capability
    """

    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize ConfigurationService

        Args:
            config_dir: Path to configuration directory. If None, uses default app/config
        """
        if config_dir is None:
            # Default to app/config directory
            self.config_dir = Path(__file__).parent.parent.parent / "config"
        else:
            self.config_dir = Path(config_dir)

        logger.info(f"ConfigurationService initialized with config_dir: {self.config_dir}")

    @lru_cache(maxsize=32)
    def load_config(self, config_name: str) -> Dict[str, Any]:
        """
        Load configuration from JSON file with caching

        Args:
            config_name: Name of config file (without .json extension)

        Returns:
            Dict containing configuration data

        Raises:
            FileNotFoundError: If config file not found
            json.JSONDecodeError: If config file is invalid JSON
        """
        try:
            config_path = self.config_dir / f"{config_name}.json"

            if not config_path.exists():
                raise FileNotFoundError(f"Config file not found: {config_path}")

            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            logger.info(f"Loaded config: {config_name} (version: {config.get('version', 'N/A')})")
            return config

        except FileNotFoundError:
            logger.error(f"Config file not found: {config_name}.json")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {config_name}.json: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load config {config_name}: {e}")
            raise

    def reload_config(self, config_name: str) -> Dict[str, Any]:
        """
        Force reload of configuration (clears cache)

        Args:
            config_name: Name of config file to reload

        Returns:
            Freshly loaded configuration
        """
        # Clear cache for this specific config
        self.load_config.cache_clear()
        logger.info(f"Cache cleared, reloading config: {config_name}")
        return self.load_config(config_name)

    def get_component_types(self) -> Dict[str, Any]:
        """Get component types configuration"""
        return self.load_config("component_types")

    def get_component_type(self, component_key: str) -> Optional[Dict[str, Any]]:
        """
        Get specific component type configuration

        Args:
            component_key: Component key (e.g., "power_source", "feeder")

        Returns:
            Component configuration dict or None if not found
        """
        config = self.get_component_types()
        return config.get("component_types", {}).get(component_key)

    def get_component_type_by_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Get component type by API key (e.g., "PowerSource", "Feeder")

        Args:
            api_key: API key used in ResponseJSON

        Returns:
            Component configuration dict or None if not found
        """
        config = self.get_component_types()
        for comp_key, comp_data in config.get("component_types", {}).items():
            if comp_data.get("api_key") == api_key:
                return {**comp_data, "key": comp_key}
        return None

    def get_response_json_field_name(self, component_key: str) -> str:
        """
        Get ResponseJSON field name from component key

        Maps snake_case component keys to CamelCase ResponseJSON field names
        using the class_name property from component_types.json

        Args:
            component_key: Component key (e.g., "powersource_accessories")

        Returns:
            ResponseJSON field name (e.g., "PowerSourceAccessories")
            Falls back to component_key if not found in config

        Examples:
            >>> config_service.get_response_json_field_name("powersource_accessories")
            "PowerSourceAccessories"
            >>> config_service.get_response_json_field_name("power_source")
            "PowerSource"
        """
        comp_config = self.get_component_type(component_key)
        if comp_config:
            return comp_config.get("class_name", component_key)

        # Fallback: return component_key if not found in config
        logger.warning(f"Component type not found in config: {component_key}, using as-is")
        return component_key

    def get_llm_config(self, purpose: str = "parameter_extraction") -> Dict[str, Any]:
        """
        Get LLM configuration for specific purpose

        Args:
            purpose: Purpose key (e.g., "parameter_extraction", "translation")

        Returns:
            LLM configuration dict
        """
        config = self.load_config("llm_config")
        models = config.get("models", {})

        if purpose not in models:
            logger.warning(f"LLM config not found for purpose: {purpose}, using defaults")
            return {
                "model": "gpt-4",
                "temperature": 0.3,
                "max_tokens": 2000
            }

        return models[purpose]

    def get_prompt(self, prompt_key: str) -> str:
        """
        Get LLM prompt by key

        Args:
            prompt_key: Prompt identifier

        Returns:
            Prompt string
        """
        config = self.load_config("llm_prompts")
        prompts = config.get("prompts", {})

        if prompt_key not in prompts:
            logger.error(f"Prompt not found: {prompt_key}")
            raise KeyError(f"Prompt not found: {prompt_key}")

        prompt_data = prompts[prompt_key]

        # Handle both simple string prompts and complex template objects
        if isinstance(prompt_data, dict):
            return prompt_data.get("prompt") or prompt_data.get("template", "")
        return str(prompt_data)

    def get_state_prompt_config(self, state_name: str) -> Dict[str, Any]:
        """
        Get state-specific prompt configuration

        Args:
            state_name: State identifier (e.g., "power_source_selection")

        Returns:
            State prompt configuration
        """
        config = self.load_config("state_prompts")
        states = config.get("states", {})

        if state_name not in states:
            logger.error(f"State prompt not found: {state_name}")
            raise KeyError(f"State prompt not found: {state_name}")

        return states[state_name]

    def get_welding_processes(self) -> List[Dict[str, Any]]:
        """Get list of all welding processes"""
        config = self.load_config("welding_processes")
        return config.get("processes", [])

    def get_welding_process_names(self) -> List[str]:
        """Get list of welding process display names"""
        processes = self.get_welding_processes()
        return [p["display_name"] for p in processes]

    def get_materials(self) -> List[Dict[str, Any]]:
        """Get list of all materials"""
        config = self.load_config("materials")
        return config.get("materials", [])

    def get_material_names(self) -> List[str]:
        """Get list of material display names"""
        materials = self.get_materials()
        return [m["display_name"] for m in materials]

    def get_cooling_types(self) -> List[Dict[str, Any]]:
        """Get list of all cooling types"""
        config = self.load_config("cooling_types")
        return config.get("cooling_types", [])

    def get_search_config(self) -> Dict[str, Any]:
        """Get search configuration"""
        return self.load_config("search_config")

    def get_fuzzy_match_config(self) -> Dict[str, Any]:
        """Get fuzzy matching configuration"""
        config = self.get_search_config()
        return config.get("fuzzy_matching", {})

    def get_search_limit(self, component_type: str = "default") -> int:
        """
        Get search result limit for component type

        Args:
            component_type: Component type key (e.g., "power_source", "feeder")

        Returns:
            Search result limit (from component_types.json, default: 10)
        """
        # Load from component_types.json (rationalized Nov 15, 2024)
        if component_type == "default":
            return 10

        component_config = self.get_component_type(component_type)
        if component_config:
            return component_config.get("search_limit", 10)

        logger.warning(f"Component type '{component_type}' not found, using default limit: 10")
        return 10

    def get_state_sequence(self) -> List[str]:
        """
        Get state sequence from component_types.json

        Returns:
            List of state names in order (e.g., ["power_source_selection", "feeder_selection", ...])
        """
        config = self.get_component_types()
        return config.get("state_sequence", [])

    def get_cache_config(self) -> Dict[str, Any]:
        """Get cache configuration"""
        return self.load_config("cache_config")

    def get_session_ttl(self) -> int:
        """Get Redis session TTL in seconds"""
        config = self.get_cache_config()
        return config.get("redis_session", {}).get("default_ttl_seconds", 3600)

    def get_error_message(self, error_code: str) -> Dict[str, Any]:
        """
        Get error message configuration

        Args:
            error_code: Error code identifier

        Returns:
            Error message configuration
        """
        config = self.load_config("error_messages")
        messages = config.get("error_messages", {})

        if error_code not in messages:
            logger.warning(f"Error message not found: {error_code}")
            return {
                "code": error_code,
                "icon": "⚠️",
                "message": "An error occurred",
                "severity": "error"
            }

        return messages[error_code]

    def get_supported_languages(self) -> List[Dict[str, Any]]:
        """Get list of supported languages"""
        config = self.load_config("languages")
        return config.get("supported_languages", [])

    def get_language_codes(self) -> List[str]:
        """Get list of supported language codes"""
        languages = self.get_supported_languages()
        return [lang["code"] for lang in languages]

    def get_default_language(self) -> str:
        """Get default language code"""
        languages = self.get_supported_languages()
        for lang in languages:
            if lang.get("is_default", False):
                return lang["code"]
        return "en"  # Fallback

    def validate_config(self, config_name: str) -> bool:
        """
        Validate configuration file

        Args:
            config_name: Name of config to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            config = self.load_config(config_name)

            # Basic validation - check if version exists
            if "version" not in config:
                logger.warning(f"Config {config_name} missing version field")

            logger.info(f"Config {config_name} validated successfully")
            return True

        except Exception as e:
            logger.error(f"Config validation failed for {config_name}: {e}")
            return False


# Global singleton instance
_config_service: Optional[ConfigurationService] = None


def get_config_service() -> ConfigurationService:
    """
    Get global ConfigurationService singleton instance

    Returns:
        ConfigurationService instance
    """
    global _config_service
    if _config_service is None:
        _config_service = ConfigurationService()
    return _config_service


def init_config_service(config_dir: Optional[str] = None) -> ConfigurationService:
    """
    Initialize global ConfigurationService with custom config directory

    Args:
        config_dir: Path to configuration directory

    Returns:
        ConfigurationService instance
    """
    global _config_service
    _config_service = ConfigurationService(config_dir)
    logger.info("Global ConfigurationService initialized")
    return _config_service
