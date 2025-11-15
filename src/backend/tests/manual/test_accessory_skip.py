"""
Test script to verify accessory skip tracking
Tests that accessories can be marked as "skipped" and appear in finalize response
"""

import json
from app.services.response.message_generator import MessageGenerator

def test_accessory_skip_tracking():
    """Test that skipped accessories are included in finalize response"""
    print("\n" + "=" * 80)
    print("TEST: Accessory Skip Tracking")
    print("=" * 80)

    # Mock response_json with:
    # - Selected PowerSource
    # - Skipped PowerSourceAccessories (the issue user reported)
    # - Selected FeederAccessories (mixed scenario)
    # - Skipped Connectivity
    response_json = {
        "PowerSource": {
            "gin": "0446200880",
            "name": "Aristo 500ix",
            "description": "500A MIG welding power source"
        },
        "Feeder": {
            "gin": "0460520880",
            "name": "RobustFeed U6",
            "description": "Wire feeder"
        },
        "PowerSourceAccessories": "skipped",  # ← User's reported issue
        "FeederAccessories": [  # ← Mixed scenario: some selected
            {
                "gin": "FACC001",
                "name": "Drive Rolls",
                "description": "0.9mm drive rolls"
            }
        ],
        "Connectivity": "skipped",  # ← Another skipped category
        "Accessories": "skipped"  # ← Legacy accessories skipped
    }

    # Mock state_config
    state_config = {
        "finalize_header": "Final Configuration:",
        "finalize_footer": "\n\nYour configuration is ready!"
    }

    # Create MessageGenerator instance
    generator = MessageGenerator()

    # Generate finalize prompt
    print("\n[TEST] Generating finalize prompt with skipped accessories...")
    prompt = generator._build_finalize_prompt(response_json, state_config)

    # Write to file to avoid encoding issues
    output_file = "test_accessory_skip_output.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(prompt)

    print(f"[RESULT] Prompt written to: {output_file}")

    # Extract JSON from prompt
    json_start = prompt.find("{")
    json_end = prompt.rfind("}") + 1
    json_str = prompt[json_start:json_end]

    # Parse JSON
    config_json = json.loads(json_str)

    # Verify skipped accessories are included
    print("\n[VERIFICATION]")

    checks = [
        # Core components
        ("PowerSource" in config_json, "[PASS] PowerSource included"),
        (config_json.get("PowerSource", {}).get("gin") == "0446200880", "[PASS] PowerSource has GIN"),
        ("Feeder" in config_json, "[PASS] Feeder included"),

        # PowerSourceAccessories - THE KEY TEST (user's reported issue)
        ("PowerSourceAccessories" in config_json, "[PASS] PowerSourceAccessories included (was skipped)"),
        (config_json.get("PowerSourceAccessories", {}).get("status") == "skipped", "[PASS] PowerSourceAccessories has status='skipped'"),
        (config_json.get("PowerSourceAccessories", {}).get("category") == "PowerSourceAccessories", "[PASS] PowerSourceAccessories has category field"),

        # FeederAccessories - Mixed scenario (selected items)
        ("FeederAccessories" in config_json, "[PASS] FeederAccessories included (has items)"),
        (isinstance(config_json.get("FeederAccessories"), list), "[PASS] FeederAccessories is a list"),
        (len(config_json.get("FeederAccessories", [])) == 1, "[PASS] FeederAccessories has 1 item"),

        # Connectivity - Another skipped category
        ("Connectivity" in config_json, "[PASS] Connectivity included (was skipped)"),
        (config_json.get("Connectivity", {}).get("status") == "skipped", "[PASS] Connectivity has status='skipped'"),

        # Legacy Accessories - Skipped
        ("Accessories" in config_json, "[PASS] Accessories included (was skipped)"),
        (config_json.get("Accessories", {}).get("status") == "skipped", "[PASS] Accessories has status='skipped'"),
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
        print("\nAccessory skip tracking working correctly:")
        print("   - Skipped accessories show: {\"category\": \"X\", \"status\": \"skipped\"}")
        print("   - Selected accessories show: [{...product details...}]")
        print("   - Empty accessories are omitted")
        print("\nUser's issue RESOLVED:")
        print("   PowerSourceAccessories selected as skipped IS NOW reflected in final response!")
        return True
    else:
        print("[FAILURE] Some checks failed")
        print("=" * 80)
        return False


if __name__ == "__main__":
    try:
        success = test_accessory_skip_tracking()
        if not success:
            exit(1)
    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
