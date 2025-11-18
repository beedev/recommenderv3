"""
Centralized State Management Utility

Provides a single source of truth for state transitions in the S1→SN configurator flow.
All state-related logic is centralized here to avoid duplication across the codebase.

Architecture:
- Configuration-driven: Uses component_types.json state_sequence
- Single responsibility: Handles ALL state transition logic
- Deterministic: Given state + applicability → next state (no side effects)
- Testable: Pure functions with clear inputs/outputs

Usage:
    from app.services.state import StateManager

    state_manager = StateManager()
    next_state = state_manager.get_next_state(
        current_state="power_source_selection",
        applicability={"Feeder": "Y", "Cooler": "N"}
    )
"""

import logging
from typing import Dict, List, Optional, Any
from enum import Enum

from app.services.config.configuration_service import get_config_service
from app.models.conversation import ConfiguratorState

logger = logging.getLogger(__name__)


class StateManager:
    """
    Centralized state management for S1→SN configurator flow.

    Responsibilities:
    - Determine next state based on current state and applicability
    - Validate state transitions
    - Provide state sequence information
    - Handle state skipping logic (when applicability = "N")

    All state-related business logic should go through this class.
    """

    def __init__(self):
        """Initialize State Manager with configuration from component_types.json."""
        self.config_service = get_config_service()

        # Load state sequence from configuration (Single Source of Truth)
        self._state_sequence: List[str] = self.config_service.get_state_sequence()
        self._finalize_state: str = "finalize"  # Fixed: hardcoded instead of calling non-existent method

        # Create state index map for O(1) lookups
        self._state_index = {state: idx for idx, state in enumerate(self._state_sequence)}

        logger.info(f"StateManager initialized with {len(self._state_sequence)} states")

    def get_next_state(
        self,
        current_state: str,
        applicability: Dict[str, str],
        selected_components: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Determine the next state in the S1→SN flow with applicability-based skipping.

        This is the PRIMARY state transition method - all state progression goes through here.

        Args:
            current_state: Current ConfiguratorState name (e.g., "power_source_selection")
            applicability: Dict mapping component API keys to "Y"/"N" flags
            selected_components: Optional ResponseJSON dict (for additional validation)

        Returns:
            Next state name, or "finalize" if at end of sequence

        Rules:
            1. Follow state_sequence order from component_types.json
            2. Auto-skip states where applicability[ComponentKey] == "N"
            3. If current state is last applicable state → "finalize"
            4. If current state not in sequence → "finalize" (error recovery)

        Examples:
            >>> manager.get_next_state("power_source_selection", {"Feeder": "Y", "Cooler": "N"})
            "cooler_selection"  # New S2 after swap

            >>> manager.get_next_state("cooler_selection", {"Feeder": "Y", "Cooler": "N"})
            "feeder_selection"  # S3 after swap, skips cooler since N
        """
        # Edge case: finalize is always final
        if current_state == self._finalize_state:
            return self._finalize_state

        # Get current position in sequence
        current_index = self._state_index.get(current_state)
        if current_index is None:
            logger.warning(f"Current state '{current_state}' not in sequence, defaulting to finalize")
            return self._finalize_state

        # Iterate through remaining states to find next applicable one
        for next_index in range(current_index + 1, len(self._state_sequence)):
            candidate_state = self._state_sequence[next_index]

            # Check if this state is applicable
            if self._is_state_applicable(candidate_state, applicability):
                logger.info(f"State transition: {current_state} → {candidate_state}")
                return candidate_state
            else:
                logger.debug(f"Skipping state '{candidate_state}' (applicability = N)")

        # No more applicable states → finalize
        logger.info(f"No more applicable states after '{current_state}' → finalize")
        return self._finalize_state

    def get_previous_state(
        self,
        current_state: str,
        applicability: Dict[str, str]
    ) -> Optional[str]:
        """
        Get the previous state in the sequence (for back navigation).

        Args:
            current_state: Current state name
            applicability: Component applicability flags

        Returns:
            Previous applicable state name, or None if at beginning
        """
        # Can't go back from finalize or if not in sequence
        if current_state == self._finalize_state:
            return None

        current_index = self._state_index.get(current_state)
        if current_index is None or current_index == 0:
            return None

        # Search backwards for applicable state
        for prev_index in range(current_index - 1, -1, -1):
            candidate_state = self._state_sequence[prev_index]

            if self._is_state_applicable(candidate_state, applicability):
                logger.info(f"Previous state: {current_state} ← {candidate_state}")
                return candidate_state

        return None  # No previous applicable state

    def _is_state_applicable(
        self,
        state_name: str,
        applicability: Dict[str, str]
    ) -> bool:
        """
        Check if a state is applicable based on applicability flags.

        Args:
            state_name: State name (e.g., "feeder_selection")
            applicability: Dict mapping component API keys to "Y"/"N"

        Returns:
            True if state is applicable (should be shown), False if should be skipped

        Logic:
            - power_source_selection: Always applicable (S1 is mandatory)
            - Other states: Check applicability[ComponentKey]
            - If key not found in applicability dict → assume "Y" (show by default)
        """
        # S1 (power_source) is ALWAYS applicable
        if state_name == "power_source_selection":
            return True

        # Map state name to component API key using configuration
        component_type = self._get_component_type_for_state(state_name)
        if not component_type:
            logger.warning(f"Could not find component type for state '{state_name}', assuming applicable")
            return True

        # Get component API key (e.g., "Feeder", "Cooler")
        component_config = self.config_service.get_component_type(component_type)
        if not component_config:
            return True

        api_key = component_config.get("api_key")
        if not api_key:
            return True

        # Check applicability flag (default to "Y" if not specified)
        is_applicable = applicability.get(api_key, "Y") == "Y"

        logger.debug(f"State '{state_name}' (API key: {api_key}) applicability: {'Y' if is_applicable else 'N'}")
        return is_applicable

    def _get_component_type_for_state(self, state_name: str) -> Optional[str]:
        """
        Map state name to component type key.

        Args:
            state_name: State name (e.g., "feeder_selection")

        Returns:
            Component type key (e.g., "feeder"), or None if not found
        """
        # Iterate through component types to find matching state_name
        component_types_config = self.config_service.get_component_types()
        # Access nested "component_types" key - get_component_types() returns entire JSON
        for component_type, config in component_types_config.get("component_types", {}).items():
            if config.get("state_name") == state_name:
                return component_type

        return None

    def get_state_sequence(self) -> List[str]:
        """
        Get the complete state sequence from configuration.

        Returns:
            List of state names in order (e.g., ["power_source_selection", "cooler_selection", ...])
        """
        return self._state_sequence.copy()  # Return copy to prevent modification

    def get_state_index(self, state_name: str) -> Optional[int]:
        """
        Get the index of a state in the sequence (0-based).

        Args:
            state_name: State name

        Returns:
            Index in sequence, or None if state not found
        """
        return self._state_index.get(state_name)

    def is_final_state(self, state_name: str) -> bool:
        """
        Check if a state is the final state (finalize).

        Args:
            state_name: State name

        Returns:
            True if this is the finalize state
        """
        return state_name == self._finalize_state

    def get_applicable_states(self, applicability: Dict[str, str]) -> List[str]:
        """
        Get list of all applicable states given applicability flags.

        Useful for progress indicators, state count, etc.

        Args:
            applicability: Component applicability flags

        Returns:
            List of applicable state names in sequence order
        """
        applicable_states = []

        for state_name in self._state_sequence:
            if self._is_state_applicable(state_name, applicability):
                applicable_states.append(state_name)

        return applicable_states

    def get_progress_percentage(
        self,
        current_state: str,
        applicability: Dict[str, str]
    ) -> float:
        """
        Calculate progress percentage through applicable states.

        Args:
            current_state: Current state name
            applicability: Component applicability flags

        Returns:
            Progress percentage (0.0 to 100.0)
        """
        applicable_states = self.get_applicable_states(applicability)

        if not applicable_states:
            return 100.0  # No applicable states → complete

        try:
            current_index = applicable_states.index(current_state)
            return (current_index / len(applicable_states)) * 100.0
        except ValueError:
            # Current state not in applicable states → at end
            return 100.0

    def validate_state_transition(
        self,
        from_state: str,
        to_state: str,
        applicability: Dict[str, str]
    ) -> bool:
        """
        Validate if a state transition is allowed.

        Args:
            from_state: Starting state
            to_state: Target state
            applicability: Component applicability flags

        Returns:
            True if transition is valid, False otherwise

        Rules:
            - Can only move forward to next applicable state
            - Can move backward to previous applicable state
            - Can jump to finalize from any state
            - Cannot skip applicable states when moving forward
        """
        # Always allow jump to finalize
        if to_state == self._finalize_state:
            return True

        # Check if both states are in sequence
        from_index = self._state_index.get(from_state)
        to_index = self._state_index.get(to_state)

        if from_index is None or to_index is None:
            return False

        # Forward transition: must be next applicable state
        if to_index > from_index:
            next_state = self.get_next_state(from_state, applicability)
            return next_state == to_state

        # Backward transition: must be previous applicable state
        elif to_index < from_index:
            prev_state = self.get_previous_state(from_state, applicability)
            return prev_state == to_state

        # Same state → invalid
        return False


# Singleton instance for easy access
_state_manager_instance: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    """
    Get singleton StateManager instance.

    Returns:
        Shared StateManager instance
    """
    global _state_manager_instance

    if _state_manager_instance is None:
        _state_manager_instance = StateManager()

    return _state_manager_instance
