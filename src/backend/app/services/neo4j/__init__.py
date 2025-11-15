"""Neo4j service package - Product search with compatibility validation"""

from .product_search import Neo4jProductSearch
from app.models.product_search import ProductResult, SearchResults

__all__ = [
    "Neo4jProductSearch",
    "ProductResult",
    "SearchResults"
]
