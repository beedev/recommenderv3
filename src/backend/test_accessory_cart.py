"""
Quick test to verify accessories appear in response_json for cart display.
"""

import requests
import json

API_BASE = "http://localhost:8000"

def test_accessory_in_cart():
    print("🧪 Testing Accessory Cart Display Fix")
    print("=" * 60)

    # Start session
    r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
        "message": "Warrior 500i",
        "language": "en"
    })
    data = r.json()
    session_id = data['session_id']
    print(f"Session ID: {session_id}")

    # Select PowerSource
    r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
        "session_id": session_id,
        "message": "select",
        "language": "en"
    })
    data = r.json()
    print(f"State after PowerSource: {data['current_state']}")
    print(f"PowerSource selected: {data['response_json'].get('PowerSource', {}).get('name', 'None')}")

    # Skip to Connectivity (6 "done" messages)
    for i in range(6):
        r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
            "session_id": session_id,
            "message": "done",
            "language": "en"
        })

    data = r.json()
    print(f"\nState: {data['current_state']}")
    print(f"Products available: {len(data.get('products', []))}")

    # Select first connectivity product
    if data.get('products'):
        r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
            "session_id": session_id,
            "message": "select",
            "language": "en"
        })
        data = r.json()

        print("\n✅ RESPONSE_JSON VERIFICATION:")
        print("=" * 60)

        # Check if Connectivity field exists
        connectivity = data['response_json'].get('Connectivity')
        if connectivity is not None:
            print(f"✅ 'Connectivity' field present: {type(connectivity).__name__}")
            if isinstance(connectivity, list) and len(connectivity) > 0:
                print(f"✅ Connectivity has {len(connectivity)} item(s)")
                print(f"✅ First item: {connectivity[0].get('name')}")
                print(f"✅ GIN: {connectivity[0].get('gin')}")
                print("\n🎯 SUCCESS: Accessory is present in response_json!")
                print("Frontend cart WILL display this item correctly.")
            elif isinstance(connectivity, list):
                print("⚠️  Connectivity is empty list (no items selected yet)")
            else:
                print(f"Connectivity value: {connectivity}")
        else:
            print("❌ 'Connectivity' field MISSING from response_json")
            print("This would cause cart display issues!")

        # Show all accessory fields
        print("\n📋 ALL ACCESSORY FIELDS:")
        accessory_fields = [
            'PowerSourceAccessories', 'FeederAccessories',
            'FeederConditionalAccessories', 'InterconnectorAccessories',
            'Remotes', 'RemoteAccessories', 'RemoteConditionalAccessories',
            'Connectivity', 'FeederWears', 'Accessories'
        ]
        for field in accessory_fields:
            value = data['response_json'].get(field)
            if value is not None:
                if isinstance(value, list):
                    print(f"  ✅ {field}: {len(value)} items")
                else:
                    print(f"  ✅ {field}: {value}")
            else:
                print(f"  ❌ {field}: MISSING")

if __name__ == "__main__":
    try:
        test_accessory_in_cart()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
