"""
Quick test to verify ORDER BY fix resolved the skipping issue.

User reported: "Even more worse now - feeder, cooler all bypassed went to torches"

Expected after fix: Feeder, Cooler, and Interconnector should show compatible products.
"""
import requests
import json

API_BASE = "http://localhost:8000"

def test_complete_flow():
    print("=" * 80)
    print("TESTING COMPLETE FLOW AFTER ORDER BY FIX")
    print("=" * 80)
    print()

    # Step 1: Start new session and select PowerSource
    print("1. Starting new session with PowerSource: Warrior 500i...")
    r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
        "message": "Warrior 500i CC/CV 380 - 415V",
        "language": "en"
    })
    data = r.json()
    session_id = data.get('session_id')
    print(f"   Session ID: {session_id}")
    print(f"   Current State: {data.get('current_state')}")
    print(f"   Products: {len(data.get('products', []))}")
    print()

    # Step 2: Select the PowerSource (should be only one match)
    if len(data.get('products', [])) > 0:
        ps_gin = data['products'][0]['gin']
        print(f"2. Auto-selecting PowerSource (GIN: {ps_gin})...")
        r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
            "session_id": session_id,
            "message": "select",
            "language": "en"
        })
        data = r.json()
        print(f"   Current State: {data.get('current_state')}")
        feeder_products = len(data.get('products', []))
        print(f"   Feeder Products: {feeder_products}")

        if feeder_products > 0:
            print("   ✅ SUCCESS: Feeder products shown (not skipped)")
        else:
            print("   ❌ FAILED: Feeder was auto-skipped (0 products)")
        print()

        # Step 3: Skip feeder to check Cooler
        print("3. Skipping Feeder to test Cooler...")
        r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
            "session_id": session_id,
            "message": "skip",
            "language": "en"
        })
        data = r.json()
        print(f"   Current State: {data.get('current_state')}")
        cooler_products = len(data.get('products', []))
        print(f"   Cooler Products: {cooler_products}")

        if cooler_products > 0:
            print("   ✅ SUCCESS: Cooler products shown (not skipped)")
        else:
            print("   ❌ FAILED: Cooler was auto-skipped (0 products)")
        print()

        # Step 4: Skip cooler to check Interconnector
        print("4. Skipping Cooler to test Interconnector...")
        r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
            "session_id": session_id,
            "message": "skip",
            "language": "en"
        })
        data = r.json()
        print(f"   Current State: {data.get('current_state')}")
        interconn_products = len(data.get('products', []))
        print(f"   Interconnector Products: {interconn_products}")

        if interconn_products > 0:
            print("   ✅ SUCCESS: Interconnector products shown (not skipped)")
        else:
            print("   ❌ FAILED: Interconnector was auto-skipped (0 products)")
    else:
        print("   ❌ No PowerSource products found to continue test")

    print()
    print("=" * 80)
    print("TEST COMPLETE - CHECK RESULTS ABOVE")
    print("=" * 80)


if __name__ == "__main__":
    try:
        test_complete_flow()
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
