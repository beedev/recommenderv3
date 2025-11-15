"""
Search Orchestrator

Coordinates execution of multiple search strategies:
- Executes strategies in parallel or sequential mode
- Handles strategy failures gracefully with fallback
- Consolidates results using ResultConsolidator
- Returns unified search results
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from langsmith import traceable
from .strategies.base import SearchStrategy, StrategySearchResult
from .consolidator import ResultConsolidator, ConsolidatedResult

logger = logging.getLogger(__name__)


class SearchOrchestrator:
    """
    Orchestrates execution of multiple search strategies.

    Coordinates:
    1. Strategy selection based on configuration
    2. Parallel or sequential execution
    3. Graceful error handling and fallback
    4. Result consolidation with scoring
    5. Zero-results handling with context-aware messages
    """

    def __init__(
        self,
        strategies: List[SearchStrategy],
        consolidator: ResultConsolidator,
        config: Dict[str, Any]
    ):
        """
        Initialize search orchestrator.

        Args:
            strategies: List of enabled search strategies
            consolidator: ResultConsolidator instance
            config: Orchestrator configuration from search_config.json
                Example:
                {
                    "execution_mode": "parallel" | "sequential",
                    "fallback_on_error": true,
                    "require_at_least_one_success": true,
                    "timeout_seconds": 30
                }
        """
        self.strategies = strategies
        self.consolidator = consolidator
        self.config = config
        self.execution_mode = config.get("execution_mode", "parallel")
        self.fallback_on_error = config.get("fallback_on_error", True)
        self.timeout = config.get("timeout_seconds", 30)

        logger.info(
            f"SearchOrchestrator initialized with {len(strategies)} strategies "
            f"(mode: {self.execution_mode})"
        )

    @traceable(name="search_orchestrator", run_type="retriever")
    async def search(
        self,
        component_type: str,
        user_message: str,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Execute search across all enabled strategies and consolidate results.

        Args:
            component_type: Type of component to search
            user_message: Raw user message
            master_parameters: LLM-extracted parameters
            selected_components: Already selected components
            limit: Maximum results to return
            offset: Pagination offset

        Returns:
            Dict with consolidated results, metadata, and zero-results handling
            {
                "products": List[Dict],  # Consolidated and sorted products
                "total_count": int,
                "metadata": {
                    "strategies_executed": List[str],
                    "strategies_succeeded": List[str],
                    "strategies_failed": List[str],
                    "consolidation_report": Dict,
                    "execution_time_ms": float
                },
                "zero_results_message": Optional[str]  # If no products found
            }
        """
        import time
        start_time = time.time()

        try:
            logger.info(
                f"SearchOrchestrator executing search for {component_type} "
                f"(limit={limit}, offset={offset}, mode={self.execution_mode})"
            )

            # Filter enabled strategies
            enabled_strategies = [s for s in self.strategies if s.is_enabled()]

            if not enabled_strategies:
                logger.warning("No enabled search strategies found")
                return self._build_zero_results_response(
                    component_type,
                    selected_components,
                    "No search strategies are currently enabled"
                )

            # Execute strategies
            if self.execution_mode == "parallel":
                strategy_results = await self._execute_parallel(
                    enabled_strategies,
                    component_type,
                    user_message,
                    master_parameters,
                    selected_components,
                    limit,
                    offset
                )
            else:  # sequential
                strategy_results = await self._execute_sequential(
                    enabled_strategies,
                    component_type,
                    user_message,
                    master_parameters,
                    selected_components,
                    limit,
                    offset
                )

            # Check if at least one strategy succeeded
            successful_results = [r for r in strategy_results if r is not None]

            if not successful_results:
                logger.error("All search strategies failed")
                return self._build_zero_results_response(
                    component_type,
                    selected_components,
                    "All search strategies encountered errors"
                )

            # Consolidate results with exact product name boosting
            consolidated = self.consolidator.consolidate(
                [(r.strategy_name, r.products, r.scores) for r in successful_results],
                master_parameters=master_parameters,
                component_type=component_type
            )

            # Apply pagination to consolidated results
            total_count = len(consolidated)
            paginated_results = consolidated[offset:offset + limit]

            # Build response
            execution_time_ms = (time.time() - start_time) * 1000

            # Check for zero results
            if not paginated_results:
                return self._build_zero_results_response(
                    component_type,
                    selected_components,
                    None,  # Will generate context-aware message
                    execution_time_ms=execution_time_ms,
                    strategies_executed=[s.strategy_name for s in successful_results]
                )

            # Generate consolidation report
            consolidation_report = self.consolidator.get_strategy_coverage_report(consolidated)

            response = {
                "products": [r.to_dict() for r in paginated_results],
                "total_count": total_count,
                "offset": offset,
                "limit": limit,
                "has_more": (offset + limit) < total_count,
                "metadata": {
                    "strategies_executed": [s.get_name() for s in enabled_strategies],
                    "strategies_succeeded": [r.strategy_name for r in successful_results],
                    "strategies_failed": [
                        s.get_name() for s in enabled_strategies
                        if s.get_name() not in [r.strategy_name for r in successful_results]
                    ],
                    "consolidation_report": consolidation_report,
                    "execution_time_ms": execution_time_ms,
                    "execution_mode": self.execution_mode
                }
            }

            logger.info(
                f"SearchOrchestrator completed: {total_count} products "
                f"in {execution_time_ms:.2f}ms"
            )

            return response

        except Exception as e:
            logger.error(f"SearchOrchestrator error: {e}", exc_info=True)
            return self._build_zero_results_response(
                component_type,
                selected_components,
                f"Search orchestration failed: {str(e)}"
            )

    async def _execute_parallel(
        self,
        strategies: List[SearchStrategy],
        component_type: str,
        user_message: str,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: int,
        offset: int
    ) -> List[Optional[StrategySearchResult]]:
        """Execute strategies in parallel"""
        try:
            tasks = [
                asyncio.wait_for(
                    strategy.search(
                        component_type,
                        user_message,
                        master_parameters,
                        selected_components,
                        limit,
                        offset
                    ),
                    timeout=self.timeout
                )
                for strategy in strategies
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Convert exceptions to None if fallback is enabled
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Strategy {strategies[i].get_name()} failed: {result}",
                        exc_info=result
                    )
                    if self.fallback_on_error:
                        processed_results.append(None)
                    else:
                        raise result
                else:
                    processed_results.append(result)

            return processed_results

        except Exception as e:
            logger.error(f"Parallel execution error: {e}", exc_info=True)
            if self.fallback_on_error:
                return [None] * len(strategies)
            raise

    async def _execute_sequential(
        self,
        strategies: List[SearchStrategy],
        component_type: str,
        user_message: str,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: int,
        offset: int
    ) -> List[Optional[StrategySearchResult]]:
        """Execute strategies sequentially"""
        results = []

        for strategy in strategies:
            try:
                result = await asyncio.wait_for(
                    strategy.search(
                        component_type,
                        user_message,
                        master_parameters,
                        selected_components,
                        limit,
                        offset
                    ),
                    timeout=self.timeout
                )
                results.append(result)

            except Exception as e:
                logger.error(f"Strategy {strategy.get_name()} failed: {e}", exc_info=True)
                if self.fallback_on_error:
                    results.append(None)
                else:
                    raise

        return results

    def _build_zero_results_response(
        self,
        component_type: str,
        selected_components: Dict[str, Any],
        error_message: Optional[str] = None,
        execution_time_ms: Optional[float] = None,
        strategies_executed: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Build response for zero results with context-aware helpful message.

        Args:
            component_type: Component type being searched
            selected_components: Already selected components
            error_message: Optional error message (if strategies failed)
            execution_time_ms: Optional execution time
            strategies_executed: Optional list of strategies that ran

        Returns:
            Response dict with zero_results_message
        """
        # Generate context-aware message
        if error_message:
            message = error_message
        else:
            message = self._generate_zero_results_message(
                component_type,
                selected_components
            )

        return {
            "products": [],
            "total_count": 0,
            "offset": 0,
            "limit": 0,
            "has_more": False,
            "zero_results_message": message,
            "metadata": {
                "strategies_executed": strategies_executed or [],
                "strategies_succeeded": [],
                "strategies_failed": strategies_executed or [],
                "execution_time_ms": execution_time_ms,
                "execution_mode": self.execution_mode
            }
        }

    def _generate_zero_results_message(
        self,
        component_type: str,
        selected_components: Dict[str, Any]
    ) -> str:
        """
        Generate context-aware helpful message for zero results.

        Args:
            component_type: Component type being searched
            selected_components: Already selected components

        Returns:
            Helpful message explaining why no results and suggesting next steps
        """
        component_type_lower = component_type.lower().replace("_", " ")

        # Check what components are already selected
        selected_names = []
        if "PowerSource" in selected_components and selected_components["PowerSource"]:
            ps = selected_components["PowerSource"]
            ps_name = ps.get("name") if isinstance(ps, dict) else getattr(ps, "name", "Unknown")
            selected_names.append(f"PowerSource: {ps_name}")

        if "Feeder" in selected_components and selected_components["Feeder"]:
            feeder = selected_components["Feeder"]
            feeder_name = feeder.get("name") if isinstance(feeder, dict) else getattr(feeder, "name", "Unknown")
            selected_names.append(f"Feeder: {feeder_name}")

        # Build context-aware message
        if component_type_lower == "powersource" or component_type_lower == "power source":
            return (
                f"No power sources found matching your requirements. "
                f"Try different specifications (e.g., different current rating, process type) "
                f"or browse all available power sources."
            )

        elif selected_names:
            selected_str = ", ".join(selected_names)
            return (
                f"No {component_type_lower} products found compatible with your selected components "
                f"({selected_str}). "
                f"You can skip this component or try selecting different components."
            )

        else:
            return (
                f"No {component_type_lower} products found. "
                f"Try different search terms or skip this component."
            )
