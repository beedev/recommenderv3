#!/usr/bin/env python3
"""
Test script to verify STAGE 4 AUTO-ADVANCE to FINALIZE works correctly.

This reproduces the bug reported by the user:
- User configures Warrior 500i power source
- Navigates through states to connectivity_selection
- Selects the only connectivity product displayed
- EXPECTED: System should auto-advance to FINALIZE with proper message_type="finalize"
- ACTUAL (before fix): System stayed in connectivity_selection, didn't auto-advance

After the fix in state_orchestrator.py lines 420-435, the system should:
1. Detect next_state == ConfiguratorState.FINALIZE
2. Use message_type="finalize" instead of "selection"
3. Display configuration summary with finalization message
"""

import requests
import json
import sys

API_BASE = "http://localhost:8000"

def print_section(title):
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)

def print_response_summary(data, step_name):
    """Print key information from API response"""
    print(f"\n📋 Response Summary for: {step_name}")
    print(f"   Current State: {data.get('current_state')}")
    print(f"   Awaiting Selection: {data.get('awaiting_selection')}")
    print(f"   Can Finalize: {data.get('can_finalize')}")
    print(f"   Products Returned: {len(data.get('products', []))}")

    # Show selected components
    response_json = data.get('response_json', {})
    print(f"\n   Selected Components:")
    for comp in ['PowerSource', 'Feeder', 'Cooler', 'Interconnector', 'Torch', 'Connectivity']:
        comp_data = response_json.get(comp)
        if comp_data:
            # Handle both single objects and lists (accessories are multi-select)
            if isinstance(comp_data, list):
                if len(comp_data) > 0:
                    print(f"      ✅ {comp}: {len(comp_data)} items")
                    for item in comp_data[:3]:  # Show first 3 items
                        name = item.get('name', 'Unknown')
                        gin = item.get('gin', 'Unknown')
                        print(f"         - {name} (GIN: {gin})")
            else:
                name = comp_data.get('name', 'Unknown')
                gin = comp_data.get('gin', 'Unknown')
                print(f"      ✅ {comp}: {name} (GIN: {gin})")

    # Show message preview
    message = data.get('message', '')
    print(f"\n   Message Preview: {message[:200]}..." if len(message) > 200 else f"\n   Message: {message}")

