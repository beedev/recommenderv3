"""
Lucene Search Strategy

Wraps existing Lucene full-text search.
Uses relevance scoring for ranking products.
"""

import logging
from typing import Dict, Any, Optional
from .base import SearchStrategy, StrategySearchResult

logger = logging.getLogger(__name__)


class LuceneSearchStrategy(SearchStrategy):
    """
    Lucene full-text search strategy.

    Uses Neo4j Lucene indexes for relevance-based product search.
    Returns products with relevance scores (0.0-1.0).

    Delegates to ComponentSearchService.search_with_lucene() for all searches.
    All component types use the generic search_with_lucene() method.
    """

    def __init__(self, config: Dict[str, Any], neo4j_product_search):
        """
        Initialize Lucene strategy with Neo4j product search service.

        Args:
            config: Strategy configuration from search_config.json
            neo4j_product_search: Instance of Neo4jProductSearch
        """
        super().__init__(config)
        self.product_search = neo4j_product_search
        self.min_score = config.get("min_score", 0.5)
        logger.info(f"LuceneSearchStrategy initialized (weight: {self.weight}, min_score: {self.min_score})")

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
        Execute Lucene full-text search for specified component type.

        Args:
            component_type: Type of component (PowerSource, Feeder, Cooler, etc.)
            user_message: Raw user message for full-text search
            master_parameters: LLM-extracted parameters (for additional filtering)
            selected_components: Already selected components (for compatibility)
            limit: Maximum results to return
            offset: Pagination offset

        Returns:
            StrategySearchResult with products and Lucene relevance scores
        """
        try:
            logger.info(f"LuceneSearchStrategy searching {component_type} (limit={limit}, offset={offset})")

            if not user_message or not user_message.strip():
                logger.warning("LuceneSearchStrategy requires user_message")
                return StrategySearchResult(
                    products=[],
                    scores={},
                    metadata={
                        "search_method": "lucene",
                        "component_type": component_type,
                        "error": "No user message provided"
                    },
                    strategy_name="lucene"
                )

            # Map component_type to component_types.json key
            component_key = self._get_component_key(component_type)

            # Execute Lucene search using ComponentSearchService
            search_results = await self.product_search.component_service.search_with_lucene(
                component_type=component_key,
                user_message=user_message,
                selected_components=selected_components,
                limit=limit,
                offset=offset
            )

            # Convert SearchResults to StrategySearchResult
            products = []
            scores = {}

            for i, p in enumerate(search_results.products, 1):
                # Extract Lucene score if present (appended to name or in specifications)
                score = self._extract_lucene_score(p)

                # DEBUG: Log specifications from first product
                if i == 1:
                    logger.debug(f"[Lucene Debug] First product specifications type: {type(p.specifications)}")
                    if p.specifications:
                        logger.debug(f"[Lucene Debug] Specifications keys: {list(p.specifications.keys())[:15] if isinstance(p.specifications, dict) else 'Not a dict'}")
                        logger.debug(f"[Lucene Debug] Has competitor_brand_product_pairs: {'competitor_brand_product_pairs' in p.specifications if isinstance(p.specifications, dict) else False}")
                    else:
                        logger.debug(f"[Lucene Debug] Specifications is None or empty")

                products.append({
                    "gin": p.gin,
                    "name": p.name,
                    "category": p.category,
                    "description": p.description,
                    "specifications": p.specifications
                })

                if score is not None:
                    scores[p.gin] = score

            logger.info(f"LuceneSearchStrategy found {len(products)} products for {component_type}")

            return StrategySearchResult(
                products=products,
                scores=scores if scores else None,
                metadata={
                    "search_method": "lucene",
                    "component_type": component_type,
                    "total_count": search_results.total_count,
                    "min_score": self.min_score,
                    "filters_applied": search_results.filters_applied,
                    "compatibility_validated": search_results.compatibility_validated
                },
                strategy_name="lucene"
            )

        except Exception as e:
            logger.error(f"LuceneSearchStrategy error for {component_type}: {e}", exc_info=True)
            return StrategySearchResult(
                products=[],
                scores={},
                metadata={
                    "search_method": "lucene",
                    "component_type": component_type,
                    "error": str(e)
                },
                strategy_name="lucene"
            )

    async def validate_compatibility(
        self,
        product_gin: str,
        selected_components: Dict[str, Any]
    ) -> bool:
        """
        Validate product compatibility (Lucene doesn't enforce compatibility during search).

        Args:
            product_gin: GIN of product to validate
            selected_components: Already selected components (ResponseJSON)

        Returns:
            True (Lucene returns all matches, compatibility validation happens elsewhere)
        """
        # Lucene search returns all textual matches
        # Compatibility validation happens during consolidation or in Cypher strategy
        return True

    def _get_component_key(self, component_type: str) -> str:
        """
        Map component type to search_config.json key.

        Args:
            component_type: Component type string

        Returns:
            Component key for search_config.json
        """
        # Normalize to search_config.json keys
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

    def _build_compatibility_filter(
        self,
        component_type: str,
        selected_components: Dict[str, Any]
    ) -> Optional[Dict[str, str]]:
        """
        Build compatibility filter from selected components.

        Args:
            component_type: Current component being searched
            selected_components: Already selected components (ResponseJSON)

        Returns:
            Compatibility filter dict or None
        """
        compatibility_filter = {}

        # PowerSource has no dependencies
        if component_type.lower() in ["powersource", "power_source"]:
            return None

        # Add selected PowerSource if exists
        if "PowerSource" in selected_components and selected_components["PowerSource"]:
            ps = selected_components["PowerSource"]
            if isinstance(ps, dict):
                compatibility_filter["power_source_gin"] = ps.get("gin")
            else:
                compatibility_filter["power_source_gin"] = getattr(ps, "gin", None)

        # Add selected Feeder if exists (for downstream components)
        if component_type.lower() not in ["feeder"]:
            if "Feeder" in selected_components and selected_components["Feeder"]:
                feeder = selected_components["Feeder"]
                if isinstance(feeder, dict):
                    compatibility_filter["feeder_gin"] = feeder.get("gin")
                else:
                    compatibility_filter["feeder_gin"] = getattr(feeder, "gin", None)

        # Add selected Cooler if exists (for Interconnector)
        if component_type.lower() in ["interconnector"]:
            if "Cooler" in selected_components and selected_components["Cooler"]:
                cooler = selected_components["Cooler"]
                if isinstance(cooler, dict):
                    compatibility_filter["cooler_gin"] = cooler.get("gin")
                else:
                    compatibility_filter["cooler_gin"] = getattr(cooler, "gin", None)

        return compatibility_filter if compatibility_filter else None

    def _extract_lucene_score(self, product) -> Optional[float]:
        """
        Extract Lucene relevance score from product.

        Score may be appended to name (e.g., "Product Name (0.85)")
        or stored in specifications.

        Args:
            product: ProductResult object

        Returns:
            Lucene score (0.0-1.0) or None
        """
        try:
            # Check if score is in specifications
            if hasattr(product, "specifications") and product.specifications:
                if "lucene_score" in product.specifications:
                    return float(product.specifications["lucene_score"])

            # Check if score is appended to name
            if hasattr(product, "name") and product.name:
                import re
                match = re.search(r'\((\d+\.\d+)\)$', product.name)
                if match:
                    return float(match.group(1))

            return None

        except Exception as e:
            logger.warning(f"Could not extract Lucene score: {e}")
            return None
