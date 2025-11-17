"""
Generic Accessory State Processor

S6a-S6h: All accessory states (multi-select, optional).

This generic processor handles all 8 accessory states:
- powersource_accessories
- feeder_accessories
- feeder_conditional_accessories
- interconnector_accessories
- remote
- remote_accessories
- remote_conditional_accessories
- connectivity

All accessories share common characteristics:
- Multi-select enabled (can select multiple products)
- Optional (can be skipped)
- Proactive display enabled (shows compatible products automatically)
"""

import logging
from typing import Dict, Any, Optional
from langsmith import traceable
from .base import StateProcessor

logger = logging.getLogger(__name__)


class AccessoryStateProcessor(StateProcessor):
    """
    Generic accessory state processor.

    Handles all accessory states with multi-select capability.

    Characteristics:
    - Multi-select enabled (configurable per state)
    - Optional (allow_skip=true)
    - Proactive display enabled (proactive_display=true)
    - Multiple selections accumulate in response_json[component_type]
    """

    def __init__(
        self,
        state_name: str,
        component_type: str,
        state_config: Dict[str, Any],
        search_orchestrator,
        next_accessory_state: Optional[str] = None
    ):
        """
        Initialize accessory processor.

        Args:
            state_name: State enum value
            component_type: Component type key
            state_config: Configuration from state_config.json
            search_orchestrator: SearchOrchestrator instance
            next_accessory_state: Next accessory state in sequence (or None if last)
        """
        super().__init__(state_name, component_type, state_config, search_orchestrator)
        self.next_accessory_state = next_accessory_state

    @traceable(name="search_products_accessory", run_type="retriever")
    async def search_products(
        self,
        user_message: str,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: Optional[int] = None,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Search for accessories compatible with selected components.

        Args:
            user_message: Raw user message
            master_parameters: LLM-extracted parameters
            selected_components: Already selected components
            limit: Max results (default from state_config)
            offset: Pagination offset

        Returns:
            Consolidated search results from multiple strategies
        """
        try:
            search_limit = self._get_search_limit(limit)

            logger.info(
                f"AccessoryStateProcessor searching {self.component_type} "
                f"(limit={search_limit}, offset={offset})"
            )

            # Execute search via SearchOrchestrator
            results = await self.search_orchestrator.search(
                component_type=self.component_type,
                user_message=user_message,
                master_parameters=master_parameters,
                selected_components=selected_components,
                limit=search_limit,
                offset=offset
            )

            if "metadata" in results and "execution_time_ms" in results["metadata"]:
                self._log_search(
                    results["total_count"],
                    results["metadata"]["execution_time_ms"]
                )

            return results

        except Exception as e:
            logger.error(f"AccessoryStateProcessor search error for {self.component_type}: {e}", exc_info=True)
            return {
                "products": [],
                "total_count": 0,
                "offset": offset,
                "limit": search_limit,
                "has_more": False,
                "zero_results_message": f"Error searching for {self.component_type}: {str(e)}",
                "metadata": {"error": str(e)}
            }

    def get_next_state(
        self,
        conversation_state,
        selection_made: bool = False
    ) -> str:
        """
        Determine next state after accessory selection/skip.

        For multi-select states:
        - If selection_made=True (orchestrator detected "done"/"next"/"skip"): Move to next state
        - Otherwise check conversation history for completion keywords
        - If neither: Stay in current state for more selections

        Conditional Accessory Logic:
        - If next state is a conditional accessory state (feeder_conditional, remote_conditional)
        - Check if parent accessory category has any selections
        - If no parent selections, skip conditional state and move to next state

        Args:
            conversation_state: Current ConversationState
            selection_made: True if orchestrator detected completion intent (done/next/skip)

        Returns:
            Next state name
        """
        # For multi-select, check if user is done
        if self.multi_select:
            # Priority 1: Check selection_made parameter (orchestrator already detected intent)
            if selection_made:
                logger.info(f"Multi-select complete (selection_made=True), moving to next state")
            # Priority 2: Check conversation history for completion keywords
            elif not self._is_done_with_multi_select(conversation_state):
                logger.info(f"Staying in {self.state_name} (multi-select in progress)")
                return self.state_name
            else:
                logger.info(f"Multi-select complete (completion keyword detected), moving to next state")

        # Move to next accessory state or finalize
        if self.next_accessory_state:
            # ✅ PRIORITY 1: APPLICABILITY CHECK (NEW)
            # Check if next accessory state is applicable for selected PowerSource
            response_json = conversation_state.response_json
            applicability = response_json.applicability.model_dump() if response_json.applicability else {}

            component_key = self._get_component_api_key_from_state(self.next_accessory_state)
            if component_key:
                component_status = applicability.get(component_key)
                if component_status not in ["mandatory", "optional", "Y", None]:  # not_applicable or N
                    logger.info(
                        f"⏭️  Skipping {self.next_accessory_state} "
                        f"({component_key} applicability: {component_status})"
                    )
                    # Recursively find next applicable state
                    return self._get_next_applicable_accessory_state(
                        self.next_accessory_state,
                        conversation_state
                    )

            # ✅ PRIORITY 2: CONDITIONAL ACCESSORY DEPENDENCY CHECK (EXISTING)
            # Check if next state is a conditional accessory state
            if self._is_conditional_accessory_state(self.next_accessory_state):
                # Check if parent accessory category has selections
                if not self._has_parent_accessory_selections(self.next_accessory_state, conversation_state):
                    logger.info(
                        f"⏭️  Skipping {self.next_accessory_state} "
                        f"(no parent accessory selections)"
                    )
                    # Skip conditional state by recursively finding next applicable state
                    return self._get_next_non_conditional_state(self.next_accessory_state, conversation_state)

            logger.info(f"Moving to {self.next_accessory_state}")
            return self.next_accessory_state
        else:
            logger.info("All accessories complete, moving to finalize")
            return "finalize"

    def _is_done_with_multi_select(self, conversation_state) -> bool:
        """
        Check if user is done with multi-select for this state.

        Looks for keywords like "done", "next", "skip", "finalize".

        Args:
            conversation_state: Current ConversationState

        Returns:
            True if user is done, False if continuing multi-select
        """
        # Check last user message for completion keywords
        conversation_history = conversation_state.conversation_history
        if not conversation_history:
            return False

        last_message = conversation_history[-1].get("user_message", "").lower()

        completion_keywords = ["done", "next", "skip", "finish", "finalize", "proceed", "continue", "that's all"]

        return any(keyword in last_message for keyword in completion_keywords)

    def _get_component_api_key_from_state(self, state_name: str) -> str:
        """
        Map state name to component API key for applicability lookup.

        Args:
            state_name: State name (e.g., "feeder_accessories_selection")

        Returns:
            Component API key (e.g., "FeederAccessories") for applicability lookup
        """
        state_to_component_map = {
            "powersource_accessories_selection": "PowerSourceAccessories",
            "feeder_accessories_selection": "FeederAccessories",
            "feeder_conditional_accessories": "FeederConditionalAccessories",
            "interconnector_accessories_selection": "InterconnectorAccessories",
            "remote_selection": "Remotes",
            "remote_accessories_selection": "RemoteAccessories",
            "remote_conditional_accessories": "RemoteConditionalAccessories",
            "connectivity_selection": "Connectivity"
        }
        return state_to_component_map.get(state_name, "")

    def _is_conditional_accessory_state(self, state_name: str) -> bool:
        """
        Check if a state is a conditional accessory state.

        Conditional states depend on their parent accessory category having selections:
        - feeder_conditional_accessories → depends on feeder_accessories
        - remote_conditional_accessories → depends on remote_accessories

        Args:
            state_name: State name to check

        Returns:
            True if state is conditional, False otherwise
        """
        conditional_states = [
            "feeder_conditional_accessories",
            "remote_conditional_accessories"
        ]
        return state_name in conditional_states

    def _has_parent_accessory_selections(self, conditional_state: str, conversation_state) -> bool:
        """
        Check if parent accessory category has any selections.

        Mapping:
        - feeder_conditional_accessories → check FeederAccessories
        - remote_conditional_accessories → check RemoteAccessories

        Args:
            conditional_state: Conditional accessory state name
            conversation_state: Current ConversationState

        Returns:
            True if parent has selections, False if empty or skipped
        """
        response_json = conversation_state.response_json

        # Map conditional states to their parent accessory fields
        parent_mapping = {
            "feeder_conditional_accessories": "FeederAccessories",
            "remote_conditional_accessories": "RemoteAccessories"
        }

        parent_field = parent_mapping.get(conditional_state)
        if not parent_field:
            logger.warning(f"Unknown conditional state: {conditional_state}")
            return False

        # Get parent accessory list from ResponseJSON
        parent_accessories = getattr(response_json, parent_field, None)

        # Check if parent has selections
        # Parent can be: List[SelectedProduct], "skipped" literal, or None
        if parent_accessories is None:
            return False
        if parent_accessories == "skipped":
            return False
        if isinstance(parent_accessories, list) and len(parent_accessories) == 0:
            return False

        # Parent has selections
        logger.info(f"Parent {parent_field} has {len(parent_accessories)} selections")
        return True

    def _get_next_applicable_accessory_state(self, current_state: str, conversation_state) -> str:
        """
        Recursively find next applicable accessory state (applicability-based skipping).

        Checks if next state is applicable for selected PowerSource. If not_applicable,
        recursively finds next applicable state.

        Args:
            current_state: Current state being skipped
            conversation_state: Current ConversationState

        Returns:
            Next applicable state name (or "finalize" if no more states)
        """
        # Get configuration
        from app.services.config.configuration_service import get_config_service
        config_service = get_config_service()
        component_types = config_service.get_component_types()

        # Get full state sequence
        full_state_sequence = component_types.get("state_sequence", [])

        # Find current state in sequence
        try:
            current_index = full_state_sequence.index(current_state)
        except ValueError:
            logger.error(f"State {current_state} not found in state_sequence")
            return "finalize"

        # Get next state in sequence
        if current_index + 1 < len(full_state_sequence):
            next_state = full_state_sequence[current_index + 1]
            logger.info(f"Checking next state after skipping {current_state}: {next_state}")

            # Get applicability for next state
            response_json = conversation_state.response_json
            applicability = response_json.applicability.model_dump() if response_json.applicability else {}

            component_key = self._get_component_api_key_from_state(next_state)
            if component_key:
                component_status = applicability.get(component_key)
                # Check if next state is also not applicable (recursive check)
                if component_status not in ["mandatory", "optional", "Y", None]:  # not_applicable or N
                    logger.info(
                        f"⏭️  Next state {next_state} also needs skipping "
                        f"({component_key} applicability: {component_status})"
                    )
                    return self._get_next_applicable_accessory_state(next_state, conversation_state)

            # Also check conditional dependency
            if self._is_conditional_accessory_state(next_state):
                if not self._has_parent_accessory_selections(next_state, conversation_state):
                    logger.info(f"⏭️  Next state {next_state} also needs skipping (no parent selections)")
                    return self._get_next_applicable_accessory_state(next_state, conversation_state)

            logger.info(f"Found applicable state: {next_state}")
            return next_state
        else:
            # No more states, go to finalize
            logger.info("No more states after skipped, moving to finalize")
            return "finalize"

    def _get_next_non_conditional_state(self, current_conditional_state: str, conversation_state) -> str:
        """
        Recursively find next applicable state when skipping a conditional state.

        Args:
            current_conditional_state: Current conditional state being skipped
            conversation_state: Current ConversationState

        Returns:
            Next applicable state name (or "finalize" if no more states)
        """
        # Get the processor for the conditional state we're skipping
        from app.services.config.configuration_service import get_config_service
        config_service = get_config_service()
        component_types = config_service.get_component_types()

        # Get full state sequence
        full_state_sequence = component_types.get("state_sequence", [])

        # Find the conditional state in sequence
        try:
            current_index = full_state_sequence.index(current_conditional_state)
        except ValueError:
            logger.error(f"State {current_conditional_state} not found in state_sequence")
            return "finalize"

        # Get next state in sequence
        if current_index + 1 < len(full_state_sequence):
            next_state = full_state_sequence[current_index + 1]
            logger.info(f"Next state after skipping {current_conditional_state}: {next_state}")

            # Check if the next state is also conditional (recursive check)
            if self._is_conditional_accessory_state(next_state):
                if not self._has_parent_accessory_selections(next_state, conversation_state):
                    logger.info(f"⏭️  Next state {next_state} also needs skipping (no parent selections)")
                    return self._get_next_non_conditional_state(next_state, conversation_state)

            return next_state
        else:
            # No more states, go to finalize
            logger.info("No more states after skipped conditional, moving to finalize")
            return "finalize"

    def is_multi_select(self) -> bool:
        """
        Check if this accessory state allows multi-select.

        Returns:
            True for most accessories (configurable per state)
        """
        return self.multi_select

    def can_skip(self) -> bool:
        """
        All accessory states can be skipped.

        Returns:
            True (accessories are optional)
        """
        return True

    def generate_selection_message(
        self,
        product: Dict[str, Any],
        is_multi_select: bool = False
    ) -> str:
        """
        Generate confirmation message for accessory selection.

        Args:
            product: Selected product dict
            is_multi_select: True if multi-select enabled

        Returns:
            Confirmation message
        """
        product_name = product.get("name", "Unknown")
        gin = product.get("gin", "")

        if is_multi_select:
            return (
                f"✅ Added {product_name} (GIN: {gin}) to {self.get_component_display_name()}\n"
                f"💡 You can select more {self.get_component_display_name()} or say 'done' to proceed."
            )
        else:
            return f"✅ {self.get_component_display_name()}: {product_name} (GIN: {gin}) selected"


# Factory function to create accessory processors with proper sequencing
def create_accessory_processors(state_config_dict: Dict[str, Any], search_orchestrator):
    """
    Create all accessory state processors with proper sequencing (configuration-driven).

    Args:
        state_config_dict: Full state_config.json dict
        search_orchestrator: SearchOrchestrator instance

    Returns:
        Dict of {state_name: AccessoryStateProcessor}
    """
    # Load accessory state sequence from component_types.json (configuration-driven)
    from app.services.config.configuration_service import get_config_service

    config_service = get_config_service()
    component_types = config_service.get_component_types()

    # Get full state sequence from config
    full_state_sequence = component_types.get("state_sequence", [])

    # Filter to get only accessory states (states that come after torch_selection)
    # Find index of torch_selection
    try:
        torch_index = full_state_sequence.index("torch_selection")
        accessory_states = full_state_sequence[torch_index + 1:]  # All states after torch
    except ValueError:
        # Fallback: hardcoded list if torch_selection not found
        logger.warning("torch_selection not found in state_sequence, using hardcoded accessory sequence")
        accessory_states = [
            "powersource_accessories_selection",
            "feeder_accessories_selection",
            "feeder_conditional_accessories",
            "interconnector_accessories_selection",
            "remote_selection",
            "remote_accessories_selection",
            "remote_conditional_accessories",
            "connectivity_selection",
        ]

    logger.info(f"Accessory state sequence from config: {accessory_states}")

    # Build processors with proper next_state linkage
    processors = {}

    for i, state_name in enumerate(accessory_states):
        # Get component type from component_types.json
        component_config = None
        for comp_key, comp_data in component_types.get("component_types", {}).items():
            if comp_data.get("state_name") == state_name:  # Use 'state_name' field, not 'state'
                component_config = comp_data
                component_type = comp_key
                break

        if not component_config:
            logger.warning(f"No component config found for state: {state_name}, skipping")
            continue

        # Get next state in sequence (or None if last)
        next_state = accessory_states[i + 1] if i < len(accessory_states) - 1 else None

        # Get state config
        state_config = state_config_dict.get("states", {}).get(state_name, {})

        # Create processor
        processor = AccessoryStateProcessor(
            state_name=state_name,
            component_type=component_type,
            state_config=state_config,
            search_orchestrator=search_orchestrator,
            next_accessory_state=next_state
        )

        processors[state_name] = processor
        logger.debug(f"Created {state_name} processor → next: {next_state}")

    return processors
