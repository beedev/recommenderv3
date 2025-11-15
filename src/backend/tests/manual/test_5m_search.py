"""
Test script to diagnose "5m" search issue
"""
import json
import pathlib

def test_5m_normalization():
    """Test how 5m is normalized"""
    print("Testing 5m normalization...\n")

    # Simulate keyword from LLM
    keyword = {
        "canonical": "5m",
        "text": "5m",
        "type": "CABLE_LENGTH",
        "confidence": 0.90,
        "boost": 6
    }

    print(f"Input keyword: {keyword}")

    # Load normalizations from JSON file
    config_path = pathlib.Path(__file__).parent.parent.parent / "app" / "config" / "parameter_normalizations.json"

    try:
        with open(config_path, 'r') as f:
            PARAMETER_NORMALIZATIONS = json.load(f)
    except Exception as e:
        print(f"\n❌ ERROR: Could not load parameter_normalizations.json: {e}")
        return

    normalizations = PARAMETER_NORMALIZATIONS.get('normalizations', {})
    print(f"\n✅ Normalizations loaded: {len(normalizations)} parameters")

    # Check cable_length specifically
    cable_length = normalizations.get('cable_length')
    if not cable_length:
        print("❌ ERROR: cable_length not found in normalizations!")
        return

    print(f"\n✅ Cable length config found")
    print(f"   Parameter type: {cable_length['parameter_type']}")
    print(f"   Confidence: {cable_length['confidence']}")

    # Check 5m mapping
    mappings = cable_length.get('mappings', {})
    five_m_variations = mappings.get('5m')

    if not five_m_variations:
        print("❌ ERROR: 5m not found in mappings!")
        return

    print(f"\n✅ 5m variations found: {five_m_variations}")
    print(f"   Type: {type(five_m_variations)}")
    print(f"   Length: {len(five_m_variations)}")

    # Check if variations is a list
    if not isinstance(five_m_variations, list):
        print(f"❌ ERROR: variations is not a list! Type: {type(five_m_variations)}")
        return

    # Check if list has valid length
    if len(five_m_variations) == 0:
        print("❌ ERROR: variations list is empty!")
        return

    if len(five_m_variations) > 1000:
        print(f"❌ ERROR: variations list is too long! Length: {len(five_m_variations)}")
        return

    print("\n✅ All checks passed!")
    print("\nSimulating keyword normalization...")

    # Simulate the normalization
    user_value = keyword['canonical'].lower().strip()
    print(f"   User value (lowercased): '{user_value}'")

    # Check if user value matches any variation
    variations_lower = [v.lower() for v in five_m_variations]
    print(f"   Variations (lowercased): {variations_lower}")

    if user_value in variations_lower:
        print(f"\n✅ MATCH FOUND!")
        print(f"   '{user_value}' matches a variation")
        print(f"   Would normalize to: '5m'")
        print(f"   Would store variations: {five_m_variations}")
    else:
        print(f"\n❌ NO MATCH: '{user_value}' not in variations")

if __name__ == "__main__":
    test_5m_normalization()
