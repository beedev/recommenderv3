#!/usr/bin/env python3
"""
Simple direct test for Interconnector Lucene.

Tests that search_interconnector_smart accepts user_message parameter
and returns Lucene scores.
"""

import requests
import json

API_BASE = "http://localhost:8000"

def test_interconnector_direct():
    """Direct test of Interconnector Lucene search"""

    print("=" * 80)
    print("DIRECT TEST: Interconnector Lucene Search")
    print("=" * 80)
    print()

    # Create a new session with PowerSource already selected
    print("Step 1: Select PowerSource")
    response1 = requests.post(
        f"{API_BASE}/api/v1/configurator/message",
        json={
            "session_id": None,
            "message": "Aristo 500ix",
            "language": "en"
        }
    )
    data1 = response1.json()
    session_id = data1["session_id"]
    print(f"Session ID: {session_id}")
    print(f"State: {data1['current_state']}")
    print()

    # If PowerSource products shown, select the first one
    if data1.get('products') and data1['current_state'] == 'power_source_selection':
        first_ps = data1['products'][0]
        print(f"Selecting: {first_ps['name']}")

        select1 = requests.post(
            f"{API_BASE}/api/v1/configurator/select",
            json={
                "session_id": session_id,
                "gin": first_ps['gin'],
                "product_data": first_ps
            }
        )
        print(f"Selection result: {select1.status_code}")
        print()

    # Step 2: Select Feeder
    print("Step 2: Select Feeder")
    response2 = requests.post(
        f"{API_BASE}/api/v1/configurator/message",
        json={
            "session_id": session_id,
            "message": "RobustFeed U6",
            "language": "en"
        }
    )
    data2 = response2.json()
    print(f"State: {data2['current_state']}")
    print()

    # If Feeder products shown, select the first one
    if data2.get('products') and 'feeder' in data2['current_state'].lower():
        first_feeder = data2['products'][0]
        print(f"Selecting: {first_feeder['name']}")

        select2 = requests.post(
            f"{API_BASE}/api/v1/configurator/select",
            json={
                "session_id": session_id,
                "gin": first_feeder['gin'],
                "product_data": first_feeder
            }
        )
        print(f"Selection result: {select2.status_code}")
        print()

    # Step 3: THE CRITICAL TEST - Interconnector search with user_message
    print("Step 3: Interconnector Search with user_message")
    print("-" * 80)
    print("Sending: 'I want a gas cooled cable with 5m'")
    print()

    try:
        response3 = requests.post(
            f"{API_BASE}/api/v1/configurator/message",
            json={
                "session_id": session_id,
                "message": "I want a gas cooled cable with 5m",
                "language": "en"
            },
            timeout=10
        )

        data3 = response3.json()

        print(f"Response Status: {response3.status_code}")
        print(f"Current State: {data3.get('current_state', 'UNKNOWN')}")
        print(f"Products Count: {len(data3.get('products', []))}")
        print()

        # Check for errors
        if 'error' in data3:
            print(f"❌ ERROR: {data3['error']}")
            print()
            return False

        if 'search failed' in data3.get('message', '').lower():
            print(f"❌ SEARCH FAILED: {data3['message']}")
            print()
            return False

        # Check for Lucene scores
        products = data3.get('products', [])
        has_scores = any('Score:' in p.get('name', '') for p in products)

        if products:
            print("Products returned:")
            for i, p in enumerate(products[:5], 1):
                name = p.get('name', '')
                score_status = '✅' if 'Score:' in name else '❌'
                print(f"  {i}. {score_status} {name}")
            print()

        # Summary
        print("=" * 80)
        print("TEST RESULT")
        print("=" * 80)

        if has_scores:
            print("✅ SUCCESS!")
            print("   - No TypeError occurred")
            print("   - search_interconnector_smart is working")
            print("   - Lucene scores are being returned")
            print("   - Fix is VERIFIED!")
            return True
        else:
            if products:
                print("⚠️  PARTIAL SUCCESS")
                print("   - No TypeError (search_interconnector_smart accepts user_message)")
                print("   - But no Lucene scores appeared")
                print("   - Check Lucene configuration")
            else:
                print("❌ FAILED")
                print("   - No products returned")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ REQUEST ERROR: {e}")
        return False

if __name__ == "__main__":
    success = test_interconnector_direct()
    exit(0 if success else 1)
