#!/usr/bin/env python3
"""
Debug Feeder Accessories Lucene search to understand why scores aren't showing.
"""

import asyncio
import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://0a8008b4.databases.neo4j.io")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

async def debug_feeder_accessories_lucene():
    """Debug Feeder Accessories Lucene search"""

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    feeder_gin = "0445800887"  # RobustFeed U6 OW

    try:
        print("=" * 80)
        print("DEBUGGING FEEDER ACCESSORIES LUCENE SEARCH")
        print("=" * 80)
        print()

        # Test 1: Direct Lucene search (no compatibility filter)
        print("Test 1: Direct Lucene search (no compatibility)")
        print("-" * 80)

        async with driver.session() as session:
            result = await session.run("""
                CALL db.index.fulltext.queryNodes("productIndex", "strain relief")
                YIELD node, score
                WHERE node.category = "Feeder Accessories"
                RETURN node.gin as gin, node.item_name as name, score
                ORDER BY score DESC
                LIMIT 5
            """)
            records = [rec async for rec in result]

            if records:
                print(f"✅ Found {len(records)} Feeder Accessories via direct Lucene:")
                for i, rec in enumerate(records, 1):
                    print(f"   {i}. {rec['name']} (GIN: {rec['gin']}, Score: {rec['score']:.2f})")
            else:
                print("❌ No Feeder Accessories found via direct Lucene")
        print()

        # Test 2: Lucene search WITH compatibility filter
        print("Test 2: Lucene search WITH compatibility filter")
        print(f"Feeder GIN: {feeder_gin}")
        print("-" * 80)

        async with driver.session() as session:
            result = await session.run("""
                CALL db.index.fulltext.queryNodes("productIndex", "strain relief")
                YIELD node, score
                WHERE node.category = "Feeder Accessories"
                  AND EXISTS {
                    MATCH (f:Product {gin: $feeder_gin, category: 'Feeder'})
                    MATCH (f)-[:COMPATIBLE_WITH]-(node)
                  }
                RETURN node.gin as gin, node.item_name as name, score
                ORDER BY score DESC
                LIMIT 5
            """, {"feeder_gin": feeder_gin})
            records = [rec async for rec in result]

            if records:
                print(f"✅ Found {len(records)} compatible Feeder Accessories via Lucene:")
                for i, rec in enumerate(records, 1):
                    print(f"   {i}. {rec['name']} (GIN: {rec['gin']}, Score: {rec['score']:.2f})")
            else:
                print("❌ No compatible Feeder Accessories found via Lucene")
                print("   This explains why fallback to traditional search is happening!")
        print()

        # Test 3: Traditional search (what happens when Lucene returns 0)
        print("Test 3: Traditional search (fallback)")
        print("-" * 80)

        async with driver.session() as session:
            result = await session.run("""
                MATCH (f:Product {gin: $feeder_gin, category: 'Feeder'})
                MATCH (f)-[:COMPATIBLE_WITH]-(fa:Product {category: 'Feeder Accessories'})
                RETURN fa.gin as gin, fa.item_name as name
                ORDER BY fa.item_name ASC
                LIMIT 5
            """, {"feeder_gin": feeder_gin})
            records = [rec async for rec in result]

            if records:
                print(f"✅ Found {len(records)} compatible Feeder Accessories via traditional:")
                for i, rec in enumerate(records, 1):
                    print(f"   {i}. {rec['name']} (GIN: {rec['gin']})")
            else:
                print("❌ No compatible Feeder Accessories found via traditional")
        print()

        # Test 4: Check if any feeder accessories are compatible with this feeder
        print("Test 4: ALL compatible Feeder Accessories (no search term)")
        print("-" * 80)

        async with driver.session() as session:
            result = await session.run("""
                MATCH (f:Product {gin: $feeder_gin, category: 'Feeder'})
                MATCH (f)-[:COMPATIBLE_WITH]-(fa:Product {category: 'Feeder Accessories'})
                RETURN count(*) as total_count
            """, {"feeder_gin": feeder_gin})
            record = await result.single()
            total = record["total_count"]

            print(f"Total Feeder Accessories compatible with {feeder_gin}: {total}")

            if total == 0:
                print("❌ NO Feeder Accessories are compatible with this feeder!")
                print("   This is why Lucene + compatibility returns 0 results.")
        print()

        print("=" * 80)
        print("DEBUG COMPLETE")
        print("=" * 80)
        print()
        print("📊 Analysis:")
        print("   - If Test 1 finds results but Test 2 doesn't:")
        print("     → Compatibility filter is blocking Lucene results")
        print("   - If Test 2 returns 0 and Test 3 returns results:")
        print("     → Code is correctly falling back to traditional search")
        print("   - If Test 4 shows 0:")
        print("     → Wrong Feeder GIN or missing relationships in database")

    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(debug_feeder_accessories_lucene())
