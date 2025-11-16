"""
Unit tests for AutoSkipService

Tests all three unified methods:
1. should_auto_skip_pre_search() - STAGE 1 dependency check
2. should_auto_skip_post_search() - STAGE 2 & 3 zero-results checks
3. should_add_parent_attribution() - Parent attribution strategy
"""

import pytest
from unittest.mock import MagicMock
from app.services.orchestrator.auto_skip_service import AutoSkipService, AutoSkipDecision


@pytest.fixture
def auto_skip_service():
    """Create AutoSkipService instance for testing."""
    return AutoSkipService()


@pytest.fixture
def mock_processor():
    """Create mock StateProcessor for testing."""
    processor = MagicMock()
    processor.is_conditional_accessory.return_value = False
    processor.check_dependencies_satisfied.return_value = (True, [], {})
    return processor


@pytest.fixture
def mock_conditional_processor():
    """Create mock StateProcessor for conditional accessories."""
    processor = MagicMock()
    processor.is_conditional_accessory.return_value = True
    processor.check_dependencies_satisfied.return_value = (True, [], {})
    return processor


class TestShouldAutoSkipPreSearch:
    """Tests for should_auto_skip_pre_search() - STAGE 1 dependency check."""

    def test_regular_component_no_skip(self, auto_skip_service, mock_processor):
        """Regular components should never be skipped in STAGE 1."""
        # Arrange
        mock_processor.is_conditional_accessory.return_value = False
        selected_components = {}

        # Act
        decision = auto_skip_service.should_auto_skip_pre_search(
            processor=mock_processor,
            selected_components=selected_components,
            current_state="feeder"
        )

        # Assert
        assert decision.should_skip is False
        assert decision.skip_reason is None
        assert decision.skip_message is None
        mock_processor.check_dependencies_satisfied.assert_not_called()

    def test_conditional_accessory_dependencies_satisfied_no_skip(
        self, auto_skip_service, mock_conditional_processor
    ):
        """Conditional accessories with satisfied dependencies should NOT skip."""
        # Arrange
        mock_conditional_processor.check_dependencies_satisfied.return_value = (
            True,  # satisfied
            [],  # no missing deps
            {"0558011712": "RobustFeed Drive Roll Kit"}  # parent info
        )
        selected_components = {"FeederAccessories": ["0558011712"]}

        # Act
        decision = auto_skip_service.should_auto_skip_pre_search(
            processor=mock_conditional_processor,
            selected_components=selected_components,
            current_state="feeder_conditional_accessories"
        )

        # Assert
        assert decision.should_skip is False
        assert decision.skip_reason is None
        mock_conditional_processor.check_dependencies_satisfied.assert_called_once_with(
            selected_components
        )

    def test_conditional_accessory_dependencies_not_satisfied_skip(
        self, auto_skip_service, mock_conditional_processor
    ):
        """Conditional accessories with UNsatisfied dependencies SHOULD skip."""
        # Arrange
        mock_conditional_processor.check_dependencies_satisfied.return_value = (
            False,  # NOT satisfied
            ["feeder_accessories"],  # missing dep
            {}  # no parent info
        )
        selected_components = {}

        # Act
        decision = auto_skip_service.should_auto_skip_pre_search(
            processor=mock_conditional_processor,
            selected_components=selected_components,
            current_state="feeder_conditional_accessories"
        )

        # Assert
        assert decision.should_skip is True
        assert "STAGE 1" in decision.skip_reason
        assert "Dependencies not satisfied" in decision.skip_reason
        assert "feeder_accessories" in decision.skip_reason
        assert decision.skip_message is None  # Silent skip
        assert decision.force_parent_attribution is False


