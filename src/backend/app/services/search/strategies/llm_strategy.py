"""
LLM-based Search Strategy with Retrieve-then-Rerank Pattern

This strategy combines:
1. Initial retrieval using Lucene, Vector, or both (broad coverage)
2. LLM-based re-ranking (semantic understanding and nuanced matching)

The LLM evaluates each product's relevance to user intent and provides:
- Relevance score (0-100)
- Reasoning for the score
- Final ranked list

Retrieval Methods:
- "lucene": Keyword-based full-text search
- "vector": Semantic similarity search
- "combined": Both Lucene + Vector (deduplicates before LLM ranking)
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI

from .base import SearchStrategy, StrategySearchResult
from .lucene_strategy import LuceneSearchStrategy
from .vector_strategy import VectorSearchStrategy

logger = logging.getLogger(__name__)


class LLMSearchStrategy(SearchStrategy):
    """
    LLM-based search strategy that re-ranks results from multiple retrieval methods.

    Architecture:
    1. Retrieve: Use Lucene, Vector, or both for initial candidates
    2. Deduplicate: Remove duplicate products by GIN (for combined mode)
    3. Rerank: LLM evaluates each product against user intent
    4. Score: Returns top products with LLM relevance scores (0-100)

    Config:
        retrieval_limit: Number of candidates per method (default: 10)
        retrieval_method: "lucene", "vector", or "combined" (default: "combined")
        model: OpenAI model to use (default: "gpt-4o-mini")
        weight: Strategy weight for consolidation (default: 0.3)
    """

    def __init__(
        self,
        config: Dict[str, Any],
        neo4j_product_search,
        openai_client: Optional[AsyncOpenAI] = None
    ):
        super().__init__(config)

        # Initialize OpenAI client
        if openai_client:
            self.openai_client = openai_client
        else:
            import os
            self.openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Configuration
        self.retrieval_limit = config.get("retrieval_limit", 10)
        self.retrieval_method = config.get("retrieval_method", "combined")  # "lucene", "vector", or "combined"
        self.model = config.get("model", "gpt-4o-mini")

        # Initialize retrieval strategies
        self.lucene_strategy = LuceneSearchStrategy(
            config={"enabled": True, "weight": 1.0, "min_score": 0.1},
            neo4j_product_search=neo4j_product_search
        )

        self.vector_strategy = VectorSearchStrategy(
            config={"enabled": True, "weight": 1.0, "min_score": 0.6},
            neo4j_product_search=neo4j_product_search
        )

        logger.info(f"Initialized LLMSearchStrategy with {self.retrieval_method.upper()} retrieval, model={self.model}")

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
        Execute LLM-based search with retrieve-then-rerank pattern.

        Args:
            component_type: Component to search for
            user_message: User's natural language query
            master_parameters: Extracted parameters
            selected_components: Previously selected components
            limit: Final number of results to return
            offset: Pagination offset

        Returns:
            StrategySearchResult with LLM-ranked products
        """
        logger.info(f"LLM search for {component_type}: '{user_message}'")

        # Step 1: Retrieve initial candidates using configured retrieval method
        logger.info(f"Retrieving top {self.retrieval_limit} candidates using {self.retrieval_method.upper()}")

        all_candidates = []
        retrieval_stats = {}

        if self.retrieval_method == "lucene":
            # Lucene-only retrieval
            lucene_result = await self.lucene_strategy.search(
                component_type=component_type,
                user_message=user_message,
                master_parameters=master_parameters,
                selected_components=selected_components,
                limit=self.retrieval_limit,
                offset=0
            )
            all_candidates = lucene_result.products
            retrieval_stats["lucene_count"] = len(lucene_result.products)

        elif self.retrieval_method == "vector":
            # Vector-only retrieval
            vector_result = await self.vector_strategy.search(
                component_type=component_type,
                user_message=user_message,
                master_parameters=master_parameters,
                selected_components=selected_components,
                limit=self.retrieval_limit,
                offset=0
            )
            all_candidates = vector_result.products
            retrieval_stats["vector_count"] = len(vector_result.products)

        elif self.retrieval_method == "combined":
            # Combined retrieval: Lucene + Vector with deduplication
            logger.info("Retrieving from both Lucene and Vector strategies")

            # Retrieve from both strategies in parallel
            lucene_result, vector_result = await asyncio.gather(
                self.lucene_strategy.search(
                    component_type=component_type,
                    user_message=user_message,
                    master_parameters=master_parameters,
                    selected_components=selected_components,
                    limit=self.retrieval_limit,
                    offset=0
                ),
                self.vector_strategy.search(
                    component_type=component_type,
                    user_message=user_message,
                    master_parameters=master_parameters,
                    selected_components=selected_components,
                    limit=self.retrieval_limit,
                    offset=0
                )
            )

            # Deduplicate by GIN (keep first occurrence)
            seen_gins = set()
            for product in lucene_result.products:
                gin = product.get("gin")
                if gin and gin not in seen_gins:
                    all_candidates.append(product)
                    seen_gins.add(gin)

            for product in vector_result.products:
                gin = product.get("gin")
                if gin and gin not in seen_gins:
                    all_candidates.append(product)
                    seen_gins.add(gin)

            retrieval_stats["lucene_count"] = len(lucene_result.products)
            retrieval_stats["vector_count"] = len(vector_result.products)
            retrieval_stats["deduplicated_count"] = len(all_candidates)
            retrieval_stats["duplicates_removed"] = (len(lucene_result.products) + len(vector_result.products)) - len(all_candidates)

            logger.info(f"Combined retrieval: Lucene={len(lucene_result.products)}, Vector={len(vector_result.products)}, "
                       f"Unique={len(all_candidates)}, Duplicates removed={retrieval_stats['duplicates_removed']}")

        if not all_candidates:
            logger.warning(f"No candidates retrieved for {component_type}")
            return StrategySearchResult(
                products=[],
                scores={},
                metadata={
                    "strategy": "llm",
                    "retrieval_method": self.retrieval_method,
                    "retrieval_count": 0,
                    **retrieval_stats
                },
                strategy_name="llm"
            )

        logger.info(f"Retrieved {len(all_candidates)} unique candidates for LLM re-ranking")

        # Step 2: LLM Re-ranking
        ranked_products, scores = await self._rerank_with_llm(
            user_message=user_message,
            component_type=component_type,
            candidates=all_candidates,
            limit=limit
        )

        # Apply offset and limit (top 5 for combined mode)
        final_products = ranked_products[offset:offset + limit]

        return StrategySearchResult(
            products=final_products,
            scores=scores,
            metadata={
                "strategy": "llm",
                "retrieval_method": self.retrieval_method,
                "retrieval_count": len(all_candidates),
                "model": self.model,
                **retrieval_stats
            },
            strategy_name="llm"
        )

    async def validate_compatibility(
        self,
        product_gin: str,
        selected_components: Dict[str, Any],
        component_type: str
    ) -> bool:
        """
        Validate product compatibility (delegates to Lucene strategy).

        Args:
            product_gin: Product GIN to validate
            selected_components: Already selected components
            component_type: Type of component

        Returns:
            True if compatible
        """
        # Delegate to Lucene strategy for compatibility validation
        return await self.lucene_strategy.validate_compatibility(
            product_gin, selected_components, component_type
        )

    async def _rerank_with_llm(
        self,
        user_message: str,
        component_type: str,
        candidates: List[Dict[str, Any]],
        limit: int
    ) -> tuple[List[Dict[str, Any]], Dict[str, float]]:
        """
        Use LLM to re-rank candidate products based on relevance to user intent.

        Args:
            user_message: User's query
            component_type: Component type
            candidates: Initial retrieved products
            limit: Number of top results needed

        Returns:
            Tuple of (ranked_products, scores_dict)
        """
        # Build prompt with products
        prompt = self._build_reranking_prompt(user_message, component_type, candidates)

        logger.debug(f"Sending {len(candidates)} products to LLM for re-ranking")

        try:
            # Call LLM for re-ranking
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert welding equipment specialist. Your task is to rank welding products based on how well they match the user's requirements.

