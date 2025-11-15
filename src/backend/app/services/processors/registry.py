"""
State Processor Registry

Central registry for all 14 state processors in S1→SN flow.
Manages processor lifecycle and dependency injection.
"""

import logging
from typing import Dict, Optional

from app.config.schema_loader import load_state_config
from .base import StateProcessor
from .power_source import PowerSourceStateProcessor
from .feeder import FeederStateProcessor
from .cooler import CoolerStateProcessor
from .interconnector import InterconnectorStateProcessor
from .torch import TorchStateProcessor
from .accessory import AccessoryStateProcessor, create_accessory_processors

logger = logging.getLogger(__name__)


class StateProcessorRegistry:
    """
    Registry for all state processors.

    Manages initialization and retrieval of state-specific processors.
    Each processor handles search, validation, and state transitions.

    Usage:
        registry = StateProcessorRegistry(state_config_path, search_orchestrator)
        processor = registry.get_processor("power_source_selection")
        results = await processor.search_products(...)
    """

    def __init__(
        self,
        state_config_path: str,  # Deprecated, kept for backward compatibility
        search_orchestrator
    ):
        """
        Initialize registry and all state processors.

        Args:
            state_config_path: DEPRECATED - State config now loaded from component_types.json via schema_loader
            search_orchestrator: SearchOrchestrator instance for searches
        """
        self.search_orchestrator = search_orchestrator
        # Load state config from component_types.json via schema_loader
        self.state_config_dict = load_state_config()
        self._processors: Dict[str, StateProcessor] = {}

        # Initialize all processors
        self._initialize_processors()

        logger.info(
            f"StateProcessorRegistry initialized with {len(self._processors)} processors from component_types.json"
        )


    def _initialize_processors(self):
        """
        Initialize all 14 state processors.

        Creates:
        - 5 primary component processors (PowerSource, Feeder, Cooler, Interconnector, Torch)
        - 9 accessory processors (using factory pattern)
        """
        states = self.state_config_dict.get("states", {})

        # S1: Power Source (MANDATORY - first component)
        if "power_source_selection" in states:
            self._processors["power_source_selection"] = PowerSourceStateProcessor(
                state_name="power_source_selection",
                component_type="PowerSource",
                state_config=states["power_source_selection"],
                search_orchestrator=self.search_orchestrator
            )
            logger.debug("✓ PowerSourceStateProcessor initialized")

        # S2: Feeder (depends on PowerSource)
        if "feeder_selection" in states:
            self._processors["feeder_selection"] = FeederStateProcessor(
                state_name="feeder_selection",
                component_type="Feeder",
                state_config=states["feeder_selection"],
                search_orchestrator=self.search_orchestrator
            )
            logger.debug("✓ FeederStateProcessor initialized")

        # S3: Cooler (depends on PowerSource)
        if "cooler_selection" in states:
            self._processors["cooler_selection"] = CoolerStateProcessor(
                state_name="cooler_selection",
                component_type="Cooler",
                state_config=states["cooler_selection"],
                search_orchestrator=self.search_orchestrator
            )
            logger.debug("✓ CoolerStateProcessor initialized")

        # S4: Interconnector (triple compatibility check)
        if "interconnector_selection" in states:
            self._processors["interconnector_selection"] = InterconnectorStateProcessor(
                state_name="interconnector_selection",
                component_type="Interconnector",
                state_config=states["interconnector_selection"],
                search_orchestrator=self.search_orchestrator
            )
            logger.debug("✓ InterconnectorStateProcessor initialized")

        # S5: Torch (depends on Feeder)
        if "torch_selection" in states:
            self._processors["torch_selection"] = TorchStateProcessor(
                state_name="torch_selection",
                component_type="Torch",
                state_config=states["torch_selection"],
                search_orchestrator=self.search_orchestrator
            )
            logger.debug("✓ TorchStateProcessor initialized")

        # S6: Accessories (9 accessory states using factory)
        accessory_processors = create_accessory_processors(
            self.state_config_dict,
            self.search_orchestrator
        )
        self._processors.update(accessory_processors)
        logger.debug(f"✓ {len(accessory_processors)} AccessoryStateProcessors initialized")

        # Validate all expected states are registered
        expected_states = [
            "power_source_selection",
            "feeder_selection",
            "cooler_selection",
            "interconnector_selection",
            "torch_selection",
            "powersource_accessories_selection",
            "feeder_accessories_selection",
            "feeder_conditional_accessories_selection",
            "interconnector_accessories_selection",
            "remote_selection",
            "remote_accessories_selection",
            "remote_conditional_accessories_selection",
            "connectivity_selection",
        ]

        missing_states = [s for s in expected_states if s not in self._processors]
        if missing_states:
            logger.warning(f"Missing processors for states: {missing_states}")

    def get_processor(self, state_name: str) -> Optional[StateProcessor]:
        """
        Retrieve state processor by state name.

        Args:
            state_name: ConfiguratorState enum value (e.g., "power_source_selection")

        Returns:
            StateProcessor instance for the given state, or None if not found
        """
        processor = self._processors.get(state_name)

        if processor is None:
            logger.warning(f"No processor found for state: {state_name}")

        return processor

    def has_processor(self, state_name: str) -> bool:
        """
        Check if processor exists for given state.

        Args:
            state_name: State name to check

        Returns:
            True if processor exists, False otherwise
        """
        return state_name in self._processors

    def get_all_processors(self) -> Dict[str, StateProcessor]:
        """
        Get all registered processors.

        Returns:
            Dictionary mapping state names to processors
        """
        return self._processors.copy()

    def get_state_config(self, state_name: str) -> Optional[Dict]:
        """
        Get configuration for a specific state.

        Args:
            state_name: State name

        Returns:
            State configuration dict or None if not found
        """
        return self.state_config_dict.get("states", {}).get(state_name)

    def is_multi_select_state(self, state_name: str) -> bool:
        """
        Check if state allows multi-select.

        Args:
            state_name: State name to check

        Returns:
            True if multi-select enabled for this state
        """
        processor = self.get_processor(state_name)
        if processor:
            return processor.is_multi_select()
        return False

    def is_mandatory_state(self, state_name: str) -> bool:
        """
        Check if state is mandatory.

        Args:
            state_name: State name to check

        Returns:
            True if state is mandatory (cannot be skipped)
        """
        config = self.get_state_config(state_name)
        if config:
            return config.get("mandatory", False)
        return False

    def get_component_type(self, state_name: str) -> Optional[str]:
        """
        Get component type for a state.

        Args:
            state_name: State name

        Returns:
            Component type (e.g., "PowerSource", "Feeder") or None
        """
        processor = self.get_processor(state_name)
        if processor:
            return processor.component_type
        return None

    def validate_state_transition(
        self,
        from_state: str,
        to_state: str
    ) -> bool:
        """
        Validate if state transition is allowed.

        Args:
            from_state: Current state
            to_state: Target state

        Returns:
            True if transition is valid, False otherwise

        Note:
            This is a basic validation. Full validation requires
            checking conversation_state and applicability.
        """
        # Get processors
        from_processor = self.get_processor(from_state)
        to_processor = self.get_processor(to_state)

        if not from_processor or not to_processor:
            logger.warning(
                f"Invalid transition: processor not found "
                f"({from_state} → {to_state})"
            )
            return False

        # Basic validation: can't go backward to power_source_selection
        # unless explicitly reset
        if to_state == "power_source_selection" and from_state != "power_source_selection":
            logger.warning(
                f"Invalid backward transition to power_source_selection "
                f"from {from_state}"
            )
            return False

        return True


# Singleton instance (initialized in main.py)
_registry_instance: Optional[StateProcessorRegistry] = None


def init_state_processor_registry(
    state_config_path: str,
    search_orchestrator
) -> StateProcessorRegistry:
    """
    Initialize global StateProcessorRegistry instance.

    Args:
        state_config_path: Path to state_config.json
        search_orchestrator: SearchOrchestrator instance

    Returns:
        Initialized registry instance
    """
    global _registry_instance

    if _registry_instance is None:
        _registry_instance = StateProcessorRegistry(
            state_config_path,
            search_orchestrator
        )
        logger.info("✓ Global StateProcessorRegistry initialized")
    else:
        logger.warning("StateProcessorRegistry already initialized")

    return _registry_instance


def get_state_processor_registry() -> Optional[StateProcessorRegistry]:
    """
    Get global StateProcessorRegistry instance.

    Returns:
        Registry instance or None if not initialized
    """
    if _registry_instance is None:
        logger.error(
            "StateProcessorRegistry not initialized. "
            "Call init_state_processor_registry() first."
        )
    return _registry_instance