class TestShouldAutoSkipPostSearch:
    """Tests for should_auto_skip_post_search() - STAGE 2 & 3 checks."""

    def test_regular_component_with_products_no_skip(self, auto_skip_service, mock_processor):
        """Regular components with products should NOT skip."""
        # Arrange
        search_results = {
            "products": [
                {"gin": "0446200880", "name": "Aristo 500ix"},
                {"gin": "0460520880", "name": "RobustFeed U6"}
            ],
            "compatibility_validated": False
        }

        # Act
        decision = auto_skip_service.should_auto_skip_post_search(
            processor=mock_processor,
            search_results=search_results,
            current_state="power_source"
        )

        # Assert
        assert decision.should_skip is False

    def test_conditional_accessory_zero_products_stage2_skip(
        self, auto_skip_service, mock_conditional_processor
    ):
        """Conditional accessories with 0 products should skip (STAGE 2)."""
        # Arrange
        search_results = {
            "products": [],
            "compatibility_validated": False
        }

        # Act
        decision = auto_skip_service.should_auto_skip_post_search(
            processor=mock_conditional_processor,
            search_results=search_results,
            current_state="feeder_conditional_accessories"
        )

        # Assert
        assert decision.should_skip is True
        assert "STAGE 2" in decision.skip_reason
        assert "Zero conditional accessories found" in decision.skip_reason
        assert decision.skip_message is None  # Silent skip
        assert decision.force_parent_attribution is True  # STAGE 2 always adds

    def test_regular_component_zero_products_compatibility_validated_stage3_skip(
        self, auto_skip_service, mock_processor
    ):
        """Regular components with 0 products after compatibility check should skip (STAGE 3)."""
        # Arrange
        search_results = {
            "products": [],
            "compatibility_validated": True  # Compatibility check was performed
        }

        # Act
        decision = auto_skip_service.should_auto_skip_post_search(
            processor=mock_processor,
            search_results=search_results,
            current_state="feeder"
        )

        # Assert
        assert decision.should_skip is True
        assert "STAGE 3" in decision.skip_reason
        assert "Compatibility validation" in decision.skip_reason
        assert decision.skip_message is not None  # User-facing message
        assert "No compatible Feeder products were found" in decision.skip_message
        assert decision.force_parent_attribution is False

    def test_conditional_accessory_compatibility_validated_uses_stage2_not_stage3(
        self, auto_skip_service, mock_conditional_processor
    ):
        """Conditional accessories use STAGE 2 skip, NOT STAGE 3 (even if compatibility_validated=True)."""
        # Arrange
        search_results = {
            "products": [],
            "compatibility_validated": True  # This is ignored for conditional accessories
        }

        # Act
        decision = auto_skip_service.should_auto_skip_post_search(
            processor=mock_conditional_processor,
            search_results=search_results,
            current_state="remote_conditional_accessories"
        )

        # Assert
        # Should use STAGE 2 logic (conditional accessories have priority)
        assert decision.should_skip is True
        assert "STAGE 2" in decision.skip_reason  # NOT STAGE 3
        assert decision.skip_message is None  # Silent skip (STAGE 2 behavior)
        assert decision.force_parent_attribution is True  # STAGE 2 behavior

    def test_regular_component_zero_products_no_compatibility_check_no_skip(
        self, auto_skip_service, mock_processor
    ):
        """Regular components with 0 products but NO compatibility check should NOT skip."""
        # Arrange
        search_results = {
            "products": [],
            "compatibility_validated": False  # No compatibility check performed
        }

        # Act
        decision = auto_skip_service.should_auto_skip_post_search(
            processor=mock_processor,
            search_results=search_results,
            current_state="accessories"
        )

        # Assert
        # No skip because compatibility_validated=False
        # This means the search just didn't find products, not that compatibility failed
        assert decision.should_skip is False


