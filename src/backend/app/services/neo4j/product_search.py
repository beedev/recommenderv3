"""
Refactored Neo4j Product Search Service
Delegates to ComponentSearchService for all search operations
Eliminates code duplication through configuration-driven approach
"""

import logging
from typing import Dict, List, Optional, Any

from app.models.product_search import ProductResult, SearchResults
from app.services.search.components import ComponentSearchService

logger = logging.getLogger(__name__)


# ============================================================================
# Neo4jProductSearch - Thin facade over ComponentSearchService
# ============================================================================

class Neo4jProductSearch:
    """
    Neo4j product search service - thin facade over ComponentSearchService.

    Provides backward-compatible API while delegating all search logic to
    the generic ComponentSearchService.

    ALL DEPRECATED METHODS REMOVED:
    - search_power_source_lucene (use LuceneStrategy instead)
    - search_power_source_smart (use SmartStrategy instead)
    - search_feeder_lucene (use LuceneStrategy instead)
    - search_feeder_smart (use SmartStrategy instead)
    - search_cooler_lucene (use LuceneStrategy instead)
    - search_cooler_smart (use SmartStrategy instead)
    - search_torch_lucene (use LuceneStrategy instead)
    - search_torch_smart (use SmartStrategy instead)
    - search_remote_lucene (use LuceneStrategy instead)
    - search_remote_smart (use SmartStrategy instead)
    - search_interconnector_lucene (use LuceneStrategy instead)
    - search_interconnector_smart (use SmartStrategy instead)
    - search_powersource_accessories_smart (use SmartStrategy instead)
    - search_feeder_accessories_smart (use SmartStrategy instead)
    - search_feeder_wears (removed - not required)
    """

    def __init__(self, driver):
        """
        Initialize Neo4jProductSearch with shared driver.

        Args:
            driver: Neo4j AsyncDriver instance from neo4j_manager

        Note:
            Driver is managed externally by neo4j_manager - this class does not own it.
            Do not close the driver from this class.
        """
        self.driver = driver
        self.component_service = ComponentSearchService(self.driver)
        logger.info("Neo4jProductSearch initialized with shared driver")

    # ============================================================================
    # Core Component Search Methods (S1→S5)
    # ============================================================================

    async def search_power_source(
        self,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> SearchResults:
        """
        S1: Search for power sources.

        Args:
            master_parameters: MasterParameterJSON dict
            selected_components: ResponseJSON dict
            limit: Maximum results
            offset: Pagination offset

        Returns:
            SearchResults with power sources
        """
        return await self.component_service.search(
            component_type="power_source",
            master_parameters=master_parameters,
            selected_components=selected_components,
            limit=limit,
            offset=offset
        )

    async def search_feeder(
        self,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> SearchResults:
        """
        S2: Search for feeders compatible with selected power source.

        Args:
            master_parameters: MasterParameterJSON dict
            selected_components: ResponseJSON dict with PowerSource
            limit: Maximum results
            offset: Pagination offset

        Returns:
            SearchResults with compatible feeders
        """
        return await self.component_service.search(
            component_type="feeder",
            master_parameters=master_parameters,
            selected_components=selected_components,
            limit=limit,
            offset=offset
        )

    async def search_cooler(
        self,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> SearchResults:
        """
        S3: Search for coolers compatible with selected power source.

        Args:
            master_parameters: MasterParameterJSON dict
            selected_components: ResponseJSON dict with PowerSource
            limit: Maximum results
            offset: Pagination offset

        Returns:
            SearchResults with compatible coolers
        """
        return await self.component_service.search(
            component_type="cooler",
            master_parameters=master_parameters,
            selected_components=selected_components,
            limit=limit,
            offset=offset
        )

    async def search_interconnector(
        self,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> SearchResults:
        """
        S4: Search for interconnectors compatible with selected components.

        Interconnectors must be compatible with:
        - PowerSource (mandatory)
        - Feeder (if selected)
        - Cooler (if selected)

        Args:
            master_parameters: MasterParameterJSON dict
            selected_components: ResponseJSON dict with selected components
            limit: Maximum results
            offset: Pagination offset

        Returns:
            SearchResults with compatible interconnectors
        """
        return await self.component_service.search(
            component_type="interconnector",
            master_parameters=master_parameters,
            selected_components=selected_components,
            limit=limit,
            offset=offset
        )

    async def search_torch(
        self,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> SearchResults:
        """
        S5: Search for torches compatible with selected feeder.

        Args:
            master_parameters: MasterParameterJSON dict
            selected_components: ResponseJSON dict with Feeder
            limit: Maximum results
            offset: Pagination offset

        Returns:
            SearchResults with compatible torches
        """
        return await self.component_service.search(
            component_type="torch",
            master_parameters=master_parameters,
            selected_components=selected_components,
            limit=limit,
            offset=offset
        )

    # ============================================================================
    # Accessory Search Methods (S6)
    # ============================================================================

    async def search_powersource_accessories(
        self,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> SearchResults:
        """
        Search for power source accessories.

        Args:
            master_parameters: MasterParameterJSON dict
            selected_components: ResponseJSON dict with PowerSource
            limit: Maximum results
            offset: Pagination offset

        Returns:
            SearchResults with power source accessories
        """
        return await self.component_service.search(
            component_type="powersource_accessories",
            master_parameters=master_parameters,
            selected_components=selected_components,
            limit=limit,
            offset=offset
        )

    async def search_feeder_accessories(
        self,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> SearchResults:
        """
        Search for feeder accessories.

        Args:
            master_parameters: MasterParameterJSON dict
            selected_components: ResponseJSON dict with Feeder
            limit: Maximum results
            offset: Pagination offset

        Returns:
            SearchResults with feeder accessories
        """
        return await self.component_service.search(
            component_type="feeder_accessories",
            master_parameters=master_parameters,
            selected_components=selected_components,
            limit=limit,
            offset=offset
        )

    async def search_powersource_conditional_accessories(
        self,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> SearchResults:
        """
        Search for power source conditional accessories.

        Args:
            master_parameters: MasterParameterJSON dict
            selected_components: ResponseJSON dict with PowerSource
            limit: Maximum results
            offset: Pagination offset

        Returns:
            SearchResults with power source conditional accessories
        """
        # Note: Conditional accessories use same component type as base accessories
        # Differentiation happens via master_parameters or query logic
        return await self.component_service.search(
            component_type="powersource_accessories",
            master_parameters=master_parameters,
            selected_components=selected_components,
            limit=limit,
            offset=offset
        )

    async def search_feeder_conditional_accessories(
        self,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> SearchResults:
        """
        Search for feeder conditional accessories.

        Args:
            master_parameters: MasterParameterJSON dict
            selected_components: ResponseJSON dict with Feeder + FeederAccessory
            limit: Maximum results
            offset: Pagination offset

        Returns:
            SearchResults with feeder conditional accessories
        """
        return await self.component_service.search(
            component_type="feeder_conditional_accessories",
            master_parameters=master_parameters,
            selected_components=selected_components,
            limit=limit,
            offset=offset
        )

    async def search_remotes(
        self,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> SearchResults:
        """
        Search for remote controls.

        Remotes are compatible with PowerSource and/or Feeder.

        Args:
            master_parameters: MasterParameterJSON dict
            selected_components: ResponseJSON dict with PowerSource/Feeder
            limit: Maximum results
            offset: Pagination offset

        Returns:
            SearchResults with remote controls
        """
        return await self.component_service.search(
            component_type="remote",
            master_parameters=master_parameters,
            selected_components=selected_components,
            limit=limit,
            offset=offset
        )

    async def search_remote_accessories(
        self,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> SearchResults:
        """
        Search for remote accessories.

        Args:
            master_parameters: MasterParameterJSON dict
            selected_components: ResponseJSON dict with Remote
            limit: Maximum results
            offset: Pagination offset

        Returns:
            SearchResults with remote accessories
        """
        return await self.component_service.search(
            component_type="remote_accessories",
            master_parameters=master_parameters,
            selected_components=selected_components,
            limit=limit,
            offset=offset
        )

    async def search_remote_conditional_accessories(
        self,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> SearchResults:
        """
        Search for remote conditional accessories.

        Args:
            master_parameters: MasterParameterJSON dict
            selected_components: ResponseJSON dict with Remote
            limit: Maximum results
            offset: Pagination offset

        Returns:
            SearchResults with remote conditional accessories
        """
        return await self.component_service.search(
            component_type="remote_conditional_accessories",
            master_parameters=master_parameters,
            selected_components=selected_components,
            limit=limit,
            offset=offset
        )

    async def search_connectivity(
        self,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> SearchResults:
        """
        Search for connectivity accessories.

        Connectivity accessories are compatible with PowerSource and Feeder.

        Args:
            master_parameters: MasterParameterJSON dict
            selected_components: ResponseJSON dict with PowerSource/Feeder
            limit: Maximum results
            offset: Pagination offset

        Returns:
            SearchResults with connectivity accessories
        """
        return await self.component_service.search(
            component_type="connectivity",
            master_parameters=master_parameters,
            selected_components=selected_components,
            limit=limit,
            offset=offset
        )

    async def search_interconn_accessories(
        self,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> SearchResults:
        """
        Search for interconnector accessories.

        Args:
            master_parameters: MasterParameterJSON dict
            selected_components: ResponseJSON dict with Interconnector
            limit: Maximum results
            offset: Pagination offset

        Returns:
            SearchResults with interconnector accessories
        """
        return await self.component_service.search(
            component_type="interconn_accessories",
            master_parameters=master_parameters,
            selected_components=selected_components,
            limit=limit,
            offset=offset
        )

    # ============================================================================
    # Legacy Methods (kept for backward compatibility)
    # ============================================================================

    async def search_accessories(
        self,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> SearchResults:
        """
        Legacy generic accessory search.

        This method is kept for backward compatibility but is no longer used.
        Use specific accessory search methods instead.
        """
        logger.warning(
            "search_accessories() is deprecated. "
            "Use specific accessory search methods instead."
        )
        # Return empty results
        return SearchResults(
            products=[],
            total_count=0,
            filters_applied={"search_method": "deprecated"},
            compatibility_validated=False,
            offset=offset,
            limit=limit,
            has_more=False
        )
