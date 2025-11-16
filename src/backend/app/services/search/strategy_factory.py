"""
Strategy Factory

Automatically discovers and initializes search strategies based on search_config.json.
This eliminates the need to manually modify main.py when adding/removing strategies.

Configuration-Driven Design:
- All strategy settings in search_config.json
- Factory reads config and dynamically imports strategy classes
- Returns list of initialized strategies ready for SearchOrchestrator

Usage:
    from app.services.search.strategy_factory import StrategyFactory

    factory = StrategyFactory(search_config, neo4j_search)
    strategies = factory.create_all_strategies()

    orchestrator = SearchOrchestrator(
        strategies=strategies,
        ...
    )
"""

import logging
from typing import List, Dict, Any, Optional
from importlib import import_module

from .strategies.base import SearchStrategy

logger = logging.getLogger(__name__)


class StrategyFactory:
    """
    Factory for creating search strategies from configuration.

    Supports:
    - Dynamic strategy discovery from search_config.json
    - Automatic class import and instantiation
    - Dependency injection (neo4j_search, openai_client)
    - Graceful error handling for missing strategies
    """

    # Strategy class mapping (strategy_name -> module.ClassName)
    STRATEGY_CLASSES = {
        "cypher": ("app.services.search.strategies.cypher_strategy", "CypherSearchStrategy"),
        "lucene": ("app.services.search.strategies.lucene_strategy", "LuceneSearchStrategy"),
        "vector": ("app.services.search.strategies.vector_strategy", "VectorSearchStrategy"),
        "llm": ("app.services.search.strategies.llm_strategy", "LLMSearchStrategy"),
    }

    def __init__(
        self,
        search_config: Dict[str, Any],
        neo4j_product_search,
        openai_client: Optional[Any] = None
    ):
        """
        Initialize strategy factory.

        Args:
            search_config: Full search_config.json dict
            neo4j_product_search: Neo4jProductSearch instance
            openai_client: Optional AsyncOpenAI client (for vector/llm)
        """
        self.search_config = search_config
        self.neo4j_search = neo4j_product_search
        self.openai_client = openai_client
        self.strategies_config = search_config.get("strategies", {})

        logger.info(f"StrategyFactory initialized with {len(self.strategies_config)} strategy configs")

    def create_all_strategies(self) -> List[SearchStrategy]:
        """
        Create all strategies defined in search_config.json.

        Only creates strategies where:
        1. Strategy is defined in STRATEGY_CLASSES mapping
        2. Strategy has a config entry in search_config.json

        Note: Individual strategy "enabled" flag is respected by the strategy itself.
              The orchestrator will filter based on this flag.

        Returns:
            List of initialized SearchStrategy instances
        """
        strategies = []

        for strategy_name, strategy_config in self.strategies_config.items():
            try:
                strategy = self.create_strategy(strategy_name, strategy_config)
                if strategy:
                    strategies.append(strategy)
                    logger.info(f"  ✅ Created {strategy_name} strategy")
            except Exception as e:
                logger.error(f"  ❌ Failed to create {strategy_name} strategy: {e}", exc_info=True)
                # Continue with other strategies (graceful degradation)

        logger.info(f"StrategyFactory created {len(strategies)} strategies: {[s.get_name() for s in strategies]}")
        return strategies

    def create_strategy(
        self,
        strategy_name: str,
        strategy_config: Dict[str, Any]
    ) -> Optional[SearchStrategy]:
        """
        Create a single strategy instance.

        Args:
            strategy_name: Strategy name (e.g., "cypher", "lucene", "vector", "llm")
            strategy_config: Configuration dict from search_config.json

        Returns:
            SearchStrategy instance or None if strategy not found
        """
        # Check if strategy is in our mapping
        if strategy_name not in self.STRATEGY_CLASSES:
            logger.warning(f"Unknown strategy '{strategy_name}' - skipping")
            return None

        # Get module and class name
        module_path, class_name = self.STRATEGY_CLASSES[strategy_name]

        # Dynamically import strategy class
        try:
            module = import_module(module_path)
            strategy_class = getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            logger.error(f"Failed to import {class_name} from {module_path}: {e}")
            return None

        # Prepare initialization arguments
        init_kwargs = {
            "config": strategy_config,
            "neo4j_product_search": self.neo4j_search
        }

        # Add OpenAI client for strategies that need it (vector, llm)
        if strategy_name in ["vector", "llm"] and self.openai_client:
            init_kwargs["openai_client"] = self.openai_client

        # Instantiate strategy
        try:
            strategy = strategy_class(**init_kwargs)
            return strategy
        except Exception as e:
            logger.error(f"Failed to instantiate {class_name}: {e}", exc_info=True)
            return None

    def get_enabled_strategies(self, strategies: List[SearchStrategy]) -> List[SearchStrategy]:
        """
        Filter strategies to only those that are enabled.

        Args:
            strategies: List of all strategy instances

        Returns:
            List of enabled strategies only
        """
        enabled = [s for s in strategies if s.is_enabled()]
        logger.info(f"Enabled strategies: {[s.get_name() for s in enabled]}")
        return enabled