class TestShouldAddParentAttribution:
    """Tests for should_add_parent_attribution() - Parent attribution strategy."""

    def test_stage2_always_adds_parent_attribution(self, auto_skip_service, mock_processor):
        """STAGE 2 should ALWAYS add parent attribution."""
        # Act
        result = auto_skip_service.should_add_parent_attribution(
            processor=mock_processor,
            skip_stage="STAGE2"
        )

        # Assert
        assert result is True

    def test_stage2_conditional_accessory_adds_parent_attribution(
        self, auto_skip_service, mock_conditional_processor
    ):
        """STAGE 2 should add parent attribution even for conditional accessories."""
        # Act
        result = auto_skip_service.should_add_parent_attribution(
            processor=mock_conditional_processor,
            skip_stage="STAGE2"
        )

        # Assert
        assert result is True

    def test_stage3_regular_component_no_parent_attribution(
        self, auto_skip_service, mock_processor
    ):
        """STAGE 3 should NOT add parent attribution for regular components."""
        # Act
        result = auto_skip_service.should_add_parent_attribution(
            processor=mock_processor,
            skip_stage="STAGE3"
        )

        # Assert
        assert result is False

    def test_stage3_conditional_accessory_adds_parent_attribution(
        self, auto_skip_service, mock_conditional_processor
    ):
        """STAGE 3 should add parent attribution for conditional accessories."""
        # Act
        result = auto_skip_service.should_add_parent_attribution(
            processor=mock_conditional_processor,
            skip_stage="STAGE3"
        )

        # Assert
        assert result is True

    def test_stage1_regular_component_no_parent_attribution(
        self, auto_skip_service, mock_processor
    ):
        """STAGE 1 should NOT add parent attribution for regular components."""
        # Act
        result = auto_skip_service.should_add_parent_attribution(
            processor=mock_processor,
            skip_stage="STAGE1"
        )

        # Assert
        assert result is False

    def test_stage1_conditional_accessory_adds_parent_attribution(
        self, auto_skip_service, mock_conditional_processor
    ):
        """STAGE 1 should add parent attribution for conditional accessories."""
        # Act
        result = auto_skip_service.should_add_parent_attribution(
            processor=mock_conditional_processor,
            skip_stage="STAGE1"
        )

        # Assert
        assert result is True

    def test_no_skip_regular_component_no_parent_attribution(
        self, auto_skip_service, mock_processor
    ):
        """Regular search (no skip) should NOT add parent attribution for regular components."""
        # Act
        result = auto_skip_service.should_add_parent_attribution(
            processor=mock_processor,
            skip_stage="NONE"
        )

        # Assert
        assert result is False

    def test_no_skip_conditional_accessory_adds_parent_attribution(
        self, auto_skip_service, mock_conditional_processor
    ):
        """Regular search (no skip) should add parent attribution for conditional accessories."""
        # Act
        result = auto_skip_service.should_add_parent_attribution(
            processor=mock_conditional_processor,
            skip_stage="NONE"
        )

        # Assert
        assert result is True


class TestAutoSkipDecision:
    """Tests for AutoSkipDecision data class."""

    def test_decision_no_skip(self):
        """Test creating decision with no skip."""
        # Act
        decision = AutoSkipDecision(should_skip=False)

        # Assert
        assert decision.should_skip is False
        assert decision.skip_reason is None
        assert decision.skip_message is None
        assert decision.force_parent_attribution is False

    def test_decision_stage1_skip(self):
        """Test creating decision for STAGE 1 skip."""
        # Act
        decision = AutoSkipDecision(
            should_skip=True,
            skip_reason="STAGE 1: Dependencies not satisfied",
            skip_message=None,  # Silent skip
            force_parent_attribution=False
        )

        # Assert
        assert decision.should_skip is True
        assert decision.skip_reason == "STAGE 1: Dependencies not satisfied"
        assert decision.skip_message is None
        assert decision.force_parent_attribution is False

    def test_decision_stage2_skip(self):
        """Test creating decision for STAGE 2 skip."""
        # Act
        decision = AutoSkipDecision(
            should_skip=True,
            skip_reason="STAGE 2: Zero conditional accessories",
            skip_message=None,  # Silent skip
            force_parent_attribution=True
        )

        # Assert
        assert decision.should_skip is True
        assert decision.skip_reason == "STAGE 2: Zero conditional accessories"
        assert decision.skip_message is None
        assert decision.force_parent_attribution is True

    def test_decision_stage3_skip(self):
        """Test creating decision for STAGE 3 skip."""
        # Act
        decision = AutoSkipDecision(
            should_skip=True,
            skip_reason="STAGE 3: Compatibility validation failed",
            skip_message="No compatible Feeder products found. Moving to the next step.",
            force_parent_attribution=False
        )

        # Assert
        assert decision.should_skip is True
        assert decision.skip_reason == "STAGE 3: Compatibility validation failed"
        assert decision.skip_message == "No compatible Feeder products found. Moving to the next step."
        assert decision.force_parent_attribution is False

    def test_decision_repr(self):
        """Test __repr__ for debugging."""
        # Arrange
        decision = AutoSkipDecision(
            should_skip=True,
            skip_reason="Test reason",
            skip_message="Test message",
            force_parent_attribution=True
        )

        # Act
        repr_str = repr(decision)

        # Assert
        assert "AutoSkipDecision" in repr_str
        assert "should_skip=True" in repr_str
        assert "Test reason" in repr_str
        assert "Test message" in repr_str
        assert "force_parent_attribution=True" in repr_str
