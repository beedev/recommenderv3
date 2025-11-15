#!/usr/bin/env python3
"""
Test script to validate all config files against their schemas.
Tests the 7 schema validations added to ConfigValidator.

Usage:
    cd /Users/bharath/Desktop/Ayna_ESAB_Nov7/src/backend
    python ../../scripts/test_schema_validation.py
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "src" / "backend"
sys.path.insert(0, str(backend_path))

from app.services.config.config_validator import ConfigValidator

def test_schema_validation():
    """Test all schema validations"""

    print("=" * 80)
    print("🧪 Testing Configuration Schema Validation")
    print("=" * 80)
    print()

    # Initialize validator
    validator = ConfigValidator()

    # Test each config individually
    configs_to_test = [
        # Original 3 configs
        ("component_types", "Component Types"),
        ("state_prompts", "State Prompts"),
        ("component_applicability", "Component Applicability"),

        # New 4 configs (added Nov 2024)
        ("component_config", "Component Config"),
        ("state_config", "State Config"),
        ("search_config", "Search Config"),
        ("master_parameter_schema", "Master Parameter Schema"),
    ]

    results = []

    for config_name, display_name in configs_to_test:
        print(f"Testing: {display_name} ({config_name}.json)")
        print("-" * 80)

        try:
            result = validator.validate_config_schema(config_name)
            results.append((display_name, result))

            if result.is_valid:
                print(f"✅ PASSED - {display_name}")
            else:
                print(f"❌ FAILED - {display_name}")
                print(f"   Errors: {len(result.errors)}")
                for error in result.errors:
                    print(f"   - {error}")
                print(f"   Warnings: {len(result.warnings)}")
                for warning in result.warnings:
                    print(f"   - {warning}")

        except FileNotFoundError as e:
            print(f"❌ ERROR - Schema file not found: {e}")
            results.append((display_name, None))

        except Exception as e:
            print(f"❌ ERROR - Validation failed: {e}")
            results.append((display_name, None))

        print()

    # Summary
    print("=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)

    passed = sum(1 for _, r in results if r and r.is_valid)
    failed = sum(1 for _, r in results if r and not r.is_valid)
    errors = sum(1 for _, r in results if r is None)

    print(f"Total Configs Tested: {len(results)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⚠️  Errors: {errors}")
    print()

    if failed > 0 or errors > 0:
        print("❌ Some validations failed. Please review the errors above.")
        sys.exit(1)
    else:
        print("✅ All schema validations passed!")
        sys.exit(0)

if __name__ == "__main__":
    test_schema_validation()