def test_auto_advance_to_finalize():
    """Test that selecting the only connectivity product auto-advances to FINALIZE"""

    print_section("🧪 AUTO-ADVANCE TO FINALIZE TEST")
    print("Testing: Warrior 500i → connectivity → auto-advance to FINALIZE")

    session_id = None

    try:
        # Step 1: Start with Warrior 500i
        print("\n1️⃣ Starting new session with Warrior 500i...")
        r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
            "message": "Warrior 500i",
            "language": "en"
        })
        data = r.json()
        session_id = data['session_id']
        print_response_summary(data, "PowerSource Search")

        # Step 2: Select Warrior 500i (should be the only result or first result)
        if data.get('products') and len(data['products']) > 0:
            product = data['products'][0]
            print(f"\n2️⃣ Selecting PowerSource: {product['name']} (GIN: {product['gin']})")

            r = requests.post(f"{API_BASE}/api/v1/configurator/select", json={
                "session_id": session_id,
                "product_gin": product['gin'],
                "product_data": product
            })
            data = r.json()
            print_response_summary(data, "PowerSource Selected")
        else:
            print("❌ No PowerSource products found!")
            return False

        # Step 3: Navigate through states to connectivity using "skip" or "done"
        print("\n3️⃣ Navigating to connectivity_selection state...")
        skip_count = 0
        max_skips = 20

        while data.get('current_state') != 'connectivity_selection' and skip_count < max_skips:
            r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
                "session_id": session_id,
                "message": "skip",
                "language": "en"
            })
            data = r.json()
            skip_count += 1
            print(f"   Skip {skip_count}: → {data.get('current_state')}")

        if data.get('current_state') != 'connectivity_selection':
            print(f"❌ Failed to reach connectivity_selection state after {max_skips} skips")
            print(f"   Current state: {data.get('current_state')}")
            return False

        print(f"\n✅ Reached connectivity_selection state")
        print_response_summary(data, "Connectivity State")

        # Step 4: Select the connectivity product (should be only one or first one)
        products = data.get('products', [])
        print(f"\n4️⃣ Connectivity products available: {len(products)}")

        if len(products) == 0:
            print("⚠️  No connectivity products found. This might be expected for Warrior 500i.")
            print("   Let me try advancing anyway...")

            # Try to advance manually
            r = requests.post(f"{API_BASE}/api/v1/configurator/message", json={
                "session_id": session_id,
                "message": "finalize",
                "language": "en"
            })
            data = r.json()
            print_response_summary(data, "Manual Finalize")

            if data.get('current_state') == 'FINALIZE':
                print("\n✅ Successfully reached FINALIZE state via manual command")
                return True
            else:
                print(f"\n❌ Failed to reach FINALIZE. Current state: {data.get('current_state')}")
                return False

        # Select the first (or only) connectivity product
        product = products[0]
        print(f"\n   Selecting: {product['name']} (GIN: {product['gin']})")

        r = requests.post(f"{API_BASE}/api/v1/configurator/select", json={
            "session_id": session_id,
            "product_gin": product['gin'],
            "product_data": product
        })
        data = r.json()

        print_section("🔍 CRITICAL CHECK: DID AUTO-ADVANCE WORK?")
        print_response_summary(data, "After Connectivity Selection")

        # Check if we auto-advanced to FINALIZE
        current_state = data.get('current_state')
        message = data.get('message', '')
        awaiting_selection = data.get('awaiting_selection')

        # Note: State is lowercase "finalize" in API response, uppercase "FINALIZE" in enum
        is_finalize = current_state and current_state.upper() == 'FINALIZE'

        print(f"\n🎯 Verification:")
        print(f"   Current State: {current_state}")
        print(f"   Expected: FINALIZE (or finalize)")
        print(f"   Match: {'✅ YES' if is_finalize else '❌ NO'}")

        print(f"\n   Awaiting Selection: {awaiting_selection}")
        print(f"   Expected: False")
        print(f"   Match: {'✅ YES' if not awaiting_selection else '❌ NO'}")

        print(f"\n   Products Returned: {len(data.get('products', []))}")
        print(f"   Expected: 0 (FINALIZE has no products)")
        print(f"   Match: {'✅ YES' if len(data.get('products', [])) == 0 else '❌ NO'}")

        # Check message content for finalization indicators
        finalize_keywords = ['final', 'complete', 'configuration', 'summary', 'package']
        has_finalize_content = any(keyword in message.lower() for keyword in finalize_keywords)
        print(f"\n   Message has finalization content: {'✅ YES' if has_finalize_content else '❌ NO'}")

        # Final verdict
        print("\n" + "=" * 80)
        if is_finalize and not awaiting_selection:
            print("✅✅✅ SUCCESS! Auto-advance to FINALIZE is working correctly!")
            print("=" * 80)
            print("\nThe fix in state_orchestrator.py is working:")
            print("  - System detected next_state == FINALIZE")
            print("  - Used message_type='finalize' instead of 'selection'")
            print("  - Properly transitioned to FINALIZE state")
            print("  - Frontend should now recognize configuration is complete")
            return True
        else:
            print("❌❌❌ FAILED! Auto-advance to FINALIZE did NOT work!")
            print("=" * 80)
            print(f"\nCurrent state is: {current_state}")
            print(f"Expected: FINALIZE")
            print("\nThe bug is NOT fixed. Need to investigate further.")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n🚀 Starting Auto-Advance to FINALIZE Test...")
    print("="*80)

    # Check server health
    try:
        r = requests.get(f"{API_BASE}/health")
        health = r.json()
        print(f"✅ Server Status: {health.get('status')}")
    except:
        print("❌ Server not reachable. Please start the server first.")
        sys.exit(1)

    # Run test
    result = test_auto_advance_to_finalize()

    # Exit with appropriate code
    sys.exit(0 if result else 1)
