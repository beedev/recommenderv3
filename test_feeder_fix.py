#!/usr/bin/env python3
"""Test script to verify feeder search fix"""
import requests
import json

API_BASE = "http://localhost:8000/api/v1/configurator"

def test_sequential_flow():
    """Test S1→S2 sequential flow"""
    print("=" * 60)
    print("Testing Sequential Flow (S1→S2)")
    print("=" * 60)

    # Step 1: Start new session with PowerSource request
    print("\n1. Requesting PowerSource...")
    r1 = requests.post(f"{API_BASE}/message", json={
        "session_id": None,
        "message": "Aristo 500ix",
        "language": "en"
    })
    data1 = r1.json()
    session_id = data1["session_id"]
    print(f"   Session: {session_id}")
    print(f"   State: {data1['current_state']}")
    print(f"   Products: {len(data1['products'])}")

    # Step 2: Select PowerSource
    print("\n2. Selecting Aristo 500ix...")
    r2 = requests.post(f"{API_BASE}/select", json={
        "session_id": session_id,
        "gin": "0446200880",
        "user_id": "test",
        "language": "en"
    })
    data2 = r2.json()
    print(f"   State: {data2.get('current_state', 'N/A')}")
    print(f"   Message preview: {data2.get('message', 'No message')[:100]}")

    # Step 3: Request Feeder
    print("\n3. Requesting Feeder...")
    r3 = requests.post(f"{API_BASE}/message", json={
        "session_id": session_id,
        "message": "robustfeed",
        "language": "en"
    })
    data3 = r3.json()
    print(f"   State: {data3['current_state']}")
    print(f"   Products: {len(data3.get('products', []))}")
    print(f"   Error: {data3.get('error', False)}")

    if data3.get('error'):
        print(f"\n   ❌ ERROR: {data3.get('message', 'Unknown error')}")
        return False
    elif len(data3.get('products', [])) > 0:
        print(f"\n   ✅ SUCCESS: Found {len(data3['products'])} feeder products")
        print(f"   First product: {data3['products'][0]['name']}")
        return True
    else:
        print(f"\n   ⚠️  WARNING: No products found")
        return False

if __name__ == "__main__":
    try:
        success = test_sequential_flow()
        print("\n" + "=" * 60)
        if success:
            print("✅ TEST PASSED: Feeder search working correctly")
        else:
            print("❌ TEST FAILED: Feeder search not working")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
