"""
Auto-Skip Decision Service

Unified service for all auto-skip decision logic across STAGE 1, 2, 3, and 4.
Eliminates code duplication by providing centralized auto-skip checks.

STAGE 1: Pre-search dependency check for conditional accessories
STAGE 2: Post-search zero-results for conditional accessories
STAGE 3: Post-search zero-results for compatibility validation
STAGE 4: Single product auto-advance (UX optimization)

This service provides single source of truth for:
- When to auto-skip a state
- What skip message to show users
- Whether to add parent attribution to products
"""

import logging
from typing import Dict, Any, Optional, Tuple
from app.services.processors.base import StateProcessor

logger = logging.getLogger(__name__)


class AutoSkipDecision:
    """
    Result of an auto-skip decision check.

    Attributes:
        should_skip: True if state should be auto-skipped
        skip_reason: Internal log message explaining why skipped (for debugging)
        skip_message: User-facing message explaining skip (None for silent skip)
        force_parent_attribution: Whether to add parent attribution to next state's products
    """

    def __init__(
        self,
        should_skip: bool,
        skip_reason: Optional[str] = None,
        skip_message: Optional[str] = None,
        force_parent_attribution: bool = False
    ):
        self.should_skip = should_skip
        self.skip_reason = skip_reason
        self.skip_message = skip_message
        self.force_parent_attribution = force_parent_attribution

    def __repr__(self) -> str:
        return (
            f"AutoSkipDecision(should_skip={self.should_skip}, "
            f"skip_reason='{self.skip_reason}', "
            f"skip_message='{self.skip_message}', "
            f"force_parent_attribution={self.force_parent_attribution})"
        )


