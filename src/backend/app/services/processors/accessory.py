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
