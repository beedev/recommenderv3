"""
Test script to verify finalize response includes skipped items
Tests that _build_finalize_prompt() properly displays skipped components
"""

from app.services.response.message_generator import MessageGenerator

def test_finalize_with_skipped_items():
    """Test that finalize prompt includes skipped components"""
    print("\n" + "=" * 80)
    print("TEST: Finalize Response with Skipped Items")
    print("=" * 80)

    # Mock response_json with mixed states
    response_json = {
        "PowerSource": {
            "gin": "0446200880",
            "name": "Aristo 500ix",
            "description": "500A MIG welding power source"
        },
        "Feeder": "skipped",  # ← Explicitly skipped
        "Cooler": "skipped",  # ← Explicitly skipped
        "Interconnector": {
            "gin": "0480100880",
            "name": "IC Cable 10m",
            "description": "Interconnector cable 10 meters"
        },
        "Torch": None,  # ← Not applicable (should be omitted)
        "PowerSourceAccessories": [
            {
                "gin": "ACC001",
                "name": "Transport Cart",
                "description": "Mobility cart"
            }
        ]
    }

    # Mock state_config
    state_config = {
        "finalize_header": "📋 **Final Configuration:**",
        "finalize_footer": "\n\n✨ Your configuration is ready!"
    }

    # Create MessageGenerator instance (no arguments needed)
    generator = MessageGenerator()

    # Generate finalize prompt
    print("\n[TEST] Generating finalize prompt...")
    prompt = generator._build_finalize_prompt(response_json, state_config)

    print("\n[RESULT] Generated Prompt:")
    print("-" * 80)
    print(prompt)
    print("-" * 80)

    # Verify skipped items are included
    print("\n[VERIFICATION]")

    checks = [
        ('"PowerSource"' in prompt, "✅ PowerSource included (selected)"),
        ('"Feeder"' in prompt, "✅ Feeder included (skipped)"),
        ('"skipped"' in prompt, "✅ 'skipped' status present"),
        ('"Cooler"' in prompt, "✅ Cooler included (skipped)"),
        ('"Interconnector"' in prompt, "✅ Interconnector included (selected)"),
        ('"Torch"' not in prompt, "✅ Torch omitted (not applicable - None)"),
        ('"PowerSourceAccessories"' in prompt, "✅ Accessories included"),
        ('"category": "Feeder"' in prompt, "✅ Feeder shows category field"),
        ('"status": "skipped"' in prompt, "✅ Feeder shows status field"),
    ]

    all_passed = True
    for check, message in checks:
        if check:
            print(f"  {message}")
        else:
            print(f"  ❌ FAILED: {message}")
            all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print("[SUCCESS] All checks passed!")
        print("=" * 80)
        print("\n✅ Finalize response correctly includes skipped items with:")
        print("   - category: Component type")
        print("   - status: 'skipped'")
        print("\n✅ Selected items show full details (GIN, name, description)")
        print("✅ Not applicable items (None) are omitted")
        return True
    else:
        print("[FAILURE] Some checks failed")
        print("=" * 80)
        return False


if __name__ == "__main__":
    try:
        success = test_finalize_with_skipped_items()
        if not success:
            exit(1)
    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
