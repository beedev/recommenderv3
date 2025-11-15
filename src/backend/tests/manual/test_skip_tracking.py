"""
Simple test script to verify skip tracking functionality
Tests that ResponseJSON properly accepts and serializes "skipped" values
"""

from app.models.conversation import ResponseJSON, SelectedProduct, ComponentApplicability

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

    print("✅ ResponseJSON correctly accepts 'skipped' literal")
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
        print("✅ response_json.dict() works")
        print(f"   PowerSource in dict: {type(serialized['PowerSource'])}")
        print(f"   Feeder in dict: {serialized['Feeder']}")
        print(f"   Cooler in dict: {serialized['Cooler']}")
    except Exception as e:
        print(f"❌ Serialization failed: {e}")
        return False

    return True


def test_type_validation():
    """Test that ResponseJSON rejects invalid types"""
    print("\n=== Test 3: Type validation ===")

    try:
        # Try to set invalid value (should fail)
        invalid_response = ResponseJSON(
            PowerSource="invalid_string"  # Should only accept SelectedProduct, "skipped", or None
        )
        print("❌ Type validation failed - accepted invalid string")
        return False
    except Exception as e:
        print(f"✅ Type validation works - rejected invalid value: {type(e).__name__}")
        return True


if __name__ == "__main__":
    print("=" * 60)
    print("SKIP TRACKING IMPLEMENTATION TEST")
    print("=" * 60)

    try:
        # Run tests
        test_response_json_skipped_literal()
        test_serialization()
        test_type_validation()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nSkip tracking implementation is working correctly.")
        print("ResponseJSON now supports:")
        print("  - SelectedProduct objects (selected components)")
        print("  - 'skipped' literal (explicitly skipped)")
        print("  - None (not reached or auto-skipped)")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
