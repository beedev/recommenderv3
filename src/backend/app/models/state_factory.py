"""
State Factory Module
Dynamically generates ConfiguratorState enum from configuration
"""

import logging
from enum import Enum
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class StateFactory:
    """
    Factory for dynamically creating ConfiguratorState enum from configuration

    This allows states to be fully configuration-driven (S1→SN) without
    hardcoding state names in Python code.
    """

    _cached_enum: Optional[type] = None
    _cached_state_sequence: Optional[List[str]] = None
    _cached_state_metadata: Optional[Dict[str, Dict[str, Any]]] = None

    @classmethod
    def load_state_config(cls, config_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Load component_types.json configuration

        Args:
            config_path: Path to component_types.json (optional)

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        import json

        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "component_types.json"

        if not config_path.exists():
            raise FileNotFoundError(f"Component types config not found: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # Validate required fields
        if "component_types" not in config:
            raise ValueError("component_types.json missing 'component_types' field")
        if "state_sequence" not in config:
            raise ValueError("component_types.json missing 'state_sequence' field")

        return config

    @classmethod
    def create_configurator_state_enum(cls, config: Optional[Dict[str, Any]] = None, force_reload: bool = False) -> type:
        """
        Create ConfiguratorState enum dynamically from configuration

        Args:
            config: Component types config dict (loads from file if not provided)
            force_reload: Force reload even if cached

        Returns:
            Dynamically created Enum class

        Example:
            >>> ConfiguratorState = create_configurator_state_enum()
            >>> state = ConfiguratorState.POWER_SOURCE_SELECTION
            >>> print(state.value)  # "power_source_selection"
        """
        # Return cached enum if available
        if cls._cached_enum is not None and not force_reload:
            logger.debug("Returning cached ConfiguratorState enum")
            return cls._cached_enum

        # Load config if not provided
        if config is None:
            config = cls.load_state_config()

        # Extract state sequence and finalize state
        state_sequence = config.get("state_sequence", [])
        finalize_state = config.get("finalize_state", "finalize")

        # Build complete state list (S1→SN + finalize)
        all_states = list(state_sequence) + [finalize_state]

        if not all_states:
            raise ValueError("No states found in configuration")

        # Create enum members dict
        # Convert snake_case state names to UPPER_CASE enum names
        enum_members = {}
        state_metadata = {}

        for state_name in all_states:
            # Convert "power_source_selection" -> "POWER_SOURCE_SELECTION"
            enum_name = state_name.upper()
            enum_members[enum_name] = state_name

            # Store metadata for this state (will be populated below)
            state_metadata[state_name] = {
                "enum_name": enum_name,
                "state_name": state_name
            }

        # Extract component metadata and add to state_metadata
        for comp_key, comp_data in config.get("component_types", {}).items():
            state_name = comp_data.get("state_name")
            if state_name in state_metadata:
                state_metadata[state_name].update({
                    "component_key": comp_key,
                    "api_key": comp_data.get("api_key"),
                    "display_name": comp_data.get("display_name"),
                    "icon": comp_data.get("icon"),
                    "state_order": comp_data.get("state_order"),
                    "is_mandatory": comp_data.get("is_mandatory", False),
                    "can_skip": comp_data.get("can_skip", True),
                    "selection_type": comp_data.get("selection_type", "single"),
                    "requires_compatibility_check": comp_data.get("requires_compatibility_check", True)
                })

        # Create the enum class dynamically
        ConfiguratorState = Enum(
            value="ConfiguratorState",
            names=enum_members,
            type=str
        )

        # Add docstring
        ConfiguratorState.__doc__ = f"""
        Dynamically generated state machine states (S1→S{len(state_sequence)} + Finalize)

        States loaded from component_types.json configuration.
        Total states: {len(all_states)}
        """

        # Cache the enum and metadata
        cls._cached_enum = ConfiguratorState
        cls._cached_state_sequence = all_states
        cls._cached_state_metadata = state_metadata

        logger.info(f"✅ Created ConfiguratorState enum with {len(all_states)} states")
        for state in all_states:
            logger.debug(f"  - {state}")

        return ConfiguratorState

    @classmethod
    def get_state_sequence(cls) -> List[str]:
        """
        Get ordered list of state names

        Returns:
            List of state names in order (S1→SN + finalize)

        Raises:
            RuntimeError: If enum hasn't been created yet
        """
        if cls._cached_state_sequence is None:
            raise RuntimeError("ConfiguratorState enum not created yet. Call create_configurator_state_enum() first")

        return cls._cached_state_sequence.copy()

    @classmethod
    def get_state_metadata(cls, state_name: str) -> Dict[str, Any]:
        """
        Get metadata for a specific state

        Args:
            state_name: State name (e.g., "power_source_selection")

        Returns:
            Metadata dictionary

        Raises:
            RuntimeError: If enum hasn't been created yet
            KeyError: If state name not found
        """
        if cls._cached_state_metadata is None:
            raise RuntimeError("ConfiguratorState enum not created yet. Call create_configurator_state_enum() first")

        if state_name not in cls._cached_state_metadata:
            raise KeyError(f"State '{state_name}' not found in metadata")

        return cls._cached_state_metadata[state_name].copy()

    @classmethod
    def get_all_metadata(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get metadata for all states

        Returns:
            Dictionary mapping state_name -> metadata

        Raises:
            RuntimeError: If enum hasn't been created yet
        """
        if cls._cached_state_metadata is None:
            raise RuntimeError("ConfiguratorState enum not created yet. Call create_configurator_state_enum() first")

        return cls._cached_state_metadata.copy()

    @classmethod
    def get_component_states(cls) -> List[str]:
        """
        Get only component selection states (excluding finalize)

        Returns:
            List of component state names
        """
        state_sequence = cls.get_state_sequence()
        # Remove last item (finalize)
        return state_sequence[:-1]

    @classmethod
    def get_finalize_state(cls) -> str:
        """
        Get the finalize state name

        Returns:
            Finalize state name
        """
        state_sequence = cls.get_state_sequence()
        return state_sequence[-1]

    @classmethod
    def clear_cache(cls):
        """Clear cached enum and metadata (useful for testing)"""
        cls._cached_enum = None
        cls._cached_state_sequence = None
        cls._cached_state_metadata = None
        logger.debug("Cleared StateFactory cache")

    @classmethod
    def validate_state_name(cls, state_name: str) -> bool:
        """
        Check if a state name is valid

        Args:
            state_name: State name to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            state_sequence = cls.get_state_sequence()
            return state_name in state_sequence
        except RuntimeError:
            return False


# Convenience functions for backward compatibility
def create_configurator_state_enum(config: Optional[Dict[str, Any]] = None, force_reload: bool = False) -> type:
    """
    Create ConfiguratorState enum (convenience function)

    See StateFactory.create_configurator_state_enum() for details.
    """
    return StateFactory.create_configurator_state_enum(config, force_reload)


def get_state_sequence() -> List[str]:
    """Get state sequence (convenience function)"""
    return StateFactory.get_state_sequence()


def get_state_metadata(state_name: str) -> Dict[str, Any]:
    """Get state metadata (convenience function)"""
    return StateFactory.get_state_metadata(state_name)
