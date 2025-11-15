"""
Simple test script to verify skip tracking functionality
Tests that ResponseJSON properly accepts and serializes "skipped" values
"""

from app.models.conversation import ResponseJSON, SelectedProduct

def test_response_json_skipped_literal():
    """Test that ResponseJSON accepts 'skipped' string literal"""
    print("\n=== Test 1: ResponseJSON accepts 'skipped' literal ===")

    # Create a SelectedProduct for PowerSource
    power_source = SelectedProduct(
        gin="0446200880",
        name="Aristo 500ix",
        category="PowerSource",
        description="500A MIG power source"
    )

    # Create ResponseJSON with mixed values: selected, skipped, None
    response_json = ResponseJSON(
        PowerSource=power_source,
        Feeder="skipped",          # Explicitly skipped
        Cooler="skipped",           # Explicitly skipped
        Interconnector=None,        # Not reached yet
        Torch=None                  # Not reached yet
    )

    # Verify values
    assert response_json.PowerSource == power_source, "PowerSource should be SelectedProduct"
    assert response_json.Feeder == "skipped", "Feeder should be 'skipped'"
    assert response_json.Cooler == "skipped", "Cooler should be 'skipped'"
    assert response_json.Interconnector is None, "Interconnector should be None"
    assert response_json.Torch is None, "Torch should be None"

    print("[PASS] ResponseJSON correctly accepts 'skipped' literal")
    print(f"   PowerSource: {type(response_json.PowerSource).__name__}")
    print(f"   Feeder: {response_json.Feeder}")
    print(f"   Cooler: {response_json.Cooler}")
    print(f"   Interconnector: {response_json.Interconnector}")
    print(f"   Torch: {response_json.Torch}")

    return response_json


def test_serialization():
    """Test that serialization handles 'skipped' values correctly"""
    print("\n=== Test 2: Serialization of 'skipped' values ===")

    response_json = test_response_json_skipped_literal()

    # Test dict() conversion (Pydantic model serialization)
    try:
        serialized = response_json.dict()
        print("[PASS] response_json.dict() works")
        print(f"   PowerSource type in dict: {type(serialized['PowerSource'])}")
        print(f"   Feeder value in dict: {serialized['Feeder']}")
        print(f"   Cooler value in dict: {serialized['Cooler']}")

        # Verify skipped values are preserved
        assert serialized['Feeder'] == 'skipped', "Feeder should be 'skipped' in dict"
        assert serialized['Cooler'] == 'skipped', "Cooler should be 'skipped' in dict"
        print("[PASS] Skipped values preserved in serialization")

    except Exception as e:
        print(f"[FAIL] Serialization failed: {e}")
        return False

    return True


if __name__ == "__main__":
    print("=" * 60)
    print("SKIP TRACKING IMPLEMENTATION TEST")
    print("=" * 60)

    try:
        # Run tests
        test_response_json_skipped_literal()
        test_serialization()

        print("\n" + "=" * 60)
        print("[SUCCESS] ALL TESTS PASSED!")
        print("=" * 60)
        print("\nSkip tracking implementation is working correctly.")
        print("ResponseJSON now supports:")
        print("  - SelectedProduct objects (selected components)")
        print("  - 'skipped' literal (explicitly skipped)")
        print("  - None (not reached or auto-skipped)")

    except Exception as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
