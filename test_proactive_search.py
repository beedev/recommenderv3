#!/usr/bin/env python3
"""
Test Proactive Search After PowerSource Selection

This script tests whether proactive feeder search is triggered after selecting
PowerSource GIN: 0446200880 (Aristo 500ix CE)
"""

import requests
import json

API_BASE = "http://localhost:8000/api/v1/configurator"

def test_proactive_search():
    """Test proactive search after PowerSource selection"""
    print("=" * 80)
    print("TEST: Proactive Search After PowerSource Selection")
    print("=" * 80)

    # Step 1: Create new session and search for PowerSource
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
    print(f"   ✅ Found {len(data1.get('products', []))} power sources")

    # Step 2: Select PowerSource GIN: 0446200880
    print("\n2️⃣  STEP 2: Selecting Aristo 500ix CE (GIN: 0446200880)...")
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

    if r2.status_code != 200:
        print(f"   ❌ ERROR: HTTP {r2.status_code}")
        print(f"   Response: {r2.text}")
        return False

    data2 = r2.json()

    print(f"\n3️⃣  STEP 3: Analyzing Response...")
    print(f"   📍 Current State: {data2['current_state']}")
    print(f"   📦 Products Count: {len(data2.get('products', []))}")
    print(f"   ⏳ Awaiting Selection: {data2.get('awaiting_selection', False)}")

    # Check message content
    message = data2.get('message', '')
    print(f"\n4️⃣  STEP 4: Message Analysis...")
    print(f"   Message Preview (first 200 chars):")
    print(f"   {message[:200]}")

    # Diagnostic checks
    print(f"\n5️⃣  STEP 5: Diagnostic Results...")

    products = data2.get('products', [])

    if len(products) > 0:
        print(f"   ✅ SUCCESS: Proactive search returned {len(products)} feeders!")
        print(f"\n   📋 Products Found:")
        for idx, p in enumerate(products[:5], 1):
            print(f"      {idx}. {p['name']} (GIN: {p['gin']})")

        if "Provide requirements" in message:
            print(f"\n   ⚠️  WARNING: Products found BUT message contains fallback prompt!")
            print(f"   This indicates message_generator might be using wrong template.")
        else:
            print(f"\n   ✅ Message looks correct (no fallback prompt detected)")

        return True
    else:
        print(f"   ❌ FAILED: No products returned!")
        print(f"\n   Possible reasons:")
        print(f"   1. Neo4j has no feeders compatible with GIN 0446200880")
        print(f"   2. Proactive search exception occurred")
        print(f"   3. Search returned 0 results due to query issue")

        if "Provide requirements" in message:
            print(f"\n   ✅ Fallback prompt detected (expected when no products)")

        # Print full response for debugging
        print(f"\n   Full Response JSON:")
        print(json.dumps(data2, indent=2))

        return False

if __name__ == "__main__":
    try:
        success = test_proactive_search()

        print("\n" + "=" * 80)
        if success:
            print("✅ TEST PASSED: Proactive search is working correctly!")
        else:
            print("❌ TEST FAILED: Proactive search did not return products")
            print("\nNext Steps:")
            print("1. Check backend logs: tail -f logs/esab-recommender.log")
            print("2. Look for: '🔍 Attempting proactive search'")
            print("3. Look for: '📦 Found X compatible products'")
            print("4. Check Neo4j: Does GIN 0446200880 have compatible feeders?")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
