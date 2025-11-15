#!/usr/bin/env python3
"""
Check Torch compatibility relationships in Neo4j.
"""

import asyncio
import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://0a8008b4.databases.neo4j.io")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

async def check_torch_relationships():
    """Check what relationships Torches have"""

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    try:
        print("=" * 80)
        print("TORCH COMPATIBILITY RELATIONSHIPS")
        print("=" * 80)
        print()

        # Check what components Torches are compatible with
        print("1. What components do Torches connect to?")
        async with driver.session() as session:
            result = await session.run("""
                MATCH (t:Product {category: 'Torches'})<-[:COMPATIBLE_WITH]-(other:Product)
                RETURN DISTINCT other.category as category, count(*) as torch_count
                ORDER BY category
            """)
            records = [rec async for rec in result]

            if records:
                print("   Torches are compatible WITH:")
                for rec in records:
                    print(f"     - {rec['category']}: {rec['torch_count']} torch relationships")
            else:
                print("   ❌ No incoming relationships found")
            print()

        # Check the reverse - what do Torches connect to?
        print("2. What do Torches connect TO?")
        async with driver.session() as session:
            result = await session.run("""
                MATCH (t:Product {category: 'Torches'})-[:COMPATIBLE_WITH]->(other:Product)
                RETURN DISTINCT other.category as category, count(*) as torch_count
                ORDER BY category
            """)
            records = [rec async for rec in result]

            if records:
                print("   Torches connect TO:")
                for rec in records:
                    print(f"     - {rec['category']}: {rec['torch_count']} relationships")
            else:
                print("   ❌ No outgoing relationships found")
            print()

        # Check if PowerSource directly connects to Torches
        print("3. Do PowerSources connect to Torches?")
        async with driver.session() as session:
            result = await session.run("""
                MATCH (ps:Product {category: 'Powersource'})-[:COMPATIBLE_WITH]->(t:Product {category: 'Torches'})
                RETURN count(*) as count
            """)
            record = await result.single()
            count = record["count"] if record else 0
            if count > 0:
                print(f"   ✅ Found {count} PowerSource → Torch relationships")
            else:
                print(f"   ❌ NO PowerSource → Torch relationships")
            print()

        # Check if Feeders connect to Torches
        print("4. Do Feeders connect to Torches?")
        async with driver.session() as session:
            result = await session.run("""
                MATCH (f:Product {category: 'Feeder'})-[:COMPATIBLE_WITH]->(t:Product {category: 'Torches'})
                RETURN count(*) as count
            """)
            record = await result.single()
            count = record["count"] if record else 0
            if count > 0:
                print(f"   ✅ Found {count} Feeder → Torch relationships")
            else:
                print(f"   ❌ NO Feeder → Torch relationships")
            print()

        # Sample some actual Torch relationships
        print("5. Sample Torch relationships:")
        async with driver.session() as session:
            result = await session.run("""
                MATCH (other:Product)-[:COMPATIBLE_WITH]->(t:Product {category: 'Torches'})
                RETURN other.category as from_category,
                       other.item_name as from_name,
                       t.item_name as torch_name
                LIMIT 10
            """)
            records = [rec async for rec in result]

            if records:
                for rec in records:
                    print(f"   {rec['from_category']}: {rec['from_name']}")
                    print(f"     → {rec['torch_name']}")
                    print()
            else:
                print("   ❌ No relationships found")

        print("=" * 80)
        print("DIAGNOSIS")
        print("=" * 80)
        print("The search_torch() method (line 1532) looks for:")
        print("  MATCH (ps)-[r1:COMPATIBLE_WITH]->(target:Product {category: 'Torches'})")
        print()
        print("This means: PowerSource → Torch relationship")
        print("Check if this relationship pattern exists in the database above.")

    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(check_torch_relationships())
