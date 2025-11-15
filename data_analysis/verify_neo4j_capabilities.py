#!/usr/bin/env python3
"""
Neo4j Capabilities Verification Script

Checks if Neo4j instance supports custom Lucene analyzers and synonym files.
This is CRITICAL to determine if synonym approach will work.

Output: Compatibility report
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


async def check_neo4j_version(driver):
    """Check Neo4j version"""

    print("1️⃣  Checking Neo4j Version")
    print("-" * 60)

    try:
        async with driver.session() as session:
            result = await session.run("""
                CALL dbms.components()
                YIELD name, versions, edition
                RETURN name, versions[0] as version, edition
            """)

            async for record in result:
                name = record['name']
                version = record['version']
                edition = record['edition']

                print(f"   Name: {name}")
                print(f"   Version: {version}")
                print(f"   Edition: {edition}")

                # Check version requirements
                major_version = int(version.split('.')[0])

                if major_version >= 5:
                    print(f"   ✅ Version {version} supports custom analyzers (requires 5.0+)")
                    return True, version, edition
                else:
                    print(f"   ❌ Version {version} does NOT support custom analyzers (requires 5.0+)")
                    return False, version, edition

    except Exception as e:
        print(f"   ⚠️  Could not determine version: {e}")
        return None, None, None


async def check_fulltext_analyzers(driver):
    """Check available fulltext analyzers"""

    print("\n2️⃣  Checking Available Lucene Analyzers")
    print("-" * 60)

    try:
        async with driver.session() as session:
            # Try to list available analyzers
            result = await session.run("""
                CALL db.index.fulltext.listAvailableAnalyzers()
                YIELD analyzer
                RETURN analyzer
                LIMIT 20
            """)

            analyzers = []
            async for record in result:
                analyzers.append(record['analyzer'])

            if analyzers:
                print(f"   ✅ Found {len(analyzers)} available analyzers:")
                for analyzer in analyzers:
                    print(f"      - {analyzer}")
                return True, analyzers
            else:
                print("   ❌ No analyzers found")
                return False, []

    except Exception as e:
        print(f"   ❌ Cannot list analyzers: {e}")
        print(f"      This feature may not be available in your Neo4j edition")
        return False, []


async def check_custom_analyzer_support(driver):
    """Check if custom analyzer creation is supported"""

    print("\n3️⃣  Checking Custom Analyzer Creation Support")
    print("-" * 60)

    try:
        async with driver.session() as session:
            # Try to create a test custom analyzer
            test_analyzer_name = "testAnalyzer_delete_me"

            print(f"   Testing custom analyzer creation...")

            try:
                # Drop if exists
                await session.run(f"""
                    CALL db.index.fulltext.dropAnalyzer('{test_analyzer_name}')
                """)
            except:
                pass  # Ignore if doesn't exist

            # Try to create
            result = await session.run(f"""
                CALL db.index.fulltext.createAnalyzer('{test_analyzer_name}', {{
                    tokenizer: 'standard',
                    filters: ['lowercase']
                }})
            """)
            await result.consume()

            print(f"   ✅ Custom analyzer creation SUPPORTED")
            print(f"      Test analyzer '{test_analyzer_name}' created successfully")

            # Clean up
            await session.run(f"""
                CALL db.index.fulltext.dropAnalyzer('{test_analyzer_name}')
            """)
            print(f"   🧹 Test analyzer cleaned up")

            return True

    except Exception as e:
        print(f"   ❌ Custom analyzer creation NOT supported: {e}")
        print(f"      This is likely due to Neo4j Aura limitations")
        return False


async def check_existing_indexes(driver):
    """Check existing fulltext indexes"""

    print("\n4️⃣  Checking Existing Fulltext Indexes")
    print("-" * 60)

    try:
        async with driver.session() as session:
            result = await session.run("""
                SHOW INDEXES
                YIELD name, type, labelsOrTypes, properties
                WHERE type = 'FULLTEXT'
                RETURN name, labelsOrTypes, properties
            """)

            indexes = []
            async for record in result:
                indexes.append(record)

            if indexes:
                print(f"   ✅ Found {len(indexes)} fulltext index(es):")
                for idx in indexes:
                    print(f"      - {idx['name']}")
                    print(f"        Labels: {idx['labelsOrTypes']}")
                    print(f"        Properties: {idx['properties']}")
                return True, indexes
            else:
                print("   ℹ️  No fulltext indexes found")
                return False, []

    except Exception as e:
        print(f"   ⚠️  Could not check indexes: {e}")
        return False, []


async def generate_compatibility_report(driver):
    """Generate comprehensive compatibility report"""

    print("\n" + "=" * 80)
    print("NEO4J CUSTOM ANALYZER COMPATIBILITY REPORT")
    print("=" * 80)
    print(f"URI: {NEO4J_URI}")
    print(f"User: {NEO4J_USERNAME}")
    print()

    # Run all checks
    version_ok, version, edition = await check_neo4j_version(driver)
    analyzers_ok, analyzers = await check_fulltext_analyzers(driver)
    custom_analyzer_ok = await check_custom_analyzer_support(driver)
    indexes_ok, indexes = await check_existing_indexes(driver)

    # Final verdict
    print("\n" + "=" * 80)
    print("COMPATIBILITY VERDICT")
    print("=" * 80)

    all_checks_passed = version_ok and custom_analyzer_ok

    if all_checks_passed:
        print("✅ COMPATIBLE - Custom analyzers and synonyms are supported!")
        print()
        print("Next Steps:")
        print("1. Create welding-synonyms.txt using generate_synonyms.py")
        print("2. Upload synonym file to Neo4j")
        print("3. Create custom analyzer with synonym filter")
        print("4. Recreate productIndex with custom analyzer")
        print()

    elif version_ok and not custom_analyzer_ok:
        print("⚠️  PARTIAL COMPATIBILITY - Version supports it, but feature disabled")
        print()
        print("Possible Reasons:")
        print("- Neo4j Aura (cloud) may restrict custom analyzer creation")
        print("- Enterprise features may be disabled")
        print()
        print("Alternative Solutions:")
        print("1. Migrate to self-hosted Neo4j (if using Aura)")
        print("2. Use application-level input normalization (fallback)")
        print("3. Contact Neo4j support for Aura custom analyzer access")
        print()

    else:
        print("❌ NOT COMPATIBLE - Custom analyzers not supported")
        print()
        print(f"Your Neo4j Version: {version}")
        print(f"Required Version: 5.0+")
        print()
        print("Solutions:")
        print("1. Upgrade Neo4j to version 5.0 or higher")
        print("2. Use application-level input normalization (recommended fallback)")
        print()

    print("=" * 80)


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

        # Run compatibility checks
        await generate_compatibility_report(driver)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
