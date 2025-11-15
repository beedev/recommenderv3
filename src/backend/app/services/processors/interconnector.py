"""
Interconnector State Processor

S4: Interconnector selection with triple compatibility (PowerSource, Feeder, Cooler).
"""

import logging
from typing import Dict, Any, Optional
from langsmith import traceable
from .base import StateProcessor

logger = logging.getLogger(__name__)


class InterconnectorStateProcessor(StateProcessor):
    """Interconnector state processor (S4) - triple compatibility check"""

    @traceable(name="search_products_interconnector", run_type="retriever")
    async def search_products(
        self,
        user_message: str,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: Optional[int] = None,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Search for interconnectors compatible with PowerSource, Feeder, Cooler"""
        try:
            search_limit = self._get_search_limit(limit)

            results = await self.search_orchestrator.search(
                component_type="Interconnector",
                user_message=user_message,
                master_parameters=master_parameters,
                selected_components=selected_components,
                limit=search_limit,
                offset=offset
            )

            if "metadata" in results and "execution_time_ms" in results["metadata"]:
                self._log_search(results["total_count"], results["metadata"]["execution_time_ms"])

            return results

        except Exception as e:
            logger.error(f"InterconnectorStateProcessor search error: {e}", exc_info=True)
            return {"products": [], "total_count": 0, "offset": offset, "limit": search_limit,
                    "has_more": False, "zero_results_message": f"Error searching for interconnectors: {str(e)}",
                    "metadata": {"error": str(e)}}

    def get_next_state(self, conversation_state, selection_made: bool = False) -> str:
        """Determine next state after interconnector selection/skip"""
        if not selection_made:
            return "interconnector_selection"

        response_json = conversation_state.response_json
        applicability = response_json.get("applicability", {})

        if applicability.get("Torch") == "Y":
            return "torch_selection"
        return "powersource_accessories_selection"
