"""
Base Search Strategy Interface

Defines the abstract interface for all product search strategies.
Strategies can be Cypher-based, Lucene-based, Vector-based, or any future implementation.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class StrategySearchResult(BaseModel):
    """
    Standardized search result from a strategy.

    Attributes:
        products: List of product dictionaries from the strategy
        scores: Optional dict mapping GIN to relevance score (0.0-1.0)
        metadata: Additional metadata about the search (e.g., execution time, query used)
        strategy_name: Name of the strategy that produced these results
    """
    products: List[Dict[str, Any]] = Field(default_factory=list)
    scores: Optional[Dict[str, float]] = None  # GIN -> score mapping
    metadata: Dict[str, Any] = Field(default_factory=dict)
    strategy_name: str

    class Config:
        arbitrary_types_allowed = True


class SearchStrategy(ABC):
    """
    Abstract base class for all search strategies.

    Each strategy implements a different approach to searching products:
    - CypherSearchStrategy: Neo4j graph-based compatibility search
    - LuceneSearchStrategy: Full-text search with relevance ranking
    - VectorSearchStrategy: Semantic similarity search (future)
    - HybridSearchStrategy: Combination of multiple approaches (future)
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize strategy with configuration.

        Args:
            config: Strategy-specific configuration from search_config.json
        """
        self.config = config
        self.enabled = config.get("enabled", True)
        self.weight = config.get("weight", 1.0)

    @abstractmethod
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
        Execute search using this strategy.

        Args:
            component_type: Type of component to search (PowerSource, Feeder, Cooler, etc.)
            user_message: Raw user input message
            master_parameters: Extracted parameters from LLM (MasterParameterJSON)
            selected_components: Already selected components (ResponseJSON)
            limit: Maximum number of results to return
            offset: Pagination offset

        Returns:
            StrategySearchResult with products, scores, and metadata
        """
        pass

    @abstractmethod
    async def validate_compatibility(
        self,
        product_gin: str,
        selected_components: Dict[str, Any]
    ) -> bool:
        """
        Validate if a product is compatible with already selected components.

        Args:
            product_gin: GIN of product to validate
            selected_components: Already selected components (ResponseJSON)

        Returns:
            True if compatible, False otherwise
        """
        pass

    def is_enabled(self) -> bool:
        """
        Check if this strategy is enabled in configuration.

        Returns:
            True if enabled, False otherwise
        """
        return self.enabled

    def get_weight(self) -> float:
        """
        Get the weight/importance of this strategy for score consolidation.

        Returns:
            Weight value (typically 0.0-1.0)
        """
        return self.weight

    def get_name(self) -> str:
        """
        Get the name of this strategy.

        Returns:
            Strategy name (e.g., "cypher", "lucene", "vector")
        """
        return self.__class__.__name__.replace("SearchStrategy", "").lower()
