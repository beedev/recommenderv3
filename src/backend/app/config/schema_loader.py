"""
Schema Loader Utility for Configuration Files
Loads component structure and search configuration from JSON files at runtime
"""

import json
import os
from functools import lru_cache
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load_component_config() -> Dict[str, Any]:
    """
    Load and cache component search configuration from component_types.json

    Returns:
        Dict containing component search configuration with all 13 component types
        Each component has: category, neo4j_label, requires_compatibility,
        dependencies, master_param_key, lucene_enabled, fuzzy_matching_enabled

    Raises:
        FileNotFoundError: If component_types.json not found
        json.JSONDecodeError: If file is invalid JSON
    """
    try:
        config_path = os.path.join(
            os.path.dirname(__file__),
            "component_types.json"
        )

        with open(config_path, "r") as f:
            data = json.load(f)

        # Extract component_types from the file
        config = data.get("component_types", {})

        logger.info(f"Loaded component config with {len(config)} component types")
        logger.info(f"Component types: {list(config.keys())}")

        return config

    except FileNotFoundError:
        logger.error(f"Component types file not found at {config_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in component types file: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to load component config: {e}")
        raise


@lru_cache(maxsize=1)
def load_master_parameter_schema() -> Dict[str, Any]:
    """
    Load and cache master parameter schema from config

    Returns:
        Dict containing schema configuration with components and features

    Raises:
        FileNotFoundError: If schema file not found
        json.JSONDecodeError: If schema file is invalid JSON
    """
    try:
        config_path = os.path.join(
            os.path.dirname(__file__),
            "master_parameter_schema.json"
        )

        with open(config_path, "r") as f:
            schema = json.load(f)

        logger.info(f"Loaded master parameter schema v{schema.get('version', 'unknown')}")
        logger.info(f"Components defined: {list(schema.get('components', {}).keys())}")

        return schema

    except FileNotFoundError:
        logger.error(f"Schema file not found at {config_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in schema file: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to load schema: {e}")
        raise


def get_component_list() -> List[str]:
    """
    Get list of all component names from schema

    Returns:
        List of component names (e.g., ["power_source", "feeder", ...])
    """
    schema = load_master_parameter_schema()
    components = list(schema["components"].keys())
    logger.info(f"Component list: {components}")
    return components


def get_component_features(component_name: str) -> List[str]:
    """
    Get list of features for a specific component

    Args:
        component_name: Name of component (e.g., "power_source")

    Returns:
        List of feature names for this component

    Raises:
        KeyError: If component not found in schema
    """
    schema = load_master_parameter_schema()

    if component_name not in schema["components"]:
        raise KeyError(f"Component '{component_name}' not found in schema")

    features = schema["components"][component_name].get("features", [])
    logger.info(f"Features for {component_name}: {features}")
    return features


def get_product_name_enabled_components() -> List[str]:
    """
    Get list of components where product_name feature is enabled

    Returns:
        List of component names (e.g., ["power_source", "feeder", "cooler"])
    """
    schema = load_master_parameter_schema()
    enabled_components = schema.get("product_name_enabled_components", [])
    logger.info(f"Product name enabled for: {enabled_components}")
    return enabled_components


def validate_component_dict(component_name: str, component_dict: Dict[str, Any]) -> bool:
    """
    Validate that all keys in component dict are defined in schema

    Args:
        component_name: Name of component
        component_dict: Dict of component features to validate

    Returns:
        True if all keys are valid, False otherwise

    Logs warnings for invalid keys
    """
    try:
        valid_features = get_component_features(component_name)

        invalid_keys = []
        for key in component_dict.keys():
            if key not in valid_features:
                invalid_keys.append(key)

        if invalid_keys:
            logger.warning(
                f"Invalid keys in {component_name}: {invalid_keys}. "
                f"Valid keys: {valid_features}"
            )
            return False

        return True

    except KeyError:
        logger.error(f"Component '{component_name}' not found in schema")
        return False


@lru_cache(maxsize=1)
def load_state_config() -> Dict[str, Any]:
    """
    Load and cache state configuration from component_types.json

    Converts component_types structure to state_config format for backward compatibility.
    State configuration fields are now stored directly in component_types.json.

    Returns:
        Dict containing state configurations in state_config.json format:
        {
          "version": "2.1.0",
          "description": "Per-state configuration for ESAB configurator S1→SN flow",
          "states": {
            "power_source_selection": {
              "state_name": "PowerSource Selection",
              "component_type": "PowerSource",
              "mandatory": true,
              "proactive_display": true,
              "search_limit": 10,
              "preview_limit": 5,
              "multi_select": false,
              "allow_skip": false,
              "description": "..."
            },
            ...
          }
        }

    Raises:
        FileNotFoundError: If component_types.json not found
        json.JSONDecodeError: If file is invalid JSON
    """
    try:
        config_path = os.path.join(
            os.path.dirname(__file__),
            "component_types.json"
        )

        with open(config_path, "r") as f:
            data = json.load(f)

        component_types = data.get("component_types", {})

        # Convert component_types structure to state_config format
        state_config = {
            "version": data.get("version", "2.1.0"),
            "description": "Per-state configuration for ESAB configurator S1→SN flow (loaded from component_types.json)",
            "states": {}
        }

        # Convert each component to state config format
        for comp_key, comp_data in component_types.items():
            state_name = comp_data.get("state_name")
            if not state_name:
                logger.warning(f"Component {comp_key} missing state_name, skipping")
                continue

            # Map selection_type to multi_select
            selection_type = comp_data.get("selection_type", "single")
            multi_select = (selection_type == "multi")

            # Map component fields to state config fields
            state_config["states"][state_name] = {
                "state_name": comp_data.get("display_name", "Unknown"),
                "component_type": comp_data.get("api_key", comp_key),
                "mandatory": comp_data.get("is_mandatory", False),
                "proactive_display": comp_data.get("proactive_display", True),
                "search_limit": comp_data.get("search_limit", 10),
                "preview_limit": comp_data.get("preview_limit", 5),
                "multi_select": multi_select,
                "allow_skip": comp_data.get("can_skip", True),
                "description": comp_data.get("description", "")
            }

        logger.info(f"Converted {len(state_config['states'])} component types to state config format")
        logger.info(f"State names: {list(state_config['states'].keys())}")

        return state_config

    except FileNotFoundError:
        logger.error(f"Component types file not found at {config_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in component types file: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to load state config from component_types: {e}")
        raise


# Convenience function to get schema version
def get_schema_version() -> str:
    """Get schema version string"""
    schema = load_master_parameter_schema()
    return schema.get("version", "unknown")
