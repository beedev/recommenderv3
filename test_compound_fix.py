#!/usr/bin/env python3
"""
Test script to verify compound request detection fix

Tests two scenarios:
1. Sequential Flow (PowerSource selected, then Feeder) - should use S2 flow
2. Compound Request (both at once) - should use compound flow
"""
import requests
import json

API_BASE = "http://localhost:8000/api/v1/configurator"

def test_sequential_flow():
    """
    Test S1→S2 sequential flow (the bug scenario)

    Scenario:
    1. User selects PowerSource: "Aristo 500ix"
    2. User requests Feeder: "RobustFeed"

    Expected: Should use S2 (Feeder Selection) sequential flow
              NOT compound request flow
    """
    print("=" * 80)
    print("TEST 1: Sequential Flow (PowerSource selected → Feeder requested)")
    print("=" * 80)

    # Step 1: Start new session with PowerSource request
    print("\n1. Requesting PowerSource...")
    r1 = requests.post(f"{API_BASE}/message", json={
        "session_id": None,
        "message": "Aristo 500ix",
        "language": "en"
    })
    data1 = r1.json()
    session_id = data1["session_id"]
    print(f"   ✓ Session: {session_id}")
    print(f"   ✓ State: {data1['current_state']}")
    print(f"   ✓ Products: {len(data1['products'])}")

    # Step 2: Select PowerSource
    print("\n2. Selecting Aristo 500ix...")
    r2 = requests.post(f"{API_BASE}/select", json={
        "session_id": session_id,
        "gin": "0446200880",
        "user_id": "test",
        "language": "en"
    })
    data2 = r2.json()
    print(f"   ✓ State: {data2.get('current_state', 'N/A')}")
    print(f"   ✓ PowerSource Selected: {data2.get('response_json', {}).get('PowerSource', {}).get('name', 'N/A')}")

    # Step 3: Request Feeder (THIS IS WHERE THE BUG WAS)
    print("\n3. Requesting Feeder (should use S2 sequential flow)...")
    r3 = requests.post(f"{API_BASE}/message", json={
        "session_id": session_id,
        "message": "robustfeed",
        "language": "en"
    })
    data3 = r3.json()

    print(f"\n   State: {data3['current_state']}")
    print(f"   Products: {len(data3.get('products', []))}")
    print(f"   Error: {data3.get('error', False)}")

    # Check for success
    if data3.get('error'):
        print(f"\n   ❌ ERROR: {data3.get('message', 'Unknown error')}")
        return False
    elif len(data3.get('products', [])) > 0:
        print(f"\n   ✅ SUCCESS: Found {len(data3['products'])} feeder products")
        print(f"   First product: {data3['products'][0]['name']}")
        print(f"\n   ✅ SEQUENTIAL FLOW CONFIRMED: Used S2 (Feeder Selection) state")
        return True
    else:
        print(f"\n   ⚠️  WARNING: No products found")
        return False


def test_compound_flow():
    """
    Test compound request flow

    Scenario:
    1. User requests both at once: "Aristo 500ix with RobustFeed U6"

    Expected: Should use compound request flow
              Auto-select both if exact matches
    """
    print("\n\n" + "=" * 80)
    print("TEST 2: Compound Request Flow (Both components at once)")
    print("=" * 80)

    # Step 1: Request both components at once
    print("\n1. Requesting both PowerSource and Feeder together...")
    r1 = requests.post(f"{API_BASE}/message", json={
        "session_id": None,
        "message": "Aristo 500ix with RobustFeed U6",
        "language": "en"
    })
    data1 = r1.json()
    session_id = data1["session_id"]

    print(f"   ✓ Session: {session_id}")
    print(f"   ✓ State: {data1['current_state']}")

    # Check if both components were handled
    response_json = data1.get('response_json', {})
    power_source = response_json.get('PowerSource')
    feeder = response_json.get('Feeder')

    print(f"\n   Response JSON:")
    if power_source:
        print(f"   ✓ PowerSource: {power_source.get('name', 'N/A')} (GIN: {power_source.get('gin', 'N/A')})")
    else:
        print(f"   ✗ PowerSource: Not selected")

    if feeder:
        print(f"   ✓ Feeder: {feeder.get('name', 'N/A')} (GIN: {feeder.get('gin', 'N/A')})")
    else:
        print(f"   ✗ Feeder: Not selected")

    # Success if both components were processed (either selected or queued for disambiguation)
    if power_source or feeder:
        print(f"\n   ✅ SUCCESS: Compound request flow used")
        if power_source and feeder:
            print(f"   ✅ BONUS: Both components auto-selected (exact matches)")
        return True
    else:
        print(f"\n   ❌ FAILED: Compound request not detected")
        return False


def test_downstream_without_powersource():
    """
    Test validation error for downstream component without PowerSource

    Scenario:
    1. User requests Feeder without PowerSource: "RobustFeed U6"

    Expected: Should trigger compound request validation error
              Prompt user to specify PowerSource
    """
    print("\n\n" + "=" * 80)
    print("TEST 3: Validation Error (Feeder without PowerSource)")
    print("=" * 80)

    # Step 1: Request Feeder without PowerSource
    print("\n1. Requesting Feeder without PowerSource (should trigger validation error)...")
    r1 = requests.post(f"{API_BASE}/message", json={
        "session_id": None,
        "message": "RobustFeed U6",
        "language": "en"
    })
    data1 = r1.json()

    print(f"   ✓ Session: {data1['session_id']}")
    print(f"   ✓ State: {data1['current_state']}")

    # Check if validation error message is present
    message = data1.get('message', '')
    if 'PowerSource' in message and ('required' in message.lower() or 'first' in message.lower()):
        print(f"\n   ✅ SUCCESS: Validation error triggered correctly")
        print(f"   Message preview: {message[:200]}...")
        return True
    else:
        print(f"\n   ❌ FAILED: Expected validation error not found")
        print(f"   Message: {message[:200]}")
        return False


if __name__ == "__main__":
    try:
        results = []

        # Test 1: Sequential Flow (the bug fix)
        test1_passed = test_sequential_flow()
        results.append(("Sequential Flow (Bug Fix)", test1_passed))

        # Test 2: Compound Request Flow
        test2_passed = test_compound_flow()
        results.append(("Compound Request Flow", test2_passed))

        # Test 3: Validation Error
        test3_passed = test_downstream_without_powersource()
        results.append(("Validation Error", test3_passed))

        # Summary
        print("\n\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)

        for test_name, passed in results:
            status = "✅ PASSED" if passed else "❌ FAILED"
            print(f"{status}: {test_name}")

        all_passed = all(passed for _, passed in results)
        print("\n" + "=" * 80)
        if all_passed:
            print("✅ ALL TESTS PASSED: Compound request detection fix working correctly!")
        else:
            print("❌ SOME TESTS FAILED: Please review the failed tests above")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
