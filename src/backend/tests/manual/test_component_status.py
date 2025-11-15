"""
Simple test to verify component status tracking
"""
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from app.models.conversation import (
    ConversationState,
    ResponseJSON,
    SelectedProduct,
    init_configurator_state
)
import uuid

# Initialize configurator state
init_configurator_state()

def test_component_status_tracking():
    """Test component status tracking functionality"""

    print("=" * 70)
    print("COMPONENT STATUS TRACKING TEST")
    print("=" * 70)

    # Create a new conversation state
    session_id = str(uuid.uuid4())
    conversation_state = ConversationState(session_id=session_id)

    print("\n1. Initial State - All components should be 'skipped'")
    print("-" * 70)
    statuses = conversation_state.response_json.get_all_component_statuses()
    for component, status in statuses.items():
        print(f"  {component}: {status}")

    # Test selecting a power source
    print("\n2. Select PowerSource - Should be marked as 'selected'")
    print("-" * 70)
    power_source = SelectedProduct(
        gin="0446200880",
        name="Aristo 500ix CE",
        category="PowerSource",
        description="500A MIG welder"
    )
    conversation_state.select_component("PowerSource", power_source)

    statuses = conversation_state.response_json.get_all_component_statuses()
    for component in ["PowerSource", "Feeder", "Cooler"]:
        status = statuses.get(component, "unknown")
        icon = "[X]" if status == "selected" else "[ ]"
        print(f"  {icon} {component}: {status}")

    # Test selecting a feeder
    print("\n3. Select Feeder - Should be marked as 'selected'")
    print("-" * 70)
    feeder = SelectedProduct(
        gin="0460520880",
        name="RobustFeed U6",
        category="Feeder",
        description="Wire feeder"
    )
    conversation_state.select_component("Feeder", feeder)

    statuses = conversation_state.response_json.get_all_component_statuses()
    for component in ["PowerSource", "Feeder", "Cooler", "Interconnector"]:
        status = statuses.get(component, "unknown")
        icon = "[X]" if status == "selected" else "[ ]"
        print(f"  {icon} {component}: {status}")

    # Test selecting accessories (multi-select)
    print("\n4. Select PowerSourceAccessories - Should be marked as 'selected'")
    print("-" * 70)
    accessory = SelectedProduct(
        gin="0111111111",
        name="Power Cable Extension",
        category="PowerSource Accessories"
    )
    conversation_state.select_component("PowerSourceAccessories", accessory)

    statuses = conversation_state.response_json.get_all_component_statuses()
    for component in ["PowerSource", "Feeder", "PowerSourceAccessories", "Remotes"]:
        status = statuses.get(component, "unknown")
        icon = "[X]" if status == "selected" else "[ ]"
        print(f"  {icon} {component}: {status}")

    # Test individual status methods
    print("\n5. Test Individual Status Methods")
    print("-" * 70)
    print(f"  PowerSource status: {conversation_state.response_json.get_component_status('PowerSource')}")
    print(f"  Torch status: {conversation_state.response_json.get_component_status('Torch')}")

    # Manual status change
    print("\n6. Manually Mark Torch as Selected")
    print("-" * 70)
    conversation_state.response_json.mark_component_selected("Torch")
    print(f"  Torch status: {conversation_state.response_json.get_component_status('Torch')}")

    # Test serialization
    print("\n7. Test Serialization (for API response)")
    print("-" * 70)
    response_dict = conversation_state.response_json.dict()
    if "component_statuses" in response_dict:
        print("  [OK] component_statuses present in serialized dict")
        print(f"  Selected components: {sum(1 for s in response_dict['component_statuses'].values() if s == 'selected')}")
        print(f"  Skipped components: {sum(1 for s in response_dict['component_statuses'].values() if s == 'skipped')}")
    else:
        print("  [FAIL] component_statuses NOT found in serialized dict")

    print("\n" + "=" * 70)
    print("TEST COMPLETE!")
    print("=" * 70)

    # Summary
    final_statuses = conversation_state.response_json.get_all_component_statuses()
    selected = [k for k, v in final_statuses.items() if v == "selected"]
    skipped = [k for k, v in final_statuses.items() if v == "skipped"]

    print(f"\nFinal Summary:")
    print(f"  Selected ({len(selected)}): {', '.join(selected)}")
    print(f"  Skipped ({len(skipped)}): {', '.join(skipped[:3])}... (showing first 3)")

if __name__ == "__main__":
    test_component_status_tracking()
