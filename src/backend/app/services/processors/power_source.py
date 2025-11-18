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

    # get_next_state() now inherited from base class (delegates to StateManager)
    # This ensures consistency with the centralized state transition logic

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
