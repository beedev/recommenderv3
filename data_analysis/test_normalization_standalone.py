#!/usr/bin/env python3
"""
Standalone test for search query normalization

Tests the _normalize_search_query() method without pytest infrastructure.
"""

import re
import sys


def normalize_search_query(user_message: str) -> str:
    """
    Normalize measurement units in user search queries.
    Copy of the implementation from product_search.py for standalone testing.
    """
    normalized = user_message

    # Rule 1: Add space between numbers and units if missing
    normalized = re.sub(r'(\d+)([A-Za-z]+)', r'\1 \2', normalized)

    # Rule 2: Amperage - normalize to "A"
    normalized = re.sub(
        r'(\d+)\s*(Amps?|Amperes?|Ampères?)\b',
        r'\1 A',
        normalized,
        flags=re.IGNORECASE
    )

    # Rule 3: Voltage - normalize to "V"
    normalized = re.sub(
        r'(\d+)\s*(Volts?|Voltios?)\b',
        r'\1 V',
        normalized,
        flags=re.IGNORECASE
    )

    # Rule 4: Power (Watts) - normalize to "W"
    normalized = re.sub(
        r'(\d+)\s*Watts?\b',
        r'\1 W',
        normalized,
        flags=re.IGNORECASE
    )

    # Rule 5: Power (Kilowatts) - normalize to "kW"
    normalized = re.sub(
        r'(\d+)\s*kilowatts?\b',
        r'\1 kW',
        normalized,
        flags=re.IGNORECASE
    )

    # Rule 6: Length (meters) - normalize to "m"
    normalized = re.sub(
        r'(\d+)\s*(meters?|metres?)\b',
        r'\1 m',
        normalized,
        flags=re.IGNORECASE
    )

    # Rule 7: Length (millimeters) - normalize to "mm"
    normalized = re.sub(
        r'(\d+(?:\.\d+)?)\s*(millimeters?|millimetres?)\b',
        r'\1 mm',
        normalized,
        flags=re.IGNORECASE
    )

    # Rule 8: Length (inches) - normalize to "inch"
    normalized = re.sub(
        r'(\d+)\s*(?:inches?|")\b',
        r'\1 inch',
        normalized,
        flags=re.IGNORECASE
    )

    # Rule 9: Pressure (bar) - normalize to lowercase "bar"
    normalized = re.sub(
        r'(\d+)\s*bar\b',
        r'\1 bar',
        normalized,
        flags=re.IGNORECASE
    )

    # Rule 10: Flow rate - normalize to "l/minute"
    normalized = re.sub(
        r'(\d+)\s*(?:l/min|liters?/min(?:ute)?|lpm)\b',
        r'\1 l/minute',
        normalized,
        flags=re.IGNORECASE
    )

    # Rule 11: Phase - normalize to "phase"
    normalized = re.sub(
        r'(\d+)[-\s]*ph\b',
        r'\1 phase',
        normalized,
        flags=re.IGNORECASE
    )

    return normalized.strip()


def test_normalization():
    """Test normalization rules with direct method call"""

    print("=" * 80)
    print("SEARCH QUERY NORMALIZATION TESTS")
    print("=" * 80)
    print()

    tests = [
        # (input, expected_output_contains, description)
        ("500A", "500 A", "Amperage: 500A → 500 A"),
        ("500 Amps", "500 A", "Amperage: 500 Amps → 500 A"),
        ("500 Amperes", "500 A", "Amperage: 500 Amperes → 500 A"),
        ("500 Ampères", "500 A", "Amperage: 500 Ampères → 500 A"),

        ("380V", "380 V", "Voltage: 380V → 380 V"),
        ("380 Volts", "380 V", "Voltage: 380 Volts → 380 V"),
        ("460 Voltios", "460 V", "Voltage: 460 Voltios → 460 V (Spanish)"),

        ("15m", "15 m", "Length: 15m → 15 m"),
        ("15 meters", "15 m", "Length: 15 meters → 15 m"),
        ("20 metres", "20 m", "Length: 20 metres → 20 m (British)"),

        ("30mm", "30 mm", "Length: 30mm → 30 mm"),
        ("30 millimeters", "30 mm", "Length: 30 millimeters → 30 mm"),
        ("1.2 millimetres", "1.2 mm", "Length: 1.2 millimetres → 1.2 mm"),

        ("500W", "500 W", "Power: 500W → 500 W"),
        ("500 Watts", "500 W", "Power: 500 Watts → 500 W"),

        ("4kW", "4 kW", "Power: 4kW → 4 kW"),
        ("4 kilowatts", "4 kW", "Power: 4 kilowatts → 4 kW"),

        ("5bar", "5 bar", "Pressure: 5bar → 5 bar"),
        ("5 BAR", "5 bar", "Pressure: 5 BAR → 5 bar (case insensitive)"),

        ("7 l/min", "7 l/minute", "Flow: 7 l/min → 7 l/minute"),
        ("7 lpm", "7 l/minute", "Flow: 7 lpm → 7 l/minute"),

        ("3ph", "3 phase", "Phase: 3ph → 3 phase"),
        ("1-phase", "1 phase", "Phase: 1-phase → 1 phase"),

        ('32 inches', "32 inch", "Inches: 32 inches → 32 inch"),

        # Combined tests
        ("I need a 500 Amps MIG welder with 380 Volts and 30mm wire",
         "500 A",
         "Combined: Multiple units in one query"),

        ("500A at 60%",
         "500 A",
         "Duty cycle: Preserved 60% while normalizing 500A"),

        ("MIG welder for aluminum",
         "MIG welder for aluminum",
         "No change: Query without measurements"),
    ]

    passed = 0
    failed = 0

    for input_query, expected, description in tests:
        result = normalize_search_query(input_query)

        if expected in result:
            print(f"✅ PASS: {description}")
            print(f"   Input:  '{input_query}'")
            print(f"   Output: '{result}'")
            passed += 1
        else:
            print(f"❌ FAIL: {description}")
            print(f"   Input:    '{input_query}'")
            print(f"   Expected: '{expected}' in result")
            print(f"   Got:      '{result}'")
            failed += 1
        print()

    print("=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)

    return failed == 0


if __name__ == "__main__":
    try:
        success = test_normalization()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
