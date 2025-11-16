"""
Feeder State Processor

S2: Feeder selection with PowerSource compatibility.
"""

import logging
from typing import Dict, Any, Optional
from langsmith import traceable
from .base import StateProcessor

logger = logging.getLogger(__name__)


class FeederStateProcessor(StateProcessor):
    """
    Feeder state processor (S2).

    Characteristics:
    - Optional (can be skipped if not applicable)
    - Depends on PowerSource compatibility
    - Single-select only
    - Proactive display enabled (shows Cooler preview after selection)
    """

    @traceable(name="search_products_feeder", run_type="retriever")
    async def search_products(
        self,
        user_message: str,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: Optional[int] = None,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Search for feeders compatible with selected PowerSource.

        Validates PowerSource is selected before searching.

        Args:
            user_message: Raw user message for Lucene search
            master_parameters: LLM-extracted parameters for Cypher search
            selected_components: Must contain PowerSource
            limit: Max results (default from state_config: 10)
            offset: Pagination offset

        Returns:
            Consolidated search results from multiple strategies
        """
        try:
            search_limit = self._get_search_limit(limit)

            # Validate PowerSource selected
            # Convert Pydantic model to dict if needed
            selected_dict = selected_components.model_dump() if hasattr(selected_components, 'model_dump') else selected_components
            if not selected_dict.get("PowerSource"):
                logger.error("FeederStateProcessor: PowerSource not selected")
                return {
                    "products": [],
                    "total_count": 0,
                    "offset": offset,
                    "limit": search_limit,
                    "has_more": False,
                    "zero_results_message": (
                        "Cannot search for feeders without a selected power source. "
                        "Please select a power source first."
                    ),
                    "metadata": {"error": "PowerSource not selected"}
                }

            logger.info(
                f"FeederStateProcessor searching "
                f"(limit={search_limit}, offset={offset})"
            )

            # Execute search via SearchOrchestrator
            results = await self.search_orchestrator.search(
                component_type="Feeder",
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
            logger.error(f"FeederStateProcessor search error: {e}", exc_info=True)
            return {
                "products": [],
                "total_count": 0,
                "offset": offset,
                "limit": search_limit,
                "has_more": False,
                "zero_results_message": f"Error searching for feeders: {str(e)}",
                "metadata": {"error": str(e)}
            }

    def get_next_state(
        self,
        conversation_state,
        selection_made: bool = False
    ) -> str:
        """
        Determine next state after feeder selection/skip.

        Logic:
        - If selection made or skipped: Check applicability for Cooler
        - If no selection and not skipped: Stay in feeder_selection

        Args:
            conversation_state: Current ConversationState
            selection_made: True if feeder was selected or skipped

        Returns:
            Next state name
        """
        if not selection_made:
            return "feeder_selection"

        response_json = conversation_state.response_json
        # Convert Pydantic model to dict for .get() access
        applicability = response_json.applicability.model_dump() if response_json.applicability else {}

        # Check if Cooler is applicable (mandatory or optional)
        cooler_status = applicability.get("Cooler")
        if cooler_status in ["mandatory", "optional", "Y"]:
            logger.info(f"Next state: cooler_selection (Cooler status: {cooler_status})")
            return "cooler_selection"

        # Cooler not applicable, check Interconnector
        interconnector_status = applicability.get("Interconnector")
        if interconnector_status in ["mandatory", "optional", "Y"]:
            logger.info(f"Next state: interconnector_selection (Cooler skipped, Interconnector status: {interconnector_status})")
            return "interconnector_selection"

        # Interconnector not applicable, check Torch
        torch_status = applicability.get("Torch")
        if torch_status in ["mandatory", "optional", "Y"]:
            logger.info(f"Next state: torch_selection (Torch status: {torch_status})")
            return "torch_selection"

        # No more primary components, go to accessories
        logger.info("Next state: powersource_accessories_selection")
        return "powersource_accessories_selection"