For each product, provide:
1. A relevance score (0-100) where:
   - 90-100: Perfect match for user requirements (exact competitor equivalent OR perfect spec match)
   - 70-89: Good match with minor gaps
   - 50-69: Partial match, some requirements met
   - 30-49: Weak match, few requirements met
   - 0-29: Poor match, not suitable

2. Brief reasoning (1-2 sentences) explaining the score

IMPORTANT: When the user asks for an "equivalent of [Brand:Model]" or "similar to [Brand:Model]":
- Prioritize products that list that exact Brand:Model in their "Competitor Equivalents" field
- Products with matching competitor equivalents should score 90-100 (near-perfect match)
- This is the PRIMARY matching criterion for equivalence queries

Also consider:
- Technical specifications (amperage, voltage, processes)
- User requirements (material, application, environment)
- Compatibility and features
- Value for the specific use case"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for consistent ranking
                response_format={"type": "json_object"}
            )

            # Parse response
            import json
            raw_response = response.choices[0].message.content
            logger.info(f"🔍 LLM Raw Response:\n{raw_response}")

            result = json.loads(raw_response)
            logger.info(f"📊 Parsed JSON structure: {json.dumps(result, indent=2)}")

            # Create ranked product list with LLM scores
            ranked_products = []
            scores_dict = {}
            rankings = result.get("rankings", [])
            logger.info(f"📋 Found {len(rankings)} rankings in LLM response")

            for i, ranking in enumerate(rankings, 1):
                gin = ranking.get("gin")
                score = ranking.get("relevance_score", 0) / 100.0  # Normalize to 0-1
                reasoning = ranking.get("reasoning", "")

                logger.debug(f"  Ranking {i}: GIN={gin}, Score={ranking.get('relevance_score', 0)}, Reasoning={reasoning[:50]}...")

                # Find corresponding product
                product = next((p for p in candidates if p.get("gin") == gin), None)
                if product:
                    # Add LLM score and reasoning to product specifications
                    if "specifications" not in product:
                        product["specifications"] = {}
                    product["specifications"]["llm_score"] = ranking.get("relevance_score", 0)  # Keep 0-100
                    product["specifications"]["llm_reasoning"] = reasoning
                    # Also add at top level for backward compatibility
                    product["llm_score"] = ranking.get("relevance_score", 0)
                    product["llm_reasoning"] = reasoning
                    ranked_products.append(product)
                    scores_dict[gin] = score  # Store normalized score
                    logger.debug(f"    ✅ Matched product: {product.get('name', 'Unknown')}")
                else:
                    logger.warning(f"    ❌ No matching product found for GIN: {gin}")

            # Sort by LLM score (descending)
            ranked_products.sort(key=lambda p: p.get("llm_score", 0), reverse=True)

            logger.info(f"✅ LLM ranked {len(ranked_products)} products, top score: {ranked_products[0].get('llm_score', 0) if ranked_products else 0}")

            # Log final rankings
            logger.info("🏆 Final LLM Rankings:")
            for i, p in enumerate(ranked_products[:5], 1):
                logger.info(f"  {i}. {p.get('name', 'Unknown')} (GIN: {p.get('gin', 'N/A')}) - Score: {p.get('llm_score', 0)}/100")

            return ranked_products, scores_dict

        except Exception as e:
            logger.error(f"LLM re-ranking failed: {e}")
            # Fallback: return original candidates with default scores
            scores_dict = {p.get("gin"): 0.5 for p in candidates}
            return candidates, scores_dict

    def _build_reranking_prompt(
        self,
        user_message: str,
        component_type: str,
        candidates: List[Dict[str, Any]]
    ) -> str:
        """
        Build prompt for LLM re-ranking.

        Args:
            user_message: User's query
            component_type: Component type
            candidates: Products to rank

        Returns:
            Formatted prompt string
        """
        # Format products for LLM (including competitor info for accurate matching)
        products_text = []
        for i, product in enumerate(candidates, 1):
            # Extract fields from specifications if available
            specs = product.get('specifications', {})

            # DEBUG: Log what fields are available in specs
            if i == 1:  # Only log for first product
                logger.debug(f"[LLM Prompt Debug] First product specs keys: {list(specs.keys())}")

            attributes_ruleset = specs.get('attribute_ruleset', specs.get('attributes_ruleset', ''))
            competitor_pairs = specs.get('competitor_brand_product_pairs', [])

            # Build comprehensive product information for LLM
            product_info = [
                f"{i}. GIN: {product.get('gin', 'N/A')}",
                f"   Name: {product.get('name', 'Unknown')}",
                f"   Category: {product.get('category', 'Unknown')}",
                f"   Description: {product.get('description', 'N/A')}"
            ]

            # Add attributes_ruleset if available (technical specifications)
            if attributes_ruleset:
                product_info.append(f"   Technical Attributes: {attributes_ruleset}")
                logger.debug(f"[LLM Prompt Debug] Product {i} has attributes_ruleset")

            # Add competitor equivalents if available (CRITICAL for competitor matching)
            if competitor_pairs:
                # Format competitor list for LLM readability
                if isinstance(competitor_pairs, list):
                    competitors_str = ', '.join(str(c) for c in competitor_pairs)
                else:
                    competitors_str = str(competitor_pairs)
                product_info.append(f"   Competitor Equivalents: {competitors_str}")
                logger.debug(f"[LLM Prompt Debug] Product {i} ({product.get('name')}) has competitor_pairs: {competitors_str[:100]}")
            else:
                logger.warning(f"[LLM Prompt Debug] Product {i} ({product.get('name')}) has NO competitor_pairs!")

            products_text.append('\n'.join(product_info))

        prompt = f"""User Request: "{user_message}"
Component Type: {component_type}

Please rank the following {len(candidates)} welding products based on how well they match the user's requirements:

{chr(10).join(products_text)}

Provide your response in JSON format:
{{
    "rankings": [
        {{
            "gin": "product_gin",
            "relevance_score": 85,
            "reasoning": "Brief explanation of why this score was given"
        }},
        ...
    ]
}}

Rank all products from most relevant to least relevant."""

        return prompt
