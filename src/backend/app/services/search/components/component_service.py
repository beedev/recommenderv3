"""
Component Search Service

Generic, configuration-driven product search service that eliminates code duplication
across component types. Provides unified search logic for all components using
Neo4jQueryBuilder for query construction.

Architecture:
- Configuration-driven via component_config.json (loaded from app/config/)
- Generic search logic that works for all component types
- Supports both Cypher and Lucene search strategies
- Handles GIN direct lookups, product name matching, and feature-based filtering
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from neo4j import AsyncGraphDatabase

from app.models.product_search import ProductResult, SearchResults
from app.config.schema_loader import load_component_config
from .query_builder import Neo4jQueryBuilder

logger = logging.getLogger(__name__)


class ComponentSearchService:
    """
    Generic component search service for all product types.

    Responsibilities:
    - Execute Cypher-based searches using Neo4jQueryBuilder
    - Execute Lucene full-text searches
    - Handle GIN direct lookups
    - Handle product name matching
    - Parse and return search results

    Used by both CypherStrategy and LuceneStrategy.
    """

    def __init__(self, driver: AsyncGraphDatabase.driver):
        """
        Initialize component search service.

        Args:
            driver: Neo4j async driver instance
        """
        self.driver = driver

        # Load component configuration from centralized config directory
        self.component_config = load_component_config()

        # Initialize query builder
        self.query_builder = Neo4jQueryBuilder(self.component_config)

        logger.info(f"ComponentSearchService initialized with {len(self.component_config)} component types")

    async def search(
        self,
        component_type: str,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> SearchResults:
        """
        Generic component search using Cypher queries.

        This is the primary search method used by CypherStrategy.

        Flow:
        1. Check for GIN in component parameters → direct lookup
        2. Check for product_name → name-based search
        3. Build search terms from component parameters
        4. Execute search with fallback logic

        Args:
            component_type: Type of component (e.g., "power_source", "feeder")
            master_parameters: MasterParameterJSON dict
            selected_components: ResponseJSON dict (already selected components)
            limit: Maximum results to return
            offset: Pagination offset

        Returns:
            SearchResults with products, filters_applied, and pagination metadata
        """
        # Get component parameters
        config = self.component_config.get(component_type)
        if not config:
            raise ValueError(f"Unknown component type: {component_type}")

        master_param_key = config["master_param_key"]
        # Convert Pydantic model to dict if needed
        master_params_dict = master_parameters.model_dump() if hasattr(master_parameters, 'model_dump') else master_parameters
        component_dict = master_params_dict.get(master_param_key, {})

        # STEP 1: Check for GIN direct lookup
        detected_gin = component_dict.get("_detected_gin")
        if detected_gin:
            logger.info(f"Using GIN-based search for {component_type}: {detected_gin}")
            product = await self._search_by_gin_direct(detected_gin, config["category"])
            if product:
                return SearchResults(
                    products=[product],
                    total_count=1,
                    filters_applied={
                        "search_method": "gin_direct",
                        "gin": detected_gin
                    },
                    compatibility_validated=config.get("requires_compatibility", False),
                    offset=offset,
                    limit=limit,
                    has_more=False
                )

        # STEP 2: Check for product name → name-based search
        product_name = component_dict.get("product_name")
        if product_name and isinstance(product_name, str) and product_name.strip():
            logger.info(f"Product name provided for {component_type}: {product_name}")

            # Build name-based query
            query, params = self.query_builder.build_base_query(component_type, "p")

            # Add product name filter (SPACE-INSENSITIVE - Nov 15, 2024)
            # Removes all spaces before comparison to handle "Renegade ES 300i" vs "Renegade ES300i"
            query += f"\nAND replace(toLower(p.item_name), ' ', '') CONTAINS replace(toLower($product_name), ' ', '')"
            params["product_name"] = product_name.strip()

            logger.info(f"Added SPACE-INSENSITIVE product_name filter: '{product_name}'")

            # Add compatibility filters if needed
            if config.get("requires_compatibility"):
                query, params = self.query_builder.add_compatibility_filters(
                    query, params, component_type, selected_components, "p"
                )

            # Add ordering and pagination
            query = self.query_builder.add_priority_ordering(query, "p", "r")
            query += f"\nSKIP $offset LIMIT $limit"
            params["offset"] = offset
            params["limit"] = limit + 1  # Query one extra to check has_more

            # Add RETURN clause
            query += self.query_builder.build_return_clause("p", include_score=False)

            # Execute name-based search
            products = await self._execute_search(query, params)

            if products:
                has_more = len(products) > limit
                if has_more:
                    products = products[:limit]

                return SearchResults(
                    products=products,
                    total_count=len(products),
                    filters_applied={
                        "search_method": "name_based",
                        "product_name": product_name
                    },
                    compatibility_validated=config.get("requires_compatibility", False),
                    offset=offset,
                    limit=limit,
                    has_more=has_more
                )

        # STEP 3: Build search terms from component parameters
        search_terms_dict = self.query_builder.build_search_terms_from_component(
            component_dict, component_type
        )

        # STEP 4: Build primary query WITH search term filters
        primary_query, primary_params = self.query_builder.build_base_query(component_type, "p")

        # Add compatibility filters if needed
        if config.get("requires_compatibility"):
            primary_query, primary_params = self.query_builder.add_compatibility_filters(
                primary_query, primary_params, component_type, selected_components, "p"
            )

        # Add search term filters
        primary_query, primary_params = self.query_builder.add_search_term_filters(
            primary_query, primary_params, search_terms_dict, "p"
        )

        # Add ordering
        primary_query = self.query_builder.add_priority_ordering(primary_query, "p", "r")

        # Add pagination
        primary_query, primary_params = self.query_builder.add_pagination(
            primary_query, primary_params, offset, limit + 1
        )

        # Add RETURN clause
        primary_query += self.query_builder.build_return_clause("p", include_score=False)

        # STEP 5: Build fallback query WITHOUT search term filters
        fallback_query, fallback_params = self.query_builder.build_base_query(component_type, "p")

        # Add compatibility filters
        if config.get("requires_compatibility"):
            fallback_query, fallback_params = self.query_builder.add_compatibility_filters(
                fallback_query, fallback_params, component_type, selected_components, "p"
            )

        # Add ordering and pagination
        fallback_query = self.query_builder.add_priority_ordering(fallback_query, "p", "r")
        fallback_query, fallback_params = self.query_builder.add_pagination(
            fallback_query, fallback_params, offset, limit + 1
        )
        fallback_query += self.query_builder.build_return_clause("p", include_score=False)

        # STEP 6: Execute search with fallback
        products, filters_applied = await self._execute_search_with_fallback(
            primary_query, primary_params,
            fallback_query, fallback_params,
            search_terms_dict.get("feature_terms", []),
            {"search_method": "cypher"},
            config["neo4j_label"]
        )

        # Check for pagination
        has_more = len(products) > limit
        if has_more:
            products = products[:limit]

        return SearchResults(
            products=products,
            total_count=len(products),
            filters_applied=filters_applied,
            compatibility_validated=config.get("requires_compatibility", False),
            offset=offset,
            limit=limit,
            has_more=has_more
        )

    async def search_with_lucene(
        self,
        component_type: str,
        user_message: str,
        selected_components: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> SearchResults:
        """
        Generic component search using Lucene full-text search.

        This is the method used by LuceneStrategy.

        Args:
            component_type: Type of component
            user_message: User's search message (raw query)
            selected_components: ResponseJSON dict (already selected components)
            limit: Maximum results to return
            offset: Pagination offset

        Returns:
            SearchResults with products and Lucene scores
        """
        config = self.component_config.get(component_type)
        if not config:
            raise ValueError(f"Unknown component type: {component_type}")

        if not config.get("lucene_enabled"):
            raise ValueError(f"Lucene search not enabled for {component_type}")

        # Build Lucene query
        query, params = self.query_builder.build_lucene_query(
            component_type, user_message, "p"
        )

        # Add compatibility filters if needed
        if config.get("requires_compatibility"):
            query, params = self.query_builder.add_compatibility_filters(
                query, params, component_type, selected_components, "p"
            )

        # Add ordering and pagination
        query += f"\nORDER BY score DESC, p.item_name"
        query, params = self.query_builder.add_pagination(query, params, offset, limit + 1)

        # Add RETURN clause with score
        query += self.query_builder.build_return_clause("p", include_score=True)

        # Execute Lucene search
        products = await self._execute_search(query, params)

        # Check for pagination
        has_more = len(products) > limit
        if has_more:
            products = products[:limit]

        return SearchResults(
            products=products,
            total_count=len(products),
            filters_applied={
                "search_method": "lucene",
                "query": user_message
            },
            compatibility_validated=config.get("requires_compatibility", False),
            offset=offset,
            limit=limit,
            has_more=has_more
        )

    async def _search_by_gin_direct(
        self,
        gin: str,
        category: Optional[str] = None
    ) -> Optional[ProductResult]:
        """
        Direct GIN lookup without category/compatibility restrictions.

        Flexible category matching - returns product even if category doesn't match.

        Args:
            gin: Product GIN (10-digit identifier)
            category: Optional expected category (for logging/validation)

        Returns:
            ProductResult if found, None otherwise
        """
        query = """
        MATCH (p:Product)
        WHERE p.gin = $gin
        RETURN p.gin as gin, p.item_name as name, p.category as category,
            p.clean_description as description,
            p.attributes_ruleset as specifications_json,
            p as specifications
        LIMIT 1
        """

        params = {"gin": gin}

        try:
            async with self.driver.session() as session:
                result = await session.run(query, params)
                records = await result.data()

                if records:
                    record = records[0]
                    found_category = record["category"]

                    logger.info(f"🔍 GIN {gin} found with category: '{found_category}'")

                    # Log category mismatch (if specified)
                    if category:
                        category_normalized = category.lower().replace(" ", "")
                        found_normalized = found_category.lower().replace(" ", "")

                        if category_normalized not in found_normalized and found_normalized not in category_normalized:
                            logger.warning(
                                f"⚠️ GIN {gin} category mismatch: "
                                f"Expected '{category}', Found '{found_category}'"
                            )

                    # Build product result
                    specs = record.get("specifications", {})
                    if hasattr(specs, "__dict__"):
                        specs = dict(specs)
                    specs = self._clean_neo4j_types(specs)

                    product = ProductResult(
                        gin=record["gin"],
                        name=record["name"],
                        category=record["category"],
                        description=record.get("description"),
                        specifications=specs
                    )

                    logger.info(f"✅ Found product by GIN: {product.name} ({product.category})")
                    return product
                else:
                    logger.warning(f"❌ No product found for GIN: {gin}")
                    return None

        except Exception as e:
            logger.error(f"GIN search failed: {e}")
            return None

    async def _execute_search(
        self,
        query: str,
        params: Dict[str, Any]
    ) -> List[ProductResult]:
        """
        Execute Neo4j search query and return results.

        Args:
            query: Cypher query string
            params: Query parameters

        Returns:
            List of ProductResult objects
        """
        # DETAILED LOGGING for query troubleshooting (Nov 15, 2024)
        logger.info("=" * 80)
        logger.info("🔍 EXECUTING NEO4J CYPHER QUERY")
        logger.info(f"Query:\n{query}")
        logger.info(f"Params: {params}")
        logger.info("=" * 80)

        try:
            async with self.driver.session() as session:
                result = await session.run(query, params)
                records = await result.data()

                products = []
                for record in records:
                    specs = record.get("specifications", {})
                    if hasattr(specs, "__dict__"):
                        specs = dict(specs)
                    specs = self._clean_neo4j_types(specs)

                    # 🔧 FIX (Nov 15, 2024): Preserve native Lucene fulltext scores
                    # Root cause: Lucene queries return score field but it was being discarded
                    # Solution: Extract score from Neo4j result and store in specifications
                    if "score" in record:
                        lucene_score = float(record["score"])
                        specs["lucene_score"] = lucene_score
                        logger.info(f"  → Product {record['gin']} native Lucene score: {lucene_score}")

                    product = ProductResult(
                        gin=record["gin"],
                        name=record["name"],
                        category=record["category"],
                        description=record.get("description"),
                        specifications=specs
                    )
                    products.append(product)

                logger.info(f"Search returned {len(products)} products")
                return products

        except Exception as e:
            logger.error(f"Neo4j search failed: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            return []

    async def _execute_search_with_fallback(
        self,
        primary_query: str,
        primary_params: Dict[str, Any],
        fallback_query: str,
        fallback_params: Dict[str, Any],
        search_terms: List[str],
        filters_applied: Dict[str, Any],
        category: str
    ) -> Tuple[List[ProductResult], Dict[str, Any]]:
        """
        Execute search with fallback logic.

        If primary query returns 0 results and search terms were applied,
        falls back to query without search term filters.

        Args:
            primary_query: Query WITH search term filters
            primary_params: Primary query parameters
            fallback_query: Query WITHOUT search term filters
            fallback_params: Fallback query parameters
            search_terms: List of search terms that were applied
            filters_applied: Metadata dict to update
            category: Component category for logging

        Returns:
            Tuple of (products, updated_filters_applied)
        """
        # Execute primary query
        products = await self._execute_search(primary_query, primary_params)

        # Fallback logic
        if search_terms and len(products) == 0:
            logger.info(
                f"No {category} found matching search terms, "
                f"falling back to all compatible {category}"
            )
            products = await self._execute_search(fallback_query, fallback_params)

            if products:
                filters_applied["fallback_used"] = True
                filters_applied["original_search_terms"] = search_terms
                filters_applied["message"] = (
                    f"No exact matches found for '{', '.join(search_terms)}'. "
                    f"Below are alternative {category} options based on compatibility and features."
                )

        return products, filters_applied

    def _clean_neo4j_types(self, obj: Any) -> Any:
        """
        Convert Neo4j-specific types to JSON-serializable types.

        Args:
            obj: Object to clean (can be dict, list, or primitive)

        Returns:
            Cleaned object with Neo4j types converted to standard Python types
        """
        from neo4j.time import DateTime, Date, Time

        if isinstance(obj, (DateTime, Date, Time)):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._clean_neo4j_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._clean_neo4j_types(item) for item in obj]
        else:
            return obj
