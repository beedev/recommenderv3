"""
Cooler State Processor

S3: Cooler selection with Feeder compatibility.
"""

import logging
from typing import Dict, Any, Optional
from langsmith import traceable
from .base import StateProcessor

logger = logging.getLogger(__name__)


class CoolerStateProcessor(StateProcessor):
    """Cooler state processor (S3) - depends on Feeder compatibility"""

    @traceable(name="search_products_cooler", run_type="retriever")
    async def search_products(
        self,
        user_message: str,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: Optional[int] = None,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Search for coolers compatible with selected Feeder"""
        try:
            search_limit = self._get_search_limit(limit)

            results = await self.search_orchestrator.search(
                component_type="Cooler",
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
            logger.error(f"CoolerStateProcessor search error: {e}", exc_info=True)
            return {"products": [], "total_count": 0, "offset": offset, "limit": search_limit,
                    "has_more": False, "zero_results_message": f"Error searching for coolers: {str(e)}",
                    "metadata": {"error": str(e)}}

    def get_next_state(self, conversation_state, selection_made: bool = False) -> str:
        """Determine next state after cooler selection/skip"""
        if not selection_made:
            return "cooler_selection"

        response_json = conversation_state.response_json
        # Convert Pydantic model to dict for .get() access
        applicability = response_json.applicability.model_dump() if response_json.applicability else {}

        # Check if Interconnector is applicable (mandatory or optional)
        interconnector_status = applicability.get("Interconnector")
        if interconnector_status in ["mandatory", "optional", "Y"]:
            logger.info(f"Next state: interconnector_selection (Interconnector status: {interconnector_status})")
            return "interconnector_selection"

        # Check if Torch is applicable (mandatory or optional)
        torch_status = applicability.get("Torch")
        if torch_status in ["mandatory", "optional", "Y"]:
            logger.info(f"Next state: torch_selection (Torch status: {torch_status})")
            return "torch_selection"

        logger.info("Next state: powersource_accessories_selection")
        return "powersource_accessories_selection"
