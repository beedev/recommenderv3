#!/usr/bin/env python3
"""
Test the fix for Lucene scores appearing on explicit user messages.

Flow:
  1. Send "I need a 500A MIG welder" → PowerSource with scores (already working)
  2. Send "I want a water-cooled feeder" → Feeder with scores (FIXED!)
"""

import requests
import json
import time

API_BASE = "http://localhost:8000"

def test_lucene_scores_sequential_flow():
    """Test Lucene scores appear in sequential explicit flow"""

    print("=" * 80)
    print("TEST: Lucene Scores - Sequential Explicit Messages")
    print("=" * 80)
    print()

    # Step 1: Send PowerSource request
    print("STEP 1: PowerSource Search - Lucene Scores")
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
    print(f"Products found: {len(data1.get('products', []))}")
    print()

    # Check PowerSource scores
    print("PowerSource Products (checking for Lucene scores):")
    for i, p in enumerate(data1.get('products', [])[:5], 1):
        name = p.get('name', '')
        has_score = 'Score:' in name
        status = '✅' if has_score else '❌'
        print(f"  {i}. {status} {name}")
    print()

    # Step 2: Send Feeder request at Feeder state
    print("STEP 2: Explicit Feeder Search - Testing the FIX")
    print("-" * 80)
    print("Waiting 2 seconds for server to process...")
    time.sleep(2)

    # First, select the PowerSource to advance to Feeder state
    if data1.get('products'):
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
        print(f"State after selection: {select_data['current_state']}")
        print()

    # Now send explicit Feeder message
    print("Sending explicit Feeder message...")
    print()

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
    print(f"Products found: {len(data2.get('products', []))}")
    print()

    # Check Feeder scores - THIS IS THE FIX TEST
    print("Feeder Products (checking for Lucene scores - FIXED!):")
    feeder_scores = []
    for i, p in enumerate(data2.get('products', [])[:5], 1):
        name = p.get('name', '')
        has_score = 'Score:' in name
        status = '✅' if has_score else '❌'
        print(f"  {i}. {status} {name}")
        if has_score:
            feeder_scores.append(name)
    print()

    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"✅ PowerSource scores: {'WORKING' if any('Score:' in p.get('name', '') for p in data1.get('products', [])) else 'NOT WORKING'}")
    print(f"{'✅' if feeder_scores else '❌'} Feeder scores: {'WORKING' if feeder_scores else 'NOT WORKING - FIX FAILED!'}")
    print()

    if feeder_scores:
        print("🎉 SUCCESS! The fix is working - Lucene scores now appear for explicit Feeder messages!")
    else:
        print("⚠️  FAILED! Scores still not appearing for Feeder. Need to debug further.")
    print()

if __name__ == "__main__":
    test_lucene_scores_sequential_flow()
