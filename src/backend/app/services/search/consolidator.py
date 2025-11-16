"""
Result Consolidator

Consolidates search results from multiple strategies:
- Deduplicates products by GIN
- Merges scores using configurable weights
- Assigns default ranking for strategies without scores
- Provides unified sorting by final consolidated score
"""

import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict

from app.config.schema_loader import load_component_config

logger = logging.getLogger(__name__)


class ConsolidatedResult:
    """
    Single consolidated product result.

    Attributes:
        gin: Product GIN (unique identifier)
        name: Product name
        category: Product category
        description: Product description
        specifications: Product specifications
        consolidated_score: Final weighted score (0.0-1.0)
        strategy_scores: Dict of {strategy_name: score} for transparency
        found_by_strategies: List of strategy names that found this product
    """

    def __init__(
        self,
        gin: str,
        name: str,
        category: str,
        description: Optional[str] = None,
        specifications: Optional[Dict[str, Any]] = None
    ):
        self.gin = gin
        self.name = name
        self.category = category
        self.description = description
        self.specifications = specifications or {}
        self.consolidated_score: float = 0.0
        self.strategy_scores: Dict[str, float] = {}
        self.found_by_strategies: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "gin": self.gin,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "specifications": self.specifications,
            "consolidated_score": self.consolidated_score,
            "strategy_scores": self.strategy_scores,
            "found_by_strategies": self.found_by_strategies
        }


