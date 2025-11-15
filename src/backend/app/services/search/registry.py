"""
Search Strategy Registry

Manages registration and retrieval of search strategies.
Configuration-driven enable/disable per strategy.
"""

import logging
from typing import Dict, List, Any, Optional
from .strategies.base import SearchStrategy

logger = logging.getLogger(__name__)


class SearchStrategyRegistry:
    """
    Registry for search strategies.

    Manages:
    - Strategy registration
    - Configuration-based enable/disable
    - Strategy retrieval by name or component type
    """

    def __init__(self):
        """Initialize empty registry"""
        self._strategies: Dict[str, SearchStrategy] = {}
        logger.info("SearchStrategyRegistry initialized")

    def register(self, name: str, strategy: SearchStrategy) -> None:
        """
        Register a search strategy.

        Args:
            name: Strategy name (e.g., "cypher", "lucene", "vector")
            strategy: SearchStrategy instance
        """
        if name in self._strategies:
            logger.warning(f"Overwriting existing strategy: {name}")

        self._strategies[name] = strategy
        logger.info(
            f"Registered strategy '{name}' "
            f"(enabled: {strategy.is_enabled()}, weight: {strategy.get_weight()})"
        )

    def get(self, name: str) -> Optional[SearchStrategy]:
        """
        Get strategy by name.

        Args:
            name: Strategy name

        Returns:
            SearchStrategy instance or None if not found
        """
        return self._strategies.get(name)

    def get_all(self) -> List[SearchStrategy]:
        """
        Get all registered strategies.

        Returns:
            List of all SearchStrategy instances
        """
        return list(self._strategies.values())

    def get_enabled(self) -> List[SearchStrategy]:
        """
        Get only enabled strategies.

        Returns:
            List of enabled SearchStrategy instances
        """
        return [s for s in self._strategies.values() if s.is_enabled()]

    def get_by_component_type(self, component_type: str) -> List[SearchStrategy]:
        """
        Get strategies applicable to a specific component type.

        For now, all strategies work with all component types.
        Future: Could implement component-specific strategy filtering.

        Args:
            component_type: Component type (PowerSource, Feeder, etc.)

        Returns:
            List of applicable SearchStrategy instances
        """
        # Currently all strategies work with all components
        return self.get_enabled()

    def list_strategy_names(self) -> List[str]:
        """
        List all registered strategy names.

        Returns:
            List of strategy names
        """
        return list(self._strategies.keys())

    def get_strategy_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed information about all registered strategies.

        Returns:
            Dict of {strategy_name: {enabled, weight, class_name}}
        """
        return {
            name: {
                "enabled": strategy.is_enabled(),
                "weight": strategy.get_weight(),
                "class_name": strategy.__class__.__name__
            }
            for name, strategy in self._strategies.items()
        }
