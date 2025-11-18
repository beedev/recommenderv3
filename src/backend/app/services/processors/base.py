"""
Base State Processor

Abstract base class defining the interface for all state processors.
Each state in the S1→SN flow has a dedicated processor.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum

from app.services.config.configuration_service import get_config_service

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

    def get_next_state(
        self,
        conversation_state,
        selection_made: bool = False
    ) -> str:
        """
        Determine the next state after this state.

        **DEFAULT IMPLEMENTATION**: Delegates to conversation_state.get_next_state() which uses
        the centralized StateManager. This ensures consistency with the configured state sequence
        and eliminates duplicate state transition logic.

        Subclasses CAN override this method if they need custom state transition logic,
        but in most cases the default delegation is sufficient and recommended.

        Args:
            conversation_state: Current ConversationState (with get_next_state() method)
            selection_made: True if user just made a selection, False if skipping

        Returns:
            Next ConfiguratorState enum value (as string)

        Example:
            >>> # Default behavior (delegation to StateManager)
            >>> next_state = processor.get_next_state(conversation_state, selection_made=True)
            >>> # StateManager automatically skips non-applicable states based on applicability flags
        """
        # Default implementation: Delegate to ConversationState which uses StateManager
        # This ensures consistency with the centralized state transition logic
        try:
            next_state_enum = conversation_state.get_next_state()

            if next_state_enum is None:
                logger.warning(
                    f"{self.__class__.__name__}.get_next_state(): "
                    f"conversation_state.get_next_state() returned None, defaulting to 'finalize'"
                )
                return "finalize"

            # Extract string value from enum
            next_state_value = next_state_enum.value if hasattr(next_state_enum, 'value') else str(next_state_enum)

            logger.info(
                f"{self.__class__.__name__}.get_next_state(): "
                f"Delegated to StateManager → {next_state_value}"
            )

            return next_state_value

        except Exception as e:
            logger.error(
                f"{self.__class__.__name__}.get_next_state() delegation error: {e}",
                exc_info=True
            )
            # Fallback to finalize on error
            return "finalize"

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
            execution_time_ms: Execution time in milliseconds (can be None)
        """
        # Handle None execution_time_ms gracefully
        time_str = f"{execution_time_ms:.2f}ms" if execution_time_ms is not None else "N/A"
        logger.info(
            f"{self.__class__.__name__} search completed: "
            f"{total_count} products in {time_str}"
        )

    def is_conditional_accessory(self) -> bool:
        """
        Check if this state processor handles conditional accessories.

        Conditional accessories are accessories that depend on other accessories being selected:
        - feeder_conditional_accessories: Depends on feeder_accessories
        - remote_conditional_accessories: Depends on remote_accessories

        Returns:
            True if this is a conditional accessory state, False otherwise

        Examples:
            >>> processor.component_type
            'feeder_conditional_accessories'
            >>> processor.is_conditional_accessory()
            True
        """
        conditional_types = {
            "feeder_conditional_accessories",
            "remote_conditional_accessories"
        }
        return self.component_type in conditional_types

    def check_dependencies_satisfied(
        self,
        selected_components: Any
    ) -> Tuple[bool, List[str], Dict[str, str]]:
        """
        Check if dependencies for this state are satisfied.

        For conditional accessories, validates that prerequisite accessories are selected
        and collects parent product information for attribution.

        Args:
            selected_components: ResponseJSON object with selected products

        Returns:
            Tuple of (satisfied, missing_deps, parent_info):
                - satisfied: True if all dependencies met
                - missing_deps: List of missing dependency keys
                - parent_info: Dict mapping parent GINs to names for attribution
                  Example: {"ACC1_GIN": "RobustFeed Drive Roll Kit"}

        Examples:
            >>> satisfied, missing, parents = processor.check_dependencies_satisfied(response_json)
            >>> if not satisfied:
            ...     print(f"Missing dependencies: {missing}")
            >>> elif len(parents) > 0:
            ...     print(f"Ready to show conditional accessories for {len(parents)} parents")
        """
        config_service = get_config_service()
        return config_service.check_dependencies_satisfied(
            self.component_type,
            selected_components
        )
