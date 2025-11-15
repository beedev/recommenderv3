"""
Component-based product search services.

This module provides reusable, configuration-driven product search functionality
that eliminates code duplication across component types.
"""

from .query_builder import Neo4jQueryBuilder
from .component_service import ComponentSearchService

__all__ = [
    "Neo4jQueryBuilder",
    "ComponentSearchService",
]
