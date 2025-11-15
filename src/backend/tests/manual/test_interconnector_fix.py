#!/usr/bin/env python3
"""
Test the Interconnector Lucene fix.

This reproduces the exact error scenario:
  1. User selects PowerSource
  2. User selects Feeder
  3. User sends: "I want a gas cooled cable with 5m" at Interconnector state
  4. Expected: Lucene search with scores displayed
  5. Before fix: TypeError because search_interconnector doesn't accept user_message
  6. After fix: Lucene scores appear successfully
"""

import requests
import time
import json

API_BASE = "http://localhost:8000"

def test_interconnector_lucene_fix():
    """Test Interconnector Lucene search with explicit user message"""

    print("=" * 80)
    print("TEST: Interconnector Lucene Fix - 'I want a gas cooled cable with 5m'")
    print("=" * 80)
    print()

    # Step 1: Start with PowerSource selection
    print("STEP 1: PowerSource Selection")
    print("-" * 80)

    response1 = requests.post(
        f"{API_BASE}/api/v1/configurator/message",
        json={
            "session_id": None,
            "message": "I need a 500A MIG welder",
            "language": "en"
        }
    )

    data1 = response1.json()
    session_id = data1["session_id"]

    print(f"Session ID: {session_id}")
    print(f"State: {data1['current_state']}")
    print(f"Products: {len(data1.get('products', []))}")

    # Check PowerSource scores
    print("\nPowerSource Products (checking for Lucene scores):")
    for i, p in enumerate(data1.get('products', [])[:3], 1):
        name = p.get('name', '')
        has_score = 'Score:' in name
        status = '✅' if has_score else '❌'
        print(f"  {i}. {status} {name}")
    print()

    # Select first PowerSource
    if data1.get('products') and data1['current_state'] == 'power_source_selection':
        first_product = data1['products'][0]
        print(f"Selecting PowerSource: {first_product['name']}")

        select_response = requests.post(
            f"{API_BASE}/api/v1/configurator/select",
            json={
                "session_id": session_id,
                "gin": first_product['gin'],
                "product_data": first_product
            }
        )

        select_data = select_response.json()
        print(f"State after selection: {select_data.get('current_state', 'UNKNOWN')}")
        print()
    elif data1['current_state'] == 'feeder_selection':
        print("Note: System auto-advanced to Feeder selection (compound request handling)")
        print()

    # Step 2: Select Feeder (to advance to Interconnector state)
    time.sleep(1)
    print("STEP 2: Feeder Selection")
    print("-" * 80)

    response2 = requests.post(
        f"{API_BASE}/api/v1/configurator/message",
        json={
            "session_id": session_id,
            "message": "I want a water-cooled feeder",
            "language": "en"
        }
    )

    data2 = response2.json()
    print(f"State: {data2['current_state']}")
    print(f"Products: {len(data2.get('products', []))}")

    # Check Feeder scores
    print("\nFeeder Products:")
    for i, p in enumerate(data2.get('products', [])[:3], 1):
        name = p.get('name', '')
        has_score = 'Score:' in name
        status = '✅' if has_score else '❌'
        print(f"  {i}. {status} {name}")
    print()

    # Select first Feeder
    if data2.get('products'):
        first_feeder = data2['products'][0]
        print(f"Selecting Feeder: {first_feeder['name']}")

        select_response2 = requests.post(
            f"{API_BASE}/api/v1/configurator/select",
            json={
                "session_id": session_id,
                "gin": first_feeder['gin'],
                "product_data": first_feeder
            }
        )

        select_data2 = select_response2.json()
        print(f"State after selection: {select_data2.get('current_state', 'UNKNOWN')}")
        print()

    # Step 3: THE FIX TEST - Interconnector with explicit user message
    time.sleep(1)
    print("STEP 3: Interconnector Search - THE FIX!")
    print("-" * 80)
    print("Sending: 'I want a gas cooled cable with 5m'")
    print()

    response3 = requests.post(
        f"{API_BASE}/api/v1/configurator/message",
        json={
            "session_id": session_id,
            "message": "I want a gas cooled cable with 5m",
            "language": "en"
        }
    )

    data3 = response3.json()

    print(f"State: {data3['current_state']}")
    print(f"Products: {len(data3.get('products', []))}")
    print()

    # Check Interconnector scores - THIS IS THE FIX TEST
    print("Interconnector Products (checking for Lucene scores - FIXED!):")
    interconnector_scores = []
    for i, p in enumerate(data3.get('products', [])[:5], 1):
        name = p.get('name', '')
        has_score = 'Score:' in name
        status = '✅' if has_score else '❌'
        print(f"  {i}. {status} {name}")
        if has_score:
            interconnector_scores.append(name)
    print()

    # Check for error message
    if 'error' in data3:
        print(f"❌ ERROR: {data3['error']}")
    elif 'Product search failed' in data3.get('message', ''):
        print(f"❌ SEARCH FAILED: {data3['message']}")

    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"✅ PowerSource scores: {'WORKING' if any('Score:' in p.get('name', '') for p in data1.get('products', [])) else 'NOT WORKING'}")
    print(f"✅ Feeder scores: {'WORKING' if any('Score:' in p.get('name', '') for p in data2.get('products', [])) else 'NOT WORKING'}")
    print(f"{'✅' if interconnector_scores else '❌'} Interconnector scores: {'WORKING' if interconnector_scores else 'NOT WORKING - FIX FAILED!'}")
    print()

    if interconnector_scores:
        print("🎉🎉🎉 SUCCESS! The fix is working - Interconnector Lucene scores now appear!")
        print("    No more TypeError! search_interconnector_smart is being called correctly!")
    else:
        print("⚠️  FAILED! Scores still not appearing for Interconnector.")
        if 'error' in data3 or 'Product search failed' in data3.get('message', ''):
            print("    The search is still failing. Need to debug further.")
        else:
            print("    Search succeeded but scores not appearing. Check Lucene configuration.")
    print()

if __name__ == "__main__":
    test_interconnector_lucene_fix()
