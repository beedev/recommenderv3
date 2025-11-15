#!/usr/bin/env python3
"""
Test PowerSource Accessories Search

Reproduces the issue where user gets stuck at PowerSource Accessories stage.
"""

import requests
import json

API_BASE = "http://localhost:8000/api/v1/configurator"

def test_accessory_search():
    """Test complete flow through to PowerSource Accessories"""
    print("=" * 80)
    print("TEST: PowerSource Accessories Search")
    print("=" * 80)

    # Step 1: Search for PowerSource
    print("\n1️⃣  STEP 1: Searching for Aristo 500ix...")
    r1 = requests.post(f"{API_BASE}/message", json={
        "session_id": None,
        "message": "Aristo 500ix",
        "language": "en"
    })
    data1 = r1.json()
    session_id = data1["session_id"]
    print(f"   ✅ Session: {session_id}")
    print(f"   ✅ State: {data1['current_state']}")

    # Step 2: Select PowerSource
    print("\n2️⃣  STEP 2: Selecting Aristo 500ix CE...")
    r2 = requests.post(f"{API_BASE}/select", json={
        "session_id": session_id,
        "user_id": "test_user",
        "product_gin": "0446200880",
        "product_data": {
            "gin": "0446200880",
            "name": "Aristo 500ix CE, (380-460V)",
            "category": "PowerSource"
        },
        "language": "en"
    })
    data2 = r2.json()
    print(f"   ✅ State: {data2['current_state']}")

    # Step 3: Skip through to accessories (skip feeder, cooler, interconnector, torch)
    print("\n3️⃣  STEP 3: Skipping through component selections...")
    for component in ["feeder", "cooler", "interconnector", "torch"]:
        r = requests.post(f"{API_BASE}/message", json={
            "session_id": session_id,
            "message": "skip",
            "language": "en"
        })
        data = r.json()
        print(f"   ✅ Skipped {component}, State: {data['current_state']}")

    # Step 4: Request PowerSource Accessories
    print("\n4️⃣  STEP 4: Requesting PowerSource Accessories...")
    r4 = requests.post(f"{API_BASE}/message", json={
        "session_id": session_id,
        "message": "show me accessories for my power source",
        "language": "en"
    })
    data4 = r4.json()

    print(f"\n   State: {data4['current_state']}")
    print(f"   Products: {len(data4.get('products', []))}")
    print(f"   Awaiting Selection: {data4.get('awaiting_selection', False)}")

    message = data4.get('message', '')
    print(f"\n   Message Preview (first 300 chars):")
    print(f"   {message[:300]}")

    # Check for success
    products = data4.get('products', [])
    if len(products) > 0:
        print(f"\n   ✅ SUCCESS: Found {len(products)} PowerSource accessories!")
        for idx, p in enumerate(products[:5], 1):
            print(f"      {idx}. {p['name']} (GIN: {p['gin']})")
        return True
    else:
        print(f"\n   ❌ FAILED: No accessories found!")
        print(f"   Full Response:")
        print(json.dumps(data4, indent=2))
        return False

if __name__ == "__main__":
    try:
        success = test_accessory_search()

        print("\n" + "=" * 80)
        if success:
            print("✅ TEST PASSED: PowerSource accessories search working!")
        else:
            print("❌ TEST FAILED: No accessories returned")
            print("\nNext Steps:")
            print("1. Check backend logs: tail -f logs/esab-recommender.log")
            print("2. Look for AccessoryStateProcessor search logs")
            print("3. Check SearchOrchestrator logs")
            print("4. Verify Neo4j has 'Powersource Accessories' category")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
