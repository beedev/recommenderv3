"""
Debug script to reproduce and diagnose accessory selection persistence issue.

Issue: Selected accessories show confirmation message but don't appear in response_json.
User reported: COOLANT LIQUID selection confirmed but PowerSourceAccessories remains empty [].

This script will:
1. Start a new session
2. Select a PowerSource (Warrior 500i)
3. Skip through to PowerSourceAccessories state
4. Select a PowerSourceAccessory (COOLANT LIQUID)
5. Check if it appears in response_json

Expected: PowerSourceAccessories should contain the selected accessory
Actual (bug): PowerSourceAccessories is empty []

Debug logging added to:
- state_orchestrator.py select_product() - lines 277-296
- configurator.py select endpoint - lines 847-874
"""

import requests
import json

API_BASE = "http://localhost:8000"

def print_section(title):
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)

def test_accessory_selection():
    print_section("🧪 ACCESSORY SELECTION DEBUG TEST")

    # Step 1: Start new session with PowerSource selection
    print("\n1️⃣ Starting new session and selecting PowerSource...")
    r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
        "message": "Warrior 500i",
        "language": "en"
    })
    data = r.json()
    session_id = data['session_id']
    print(f"   Session ID: {session_id}")
    print(f"   Current State: {data['current_state']}")
    print(f"   Products: {len(data.get('products', []))}")

    # Auto-select PowerSource if only one result
    if len(data.get('products', [])) == 1:
        product = data['products'][0]
        print(f"\n2️⃣ Auto-selecting PowerSource: {product['name']} (GIN: {product['gin']})")

        r = requests.post(f"{API_BASE}/api/v1/configurator/select", json={
            "session_id": session_id,
            "product_gin": product['gin'],
            "product_data": product
        })
        data = r.json()
        print(f"   ✅ PowerSource selected")
        print(f"   Current State: {data.get('current_state', 'MISSING')}")
        print(f"   Response JSON PowerSource: {data.get('response_json', {}).get('PowerSource', {}).get('name', 'None')}")

        # Debug: Print full response if current_state missing
        if 'current_state' not in data:
            print(f"   ⚠️  WARNING: 'current_state' missing from response!")
            print(f"   Response keys: {list(data.keys())}")
            print(f"   Full response: {json.dumps(data, indent=2)[:500]}...")

    # Step 3: Skip through states to PowerSourceAccessories
    print("\n3️⃣ Skipping to PowerSourceAccessories state...")
    skip_count = 0
    while data.get('current_state') != 'powersource_accessories_selection' and skip_count < 10:
        r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
            "session_id": session_id,
            "message": "done",
            "language": "en"
        })
        data = r.json()
        skip_count += 1
        print(f"   Skipped → {data.get('current_state', 'UNKNOWN')}")

    if data.get('current_state') != 'powersource_accessories_selection':
        print(f"\n❌ FAILED: Could not reach powersource_accessories_selection state")
        print(f"   Current state: {data.get('current_state', 'UNKNOWN')}")
        return False

    print(f"\n   ✅ Reached powersource_accessories_selection")
    print(f"   Products available: {len(data.get('products', []))}")

    # Display available accessories
    if data.get('products'):
        print(f"\n   Available PowerSource Accessories:")
        for i, product in enumerate(data['products'][:5], 1):
            print(f"      {i}. {product['name']} (GIN: {product['gin']})")

    # Step 4: Select first PowerSourceAccessory
    if data.get('products') and len(data['products']) > 0:
        accessory = data['products'][0]
        print(f"\n4️⃣ Selecting PowerSource Accessory: {accessory['name']} (GIN: {accessory['gin']})")

        r = requests.post(f"{API_BASE}/api/v1/configurator/select", json={
            "session_id": session_id,
            "product_gin": accessory['gin'],
            "product_data": accessory
        })
        data = r.json()

        print(f"\n   📨 API Response:")
        print(f"   Message: {data.get('message', 'No message')[:100]}...")
        print(f"   Current State: {data['current_state']}")

        # CRITICAL CHECK: Is accessory in PowerSourceAccessories?
        powersource_accessories = data['response_json'].get('PowerSourceAccessories', None)

        print(f"\n   🔍 CRITICAL CHECK:")
        print(f"   PowerSourceAccessories field present: {powersource_accessories is not None}")

        if powersource_accessories is not None:
            print(f"   PowerSourceAccessories type: {type(powersource_accessories)}")
            if isinstance(powersource_accessories, list):
                print(f"   PowerSourceAccessories length: {len(powersource_accessories)}")
                if len(powersource_accessories) > 0:
                    print(f"\n   ✅ SUCCESS: Accessory found in response_json!")
                    for i, acc in enumerate(powersource_accessories, 1):
                        print(f"      {i}. {acc.get('name')} (GIN: {acc.get('gin')})")
                    return True
                else:
                    print(f"\n   ❌ FAILED: PowerSourceAccessories is empty []")
                    print(f"   Expected to contain: {accessory['name']} (GIN: {accessory['gin']})")
                    return False
            else:
                print(f"   ❌ FAILED: PowerSourceAccessories is not a list: {powersource_accessories}")
                return False
        else:
            print(f"   ❌ FAILED: PowerSourceAccessories field missing from response_json")
            return False
    else:
        print(f"\n   ❌ No accessories available to test")
        return False

if __name__ == "__main__":
    try:
        print("\n🚀 Starting server check...")
        r = requests.get(f"{API_BASE}/health")
        health = r.json()
        print(f"   Server Status: {health.get('status')}")

        result = test_accessory_selection()

        print_section("TEST RESULT")
        if result:
            print("✅ SUCCESS: Accessory selection is working correctly!")
        else:
            print("❌ FAILED: Accessory selection bug reproduced")
            print("\n📋 Next Steps:")
            print("   1. Check server logs for debug output")
            print("   2. Look for 🔍 DEBUG markers in logs")
            print("   3. Verify getattr/setattr operations in select_product()")
            print("   4. Check _serialize_response_json() execution")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
