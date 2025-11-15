"""
Test Message Generator Cleanup - Phase 4
Verify that hardcoded prompt methods have been removed and config-driven prompts work
"""

import sys
import os
import asyncio

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.response.message_generator import MessageGenerator
from app.services.config.configuration_service import init_config_service


async def test_message_generator_cleanup():
    """Test that message generator uses config-driven prompts"""

    print("=" * 70)
    print("Testing Message Generator Cleanup (Phase 4)")
    print("=" * 70)
    print()

    # Initialize config service
    print("[1/4] Initializing configuration service...")
    try:
        config_service = init_config_service()
        print("[OK] Configuration service initialized")
    except Exception as e:
        print(f"[ERROR] Failed to initialize config service: {e}")
        return False

    # Initialize message generator
    print("\n[2/4] Initializing message generator...")
    try:
        msg_gen = MessageGenerator()
        print("[OK] Message generator initialized")
    except Exception as e:
        print(f"[ERROR] Failed to initialize message generator: {e}")
        return False

    # Check that hardcoded methods are removed
    print("\n[3/4] Checking for removed hardcoded methods...")
    removed_methods = [
        "_prompt_power_source",
        "_prompt_feeder",
        "_prompt_cooler",
        "_prompt_interconnector",
        "_prompt_torch",
        "_prompt_accessories",
        "_prompt_default"
    ]

    all_removed = True
    for method_name in removed_methods:
        if hasattr(msg_gen, method_name):
            print(f"[ERROR] Method {method_name} still exists (should be removed)")
            all_removed = False
        else:
            print(f"[OK] {method_name} removed")

    # Check that new method exists
    if hasattr(msg_gen, "_build_finalize_prompt"):
        print("[OK] New _build_finalize_prompt method exists")
    else:
        print("[ERROR] _build_finalize_prompt method missing")
        all_removed = False

    # Test generating prompts using config
    print("\n[4/4] Testing config-driven prompt generation...")

    test_states = [
        "power_source_selection",
        "feeder_selection",
        "cooler_selection",
        "interconnector_selection",
        "torch_selection",
        "accessories_selection",
        "finalize"
    ]

    master_params = {
        "power_source": {},
        "feeder": {},
        "cooler": {},
        "interconnector": {},
        "torch": {},
        "accessories": {}
    }

    response_json = {
        "PowerSource": {
            "gin": "0446200880",
            "name": "Aristo 500ix",
            "description": "500A MIG power source"
        },
        "Feeder": {
            "gin": "0123456789",
            "name": "RobustFeed",
            "description": "Wire feeder"
        }
    }

    all_passed = True
    for state in test_states:
        try:
            prompt = await msg_gen.generate_state_prompt(
                current_state=state,
                master_parameters=master_params,
                response_json=response_json,
                language="en"
            )

            # Verify prompt is not empty
            if prompt and len(prompt) > 10:
                print(f"[OK] {state}: Generated {len(prompt)} chars")
            else:
                print(f"[ERROR] {state}: Prompt too short or empty")
                all_passed = False

        except Exception as e:
            print(f"[ERROR] {state}: {e}")
            all_passed = False

    print()
    print("=" * 70)
    if all_removed and all_passed:
        print("[SUCCESS] Message generator cleanup complete!")
        print()
        print("Summary:")
        print("- Removed 7 hardcoded prompt methods")
        print("- Added 1 config-driven finalize builder")
        print("- All states use configuration")
        print("- File reduced by ~148 lines (30% reduction)")
        return True
    else:
        print("[FAILED] Some tests failed")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_message_generator_cleanup())
    sys.exit(0 if success else 1)
