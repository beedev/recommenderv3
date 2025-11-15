#!/usr/bin/env python3
"""
Debug test to see what's happening with state transitions.
"""

import requests
import json

API_BASE = "http://localhost:8000"

def test_debug():
    """Debug test to understand state flow"""

    print("=" * 80)
    print("DEBUG TEST: State Transition Flow")
    print("=" * 80)
    print()

    # Step 1: New session, send PowerSource message
    print("Step 1: Send 'I need Aristo 500ix power source'")
    response1 = requests.post(
        f"{API_BASE}/api/v1/configurator/message",
        json={
            "session_id": None,
            "message": "I need Aristo 500ix power source",
            "language": "en"
        }
    )
    data1 = response1.json()
    session_id = data1["session_id"]

    print(f"Response 1:")
    print(f"  Session: {session_id}")
    print(f"  State: {data1['current_state']}")
    print(f"  Products: {len(data1.get('products', []))}")
    if data1.get('products'):
        print(f"  First product: {data1['products'][0]['name']}")
    print(f"  Awaiting selection: {data1.get('awaiting_selection', False)}")
    print()

    # If we have products, try to select the first one
    if data1.get('products'):
        first = data1['products'][0]
        print(f"Step 2: Select '{first['name']}'")

        select_response = requests.post(
            f"{API_BASE}/api/v1/configurator/select",
            json={
                "session_id": session_id,
                "gin": first['gin'],
                "product_data": first
            }
        )

        print(f"  Status: {select_response.status_code}")

        if select_response.status_code == 422:
            print(f"  ERROR 422:")
            print(json.dumps(select_response.json(), indent=2))
        else:
            select_data = select_response.json()
            print(f"  New state: {select_data.get('current_state', 'UNKNOWN')}")
            print(f"  Message: {select_data.get('message', '')[:100]}...")
        print()

if __name__ == "__main__":
    test_debug()
