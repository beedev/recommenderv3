"""
Base State Processor

Abstract base class defining the interface for all state processors.
Each state in the S1→SN flow has a dedicated processor.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class StateProcessor(ABC):
    """
    Abstract base class for state processors.

    Each state processor handles:
    1. Product search for its component type
    2. State transition logic (which state comes next)
    3. Selection validation (single-select vs multi-select)
    4. Proactive preview generation for next state
    5. Zero-results handling with context-aware messages
    """

    def __init__(
        self,
        state_name: str,
        component_type: str,
        state_config: Dict[str, Any],
        search_orchestrator
    ):
        """
        Initialize state processor.

        Args:
            state_name: ConfiguratorState enum value (e.g., "power_source_selection")
            component_type: Component type key (e.g., "PowerSource", "Feeder")
            state_config: Configuration from state_config.json for this state
            search_orchestrator: SearchOrchestrator instance for executing searches
        """
        self.state_name = state_name
        self.component_type = component_type
        self.state_config = state_config
        self.search_orchestrator = search_orchestrator

        # Extract configuration
        self.mandatory = state_config.get("mandatory", False)
        self.proactive_display = state_config.get("proactive_display", False)
        self.search_limit = state_config.get("search_limit", 10)
        self.multi_select = state_config.get("multi_select", False)
        self.allow_skip = state_config.get("allow_skip", True)

        logger.info(
            f"{self.__class__.__name__} initialized "
            f"(mandatory={self.mandatory}, multi_select={self.multi_select})"
        )

    @abstractmethod
    async def search_products(
        self,
        user_message: str,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: Optional[int] = None,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Search for products for this state's component type.

        Args:
            user_message: Raw user message
            master_parameters: LLM-extracted parameters (MasterParameterJSON)
            selected_components: Already selected components (ResponseJSON)
            limit: Max results to return (overrides state_config.search_limit)
            offset: Pagination offset

        Returns:
            Search results dict from SearchOrchestrator:
            {
                "products": List[Dict],
                "total_count": int,
                "offset": int,
                "limit": int,
                "has_more": bool,
                "metadata": {...},
                "zero_results_message": Optional[str]
            }
        """
        pass

    @abstractmethod
    def get_next_state(
        self,
        conversation_state,
        selection_made: bool = False
    ) -> str:
        """
        Determine the next state after this state.

        Args:
            conversation_state: Current ConversationState
            selection_made: True if user just made a selection, False if skipping

        Returns:
            Next ConfiguratorState enum value (as string)
        """
        pass

    def validate_selection(
        self,
        product_gin: str,
        product_data: Dict[str, Any],
        selected_components: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Validate a product selection for this state.

        Args:
            product_gin: GIN of product being selected
            product_data: Product data dict
            selected_components: Already selected components

        Returns:
            (is_valid, error_message)
        """
        # Default: All selections valid
        # Subclasses can override for custom validation
        return True, None

    def can_skip(self) -> bool:
        """
        Check if this state can be skipped.

        Returns:
            True if allow_skip=true in config, False otherwise
        """
        return self.allow_skip

    def is_multi_select(self) -> bool:
        """
        Check if this state allows selecting multiple products.

        Returns:
            True if multi_select=true in config, False otherwise
        """
        return self.multi_select

    def is_mandatory(self) -> bool:
        """
        Check if this state is mandatory (must select before finalize).

        Returns:
            True if mandatory=true in config, False otherwise
        """
        return self.mandatory

    def should_show_proactive_preview(self) -> bool:
        """
        Check if proactive preview should be shown after selection.

        Returns:
            True if proactive_display=true in config, False otherwise
        """
        return self.proactive_display

    async def get_proactive_preview(
        self,
        user_message: str,
        master_parameters: Dict[str, Any],
        selected_components: Dict[str, Any],
        limit: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate proactive preview for this state (shown after previous state selection).

        PREVIEW vs REGULAR search:
        - PREVIEW: Automatic display after selection (smaller limit, quick preview)
        - REGULAR: User explicitly requests products (larger limit, comprehensive)

        Args:
            user_message: Raw user message
            master_parameters: LLM-extracted parameters
            selected_components: Already selected components for compatibility
            limit: Max preview products (if None, uses preview_limit from config)

        Returns:
            Preview search results or None if proactive_display=false
        """
        if not self.proactive_display:
            return None

        try:
            # Get preview limit from config (fallback to search_limit / 2 if not set)
            if limit is None:
                limit = self.state_config.get("preview_limit", self.search_limit // 2)

            logger.info(
                f"Generating proactive preview for {self.state_name} "
                f"(preview_limit={limit}, regular_limit={self.search_limit})"
            )

            # Execute search with smaller limit for preview
            preview_results = await self.search_products(
                user_message=user_message,
                master_parameters=master_parameters,
                selected_components=selected_components,
                limit=limit,
                offset=0
            )

            logger.info(
                f"Proactive preview generated: {preview_results.get('total_count', 0)} products "
                f"for {self.state_name}"
            )

            return preview_results

        except Exception as e:
            logger.error(f"Error generating proactive preview for {self.state_name}: {e}")
            return None

    def get_component_display_name(self) -> str:
        """
        Get human-readable display name for this component type.

        Returns:
            Display name (e.g., "Power Source", "Feeder", "Cooler")
        """
        return self.state_config.get("state_name", self.component_type)

    def generate_selection_message(
        self,
        product: Dict[str, Any],
        is_multi_select: bool = False
    ) -> str:
        """
        Generate confirmation message for product selection.

        Args:
            product: Selected product dict
            is_multi_select: True if this is part of multi-select

        Returns:
            Confirmation message
        """
        product_name = product.get("name", "Unknown")
        gin = product.get("gin", "")

        if is_multi_select:
            return f"✅ Added {product_name} (GIN: {gin}) to selection"
        else:
            return f"✅ {self.get_component_display_name()}: {product_name} (GIN: {gin}) selected"

    def generate_skip_message(self) -> str:
        """
        Generate message when user skips this state.

        Returns:
            Skip confirmation message
        """
        return f"⏭️ Skipped {self.get_component_display_name()} selection"

    def _get_search_limit(self, override_limit: Optional[int] = None) -> int:
        """
        Get search limit (from override or config).

        Args:
            override_limit: Optional limit override

        Returns:
            Search limit to use
        """
        return override_limit if override_limit is not None else self.search_limit

    def _log_search(self, total_count: int, execution_time_ms: float):
        """
        Log search execution details.

        Args:
            total_count: Number of products found
            execution_time_ms: Execution time in milliseconds
        """
        logger.info(
            f"{self.__class__.__name__} search completed: "
            f"{total_count} products in {execution_time_ms:.2f}ms"
        )
