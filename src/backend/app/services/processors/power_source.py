"""
Power Source State Processor

S1: Mandatory first state - power source selection.
No compatibility dependencies (first component in flow).
"""

import logging
from typing import Dict, Any, Optional
from langsmith import traceable
from .base import StateProcessor

logger = logging.getLogger(__name__)


class PowerSourceStateProcessor(StateProcessor):
    """
    Power Source state processor (S1).

    Characteristics:
    - Mandatory (must select before proceeding to finalize)
    - No compatibility dependencies (first component)
    - Single-select only
    - Proactive display enabled (shows Feeder preview after selection)
    - Cannot be skipped
    """

    @traceable(name="search_products_power_source", run_type="retriever")
    async def search_products(
        self,
        user_message: str,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: Optional[int] = None,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Search for power sources based on user requirements.

        No compatibility checks (first component in flow).
        Uses both Cypher (parameter-based) and Lucene (text-based) strategies.

        Args:
            user_message: Raw user message for Lucene search
            master_parameters: LLM-extracted parameters for Cypher search
            selected_components: Not used (no dependencies)
            limit: Max results (default from state_config: 10)
            offset: Pagination offset

        Returns:
            Consolidated search results from multiple strategies
        """
        try:
            search_limit = self._get_search_limit(limit)

            logger.info(
                f"PowerSourceStateProcessor searching "
                f"(limit={search_limit}, offset={offset})"
            )

            # Execute search via SearchOrchestrator
            # Both Cypher and Lucene strategies will run
            results = await self.search_orchestrator.search(
                component_type="PowerSource",
                user_message=user_message,
                master_parameters=master_parameters,
                selected_components=selected_components,  # Empty for S1
                limit=search_limit,
                offset=offset
            )

            # Log execution
            if "metadata" in results and "execution_time_ms" in results["metadata"]:
                self._log_search(
                    results["total_count"],
                    results["metadata"]["execution_time_ms"]
                )

            return results

        except Exception as e:
            logger.error(f"PowerSourceStateProcessor search error: {e}", exc_info=True)
            return {
                "products": [],
                "total_count": 0,
                "offset": offset,
                "limit": search_limit,
                "has_more": False,
                "zero_results_message": (
                    f"Error searching for power sources: {str(e)}. "
                    f"Please try again or contact support."
                ),
                "metadata": {"error": str(e)}
            }

    def get_next_state(
        self,
        conversation_state,
        selection_made: bool = False
    ) -> str:
        """
        Determine next state after power source selection.

        Logic:
        - If selection made: Check applicability for Feeder
          - If Feeder applicable (Y): → feeder_selection
          - If Feeder not applicable (N): Skip to Cooler (or next applicable component)
        - If no selection (error case): Stay in power_source_selection

        Args:
            conversation_state: Current ConversationState
            selection_made: True if power source was selected

        Returns:
            Next state name
        """
        if not selection_made:
            # Error case: No selection made (shouldn't happen - power source is mandatory)
            logger.warning("PowerSourceStateProcessor: No selection made (mandatory state)")
            return "power_source_selection"

        # Get applicability from response_json
        response_json = conversation_state.response_json
        # Convert Pydantic model to dict for .get() access
        applicability = response_json.applicability.model_dump() if response_json.applicability else {}

        # Check if Feeder is applicable (mandatory or optional)
        feeder_status = applicability.get("Feeder")
        if feeder_status in ["mandatory", "optional", "Y"]:
            logger.info(f"Next state: feeder_selection (Feeder status: {feeder_status})")
            return "feeder_selection"

        # Feeder not applicable, check Cooler
        cooler_status = applicability.get("Cooler")
        if cooler_status in ["mandatory", "optional", "Y"]:
            logger.info(f"Next state: cooler_selection (Feeder skipped, Cooler status: {cooler_status})")
            return "cooler_selection"

        # Cooler not applicable, check Interconnector
        interconnector_status = applicability.get("Interconnector")
        if interconnector_status in ["mandatory", "optional", "Y"]:
            logger.info(f"Next state: interconnector_selection (Feeder, Cooler skipped, Interconnector status: {interconnector_status})")
            return "interconnector_selection"

        # Interconnector not applicable, check Torch
        torch_status = applicability.get("Torch")
        if torch_status in ["mandatory", "optional", "Y"]:
            logger.info(f"Next state: torch_selection (primary components skipped, Torch status: {torch_status})")
            return "torch_selection"

        # No primary components applicable, go to accessories
        logger.info("Next state: powersource_accessories_selection (all primary skipped)")
        return "powersource_accessories_selection"

    def validate_selection(
        self,
        product_gin: str,
        product_data: Dict[str, Any],
        selected_components: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Validate power source selection.

        Power source has no dependencies, so all selections are valid.

        Args:
            product_gin: GIN of power source being selected
            product_data: Power source product data
            selected_components: Not used (no dependencies)

        Returns:
            (True, None) - all power sources are valid
        """
        # Power source is first component - no validation needed
        return True, None

    def can_skip(self) -> bool:
        """
        Power source cannot be skipped (mandatory).

        Returns:
            False (power source is mandatory)
        """
        return False

    def is_multi_select(self) -> bool:
        """
        Power source is single-select only.

        Returns:
            False (single-select)
        """
        return False
