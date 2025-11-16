"""
Test script to verify conditional accessory dependency fix.

Tests that conditional accessories are skipped when parent accessories have no selections:
- feeder_conditional_accessories → skipped if FeederAccessories is empty
- remote_conditional_accessories → skipped if RemoteAccessories is empty

Usage:
    python test_conditional_accessory_fix.py
"""

import requests
import json
import sys

API_BASE = "http://localhost:8000"


def print_section(title):
    """Print section header."""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def test_feeder_conditional_skip():
    """
    Test Case 1: Skip feeder accessories → feeder conditional should also be skipped

    Flow:
    1. Select PowerSource: Warrior 500i CC/CV 380 - 415V (GIN: 0465350883)
    2. Skip Feeder (assume "done")
    3. Skip Cooler (assume "done")
    4. Skip Interconnector (assume "done")
    5. Skip Torch (assume "done")
    6. Skip PowerSourceAccessories (type "done")
    7. Skip FeederAccessories (type "done" without selecting anything)
    8. ✅ VERIFY: Next state should be InterconnectorAccessories, NOT FeederConditionalAccessories
    """
    print_section("TEST CASE 1: Feeder Conditional Accessory Skip")

    # Start new session
    print("\n1. Starting new session with PowerSource selection...")
    r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
        "message": "Warrior 500i CC/CV 380 - 415V",
        "language": "en"
    })
    data = r.json()
    session_id = data.get('session_id')
    print(f"   Session ID: {session_id}")
    print(f"   Current State: {data.get('current_state')}")

    # Auto-select if only one product (likely for Warrior 500i)
    if len(data.get('products', [])) == 1:
        print("\n2. Auto-selecting PowerSource...")
        r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
            "session_id": session_id,
            "message": "select",
            "language": "en"
        })
        data = r.json()
        print(f"   Current State: {data.get('current_state')}")

    # Skip through primary components (Feeder, Cooler, Interconnector, Torch)
    print("\n3. Skipping primary components (Feeder → Torch)...")
    for i in range(4):  # Feeder, Cooler, Interconnector, Torch
        r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
            "session_id": session_id,
            "message": "skip",
            "language": "en"
        })
        data = r.json()
        print(f"   Skipped → Current State: {data.get('current_state')}")

    # Skip PowerSource Accessories
    print("\n4. Skipping PowerSource Accessories...")
    r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
        "session_id": session_id,
        "message": "done",
        "language": "en"
    })
    data = r.json()
    current_state = data.get('current_state')
    print(f"   Current State: {current_state}")

    # Verify we're at feeder_accessories_selection
    if current_state != "feeder_accessories_selection":
        print(f"   ❌ UNEXPECTED: Expected feeder_accessories_selection, got {current_state}")
        return False

    # Skip Feeder Accessories (type "done" without selecting anything)
    print("\n5. Skipping Feeder Accessories (no selections)...")
    r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
        "session_id": session_id,
        "message": "done",
        "language": "en"
    })
    data = r.json()
    current_state = data.get('current_state')
    print(f"   Current State: {current_state}")

    # ✅ CRITICAL CHECK: Should skip feeder_conditional_accessories
    if current_state == "feeder_conditional_accessories":
        print("\n   ❌ FAILED: feeder_conditional_accessories was NOT skipped")
        print("   Expected: interconnector_accessories_selection")
        print(f"   Actual: {current_state}")
        return False
    elif current_state == "interconnector_accessories_selection":
        print("\n   ✅ SUCCESS: feeder_conditional_accessories was correctly skipped")
        print(f"   Moved directly to: {current_state}")
        return True
    else:
        print(f"\n   ⚠️  UNEXPECTED STATE: {current_state}")
        print("   Expected: interconnector_accessories_selection")
        return False


