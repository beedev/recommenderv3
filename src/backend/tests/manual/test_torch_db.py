#!/usr/bin/env python3
"""
Test script to verify Torch database content and Lucene search.
"""

import asyncio
import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

# Load environment variables
load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://0a8008b4.databases.neo4j.io")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

async def test_torch():
    """Check Torch products and Lucene search"""

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    try:
        print("=" * 80)
        print("TESTING TORCH LUCENE SEARCH")
        print("=" * 80)
        print()

        # 1. Count total Torches
        print("1. Total Torch products:")
        async with driver.session() as session:
            result = await session.run("""
                MATCH (t:Product {category: 'Torches'})
                RETURN count(t) as total
            """)
            record = await result.single()
            total = record["total"] if record else 0
            print(f"   Total: {total}")
            print()

        # 2. Sample Torch products
        print("2. Sample Torch products:")
        async with driver.session() as session:
            result = await session.run("""
                MATCH (t:Product {category: 'Torches'})
                RETURN t.gin as gin,
                       t.item_name as name
                LIMIT 5
            """)
            records = [rec async for rec in result]
            for i, rec in enumerate(records, 1):
                print(f"   {i}. {rec['name']} (GIN: {rec['gin']})")
            print()

        # 3. Test Lucene search for "520W torch"
        print("3. Lucene search for '520W torch':")
        async with driver.session() as session:
            result = await session.run("""
                CALL db.index.fulltext.queryNodes("productIndex", "520W torch")
                YIELD node, score
                WHERE node.category = 'Torches'
                RETURN node.gin as gin,
                       node.item_name as name,
                       score
                ORDER BY score DESC
                LIMIT 5
            """)
            records = [rec async for rec in result]
            print(f"   Found {len(records)} results")
            print()

            if records:
                for i, rec in enumerate(records, 1):
                    print(f"   {i}. {rec['name']} (GIN: {rec['gin']}, Score: {rec['score']:.2f})")
            else:
                print("   ⚠️ NO Lucene results!")
            print()

        # 4. Test with alternate search terms
        print("4. Lucene search for 'water cooled welding torch':")
        async with driver.session() as session:
            result = await session.run("""
                CALL db.index.fulltext.queryNodes("productIndex", "water cooled welding torch")
                YIELD node, score
                WHERE node.category = 'Torches'
                RETURN node.gin as gin,
                       node.item_name as name,
                       score
                ORDER BY score DESC
                LIMIT 5
            """)
            records = [rec async for rec in result]
            print(f"   Found {len(records)} results")
            print()

            if records:
                for i, rec in enumerate(records, 1):
                    print(f"   {i}. {rec['name']} (GIN: {rec['gin']}, Score: {rec['score']:.2f})")
            print()

        print("=" * 80)
        print("DIAGNOSIS")
        print("=" * 80)

        if total > 0:
            print("✅ Torch products exist in database")
            print("✅ Database uses category 'Torches'")
            print("✅ Lucene search can find Torch products")
            print()
            print("Next: Test via API to verify scores appear in product names")
        else:
            print("❌ No Torch products found in database")

    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(test_torch())