class AutoSkipService:
    """
    Centralized auto-skip decision engine.

    Handles all 4 stages of auto-skip logic:
    - STAGE 1: Pre-search dependency check
    - STAGE 2: Post-search zero-results for conditional accessories
    - STAGE 3: Post-search zero-results for compatibility validation
    - STAGE 4: Single product auto-advance (UX optimization)

    Eliminates ~150 lines of duplicated code across 4 locations in state_orchestrator.py.
    """

    def should_auto_skip_pre_search(
        self,
        processor: StateProcessor,
        selected_components: Any,
        current_state: str
    ) -> AutoSkipDecision:
        """
        STAGE 1: Check if state should be auto-skipped BEFORE search.

        For conditional accessories, validates that prerequisite components are selected
        before attempting product search.

        Args:
            processor: StateProcessor for current state
            selected_components: ResponseJSON with selected components
            current_state: Current state name (for logging)

        Returns:
            AutoSkipDecision with skip decision and metadata

        Example:
            >>> decision = service.should_auto_skip_pre_search(processor, response_json, "feeder_conditional_accessories")
            >>> if decision.should_skip:
            ...     logger.info(decision.skip_reason)
            ...     # Advance to next state
        """
        # Only applies to conditional accessories
        if not processor.is_conditional_accessory():
            return AutoSkipDecision(should_skip=False)

        # Check if dependencies are satisfied
        satisfied, missing_deps, parent_info = processor.check_dependencies_satisfied(
            selected_components
        )

        if satisfied:
            # Dependencies satisfied, proceed with search
            return AutoSkipDecision(should_skip=False)

        # Dependencies NOT satisfied - auto-skip this state
        logger.info(
            f"⏭️  STAGE 1 AUTO-SKIP: Dependencies not satisfied for {current_state}. "
            f"Missing: {missing_deps}. Advancing to next state."
        )

        skip_reason = (
            f"STAGE 1 (Pre-search): Dependencies not satisfied for {current_state}. "
            f"Missing: {missing_deps}"
        )

        # No user-facing message for STAGE 1 (silent skip)
        # Parent attribution will be added when advancing to next state
        return AutoSkipDecision(
            should_skip=True,
            skip_reason=skip_reason,
            skip_message=None,  # Silent skip
            force_parent_attribution=False  # Let next stage decide
        )

    def should_auto_skip_post_search(
        self,
        processor: StateProcessor,
        search_results: Dict[str, Any],
        current_state: str
    ) -> AutoSkipDecision:
        """
        STAGE 2 & 3: Check if state should be auto-skipped AFTER search.

        Two scenarios trigger auto-skip:
        - STAGE 2: Conditional accessory with zero products found
        - STAGE 3: Compatibility validation with zero compatible products

        Args:
            processor: StateProcessor for current state
            search_results: Search results dict from orchestrator.search_products()
            current_state: Current state name (for logging)

        Returns:
            AutoSkipDecision with skip decision and metadata

        Example:
            >>> decision = service.should_auto_skip_post_search(processor, search_results, "feeder")
            >>> if decision.should_skip:
            ...     return await self._auto_skip_to_next_state(
            ...         skip_reason=decision.skip_reason,
            ...         skip_message=decision.skip_message,
            ...         force_parent_attribution=decision.force_parent_attribution
            ...     )
        """
        products = search_results.get("products", [])
        compatibility_validated = search_results.get("compatibility_validated", False)

        # ===== STAGE 2: CONDITIONAL ACCESSORY ZERO-RESULTS CHECK =====
        # For conditional accessories, auto-skip if no conditional products found
        if processor.is_conditional_accessory() and len(products) == 0:
            logger.info(
                f"⏭️  STAGE 2 AUTO-SKIP: Zero conditional accessories found for {current_state}. "
                f"Selected parent accessories have no conditional products."
            )

            skip_reason = (
                f"STAGE 2: Zero conditional accessories found for {current_state}. "
                f"Selected parent accessories have no conditional products."
            )

            # STAGE 2: Silent skip with parent attribution
            return AutoSkipDecision(
                should_skip=True,
                skip_reason=skip_reason,
                skip_message=None,  # No user-facing message for STAGE 2
                force_parent_attribution=True  # STAGE 2 always adds parent attribution
            )

        # ===== STAGE 3: COMPATIBILITY VALIDATION ZERO-RESULTS CHECK =====
        # If compatibility validation was performed but yielded no results, gracefully skip
        # NOTE: Skip STAGE 3 for conditional accessories (they use STAGE 2 instead)
        if compatibility_validated and len(products) == 0 and not processor.is_conditional_accessory():
            component_name = current_state.replace("_", " ").title()
            compatibility_message = (
                f"No compatible {component_name} products were found that work with your selected components. "
                f"Moving to the next step."
            )

            logger.info(
                f"⏭️  STAGE 3 AUTO-SKIP: Compatibility validation for {current_state} yielded no compatible products."
            )

            skip_reason = (
                f"STAGE 3: Compatibility validation for {current_state} yielded no compatible products."
            )

            # STAGE 3: User-facing message explaining compatibility failure
            # Parent attribution only for conditional accessories (but we already excluded them above)
            return AutoSkipDecision(
                should_skip=True,
                skip_reason=skip_reason,
                skip_message=compatibility_message,  # User sees compatibility failure message
                force_parent_attribution=False  # STAGE 3: Only add for conditional accessories
            )

        # No auto-skip needed
        return AutoSkipDecision(should_skip=False)

    def should_auto_advance_single_product(
        self,
        search_results: Dict[str, Any],
        current_state: str
    ) -> AutoSkipDecision:
        """
        STAGE 4: Check if we should auto-advance after selecting the only compatible product.

        When a state has exactly ONE compatible product and user selects it,
        auto-advance to next state instead of waiting for confirmation.

        This is a UX optimization that reduces unnecessary user interactions when
        there's only one choice available.

        Args:
            search_results: Search results dict from processor.search_products()
            current_state: Current state name (for logging)

        Returns:
            AutoSkipDecision with skip decision and metadata

        Example:
            >>> # After product selection in select_product()
            >>> decision = service.should_auto_advance_single_product(next_search_results, next_state)
            >>> if decision.should_skip:
            ...     # Auto-advance to next state instead of waiting for user confirmation
            ...     continue  # Loop will handle advancing
        """
        products = search_results.get("products", [])

        # Only auto-advance if exactly 1 product
        if len(products) == 1:
            logger.info(
                f"⏭️  STAGE 4 AUTO-ADVANCE: Only one compatible product for {current_state}. "
                f"Auto-advancing after selection."
            )

            skip_reason = (
                f"STAGE 4 (Single Product): Only one compatible product for {current_state}. "
                f"Auto-advancing after selection."
            )

            # STAGE 4: Silent auto-advance (no user message, just auto-select and continue)
            return AutoSkipDecision(
                should_skip=True,
                skip_reason=skip_reason,
                skip_message=None,  # Silent auto-advance (UX optimization)
                force_parent_attribution=False
            )

        # Multiple products or zero products, normal flow
        return AutoSkipDecision(should_skip=False)

    def should_add_parent_attribution(
        self,
        processor: StateProcessor,
        skip_stage: str
    ) -> bool:
        """
        Determine if parent attribution should be added to products.

        Parent attribution adds "Compatible with: RobustFeed Drive Roll Kit (GIN: 0558011712)"
        to product descriptions when showing conditional accessories.

        Rules:
        - STAGE 1 (Pre-search): Add for conditional accessories when advancing
        - STAGE 2 (Post-search zero conditional): Always add (show parent context)
        - STAGE 3 (Post-search zero compatibility): Only for conditional accessories
        - Regular search: Add for conditional accessories

        Args:
            processor: StateProcessor for state being displayed
            skip_stage: Which stage triggered the skip ("STAGE1", "STAGE2", "STAGE3", or "NONE")

        Returns:
            True if parent attribution should be added, False otherwise

        Example:
            >>> if service.should_add_parent_attribution(next_processor, "STAGE2"):
            ...     self._add_parent_attribution_to_products(
            ...         next_products, next_processor, conversation_state.response_json
            ...     )
        """
        # STAGE 2: Always add parent attribution (show parent context for conditional accessories)
        if skip_stage == "STAGE2":
            return True

        # STAGE 3: Only add for conditional accessories
        if skip_stage == "STAGE3":
            return processor.is_conditional_accessory()

        # STAGE 1 or regular search: Add for conditional accessories
        return processor.is_conditional_accessory()
