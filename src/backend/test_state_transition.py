"""
E2E Test: Verify Cooler→Feeder state swap is working correctly after StateManager fix.

Expected Flow:
1. S1 (PowerSource) → Select power source
2. S2 (Cooler) → Should transition to cooler_selection (NEW - after swap)
3. S3 (Feeder) → Should transition to feeder_selection (NEW - after swap)
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_state_transition():
    """Test that PowerSource → Cooler → Feeder state flow works correctly."""
    print("=" * 80)
    print("E2E Test: State Transition Verification (Cooler ↔ Feeder Swap)")
    print("=" * 80)

    # Step 1: Start new session - should be in power_source_selection (S1)
    print("\n📍 Step 1: Starting new session...")
    response = requests.post(
        f"{BASE_URL}/api/v1/configurator/message",
        json={"message": "I need a power source", "language": "en", "reset": True}
    )
    data = response.json()

    print(f"✅ Current State: {data['current_state']}")
    print(f"   Expected: power_source_selection")
    assert data['current_state'] == "power_source_selection", f"Expected power_source_selection, got {data['current_state']}"

    session_id = data['session_id']
    print(f"   Session ID: {session_id}")

    # Step 2: Select a PowerSource (Aristo 500ix - GIN: 0446200880)
    print("\n📍 Step 2: Selecting PowerSource (Aristo 500ix)...")
    response = requests.post(
        f"{BASE_URL}/api/v1/configurator/select",
        json={
            "session_id": session_id,
            "product_gin": "0446200880",
            "product_data": {
                "gin": "0446200880",
                "name": "Aristo 500ix",
                "category": "PowerSource"
            }
        }
    )
    data = response.json()

    # Debug: print response structure
    if 'current_state' not in data:
        print(f"   DEBUG: Response keys: {list(data.keys())}")
        print(f"   DEBUG: Full response: {json.dumps(data, indent=2)}")

    current_state = data.get('current_state') or data.get('conversation_state', {}).get('current_state')

    print(f"✅ Current State after PowerSource selection: {current_state}")
    print(f"   Expected: cooler_selection (S2 - after swap)")

    # CRITICAL VERIFICATION: Should be cooler_selection, NOT feeder_selection
    if current_state == "cooler_selection":
        print("   ✅ SUCCESS! State transition is working correctly!")
        print("   ✅ PowerSource → Cooler (S2) ✓")
    elif current_state == "feeder_selection":
        print("   ❌ FAILURE! Still going to Feeder (S3) - StateManager fix didn't work!")
        print("   ❌ PowerSource → Feeder (OLD behavior) ✗")
        return False
    else:
        print(f"   ⚠️  UNEXPECTED STATE: {current_state}")
        return False

    # Step 3: Skip Cooler to verify next state is Feeder (S3)
    print("\n📍 Step 3: Skipping Cooler to verify next state...")
    response = requests.post(
        f"{BASE_URL}/api/v1/configurator/message",
        json={"session_id": session_id, "message": "skip", "language": "en"}
    )
    data = response.json()

    next_state = data.get('current_state', 'unknown')
    print(f"✅ Current State after skipping Cooler: {next_state}")
    print(f"   Expected: feeder_selection (S3 - after swap)")

    if next_state == "feeder_selection":
        print("   ✅ SUCCESS! Cooler → Feeder transition working!")
        print("   ✅ Complete flow verified: PowerSource (S1) → Cooler (S2) → Feeder (S3) ✓")
    else:
        print(f"   ⚠️  UNEXPECTED STATE: {next_state}")
        return False

    print("\n" + "=" * 80)
    print("🎉 ALL TESTS PASSED! State swap is working correctly!")
    print("=" * 80)
    return True

if __name__ == "__main__":
    try:
        success = test_state_transition()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