def test_remote_conditional_skip():
    """
    Test Case 2: Skip remote accessories → remote conditional should also be skipped

    Flow:
    1. Select PowerSource: Warrior 500i CC/CV 380 - 415V
    2. Skip through to remote_accessories_selection
    3. Skip RemoteAccessories (type "done" without selecting anything)
    4. ✅ VERIFY: Next state should be Connectivity, NOT RemoteConditionalAccessories
    """
    print_section("TEST CASE 2: Remote Conditional Accessory Skip")

    # Start new session
    print("\n1. Starting new session with PowerSource selection...")
    r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
        "message": "Warrior 500i CC/CV 380 - 415V",
        "language": "en"
    })
    data = r.json()
    session_id = data.get('session_id')
    print(f"   Session ID: {session_id}")

    # Auto-select PowerSource
    if len(data.get('products', [])) == 1:
        r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
            "session_id": session_id,
            "message": "select",
            "language": "en"
        })
        data = r.json()

    # Skip through all states until we reach remote_accessories_selection
    print("\n2. Skipping to remote_accessories_selection...")
    max_skips = 20  # Safety limit
    skip_count = 0

    while skip_count < max_skips:
        current_state = data.get('current_state')
        print(f"   Current State: {current_state}")

        if current_state == "remote_accessories_selection":
            print("   ✅ Reached remote_accessories_selection")
            break

        # Skip/done current state
        r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
            "session_id": session_id,
            "message": "done",
            "language": "en"
        })
        data = r.json()
        skip_count += 1

    if data.get('current_state') != "remote_accessories_selection":
        print(f"   ❌ FAILED: Could not reach remote_accessories_selection")
        return False

    # Skip Remote Accessories (type "done" without selecting anything)
    print("\n3. Skipping Remote Accessories (no selections)...")
    r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
        "session_id": session_id,
        "message": "done",
        "language": "en"
    })
    data = r.json()
    current_state = data.get('current_state')
    print(f"   Current State: {current_state}")

    # ✅ CRITICAL CHECK: Should skip remote_conditional_accessories
    if current_state == "remote_conditional_accessories":
        print("\n   ❌ FAILED: remote_conditional_accessories was NOT skipped")
        print("   Expected: connectivity_selection")
        print(f"   Actual: {current_state}")
        return False
    elif current_state == "connectivity_selection":
        print("\n   ✅ SUCCESS: remote_conditional_accessories was correctly skipped")
        print(f"   Moved directly to: {current_state}")
        return True
    else:
        print(f"\n   ⚠️  UNEXPECTED STATE: {current_state}")
        print("   Expected: connectivity_selection")
        return False


def main():
    """Run all test cases."""
    print_section("CONDITIONAL ACCESSORY DEPENDENCY FIX TESTS")
    print("\nTesting that conditional accessories are skipped when parent has no selections")

    # Check server health
    print("\n1. Checking server health...")
    try:
        r = requests.get(f"{API_BASE}/health")
        health = r.json()
        print(f"   Server Status: {health.get('status')}")
        print(f"   Session Storage: {health.get('session_storage', {}).get('type')}")
    except Exception as e:
        print(f"   ❌ ERROR: Server not reachable: {e}")
        print(f"   Make sure server is running on {API_BASE}")
        sys.exit(1)

    # Run test cases
    results = []

    # Test Case 1: Feeder Conditional Skip
    try:
        result1 = test_feeder_conditional_skip()
        results.append(("Feeder Conditional Skip", result1))
    except Exception as e:
        print(f"\n❌ TEST CASE 1 EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Feeder Conditional Skip", False))

    # Test Case 2: Remote Conditional Skip
    try:
        result2 = test_remote_conditional_skip()
        results.append(("Remote Conditional Skip", result2))
    except Exception as e:
        print(f"\n❌ TEST CASE 2 EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Remote Conditional Skip", False))

    # Print summary
    print_section("TEST SUMMARY")
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")

    all_passed = all(result for _, result in results)
    if all_passed:
        print("\n✅ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
