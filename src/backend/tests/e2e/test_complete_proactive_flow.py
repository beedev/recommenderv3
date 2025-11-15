"""
End-to-End Test: Complete S1→SN Flow with Proactive Selection

Tests the entire configurator flow by:
1. Starting with a PowerSource query
2. Auto-selecting the first product at each state
3. Progressing through all applicable states (S1→SN)
4. Validating final configuration package

This test validates that the complete workflow functions correctly
with automatic product selection.
"""

import pytest
import asyncio
from typing import Dict, Any, Optional

from app.services.orchestrator.state_orchestrator import StateByStateOrchestrator
from app.services.intent.parameter_extractor import ParameterExtractor
from app.services.neo4j.product_search import Neo4jProductSearch
from app.services.response.message_generator import MessageGenerator
from app.models.conversation import ConversationState, ConfiguratorState


class ProactiveFlowTester:
    """
    End-to-end flow tester with automatic product selection.

    Simulates a user completing the entire configuration by automatically
    selecting the first product returned at each state.
    """

    def __init__(
        self,
        orchestrator: StateByStateOrchestrator,
        initial_query: str,
        language: str = "en"
    ):
        """
        Initialize flow tester.

        Args:
            orchestrator: State orchestrator instance
            initial_query: Initial PowerSource query (e.g., "I want an Aristo")
            language: Language code (default: "en")
        """
        self.orchestrator = orchestrator
        self.initial_query = initial_query
        self.language = language
        self.conversation_state: Optional[ConversationState] = None
        self.state_history = []
        self.selection_history = []

    async def run_complete_flow(self) -> Dict[str, Any]:
        """
        Execute complete S1→SN flow with automatic selection.

        Returns:
            Dict with flow results and statistics
        """
        print("\n" + "=" * 70)
        print("🧪 PROACTIVE FLOW TEST - COMPLETE S1→SN CONFIGURATION")
        print("=" * 70)
        print(f"Initial Query: {self.initial_query}")
        print(f"Language: {self.language}")
        print()

        # STEP 1: Process initial PowerSource query
        print("[STEP 1] Processing initial PowerSource query...")
        response = await self._process_message(self.initial_query)

        if not response or not response.get("products"):
            raise AssertionError(
                f"❌ S1 (PowerSource) failed: No products returned\n"
                f"Response: {response}"
            )

        print(f"✅ S1 returned {len(response['products'])} PowerSource products")

        # STEP 2: Auto-select first PowerSource
        first_product = response["products"][0]
        print(f"🎯 Auto-selecting: {first_product['name']} (GIN: {first_product['gin']})")

        selection_response = await self._select_product(first_product)
        print(f"✅ PowerSource selected: {first_product['name']}")

        # STEP 3: Progress through remaining states with auto-selection
        step_count = 2
        max_steps = 20  # Safety limit to prevent infinite loops

        while self.conversation_state.current_state != ConfiguratorState.FINALIZE:
            step_count += 1

            if step_count > max_steps:
                raise AssertionError(f"❌ Exceeded max steps ({max_steps}). Possible infinite loop.")

            current_state = self.conversation_state.current_state.value
            print(f"\n[STEP {step_count}] Current state: {current_state}")

            # Process message to trigger search for current state
            response = await self._process_message("show options")

            # Check if state requires selection
            if response.get("awaiting_selection") and response.get("products"):
                # Auto-select first product
                first_product = response["products"][0]
                print(f"🎯 Auto-selecting: {first_product['name']} (GIN: {first_product['gin']})")

                selection_response = await self._select_product(first_product)
                print(f"✅ Selected: {first_product['name']}")

            elif response.get("can_finalize"):
                # Ready to finalize
                print("✅ Configuration ready to finalize")
                break
            else:
                # State was auto-skipped (not applicable)
                print(f"⏭️  State skipped (not applicable)")

        # STEP 4: Finalize configuration
        print(f"\n[STEP {step_count + 1}] Finalizing configuration...")
        final_response = await self._process_message("finalize")

        # Validate final configuration
        response_json = self.conversation_state.response_json

        print("\n" + "=" * 70)
        print("📦 FINAL CONFIGURATION PACKAGE")
        print("=" * 70)

        components = []
        if response_json.PowerSource:
            components.append(f"✓ PowerSource: {response_json.PowerSource.name}")
        if response_json.Feeder:
            components.append(f"✓ Feeder: {response_json.Feeder.name}")
        if response_json.Cooler:
            components.append(f"✓ Cooler: {response_json.Cooler.name}")
        if response_json.Interconnector:
            components.append(f"✓ Interconnector: {response_json.Interconnector.name}")
        if response_json.Torch:
            components.append(f"✓ Torch: {response_json.Torch.name}")
        if response_json.Accessories:
            components.append(f"✓ Accessories: {len(response_json.Accessories)} items")

        for component in components:
            print(component)

        print("\n" + "=" * 70)
        print("📊 TEST STATISTICS")
        print("=" * 70)
        print(f"Total Steps: {step_count + 1}")
        print(f"States Visited: {len(self.state_history)}")
        print(f"Products Selected: {len(self.selection_history)}")
        print(f"Final State: {self.conversation_state.current_state.value}")
        print("=" * 70)

        return {
            "success": True,
            "total_steps": step_count + 1,
            "states_visited": len(self.state_history),
            "products_selected": len(self.selection_history),
            "final_configuration": {
                "PowerSource": response_json.PowerSource.dict() if response_json.PowerSource else None,
                "Feeder": response_json.Feeder.dict() if response_json.Feeder else None,
                "Cooler": response_json.Cooler.dict() if response_json.Cooler else None,
                "Interconnector": response_json.Interconnector.dict() if response_json.Interconnector else None,
                "Torch": response_json.Torch.dict() if response_json.Torch else None,
                "Accessories": [acc.dict() for acc in response_json.Accessories] if response_json.Accessories else []
            },
            "state_history": self.state_history,
            "selection_history": self.selection_history
        }

    async def _process_message(self, message: str) -> Dict[str, Any]:
        """Process a message through the orchestrator."""
        if self.conversation_state is None:
            # Initialize new conversation
            self.conversation_state = ConversationState()

        response = await self.orchestrator.process_message(
            message=message,
            conversation_state=self.conversation_state,
            language=self.language
        )

        # Track state history
        self.state_history.append(self.conversation_state.current_state.value)

        return response

    async def _select_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Select a product in the current state."""
        # Create selection dict matching SelectedProduct structure
        selection = {
            "gin": product["gin"],
            "name": product["name"],
            "category": product.get("category", ""),
            "description": product.get("description", ""),
            "specifications": product.get("specifications", {})
        }

        response = await self.orchestrator.handle_explicit_selection(
            gin=product["gin"],
            product_data=selection,
            conversation_state=self.conversation_state,
            language=self.language
        )

        # Track selection history
        self.selection_history.append({
            "state": self.conversation_state.current_state.value,
            "product": product["name"],
            "gin": product["gin"]
        })

        return response


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_complete_proactive_flow_aristo():
    """
    Test complete S1→SN flow with Aristo PowerSource.

    This test validates the entire configurator workflow by:
    1. Starting with "I want an Aristo"
    2. Auto-selecting the first product at each state
    3. Progressing through all applicable states
    4. Finalizing the configuration
    """
    # Initialize services
    from app.main import (
        parameter_extractor,
        neo4j_search,
        message_generator,
        orchestrator
    )

    # Create flow tester
    tester = ProactiveFlowTester(
        orchestrator=orchestrator,
        initial_query="I want an Aristo",
        language="en"
    )

    # Run complete flow
    results = await tester.run_complete_flow()

    # Assertions
    assert results["success"], "Flow should complete successfully"
    assert results["total_steps"] > 1, "Flow should have multiple steps"
    assert results["products_selected"] >= 1, "At least PowerSource should be selected"

    # Validate final configuration has PowerSource
    assert results["final_configuration"]["PowerSource"] is not None, \
        "Final configuration must have PowerSource"

    assert "Aristo" in results["final_configuration"]["PowerSource"]["name"], \
        "PowerSource should be an Aristo model"

    print("\n✅ TEST PASSED - Complete S1→SN flow working correctly!")


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_complete_proactive_flow_warrior():
    """Test complete S1→SN flow with Warrior PowerSource."""
    from app.main import orchestrator

    tester = ProactiveFlowTester(
        orchestrator=orchestrator,
        initial_query="I need a Warrior 500i",
        language="en"
    )

    results = await tester.run_complete_flow()

    assert results["success"], "Flow should complete successfully"
    assert results["final_configuration"]["PowerSource"] is not None
    assert "Warrior" in results["final_configuration"]["PowerSource"]["name"]

    print("\n✅ TEST PASSED - Warrior flow working correctly!")


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_complete_proactive_flow_renegade():
    """Test complete S1→SN flow with Renegade PowerSource."""
    from app.main import orchestrator

    tester = ProactiveFlowTester(
        orchestrator=orchestrator,
        initial_query="I want a Renegade ES300i",
        language="en"
    )

    results = await tester.run_complete_flow()

    assert results["success"], "Flow should complete successfully"
    assert results["final_configuration"]["PowerSource"] is not None
    assert "Renegade" in results["final_configuration"]["PowerSource"]["name"]

    print("\n✅ TEST PASSED - Renegade flow working correctly!")


if __name__ == "__main__":
    """
    Run proactive flow test standalone.

    Usage:
        cd src/backend
        python -m tests.e2e.test_complete_proactive_flow
    """
    import sys
    import os

    # Add app to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

    # Initialize app services (simplified for testing)
    print("Initializing services...")

    # Run test
    asyncio.run(test_complete_proactive_flow_aristo())
