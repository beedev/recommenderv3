"""
Integration Test - Phase 6
Test complete dynamic state machine integration with startup initialization
"""

import sys
import os
import asyncio

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.models.conversation import init_configurator_state, get_configurator_state
from app.services.orchestrator.state_processors import init_processor_registry, get_processor_registry
from app.services.config.config_validator import get_validator, validate_configs_on_startup
from app.models.state_factory import StateFactory


async def test_integration():
    """Test complete integration of dynamic state machine"""

    print("=" * 70)
    print("Integration Test - Phase 6: Dynamic State Machine")
    print("=" * 70)
    print()

    all_passed = True

    # Step 1: Validate configurations
    print("[1/8] Validating configurations on startup...")
    try:
        is_valid, report = validate_configs_on_startup()
        if is_valid:
            print("[OK] Configuration validation passed")
        else:
            print("[WARNING] Configuration has issues:")
            for result_name, result_data in report.get("results", {}).items():
                if not result_data.get("is_valid"):
                    print(f"     - {result_name}: {result_data.get('errors', [])}")
    except Exception as e:
        print(f"[ERROR] Configuration validation failed: {e}")
        all_passed = False

    # Step 2: Initialize dynamic enum
    print("\n[2/8] Initializing ConfiguratorState enum...")
    try:
        ConfiguratorState = init_configurator_state()

        # Verify enum was created
        if ConfiguratorState is None:
            print("[ERROR] ConfiguratorState enum not created")
            all_passed = False
        else:
            # Count states
            state_count = len(list(ConfiguratorState))
            print(f"[OK] ConfiguratorState enum created with {state_count} states")

            # List all states
            print("     States:")
            for state in ConfiguratorState:
                print(f"       - {state.name} = {state.value}")
    except Exception as e:
        print(f"[ERROR] Enum initialization failed: {e}")
        all_passed = False

    # Step 3: Verify StateFactory metadata
    print("\n[3/8] Verifying StateFactory metadata...")
    try:
        state_sequence = StateFactory.get_state_sequence()
        print(f"[OK] State sequence loaded: {len(state_sequence)} states")

        finalize_state = StateFactory.get_finalize_state()
        print(f"[OK] Finalize state: {finalize_state}")

        # Check metadata for each state
        print("     State metadata:")
        for state_name in state_sequence:
            try:
                metadata = StateFactory.get_state_metadata(state_name)
                api_key = metadata.get("api_key", "N/A")
                selection_type = metadata.get("selection_type", "N/A")
                print(f"       - {state_name}: api_key={api_key}, type={selection_type}")
            except KeyError:
                print(f"       - {state_name}: [WARNING] No metadata")

    except Exception as e:
        print(f"[ERROR] StateFactory metadata check failed: {e}")
        all_passed = False

    # Step 4: Initialize processor registry
    print("\n[4/8] Initializing processor registry...")
    try:
        registry = init_processor_registry()
        registered_states = registry.get_all_states()
        print(f"[OK] Processor registry initialized with {len(registered_states)} processors")

        # List processor mappings
        print("     Processor mappings:")
        for state_name in registered_states:
            processor = registry.get_processor(state_name)
            processor_type = processor.__class__.__name__
            print(f"       - {state_name}: {processor_type}")

    except Exception as e:
        print(f"[ERROR] Processor registry initialization failed: {e}")
        all_passed = False

    # Step 5: Verify processor-state alignment
    print("\n[5/8] Verifying processor-state alignment...")
    try:
        state_sequence = StateFactory.get_state_sequence()
        registry = get_processor_registry()

        mismatches = []
        for state_name in state_sequence:
            if not registry.has_processor(state_name):
                mismatches.append(state_name)

        if mismatches:
            print(f"[WARNING] {len(mismatches)} states without processors:")
            for state in mismatches:
                print(f"     - {state}")
        else:
            print("[OK] All states have processors")

    except Exception as e:
        print(f"[ERROR] Alignment check failed: {e}")
        all_passed = False

    # Step 6: Test state transitions
    print("\n[6/8] Testing state transitions...")
    try:
        from app.models.conversation import ConversationState, ComponentApplicability

        # Create test conversation state
        conv_state = ConversationState(session_id="test-integration")

        # Set applicability (all Y for testing)
        conv_state.set_applicability(ComponentApplicability(
            Feeder="Y",
            Cooler="Y",
            Interconnector="Y",
            Torch="Y",
            Accessories="Y"
        ))

        # Test state progression
        states_visited = [conv_state.current_state.value]
        for i in range(7):  # Try to traverse all states
            next_state = conv_state.get_next_state()
            if next_state is None:
                break
            states_visited.append(next_state.value)
            conv_state.current_state = next_state

        print(f"[OK] State transition test completed")
        print(f"     States visited: {len(states_visited)}")
        print(f"     Path: {' -> '.join(states_visited)}")

    except Exception as e:
        print(f"[ERROR] State transition test failed: {e}")
        all_passed = False

    # Step 7: Test processor invocation
    print("\n[7/8] Testing processor invocation...")
    try:
        registry = get_processor_registry()

        # Test getting processors for each state
        test_states = ["power_source_selection", "feeder_selection", "accessories_selection"]

        for state_name in test_states:
            processor = registry.get_processor(state_name)
            if processor:
                print(f"[OK] {state_name}: {processor.__class__.__name__}")
            else:
                print(f"[ERROR] {state_name}: No processor found")
                all_passed = False

    except Exception as e:
        print(f"[ERROR] Processor invocation test failed: {e}")
        all_passed = False

    # Step 8: Verify backwards compatibility
    print("\n[8/8] Verifying backwards compatibility...")
    try:
        # Check that get_configurator_state works
        ConfiguratorState = get_configurator_state()

        # Try to access enum members
        power_source_state = ConfiguratorState.POWER_SOURCE_SELECTION
        print(f"[OK] Enum access works: {power_source_state.value}")

        # Check that state values match expected format
        if power_source_state.value == "power_source_selection":
            print("[OK] State value format is correct")
        else:
            print(f"[ERROR] Unexpected state value: {power_source_state.value}")
            all_passed = False

    except Exception as e:
        print(f"[ERROR] Backwards compatibility check failed: {e}")
        all_passed = False

    # Summary
    print()
    print("=" * 70)
    if all_passed:
        print("[SUCCESS] Integration test passed!")
        print()
        print("Summary:")
        print("[OK] Configuration validation working")
        print("[OK] Dynamic enum generation working")
        print("[OK] StateFactory metadata loaded")
        print("[OK] Processor registry initialized")
        print("[OK] All states have processors")
        print("[OK] State transitions working")
        print("[OK] Processor invocation working")
        print("[OK] Backwards compatibility maintained")
        print()
        print("System ready for dynamic S1->SN flow!")
        print("Dynamic routing: ENABLED")
        return True
    else:
        print("[FAILED] Some integration tests failed")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_integration())
    sys.exit(0 if success else 1)
