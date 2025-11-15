#!/usr/bin/env python3
"""
Test that Interconnector search is fixed after adding search_config.json entry.
"""

import requests
import json

API_BASE = "http://localhost:8000"

def test_interconnector_fix():
    """Test the complete Interconnector search flow"""

    print("=" * 80)
    print("TESTING INTERCONNECTOR FIX")
    print("=" * 80)
    print()

    # Step 1: Create session and select PowerSource
    print("Step 1: Selecting PowerSource (Aristo 500ix)")
    response1 = requests.post(
        f"{API_BASE}/api/v1/configurator/message",
        json={
            "session_id": None,
            "message": "I need Aristo 500ix",
            "language": "en"
        }
    )
    data1 = response1.json()
    session_id = data1["session_id"]
    print(f"  Session: {session_id}")
    print(f"  State: {data1['current_state']}")

    if data1.get('products'):
        first_ps = data1['products'][0]
        print(f"  Selecting: {first_ps['name']}")
        requests.post(
            f"{API_BASE}/api/v1/configurator/select",
            json={"session_id": session_id, "gin": first_ps['gin'], "product_data": first_ps}
        )
    print()

    # Step 2: Select Feeder
    print("Step 2: Selecting Feeder (RobustFeed U6)")
    response2 = requests.post(
        f"{API_BASE}/api/v1/configurator/message",
        json={
            "session_id": session_id,
            "message": "RobustFeed U6",
            "language": "en"
        }
    )
    data2 = response2.json()
    print(f"  State: {data2['current_state']}")

    if data2.get('products'):
        first_feeder = data2['products'][0]
        print(f"  Selecting: {first_feeder['name']}")
        requests.post(
            f"{API_BASE}/api/v1/configurator/select",
            json={"session_id": session_id, "gin": first_feeder['gin'], "product_data": first_feeder}
        )
    print()

    # Step 3: THE FIX TEST - Search for Interconnector with explicit message
    print("Step 3: THE FIX TEST - Interconnector search")
    print("-" * 80)
    print("User message: 'I want a gas cooled cable with 5m'")
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

    print(f"Response Status: {response3.status_code}")
    print(f"Current State: {data3.get('current_state', 'UNKNOWN')}")
    print(f"Products Count: {len(data3.get('products', []))}")
    print()

    # Check for errors
    if 'error' in data3:
        print(f"❌ ERROR: {data3['error']}")
        return False

    if 'search failed' in data3.get('message', '').lower() or 'no compatible' in data3.get('message', '').lower():
        print(f"❌ SEARCH FAILED: {data3.get('message', '')}")
        return False

    # Check for products and scores
    products = data3.get('products', [])
    has_scores = any('Score:' in p.get('name', '') for p in products)

    if products:
        print("Interconnector Products Found:")
        for i, p in enumerate(products[:5], 1):
            name = p.get('name', '')
            score_status = '✅ with score' if 'Score:' in name else '⚠️  no score'
            print(f"  {i}. {score_status} - {name}")
        print()

    # VERDICT
    print("=" * 80)
    print("TEST RESULT")
    print("=" * 80)

    if products and has_scores:
        print("✅ SUCCESS!")
        print("   - Interconnector search returned results")
        print("   - Lucene scores are appearing")
        print("   - search_config.json fix is working!")
        print("   - No TypeError (search_interconnector_smart accepts user_message)")
        print()
        print("🎉 FIX VERIFIED! Interconnector Lucene search is now working!")
        return True
    elif products and not has_scores:
        print("⚠️  PARTIAL SUCCESS")
        print("   - Products returned (traditional search working)")
        print("   - But no Lucene scores (Lucene might be disabled or not finding results)")
        return False
    else:
        print("❌ FAILED")
        print("   - No products returned")
        print("   - Check server logs for errors")
        return False

if __name__ == "__main__":
    try:
        success = test_interconnector_fix()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST EXCEPTION: {e}")
        exit(1)
