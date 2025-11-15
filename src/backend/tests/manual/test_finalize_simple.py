"""
Test script to verify finalize response includes skipped items
Tests that _build_finalize_prompt() properly displays skipped components
"""

import json
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
        "finalize_header": "Final Configuration:",
        "finalize_footer": "\n\nYour configuration is ready!"
    }

    # Create MessageGenerator instance (no arguments needed)
    generator = MessageGenerator()

    # Generate finalize prompt
    print("\n[TEST] Generating finalize prompt...")
    prompt = generator._build_finalize_prompt(response_json, state_config)

    # Write to file to avoid encoding issues
    output_file = "test_finalize_output.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(prompt)

    print(f"[RESULT] Prompt written to: {output_file}")

    # Extract JSON from prompt
    json_start = prompt.find("{")
    json_end = prompt.rfind("}") + 1
    json_str = prompt[json_start:json_end]

    # Parse JSON
    config_json = json.loads(json_str)

    # Verify skipped items are included
    print("\n[VERIFICATION]")

    checks = [
        ("PowerSource" in config_json, "[PASS] PowerSource included (selected)"),
        (config_json.get("PowerSource", {}).get("gin") == "0446200880", "[PASS] PowerSource has GIN"),
        ("Feeder" in config_json, "[PASS] Feeder included (skipped)"),
        (config_json.get("Feeder", {}).get("status") == "skipped", "[PASS] Feeder has status='skipped'"),
        (config_json.get("Feeder", {}).get("category") == "Feeder", "[PASS] Feeder has category field"),
        ("Cooler" in config_json, "[PASS] Cooler included (skipped)"),
        (config_json.get("Cooler", {}).get("status") == "skipped", "[PASS] Cooler has status='skipped'"),
        ("Interconnector" in config_json, "[PASS] Interconnector included (selected)"),
        ("Torch" not in config_json, "[PASS] Torch omitted (None - not applicable)"),
        ("PowerSourceAccessories" in config_json, "[PASS] Accessories included"),
        (len(config_json.get("PowerSourceAccessories", [])) == 1, "[PASS] Accessories has 1 item"),
    ]

    all_passed = True
    for check, message in checks:
        if check:
            print(f"  {message}")
        else:
            print(f"  [FAIL] {message}")
            all_passed = False

    # Print JSON structure
    print("\n[FINAL JSON STRUCTURE]")
    print(json.dumps(config_json, indent=2))

    print("\n" + "=" * 80)
    if all_passed:
        print("[SUCCESS] All checks passed!")
        print("=" * 80)
        print("\nFinalize response correctly includes skipped items with:")
        print("   - category: Component type")
        print("   - status: 'skipped'")
        print("\nSelected items show full details (GIN, name, description)")
        print("Not applicable items (None) are omitted")
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
