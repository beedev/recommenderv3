"""Quick test to verify Remote search fix via API"""
import requests
import json

API_BASE = "http://localhost:8000"

def test_remote_fix():
    print("=" * 80)
    print("TESTING REMOTE SEARCH FIX")
    print("=" * 80)
    print()

    # Step 1: Start new session
    print("1. Creating new session...")
    r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
        "message": "I need a power source",
        "language": "en"
    })
    data = r.json()
    session_id = data['session_id']
    print(f"   Session ID: {session_id}")
    print()

    # Step 2: Request PowerSource and select via message
    print("2. Selecting PowerSource: Warrior 500i CC/CV 380 - 415V (0465350883)")
    r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
        "session_id": session_id,
        "message": "Warrior 500i CC/CV 380 - 415V",
        "language": "en"
    })
    data = r.json()
    print(f"   State: {data['current_state']}")
    print()

    # Step 3: Select Feeder
    print("3. Selecting Feeder: Robust Feed Pro Water Cooled (0445800881)")
    r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
        "session_id": session_id,
        "message": "Robust Feed Pro Water Cooled",
        "language": "en"
    })
    data = r.json()
    print(f"   State: {data['current_state']}")
    print()

    # Step 4: Select Cooler
    print("4. Selecting Cooler: Cool 2 (0465427880)")
    r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
        "session_id": session_id,
        "message": "Cool 2",
        "language": "en"
    })
    data = r.json()
    print(f"   State: {data['current_state']}")
    print()

    # Step 5: Skip to Remote (send "done" to skip optional components)
    print("5. Sending 'done' to proceed to Remote selection...")
    r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
        "session_id": session_id,
        "message": "done",
        "language": "en"
    })
    data = r.json()
    current_state = data['current_state']
    products = data.get('products', [])

    print(f"   Current State: {current_state}")
    print(f"   Products Found: {len(products)}")
    print()

    if current_state == 'remote_selection':
        if len(products) > 0:
            print("✅ SUCCESS! Remote search returned products:")
            for i, p in enumerate(products[:5], 1):
                print(f"   {i}. {p.get('name')} (GIN: {p.get('gin')})")
            print()
            if len(products) >= 4:
                print(f"✅ EXPECTED: Found {len(products)} products (expected ≥4)")
            else:
                print(f"⚠️  WARNING: Found {len(products)} products (expected ≥4)")
        else:
            print("❌ FAILED: Remote search returned 0 products")
            print("   Check server logs for Cypher query")
    else:
        print(f"❌ ERROR: Not at Remote selection state (current: {current_state})")

    print()
    print("=" * 80)

if __name__ == "__main__":
    try:
        test_remote_fix()
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
