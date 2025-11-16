"""
Cypher Search Strategy

Wraps existing Neo4j Cypher-based product search.
Uses graph database compatibility relationships for filtering.
"""

import logging
from typing import Dict, Any, Optional
from .base import SearchStrategy, StrategySearchResult

logger = logging.getLogger(__name__)


class CypherSearchStrategy(SearchStrategy):
    """
    Neo4j Cypher-based search strategy.

    Uses graph database COMPATIBLE_WITH relationships to filter products.
    Applies LLM-extracted parameters as Cypher WHERE clauses.

    Delegates to ComponentSearchService.search() for all searches.
    All component types use the generic search() method with configuration-driven logic.
    """

    def __init__(self, config: Dict[str, Any], neo4j_product_search):
        """
        Initialize Cypher strategy with Neo4j product search service.

        Args:
            config: Strategy configuration from search_config.json
            neo4j_product_search: Instance of Neo4jProductSearch
        """
        super().__init__(config)
        self.product_search = neo4j_product_search

        # Priority-to-score conversion parameters
        self.max_priority = config.get("max_priority", 20)
        self.min_score = config.get("min_score", 0.1)
        self.default_priority = config.get("default_priority", 1)

        logger.info(
            f"CypherSearchStrategy initialized (weight: {self.weight}, "
            f"max_priority: {self.max_priority}, min_score: {self.min_score})"
        )

    async def search(
        self,
        component_type: str,
        user_message: str,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> StrategySearchResult:
        """
        Execute Cypher-based search for specified component type.

        Args:
            component_type: Type of component (PowerSource, Feeder, Cooler, etc.)
            user_message: Raw user message (not used for Cypher, uses master_parameters)
            master_parameters: LLM-extracted parameters (MasterParameterJSON)
            selected_components: Already selected components (ResponseJSON)
            limit: Maximum results to return
            offset: Pagination offset

        Returns:
            StrategySearchResult with products from Cypher query
        """
        try:
            logger.info(f"CypherSearchStrategy searching {component_type} (limit={limit}, offset={offset})")

            # Map component_type to component_types.json key
            component_key = self._get_component_key(component_type)

            # Execute Cypher search using ComponentSearchService
            search_results = await self.product_search.component_service.search(
                component_type=component_key,
                master_parameters=master_parameters,
                selected_components=selected_components,
                limit=limit,
                offset=offset
            )

            # Convert SearchResults to StrategySearchResult with scoring
            products = []
            scores = {}

            for p in search_results.products:
                # Convert priority to confidence score
                score = self._priority_to_score(p.priority)
                scores[p.gin] = score

                products.append({
                    "gin": p.gin,
                    "name": p.name,
                    "category": p.category,
                    "description": p.description,
                    "specifications": p.specifications
                })

            logger.info(
                f"CypherSearchStrategy found {len(products)} products for {component_type} "
                f"with scores (avg: {sum(scores.values())/len(scores) if scores else 0:.2f})"
            )

            return StrategySearchResult(
                products=products,
                scores=scores,  # Now includes priority-based confidence scores
                metadata={
                    "search_method": "cypher",
                    "component_type": component_type,
                    "total_count": search_results.total_count,
                    "filters_applied": search_results.filters_applied,
                    "compatibility_validated": search_results.compatibility_validated,
                    "has_more": search_results.has_more,
                    "scoring": {
                        "method": "priority_normalized_linear",
                        "max_priority": self.max_priority,
                        "min_score": self.min_score
                    }
                },
                strategy_name="cypher"
            )

        except Exception as e:
            logger.error(f"CypherSearchStrategy error for {component_type}: {e}", exc_info=True)
            return StrategySearchResult(
                products=[],
                scores=None,
                metadata={
                    "search_method": "cypher",
                    "component_type": component_type,
                    "error": str(e)
                },
                strategy_name="cypher"
            )

    async def validate_compatibility(
        self,
        product_gin: str,
        selected_components: Dict[str, Any]
    ) -> bool:
        """
        Validate product compatibility using Neo4j relationships.

        Args:
            product_gin: GIN of product to validate
            selected_components: Already selected components (ResponseJSON)

        Returns:
            True if compatible, False otherwise
        """
        try:
            # Delegate to Neo4jProductSearch validation methods
            # This would call the existing compatibility validation logic
            # For now, return True as validation happens during search
            return True

        except Exception as e:
            logger.error(f"CypherSearchStrategy compatibility validation error: {e}")
            return False

    def _get_component_key(self, component_type: str) -> str:
        """
        Map component type to component_types.json key.

        Args:
            component_type: Component type string

        Returns:
            Component key for component_types.json
        """
        # Normalize to component_types.json keys
        key_map = {
            "powersource": "power_source",
            "power_source": "power_source",
            "feeder": "feeder",
            "cooler": "cooler",
            "interconnector": "interconnector",
            "torch": "torch",
            "remote": "remote",
            "connectivity": "connectivity",
            "powersource_accessories": "powersource_accessories",
            "feeder_accessories": "feeder_accessories",
            "feeder_conditional_accessories": "feeder_conditional_accessories",
            "interconnector_accessories": "interconnector_accessories",
            "remote_accessories": "remote_accessories",
            "remote_conditional_accessories": "remote_conditional_accessories"
        }

        component_type_lower = component_type.lower().replace(" ", "_")
        return key_map.get(component_type_lower, component_type_lower)

    def _priority_to_score(self, priority: Optional[int]) -> float:
        """
        Convert Neo4j relationship priority to normalized confidence score.

        Uses Normalized Linear Scoring:
        - priority=1 → score=1.00 (perfect match)
        - priority=5 → score=0.79 (very good)
        - priority=10 → score=0.53 (moderate)
        - priority=20 → score=0.10 (minimum)

        Args:
            priority: Priority value from COMPATIBLE_WITH relationship (lower = better)
                     None for PowerSource (no relationships)

        Returns:
            Confidence score between min_score and 1.0
        """
        if priority is None:
            # PowerSource has no priority (first component, no relationships)
            # Assign default priority
            priority = self.default_priority

        # Cap at max_priority to avoid negative scores
        if priority > self.max_priority:
            return self.min_score

        # Normalized Linear: score = max(min_score, 1.0 - (priority - 1) / (max_priority - 1))
        normalized_score = 1.0 - (priority - 1) / (self.max_priority - 1)
        return max(self.min_score, normalized_score)