class ResultConsolidator:
    """
    Consolidates search results from multiple strategies.

    Handles:
    1. Deduplication by GIN (keep first occurrence for product details)
    2. Score merging with configurable weights per strategy
    3. Default score assignment for strategies without scores
    4. Unified sorting by final consolidated score
    """

    def __init__(self, config: Dict[str, Any], search_config: Optional[Dict[str, Any]] = None):
        """
        Initialize consolidator with configuration.

        Args:
            config: Consolidation configuration from search_config.json
                Example:
                {
                    "strategy_weights": {
                        "lucene": 0.6,
                        "cypher": 0.4,
                        "vector": 0.5
                    },
                    "default_score_for_unscored": 0.5,
                    "score_normalization": "min_max" | "z_score" | "none"
                }
            search_config: Full search_config.json for accessing lucene_search settings
        """
        self.config = config
        self.strategy_weights = config.get("strategy_weights", {})
        self.default_score = config.get("default_score_for_unscored", 0.5)
        self.normalization = config.get("score_normalization", "none")

        # Score display configuration from strategies.lucene (rationalized Nov 15, 2024)
        self.search_config = search_config or {}
        lucene_config = self.search_config.get("strategies", {}).get("lucene", {})
        self.append_score_to_name = lucene_config.get("append_score_to_name", True)
        self.score_decimal_places = lucene_config.get("score_decimal_places", 1)

        logger.info(
            f"ResultConsolidator initialized with weights: {self.strategy_weights}, "
            f"append_score: {self.append_score_to_name}"
        )

    def consolidate(
        self,
        strategy_results: List[tuple[str, List[Dict[str, Any]], Optional[Dict[str, float]]]],
        master_parameters: Optional[Dict[str, Any]] = None,
        component_type: Optional[str] = None
    ) -> List[ConsolidatedResult]:
        """
        Consolidate results from multiple strategies with optional exact product name boosting.

        Args:
            strategy_results: List of (strategy_name, products, scores) tuples
                Example:
                [
                    ("lucene", [{"gin": "123", ...}], {"123": 0.8}),
                    ("cypher", [{"gin": "123", ...}, {"gin": "456", ...}], None)
                ]
            master_parameters: Optional LLM-extracted parameters containing product_name
            component_type: Optional component type (e.g., "PowerSource", "Feeder")

        Returns:
            List of ConsolidatedResult objects sorted by consolidated_score (descending)
        """
        try:
            logger.info(f"Consolidating results from {len(strategy_results)} strategies")

            # Step 1: Deduplicate and collect all products by GIN
            products_by_gin: Dict[str, ConsolidatedResult] = {}

            for strategy_name, products, scores in strategy_results:
                logger.info(f"Processing {len(products)} products from {strategy_name}")

                for product in products:
                    gin = product.get("gin")
                    if not gin:
                        logger.warning(f"Product missing GIN: {product}")
                        continue

                    # First occurrence: Create ConsolidatedResult
                    if gin not in products_by_gin:
                        products_by_gin[gin] = ConsolidatedResult(
                            gin=gin,
                            name=product.get("name", ""),
                            category=product.get("category", ""),
                            description=product.get("description"),
                            specifications=product.get("specifications", {})
                        )

                    # Track which strategies found this product
                    products_by_gin[gin].found_by_strategies.append(strategy_name)

                    # Get or assign score for this strategy
                    if scores and gin in scores:
                        strategy_score = scores[gin]
                    else:
                        strategy_score = self.default_score
                        logger.debug(f"Assigned default score {self.default_score} for {gin} from {strategy_name}")

                    # Store strategy-specific score
                    products_by_gin[gin].strategy_scores[strategy_name] = strategy_score

            logger.info(f"Deduplicated to {len(products_by_gin)} unique products")

            # Step 2: Calculate consolidated scores using weighted average
            for gin, result in products_by_gin.items():
                result.consolidated_score = self._calculate_weighted_score(result.strategy_scores)

            # Step 2.5: Apply 100x boosting for exact product name matches
            if master_parameters and component_type:
                self._apply_exact_match_boosting(
                    products_by_gin,
                    master_parameters,
                    component_type
                )

            # Step 2.6: Append consolidated scores to product names
            if self.append_score_to_name:
                self._append_scores_to_names(products_by_gin)

            # Step 3: Sort by consolidated score (descending)
            sorted_results = sorted(
                products_by_gin.values(),
                key=lambda x: x.consolidated_score,
                reverse=True
            )

            # DEBUG: Log all products BEFORE threshold filtering
            logger.info(f"📊 PRE-THRESHOLD: {len(sorted_results)} products before filtering:")
            for idx, result in enumerate(sorted_results[:10], 1):  # Show top 10
                strategy_scores_str = ", ".join([f"{s}: {sc:.2f}" for s, sc in result.strategy_scores.items()])
                logger.info(
                    f"   {idx}. {result.name} (GIN: {result.gin}) | "
                    f"Consolidated: {result.consolidated_score:.2f} | "
                    f"Strategies: {strategy_scores_str}"
                )

            # Step 3.5: Apply score threshold filtering
            if component_type:
                sorted_results = self._apply_score_threshold(sorted_results, component_type)

            logger.info(f"Consolidated {len(sorted_results)} results with scores")
            return sorted_results

        except Exception as e:
            logger.error(f"Error consolidating results: {e}", exc_info=True)
            return []

    def _calculate_weighted_score(self, strategy_scores: Dict[str, float]) -> float:
        """
        Calculate weighted average score from multiple strategies.

        Args:
            strategy_scores: Dict of {strategy_name: score}

        Returns:
            Weighted average score (0.0-1.0)
        """
        if not strategy_scores:
            return self.default_score

        weighted_sum = 0.0
        total_weight = 0.0

        for strategy_name, score in strategy_scores.items():
            weight = self.strategy_weights.get(strategy_name, 1.0)
            weighted_sum += score * weight
            total_weight += weight

        if total_weight == 0:
            return self.default_score

        return weighted_sum / total_weight

    def _apply_exact_match_boosting(
        self,
        products_by_gin: Dict[str, ConsolidatedResult],
        master_parameters: Dict[str, Any],
        component_type: str
    ) -> None:
        """
        Apply 100x score boosting for exact product name matches.

        This method has been simplified - product matching is now handled
        during Cypher query building via normalized CONTAINS matching.

        Legacy exact/substring matching is kept for backward compatibility.

        Args:
            products_by_gin: Dict of GIN -> ConsolidatedResult (modified in-place)
            master_parameters: LLM-extracted parameters
            component_type: Component type being searched
        """
        try:
            # Map component_type to master_parameters key
            component_key_map = {
                "PowerSource": "power_source",
                "Feeder": "feeder",
                "Cooler": "cooler",
                "Interconnector": "interconnector",
                "Torch": "torch",
                "Accessory": "accessory"
            }

            component_key = component_key_map.get(component_type)
            if not component_key or component_key not in master_parameters:
                return

            component_params = master_parameters[component_key]
            if not component_params or not isinstance(component_params, dict):
                return

            # Extract product_name for exact matching
            product_name = component_params.get("product_name")
            if not product_name or not isinstance(product_name, str):
                return

            product_name = product_name.strip().lower()
            if not product_name:
                return

            # Space-insensitive exact/substring matching
            for gin, result in products_by_gin.items():
                result_name = result.name.strip().lower()

                # Remove spaces for comparison (space-insensitive)
                result_name_no_spaces = result_name.replace(' ', '')
                product_name_no_spaces = product_name.replace(' ', '')

                # Exact match or substring match (space-insensitive)
                if result_name_no_spaces == product_name_no_spaces or product_name_no_spaces in result_name_no_spaces:
                    original_score = result.consolidated_score
                    result.consolidated_score = original_score * 100.0

                    logger.info(
                        f"✨ BOOSTED: '{result.name}' (GIN: {gin}) | "
                        f"Matched: '{product_name}' (space-insensitive) | "
                        f"Score: {original_score:.4f} → {result.consolidated_score:.4f} (100x)"
                    )

        except Exception as e:
            logger.error(f"Error applying exact match boosting: {e}", exc_info=True)

    def _append_scores_to_names(self, products_by_gin: Dict[str, ConsolidatedResult]) -> None:
        """
        Append consolidated scores to product names for display.

        Args:
            products_by_gin: Dict of GIN -> ConsolidatedResult (modified in-place)

        APPENDING LOGIC:
        - Remove any existing score from product name
        - Append consolidated_score in format: "Product Name (Score: X.X)"
        - Use configured decimal places from search_config.json
        """
        try:
            import re

            for gin, result in products_by_gin.items():
                # Remove any existing score pattern from name
                # Pattern matches: "(Score: 11.5)" or "(95.0)" or any number in parentheses at end
                clean_name = re.sub(r'\s*\((?:Score:\s*)?[\d.]+\)\s*$', '', result.name.strip())

                # Append new consolidated score
                score_str = f"{result.consolidated_score:.{self.score_decimal_places}f}"
                result.name = f"{clean_name} (Score: {score_str})"

                logger.debug(f"Appended score to: {result.name}")

        except Exception as e:
            logger.error(f"Error appending scores to names: {e}", exc_info=True)

    def _apply_score_threshold(
        self,
        results: List[ConsolidatedResult],
        component_type: str
    ) -> List[ConsolidatedResult]:
        """
        Filter products by score threshold percentage.

        Keeps only products within configured percentage of top score.
        Example: score_threshold_percent=20 means keep products with
        score >= top_score * 0.80 (within 20% of top).

        Args:
            results: Sorted list of ConsolidatedResult (descending by score)
            component_type: Component type (PowerSource, Feeder, etc.)

        Returns:
            Filtered list of products meeting threshold
        """
        try:
            if not results:
                return results

            # Map component_type to config key
            component_key_map = {
                "PowerSource": "power_source",
                "Feeder": "feeder",
                "Cooler": "cooler",
                "Interconnector": "interconnector",
                "Torch": "torch",
                "Remote": "remote",
                "Accessory": "powersource_accessories"  # Default for accessories
            }

            component_key = component_key_map.get(component_type)
            if not component_key:
                logger.warning(f"Unknown component type for threshold: {component_type}")
                return results

            # Get component-specific threshold from component_types.json (rationalized Nov 15, 2024)
            component_types = load_component_config()
            component_config = component_types.get(component_key, {})

            # Get score_threshold_percent (default to 25 if not configured)
            threshold_percent = component_config.get("lucene_score_threshold_percent", 25)

            # Get top score (first result in sorted list)
            top_score = results[0].consolidated_score

            # Calculate minimum acceptable score
            # If threshold_percent=20, keep products with score >= top_score * 0.80
            min_score = top_score * (1 - threshold_percent / 100.0)

            # Filter products
            filtered_results = [
                r for r in results
                if r.consolidated_score >= min_score
            ]

            # Log filtering with details
            filtered_count = len(results) - len(filtered_results)
            if filtered_count > 0:
                logger.info(
                    f"🔍 THRESHOLD: Filtered {filtered_count} products below threshold | "
                    f"Top Score: {top_score:.2f} | "
                    f"Threshold: {threshold_percent}% | "
                    f"Min Score: {min_score:.2f} | "
                    f"Kept: {len(filtered_results)}/{len(results)}"
                )

                # DEBUG: Show filtered products
                filtered_products = [r for r in results if r.consolidated_score < min_score]
                logger.info(f"❌ FILTERED OUT ({len(filtered_products)} products):")
                for idx, product in enumerate(filtered_products[:5], 1):  # Show first 5
                    logger.info(
                        f"   {idx}. {product.name} (GIN: {product.gin}) | "
                        f"Score: {product.consolidated_score:.2f} (< {min_score:.2f})"
                    )
            else:
                logger.debug(
                    f"All {len(results)} products meet threshold "
                    f"(>= {min_score:.2f})"
                )

            return filtered_results

        except Exception as e:
            logger.error(f"Error applying score threshold: {e}", exc_info=True)
            return results  # Return unfiltered on error

    def _normalize_scores(self, results: List[ConsolidatedResult]) -> None:
        """
        Normalize consolidated scores (optional, based on configuration).

        Args:
            results: List of ConsolidatedResult objects (modified in-place)
        """
        if self.normalization == "none" or not results:
            return

        scores = [r.consolidated_score for r in results]

        if self.normalization == "min_max":
            # Min-Max normalization to [0, 1]
            min_score = min(scores)
            max_score = max(scores)
            score_range = max_score - min_score

            if score_range > 0:
                for result in results:
                    result.consolidated_score = (result.consolidated_score - min_score) / score_range

        elif self.normalization == "z_score":
            # Z-score normalization
            mean_score = sum(scores) / len(scores)
            variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
            std_dev = variance ** 0.5

            if std_dev > 0:
                for result in results:
                    z_score = (result.consolidated_score - mean_score) / std_dev
                    # Convert z-score to [0, 1] range (approximately)
                    result.consolidated_score = (z_score + 3) / 6  # Assuming ±3σ range

    def get_strategy_coverage_report(
        self,
        results: List[ConsolidatedResult]
    ) -> Dict[str, Any]:
        """
        Generate coverage report showing which strategies found which products.

        Args:
            results: List of ConsolidatedResult objects

        Returns:
            Coverage statistics dict
        """
        if not results:
            return {
                "total_products": 0,
                "strategy_coverage": {},
                "products_found_by_multiple_strategies": 0
            }

        strategy_coverage = defaultdict(int)
        multiple_strategy_count = 0

        for result in results:
            for strategy_name in result.found_by_strategies:
                strategy_coverage[strategy_name] += 1

            if len(result.found_by_strategies) > 1:
                multiple_strategy_count += 1

        return {
            "total_products": len(results),
            "strategy_coverage": dict(strategy_coverage),
            "products_found_by_multiple_strategies": multiple_strategy_count,
            "overlap_percentage": (
                (multiple_strategy_count / len(results) * 100)
                if results else 0
            )
        }
