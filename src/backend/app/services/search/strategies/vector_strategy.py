"""
Vector Search Strategy

Semantic similarity search using OpenAI embeddings and Neo4j vector index.

Architecture:
1. Generate embedding for user query using OpenAI text-embedding-3-large (3072 dims)
2. Search Neo4j vector index for semantically similar products
3. Return ranked results by similarity score
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

        # Step 1: Generate embedding for user query
        logger.debug(f"Generating embedding using {self.embedding_model} ({self.embedding_dims} dims)")
        try:
            response = await self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=user_message,
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

        # Step 2: Search Neo4j vector index
        neo4j_category = self._map_component_to_neo4j_category(component_type)
        logger.debug(f"Searching vector index for category: {neo4j_category}")

        try:
            # Get driver from centralized manager (supports auto-reconnection)
            driver = await neo4j_manager.get_driver()
            async with driver.session() as session:
                result = await session.run("""
                    CALL db.index.vector.queryNodes('embeddingIndex', $limit, $vector)
                    YIELD node, score
                    MATCH (p:Product)-[:HAS_EMBEDDING]->(node)
                    WHERE p.category = $category AND score >= $min_score
                    RETURN
                        p.gin as gin,
                        p.item_name as name,
                        p.category as category,
                        p.description_catalogue as description,
                        p as specifications,
                        score
                    ORDER BY score DESC
                """, vector=embedding, limit=limit + offset, category=neo4j_category, min_score=self.min_score)

                records = await result.data()

        except Exception as e:
            logger.error(f"Neo4j vector search failed: {e}")
            return StrategySearchResult(
                products=[],
                scores={},
                metadata={"strategy": "vector", "error": str(e)},
                strategy_name="vector"
            )

        # Step 3: Convert results to product dictionaries
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
            "accessory": "Accessory"
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
