"""
Vector Search Strategy

Semantic similarity search using OpenAI embeddings and Neo4j vector index.

Architecture:
1. Generate embedding for user query using OpenAI text-embedding-3-large (3072 dims)
2. Search Neo4j vector index (embeddings stored directly in Product nodes)
3. Return ranked results by similarity score

Note: Embeddings are stored directly in Product.embedding property (no separate node/relationship).
"""

import logging
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI

from .base import SearchStrategy, StrategySearchResult
from app.database.database import neo4j_manager

logger = logging.getLogger(__name__)


class VectorSearchStrategy(SearchStrategy):
    """
    Vector-based search strategy using OpenAI embeddings and Neo4j vector index.

    Uses semantic similarity to find products that match the user's intent,
    even if exact keywords don't match.

    Config:
        enabled: Whether this strategy is enabled (default: True)
        weight: Strategy weight for consolidation (default: 0.6)
        min_score: Minimum similarity score threshold (default: 0.6)
        embedding_model: OpenAI embedding model (default: "text-embedding-3-large")
        embedding_dims: Embedding dimensions (default: 3072)
    """

    def __init__(
        self,
        config: Dict[str, Any],
        neo4j_product_search,
        openai_client: Optional[AsyncOpenAI] = None
    ):
        super().__init__(config)

        self.neo4j_search = neo4j_product_search
        self.min_score = config.get("min_score", 0.6)
        self.embedding_model = config.get("embedding_model", "text-embedding-3-large")
        self.embedding_dims = config.get("embedding_dims", 3072)

        # Initialize OpenAI client
        if openai_client:
            self.openai_client = openai_client
        else:
            from openai import AsyncOpenAI
            import os
            self.openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Note: We don't store neo4j_driver here - we get it from global neo4j_manager when needed
        # This ensures we always use the latest connection (auto-reconnection support)

        logger.info(f"Initialized VectorSearchStrategy with {self.embedding_model} ({self.embedding_dims} dims), min_score={self.min_score}")
        logger.info("  Will use centralized neo4j_manager for driver access")

    def _enrich_query_context(
        self,
        user_message: str,
        master_parameters: Dict[str, Any],
        component_type: str
    ) -> str:
        """
        Enrich user query with extracted parameters for better semantic matching.

        Combines user message with structured extracted parameters to create
        a richer context for embedding generation. This improves semantic
        understanding by including technical requirements.

        Args:
            user_message: Raw user message
            master_parameters: Extracted parameters from LLM (MasterParameterJSON)
            component_type: Component being searched (e.g., "Feeder", "PowerSource")

        Returns:
            Enriched context string combining user intent + extracted features

        Example:
            Input:  user_message="I need a feeder"
                    master_parameters={"feeder": {"cooling_type": "water-cooled", "current_output": "500A"}}
            Output: "I need a feeder | cooling_type: water-cooled | current_output: 500A | Component type: Feeder"
        """
        context_parts = [user_message]

        # Add extracted parameters as context (if available)
        component_key = component_type.lower()
        if component_key in master_parameters:
            params = master_parameters[component_key]

            # Add non-empty parameter values
            for key, value in params.items():
                if value and key not in ['_detected_gin', 'product_name']:  # Skip internal fields
                    context_parts.append(f"{key}: {value}")

        # Add component type context for categorical awareness
        context_parts.append(f"Component type: {component_type}")

        enriched_context = " | ".join(context_parts)
        logger.debug(f"Enriched query context: {enriched_context[:200]}...")  # Log first 200 chars

        return enriched_context

    def _filter_by_specifications(
        self,
        records: List[Dict[str, Any]],
        master_parameters: Dict[str, Any],
        component_type: str
    ) -> List[Dict[str, Any]]:
        """
        Post-filter vector search results by matching specifications against extracted parameters.

        Uses fuzzy matching to compare product specifications with user requirements.
        Keeps products that match ≥70% of specified parameters.

        Args:
            records: Neo4j records from vector search
            master_parameters: Extracted parameters from LLM (MasterParameterJSON)
            component_type: Component being searched

        Returns:
            Filtered list of records that meet specification threshold

        Example:
            Input: Records with various cooling types, user wants "water-cooled"
            Output: Only water-cooled products (or close matches)
        """
        from rapidfuzz import fuzz

        component_key = component_type.lower()
        if component_key not in master_parameters:
            logger.debug("No master parameters for filtering, returning all records")
            return records

        params = master_parameters[component_key]

        # Extract relevant parameters (skip internal fields)
        search_params = {
            k: v for k, v in params.items()
            if v and k not in ['_detected_gin', 'product_name']
        }

        if not search_params:
            logger.debug("No non-empty parameters for filtering, returning all records")
            return records

        logger.debug(f"Filtering {len(records)} records using parameters: {search_params}")

        # Match threshold: 70% of specified parameters must match
        match_threshold = 0.70
        filtered_records = []

        for record in records:
            specs = record.get("specifications", {})

            # Convert Neo4j node to dict if needed
            if hasattr(specs, "__dict__"):
                specs = dict(specs)

            # Count matches
            total_params = len(search_params)
            matched_params = 0

            for param_key, param_value in search_params.items():
                # Try to find matching spec field
                # Common mappings: cooling_type → cooling, current_output → current_range
                possible_keys = [
                    param_key,
                    param_key.replace('_', ''),
                    param_key.replace('_type', ''),
                    param_key.replace('_output', '_range'),
                    param_key.split('_')[0]  # First word only
                ]

                matched = False
                for spec_key in possible_keys:
                    if spec_key in specs:
                        spec_value = str(specs[spec_key])
                        param_value_str = str(param_value)

                        # Fuzzy string matching (case-insensitive)
                        similarity = fuzz.ratio(
                            spec_value.lower(),
                            param_value_str.lower()
                        )

                        # 80% similarity threshold for individual parameter
                        if similarity >= 80:
                            matched = True
                            logger.debug(
                                f"  ✓ Matched {param_key}='{param_value}' with "
                                f"{spec_key}='{spec_value}' (similarity: {similarity}%)"
                            )
                            break

                        # Also check if param_value is substring (e.g., "water" in "water-cooled")
                        if param_value_str.lower() in spec_value.lower():
                            matched = True
                            logger.debug(
                                f"  ✓ Matched {param_key}='{param_value}' (substring) in "
                                f"{spec_key}='{spec_value}'"
                            )
                            break

                if matched:
                    matched_params += 1

            # Calculate match percentage
            match_percentage = matched_params / total_params if total_params > 0 else 0

            if match_percentage >= match_threshold:
                logger.debug(
                    f"  ✅ Product {record.get('gin')} matched {matched_params}/{total_params} "
                    f"parameters ({match_percentage:.1%}) - KEEP"
                )
                filtered_records.append(record)
            else:
                logger.debug(
                    f"  ❌ Product {record.get('gin')} matched {matched_params}/{total_params} "
                    f"parameters ({match_percentage:.1%}) - FILTER OUT"
                )

        logger.info(
            f"Specification filtering: {len(filtered_records)}/{len(records)} products "
            f"matched ≥{match_threshold:.0%} of requirements"
        )

        return filtered_records

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
        Execute vector search using OpenAI embeddings and Neo4j vector index.

        Args:
            component_type: Component to search for
            user_message: User's natural language query
            master_parameters: Extracted parameters (not used in vector search)
            selected_components: Previously selected components
            limit: Number of results to return
            offset: Pagination offset

        Returns:
            StrategySearchResult with similarity-ranked products
        """
        logger.info(f"Vector search for {component_type}: '{user_message}'")

        # Step 1: Enrich query context with extracted parameters
        enriched_query = self._enrich_query_context(
            user_message=user_message,
            master_parameters=master_parameters,
            component_type=component_type
        )

        # Step 2: Generate embedding for enriched query
        logger.debug(f"Generating embedding using {self.embedding_model} ({self.embedding_dims} dims)")
        try:
            response = await self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=enriched_query,  # Use enriched context instead of raw user_message
                dimensions=self.embedding_dims
            )
            embedding = response.data[0].embedding
            logger.debug(f"Generated embedding vector of length {len(embedding)}")
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return StrategySearchResult(
                products=[],
                scores={},
                metadata={"strategy": "vector", "error": str(e)},
                strategy_name="vector"
            )

        # Step 3: Build compatibility-aware vector search query
        neo4j_category = self._map_component_to_neo4j_category(component_type)
        logger.debug(f"Searching vector index for category: {neo4j_category}")

        # Build base vector query
        base_query = """
            CALL db.index.vector.queryNodes('embeddingIndex', $limit, $vector)
            YIELD node AS p, score
            WHERE p.category = $category AND score >= $min_score
            WITH p, score
        """
        
        params = {
            "vector": embedding,
            "limit": limit + offset,
            "category": neo4j_category,
            "min_score": self.min_score
        }
        
        # Add compatibility filters using Neo4jQueryBuilder
        from app.services.search.components.query_builder import Neo4jQueryBuilder
        from app.config.schema_loader import load_component_config
        
        component_config = load_component_config()
        query_builder = Neo4jQueryBuilder(component_config)
        
        # Add compatibility filters (reuses same logic as cypher strategy)
        query, params, _ = query_builder.add_compatibility_filters(
            query=base_query,
            params=params,
            component_type=component_type.lower(),
            selected_components=selected_components,
            node_alias="p"
        )
        
        # Add RETURN clause
        query += """
            RETURN
                p.gin as gin,
                p.item_name as name,
                p.category as category,
                p.description_catalogue as description,
                p as specifications,
                score
            ORDER BY score DESC
        """

        try:
            # Get driver from centralized manager (supports auto-reconnection)
            driver = await neo4j_manager.get_driver()
            async with driver.session() as session:
                result = await session.run(query, params)
                records = await result.data()

        except Exception as e:
            logger.error(f"Neo4j vector search failed: {e}")
            return StrategySearchResult(
                products=[],
                scores={},
                metadata={"strategy": "vector", "error": str(e)},
                strategy_name="vector"
            )

        # Step 4: Post-filter by specifications (if parameters extracted)
        if component_type.lower() in master_parameters:
            logger.debug(f"Applying specification filtering for {component_type}")
            records = self._filter_by_specifications(
                records=records,
                master_parameters=master_parameters,
                component_type=component_type
            )
            logger.info(f"After specification filtering: {len(records)} products remaining")

        # Step 5: Convert results to product dictionaries
        products = []
        scores_dict = {}

        for i, record in enumerate(records[offset:offset + limit], 1):
            # Extract full product node for specifications (includes attribute_ruleset)
            specs = record.get("specifications", {})

            # DEBUG: Log raw Neo4j node before conversion
            if i == 1:
                logger.debug(f"[Vector Debug] Raw Neo4j record type: {type(specs)}")
                if hasattr(specs, "__dict__"):
                    logger.debug(f"[Vector Debug] Raw Neo4j node attributes: {list(specs.__dict__.keys())[:10]}")
                elif isinstance(specs, dict):
                    logger.debug(f"[Vector Debug] Raw dict keys: {list(specs.keys())[:10]}")

            if hasattr(specs, "__dict__"):
                specs = dict(specs)

            # DEBUG: Log after dict conversion
            if i == 1:
                logger.debug(f"[Vector Debug] After dict conversion - specs keys: {list(specs.keys())[:15]}")
                logger.debug(f"[Vector Debug] Has competitor_brand_product_pairs: {'competitor_brand_product_pairs' in specs}")
                if 'competitor_brand_product_pairs' in specs:
                    logger.debug(f"[Vector Debug] competitor_brand_product_pairs value: {specs['competitor_brand_product_pairs'][:100] if specs['competitor_brand_product_pairs'] else 'None'}")

            # Clean Neo4j types (convert Neo4j types to Python types)
            if specs:
                specs = self._clean_neo4j_types(specs)

            # DEBUG: Log after type cleaning
            if i == 1:
                logger.debug(f"[Vector Debug] After _clean_neo4j_types - specs keys: {list(specs.keys())[:15]}")
                logger.debug(f"[Vector Debug] Still has competitor_brand_product_pairs: {'competitor_brand_product_pairs' in specs}")

            # Add vector similarity score to specifications
            if not specs:
                specs = {}
            specs["vector_similarity"] = record["score"]

            product = {
                "gin": record["gin"],
                "name": record["name"],
                "category": record["category"],
                "description": record.get("description", ""),
                "specifications": specs
            }
            products.append(product)
            scores_dict[record["gin"]] = record["score"]

        logger.info(f"Vector search returned {len(products)} products (similarity >= {self.min_score})")

        return StrategySearchResult(
            products=products,
            scores=scores_dict,
            metadata={
                "strategy": "vector",
                "embedding_model": self.embedding_model,
                "embedding_dims": self.embedding_dims,
                "min_score": self.min_score,
                "total_found": len(records)
            },
            strategy_name="vector"
        )

    async def validate_compatibility(
        self,
        product_gin: str,
        selected_components: Dict[str, Any],
        component_type: str
    ) -> bool:
        """
        Validate product compatibility using Neo4j graph relationships.

        Delegates to the Neo4j product search service for compatibility validation.

        Args:
            product_gin: Product GIN to validate
            selected_components: Already selected components
            component_type: Type of component

        Returns:
            True if compatible
        """
        # Delegate to Neo4j search for compatibility validation
        # (Vector search doesn't have compatibility logic itself)
        return await self.neo4j_search.validate_compatibility(
            product_gin=product_gin,
            selected_components=selected_components,
            component_type=component_type
        )

    def _map_component_to_neo4j_category(self, component_type: str) -> str:
        """
        Map component type to Neo4j Product category label.

        Args:
            component_type: Component type from configurator

        Returns:
            Neo4j category string
        """
        mapping = {
            "power_source": "Powersource",
            "feeder": "Feeder",
            "cooler": "Cooler",
            "interconnector": "Interconnector",
            "torch": "Torch",
            "accessory": "Accessory",
            # Accessory subcategories (all map to "Accessory" category in Neo4j)
            "remote": "Accessory",
            "connectivity": "Accessory",
            "feeder_wear": "Accessory",
            "powersource_accessory": "Accessory",
            "feeder_accessory": "Accessory",
            "remote_accessory": "Accessory",
            "interconn_accessory": "Accessory",
            # Common accessory type aliases
            "consumable": "Accessory",
            "cable": "Accessory",
            "safety_gear": "Accessory",
            "wear_part": "Accessory"
        }
        return mapping.get(component_type.lower(), "Powersource")

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

    async def close(self):
        """
        Cleanup resources.

        Note: This strategy does not manage database connections.
        All connections are managed by the centralized neo4j_manager.
        """
        logger.debug("VectorSearchStrategy cleanup (no resources to clean)")
