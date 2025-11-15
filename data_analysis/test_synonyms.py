#!/usr/bin/env python3
"""
Synonym Testing Script

Tests that synonym matching works correctly after custom analyzer is configured.
Validates that different unit variations return consistent results.

Prerequisites:
- welding-synonyms.txt uploaded to Neo4j
- Custom analyzer created
- productIndex recreated with custom analyzer
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent / 'src' / 'backend'
sys.path.insert(0, str(parent_dir))

from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

# Load environment variables
env_path = parent_dir / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")


# Test cases: groups of variations that should return similar results
TEST_CASES = [
    {
        "name": "Amperage Variations",
        "variations": ["500A", "500 A", "500 Amps", "500 Ampere", "500 Ampères"],
        "expected_behavior": "All variations should return similar products"
    },
    {
        "name": "Voltage Variations",
        "variations": ["380V", "380 V", "380 Volts"],
        "expected_behavior": "All variations should return similar products"
    },
    {
        "name": "Length (mm) Variations",
        "variations": ["30mm", "30 mm", "30 millimeters"],
        "expected_behavior": "All variations should return similar products"
    },
    {
        "name": "Length (m) Variations",
        "variations": ["5m", "5 m", "5 meters", "5 metres"],
        "expected_behavior": "All variations should return similar products"
    },
    {
        "name": "Weight Variations",
        "variations": ["15kg", "15 kg", "15 kilograms"],
        "expected_behavior": "All variations should return similar products"
    },
    {
        "name": "Pressure Variations",
        "variations": ["200bar", "200 bar", "200 bars"],
        "expected_behavior": "All variations should return similar products"
    },
    {
        "name": "Duty Cycle Variations",
        "variations": ["60%", "60 percent"],
        "expected_behavior": "All variations should return similar products"
    },
]


async def test_synonym_matching(driver):
    """Test that synonym variations return consistent results"""

    print("\n" + "=" * 80)
    print("SYNONYM MATCHING TEST SUITE")
    print("=" * 80)
    print(f"URI: {NEO4J_URI}")
    print()

    total_tests = len(TEST_CASES)
    passed_tests = 0
    failed_tests = 0

    for test_idx, test_case in enumerate(TEST_CASES, 1):
        print(f"\n{test_idx}. {test_case['name']}")
        print("-" * 60)
        print(f"Expected: {test_case['expected_behavior']}")
        print()

        variations = test_case['variations']
        results_per_variation = []

        # Test each variation
        for query in variations:
            async with driver.session() as session:
                result = await session.run("""
                    CALL db.index.fulltext.queryNodes("productIndex", $query)
                    YIELD node, score
                    RETURN count(node) as count,
                           collect(node.gin)[0..5] as sample_gins,
                           max(score) as max_score
                """, {"query": query})

                record = await result.single()

                results_per_variation.append({
                    'query': query,
                    'count': record['count'],
                    'sample_gins': record['sample_gins'],
                    'max_score': record['max_score']
                })

        # Display results
        for res in results_per_variation:
            score_str = f"{res['max_score']:.2f}" if res['max_score'] else "N/A"
            print(f"   '{res['query']:20s}' → {res['count']:3d} products (max score: {score_str})")

        # Verify consistency
        counts = [r['count'] for r in results_per_variation]
        unique_counts = set(counts)

        if len(unique_counts) == 1:
            print(f"   ✅ PASS: All variations returned {counts[0]} products")
            passed_tests += 1
        else:
            print(f"   ❌ FAIL: Inconsistent results - counts: {counts}")
            print(f"      This indicates synonyms are NOT working correctly")
            failed_tests += 1

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests} ✅")
    print(f"Failed: {failed_tests} ❌")
    print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
    print()

    if failed_tests == 0:
        print("🎉 SUCCESS! All synonym variations are working correctly!")
        print()
        print("Next Steps:")
        print("1. Synonyms are properly configured in Neo4j")
        print("2. Application code can now use raw user input without normalization")
        print("3. Monitor search quality in production")
        print()
    else:
        print("⚠️  ISSUES DETECTED - Synonyms are not working as expected")
        print()
        print("Troubleshooting:")
        print("1. Verify custom analyzer is created: CALL db.index.fulltext.listAvailableAnalyzers()")
        print("2. Verify productIndex uses custom analyzer: SHOW INDEXES")
        print("3. Check welding-synonyms.txt was uploaded correctly")
        print("4. Rebuild index if needed: DROP + CREATE INDEX")
        print()

    return failed_tests == 0


async def test_index_configuration(driver):
    """Verify that productIndex uses custom analyzer"""

    print("\n" + "=" * 80)
    print("INDEX CONFIGURATION CHECK")
    print("=" * 80)

    try:
        async with driver.session() as session:
            # Check index configuration
            result = await session.run("""
                SHOW INDEXES
                YIELD name, type, options
                WHERE name = 'productIndex'
                RETURN name, type, options
            """)

            record = await result.single()

            if record:
                print(f"✅ productIndex found")
                print(f"   Type: {record['type']}")
                print(f"   Options: {record['options']}")

                # Check if custom analyzer is used
                options = record['options']
                if 'indexConfig' in options:
                    analyzer = options['indexConfig'].get('fulltext.analyzer')
                    if analyzer and analyzer != 'standard':
                        print(f"   ✅ Using custom analyzer: {analyzer}")
                        return True
                    else:
                        print(f"   ⚠️  Using default analyzer: standard")
                        print(f"      Custom analyzer may not be configured!")
                        return False
                else:
                    print(f"   ⚠️  No indexConfig found - using defaults")
                    return False
            else:
                print(f"   ❌ productIndex not found!")
                return False

    except Exception as e:
        print(f"   ⚠️  Could not check index configuration: {e}")
        return False


async def main():
    """Main execution function"""

    if not all([NEO4J_URI, NEO4J_PASSWORD]):
        print("❌ ERROR: Neo4j credentials not found in environment")
        sys.exit(1)

    # Connect to Neo4j
    driver = AsyncGraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )

    try:
        # Verify connection
        async with driver.session() as session:
            await session.run("RETURN 1")

        # Check index configuration
        index_ok = await test_index_configuration(driver)

        if not index_ok:
            print("\n⚠️  Index configuration issues detected")
            print("   Please verify custom analyzer is properly configured")
            print()

        # Run synonym matching tests
        all_tests_passed = await test_synonym_matching(driver)

        # Exit code
        sys.exit(0 if all_tests_passed else 1)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
