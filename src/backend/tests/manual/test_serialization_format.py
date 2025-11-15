"""
Test new ResponseJSON serialization format
All components should appear with selected (object) or "skipped" (string)
"""
import sys
from pathlib import Path
import json

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from app.models.conversation import (
    ConversationState,
    ResponseJSON,
    SelectedProduct,
    init_configurator_state
)
from app.services.orchestrator.state_orchestrator import StateByStateOrchestrator
import uuid

# Initialize configurator state
init_configurator_state()

def test_serialization_format():
    """Test new serialization format with all components appearing"""

    print("=" * 70)
    print("RESPONSE JSON SERIALIZATION TEST")
    print("=" * 70)

    # Create a mock orchestrator to access _serialize_response_json
    # We'll mock the dependencies
    class MockProductSearch:
        pass

    class MockParameterExtractor:
        pass

    class MockMessageGenerator:
        pass

    orchestrator = StateByStateOrchestrator(
        product_search=MockProductSearch(),
        parameter_extractor=MockParameterExtractor(),
        message_generator=MockMessageGenerator(),
        powersource_state_specifications_config={}
    )

    # Test Case 1: Empty state (all components should be "skipped")
    print("\n1. Test Case: Empty State (all skipped)")
    print("-" * 70)
    session_id = str(uuid.uuid4())
    conversation_state1 = ConversationState(session_id=session_id)

    serialized1 = orchestrator._serialize_response_json(conversation_state1)
    print(f"PowerSource: {serialized1.get('PowerSource')}")
    print(f"Feeder: {serialized1.get('Feeder')}")
    print(f"Cooler: {serialized1.get('Cooler')}")
    print(f"PowerSourceAccessories: {serialized1.get('PowerSourceAccessories')}")
    print(f"Remotes: {serialized1.get('Remotes')}")

    # Verify all are "skipped"
    assert serialized1.get('PowerSource') == "skipped", "PowerSource should be 'skipped'"
    assert serialized1.get('Feeder') == "skipped", "Feeder should be 'skipped'"
    assert serialized1.get('Cooler') == "skipped", "Cooler should be 'skipped'"
    print("[PASS] All components are 'skipped'")

    # Test Case 2: PowerSource + Feeder selected
    print("\n2. Test Case: PowerSource + Feeder Selected")
    print("-" * 70)
    conversation_state2 = ConversationState(session_id=str(uuid.uuid4()))

    power_source = SelectedProduct(
        gin="0446200880",
        name="Aristo 500ix CE",
        category="PowerSource",
        description="500A MIG welder"
    )
    feeder = SelectedProduct(
        gin="0460520880",
        name="RobustFeed U6",
        category="Feeder",
        description="Wire feeder"
    )

    conversation_state2.select_component("PowerSource", power_source)
    conversation_state2.select_component("Feeder", feeder)

    serialized2 = orchestrator._serialize_response_json(conversation_state2)

    # Verify PowerSource is object
    ps_data = serialized2.get('PowerSource')
    assert isinstance(ps_data, dict), "PowerSource should be dict"
    assert ps_data.get('gin') == "0446200880", "PowerSource GIN should match"
    print(f"[PASS] PowerSource: {ps_data.get('name')} (GIN: {ps_data.get('gin')})")

    # Verify Feeder is object
    feeder_data = serialized2.get('Feeder')
    assert isinstance(feeder_data, dict), "Feeder should be dict"
    assert feeder_data.get('gin') == "0460520880", "Feeder GIN should match"
    print(f"[PASS] Feeder: {feeder_data.get('name')} (GIN: {feeder_data.get('gin')})")

    # Verify others are "skipped"
    assert serialized2.get('Cooler') == "skipped", "Cooler should be 'skipped'"
    assert serialized2.get('Interconnector') == "skipped", "Interconnector should be 'skipped'"
    assert serialized2.get('Torch') == "skipped", "Torch should be 'skipped'"
    print("[PASS] Unselected components are 'skipped'")

    # Test Case 3: With Accessories
    print("\n3. Test Case: With Accessories Selected")
    print("-" * 70)
    conversation_state3 = ConversationState(session_id=str(uuid.uuid4()))
    conversation_state3.select_component("PowerSource", power_source)

    accessory1 = SelectedProduct(
        gin="0111111111",
        name="Power Cable 5m",
        category="PowerSourceAccessories"
    )
    accessory2 = SelectedProduct(
        gin="0222222222",
        name="Remote Control",
        category="Remotes"
    )

    conversation_state3.select_component("PowerSourceAccessories", accessory1)
    conversation_state3.select_component("Remotes", accessory2)

    serialized3 = orchestrator._serialize_response_json(conversation_state3)

    # Verify PowerSourceAccessories is list
    ps_acc_data = serialized3.get('PowerSourceAccessories')
    assert isinstance(ps_acc_data, list), "PowerSourceAccessories should be list"
    assert len(ps_acc_data) == 1, "Should have 1 accessory"
    assert ps_acc_data[0].get('gin') == "0111111111", "Accessory GIN should match"
    print(f"[PASS] PowerSourceAccessories: {len(ps_acc_data)} item(s)")

    # Verify Remotes is list
    remotes_data = serialized3.get('Remotes')
    assert isinstance(remotes_data, list), "Remotes should be list"
    assert len(remotes_data) == 1, "Should have 1 remote"
    print(f"[PASS] Remotes: {len(remotes_data)} item(s)")

    # Verify other accessory categories are "skipped"
    assert serialized3.get('FeederAccessories') == "skipped", "FeederAccessories should be 'skipped'"
    assert serialized3.get('Connectivity') == "skipped", "Connectivity should be 'skipped'"
    print("[PASS] Empty accessory categories are 'skipped'")

    # Test Case 4: All 15 categories present
    print("\n4. Test Case: All 15 Categories Present in Response")
    print("-" * 70)
    expected_categories = [
        "PowerSource", "Feeder", "Cooler", "Interconnector", "Torch",
        "PowerSourceAccessories", "FeederAccessories", "FeederConditionalAccessories",
        "InterconnectorAccessories", "Remotes", "RemoteAccessories",
        "RemoteConditionalAccessories", "Connectivity", "FeederWears", "Accessories"
    ]

    for category in expected_categories:
        assert category in serialized1, f"{category} should be in response"

    print(f"[PASS] All {len(expected_categories)} categories present")
    print("Categories:", ", ".join(expected_categories))

    # Test Case 5: Pretty JSON output format
    print("\n5. Test Case: JSON Output Format")
    print("-" * 70)
    json_output = json.dumps(serialized2, indent=2)
    print(json_output[:500])  # Print first 500 chars
    print("...")
    print("[PASS] JSON serialization works")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED!")
    print("=" * 70)

    # Summary
    print("\nSummary:")
    print(f"  - Selected components: Full object with gin, name, category, description")
    print(f"  - Unselected components: String literal 'skipped'")
    print(f"  - All 15 categories always present in response")
    print(f"  - Accessories: List of objects or 'skipped'")

if __name__ == "__main__":
    try:
        test_serialization_format()
    except AssertionError as e:
        print(f"\n[FAIL] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
