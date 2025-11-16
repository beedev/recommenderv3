"""
Search Package

Pluggable search architecture with multiple strategies:
- CypherSearchStrategy: Neo4j graph-based compatibility search
- LuceneSearchStrategy: Full-text relevance search
- VectorSearchStrategy: Semantic similarity search using embeddings
- Future: HybridSearchStrategy, etc.

Consolidates results with configurable weights and unified ranking.
"""

from .strategies.base import SearchStrategy, StrategySearchResult
from .strategies.cypher_strategy import CypherSearchStrategy
from .strategies.lucene_strategy import LuceneSearchStrategy
from .strategies.vector_strategy import VectorSearchStrategy
from .consolidator import ResultConsolidator, ConsolidatedResult
from .orchestrator import SearchOrchestrator
from .registry import SearchStrategyRegistry

__all__ = [
    "SearchStrategy",
    "StrategySearchResult",
    "CypherSearchStrategy",
    "LuceneSearchStrategy",
    "VectorSearchStrategy",
    "ResultConsolidator",
    "ConsolidatedResult",
    "SearchOrchestrator",
    "SearchStrategyRegistry",
]
