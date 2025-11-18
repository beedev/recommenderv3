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

    # get_next_state() now inherited from base class (delegates to StateManager)
    # This ensures consistency with the centralized state transition logic
