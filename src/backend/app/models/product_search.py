"""
Product Search Data Models

Shared data models for product search results used across the application.
These models are imported by both Neo4jProductSearch and ComponentSearchService
to avoid circular imports.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel


class ProductResult(BaseModel):
    """Single product search result"""
    gin: str
    name: str
    category: str
    description: Optional[str] = None
    specifications: Dict[str, Any] = {}
    priority: Optional[int] = None  # Priority from COMPATIBLE_WITH relationship (lower = better)


class SearchResults(BaseModel):
    """Search results with metadata"""
    products: List[ProductResult]
    total_count: int
    filters_applied: Dict[str, Any]
    compatibility_validated: bool = False
    # Pagination fields
    offset: int = 0
    limit: int = 10
    has_more: bool = False  # Indicates if there are more results beyond current page
