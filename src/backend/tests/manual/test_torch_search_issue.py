#!/usr/bin/env python3
"""
Reproduce the Torch search issue.
"""

import asyncio
import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://0a8008b4.databases.neo4j.io")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

async def test_torch_search():
    """Test the exact query that search_torch() runs"""

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    try:
        print("=" * 80)
        print("REPRODUCING TORCH SEARCH ISSUE")
        print("=" * 80)
        print()

        # Simulate: PowerSource selected, Feeder NOT selected, Cooler NOT selected
        power_source_gin = "0446200880"  # Aristo 500ix

        print(f"Scenario: PowerSource selected ({power_source_gin}), Feeder NOT selected, Cooler NOT selected")
        print()

        # This is the CURRENT query that search_torch() runs
        print("1. CURRENT QUERY (with NOT EXISTS filters):")
        print("-" * 80)
        current_query = """
        MATCH (ps:Product {gin: $power_source_gin, category: 'Powersource'})
        MATCH (ps)-[r1:COMPATIBLE_WITH]->(target:Product {category: 'Torches'})
        WHERE NOT EXISTS { MATCH (:Product {category: 'Feeder'})-[:COMPATIBLE_WITH]->(target) }
          AND NOT EXISTS { MATCH (:Product {category: 'Cooler'})-[:COMPATIBLE_WITH]->(target) }
        WITH target, MIN(COALESCE(r1.priority, 999999)) AS best_priority
        ORDER BY best_priority ASC, target.item_name ASC
        LIMIT 10
        RETURN target.gin AS gin,
               target.item_name AS name
        """
        print(current_query)
        print()

        async with driver.session() as session:
            result = await session.run(current_query, {"power_source_gin": power_source_gin})
            records = [rec async for rec in result]

            print(f"Results: {len(records)} torches")
            if records:
                for i, rec in enumerate(records, 1):
                    print(f"   {i}. {rec['name']} (GIN: {rec['gin']})")
            else:
                print("   ❌ NO RESULTS (This is the bug!)")
            print()

        # This is what the query SHOULD be
        print("2. CORRECT QUERY (without NOT EXISTS filters):")
        print("-" * 80)
        correct_query = """
        MATCH (ps:Product {gin: $power_source_gin, category: 'Powersource'})
        MATCH (ps)-[r1:COMPATIBLE_WITH]->(target:Product {category: 'Torches'})
        WITH target, MIN(COALESCE(r1.priority, 999999)) AS best_priority
        ORDER BY best_priority ASC, target.item_name ASC
        LIMIT 10
        RETURN target.gin AS gin,
               target.item_name AS name
        """
        print(correct_query)
        print()

        async with driver.session() as session:
            result = await session.run(correct_query, {"power_source_gin": power_source_gin})
            records = [rec async for rec in result]

            print(f"Results: {len(records)} torches")
            if records:
                for i, rec in enumerate(records, 1):
                    print(f"   {i}. {rec['name']} (GIN: {rec['gin']})")
            else:
                print("   ❌ NO RESULTS")
            print()

        print("=" * 80)
        print("DIAGNOSIS")
        print("=" * 80)
        print()
        print("❌ PROBLEM: The NOT EXISTS filters (lines 1543-1546) exclude ALL torches")
        print("   that are compatible with ANY feeder or cooler.")
        print()
        print("   Since most torches (204/24) are compatible with feeders, this excludes")
        print("   almost all torches when no feeder is selected!")
        print()
        print("✅ SOLUTION: Remove the NOT EXISTS filters (lines 1543-1549)")
        print("   The search should show all torches compatible with the PowerSource,")
        print("   regardless of whether they're also compatible with feeders/coolers.")

    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(test_torch_search())
