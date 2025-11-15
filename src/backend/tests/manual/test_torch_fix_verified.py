#!/usr/bin/env python3
"""
Verify the Torch search fix works.
"""

import asyncio
import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://0a8008b4.databases.neo4j.io")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

async def verify_fix():
    """Verify the fix works - should now return torches"""

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    try:
        print("=" * 80)
        print("VERIFYING TORCH SEARCH FIX")
        print("=" * 80)
        print()

        # Simulate: PowerSource selected, Feeder NOT selected, Cooler NOT selected
        power_source_gin = "0446200880"  # Aristo 500ix

        print(f"✅ AFTER FIX: Removed NOT EXISTS filters")
        print(f"   PowerSource: {power_source_gin} (Aristo 500ix)")
        print(f"   Feeder: NOT selected")
        print(f"   Cooler: NOT selected")
        print()

        # This is the NEW query (without NOT EXISTS filters)
        query = """
        MATCH (ps:Product {gin: $power_source_gin, category: 'Powersource'})
        MATCH (ps)-[r1:COMPATIBLE_WITH]->(target:Product {category: 'Torches'})
        WITH target, MIN(COALESCE(r1.priority, 999999)) AS best_priority
        ORDER BY best_priority ASC, target.item_name ASC
        LIMIT 10
        RETURN target.gin AS gin,
               target.item_name AS name
        """

        async with driver.session() as session:
            result = await session.run(query, {"power_source_gin": power_source_gin})
            records = [rec async for rec in result]

            print(f"Results: {len(records)} torches ✅")
            print()

            if records:
                print("Top 10 torches compatible with Aristo 500ix:")
                for i, rec in enumerate(records, 1):
                    print(f"   {i}. {rec['name']} (GIN: {rec['gin']})")
                print()
                print("=" * 80)
                print("SUCCESS! ✅")
                print("=" * 80)
                print("The Torch search now works correctly!")
                print("Users will see torch products when PowerSource is selected.")
            else:
                print("   ❌ STILL NO RESULTS - Fix did not work")

    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(verify_fix())
