"""
E2E Test: Verify ORIGINAL flow (Feeder→Cooler) works after reversing config.

Expected Flow:
1. S1 (PowerSource) → Select power source
2. S2 (Feeder) → Should transition to feeder_selection (ORIGINAL order)
3. S3 (Cooler) → Should transition to cooler_selection (ORIGINAL order)
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_original_flow():
    """Test that PowerSource → Feeder → Cooler flow works (original order)."""
    print("=" * 80)
    print("E2E Test: ORIGINAL Flow Verification (Feeder at S2, Cooler at S3)")
    print("=" * 80)

    # Step 1: Start new session
    print("\n📍 Step 1: Starting new session...")
    response = requests.post(
        f"{BASE_URL}/api/v1/configurator/message",
        json={"message": "I need a power source", "language": "en", "reset": True}
    )
    data = response.json()

    print(f"✅ Current State: {data['current_state']}")
    assert data['current_state'] == "power_source_selection"

    session_id = data['session_id']

    # Step 2: Select PowerSource
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

    current_state = data.get('current_state') or data.get('conversation_state', {}).get('current_state')

    print(f"✅ Current State after PowerSource: {current_state}")
    print(f"   Expected: feeder_selection (S2 - ORIGINAL order)")

    if current_state == "feeder_selection":
        print("   ✅ SUCCESS! ORIGINAL flow working!")
        print("   ✅ PowerSource → Feeder (S2) ✓")
    else:
        print(f"   ❌ UNEXPECTED STATE: {current_state}")
        return False

    # Step 3: Skip Feeder to verify next state is Cooler
    print("\n📍 Step 3: Skipping Feeder to verify next state...")
    response = requests.post(
        f"{BASE_URL}/api/v1/configurator/message",
        json={"session_id": session_id, "message": "skip", "language": "en"}
    )
    data = response.json()

    next_state = data.get('current_state', 'unknown')
    print(f"✅ Current State after skipping Feeder: {next_state}")
    print(f"   Expected: cooler_selection (S3 - ORIGINAL order)")

    if next_state == "cooler_selection":
        print("   ✅ SUCCESS! Feeder → Cooler transition working!")
        print("   ✅ Complete flow verified: PowerSource (S1) → Feeder (S2) → Cooler (S3) ✓")
    else:
        print(f"   ⚠️  UNEXPECTED STATE: {next_state}")
        return False

    print("\n" + "=" * 80)
    print("🎉 ORIGINAL FLOW TEST PASSED!")
    print("=" * 80)
    return True

if __name__ == "__main__":
    try:
        success = test_original_flow()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
