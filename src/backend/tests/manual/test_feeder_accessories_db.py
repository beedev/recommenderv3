#!/usr/bin/env python3
"""
Check what Feeder Accessories exist in Neo4j database.
"""

import asyncio
import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://0a8008b4.databases.neo4j.io")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

async def check_feeder_accessories():
    """Check Feeder Accessories in database"""

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    try:
        print("=" * 80)
        print("FEEDER ACCESSORIES DATABASE CHECK")
        print("=" * 80)
        print()

        # Check total count
        async with driver.session() as session:
            result = await session.run("""
                MATCH (fa:Product {category: 'Feeder Accessories'})
                RETURN count(fa) as count
            """)
            record = await result.single()
            total = record["count"]
            print(f"Total Feeder Accessories in database: {total}")
            print()

        # Check if any are compatible with RobustFeed U6
        async with driver.session() as session:
            result = await session.run("""
                MATCH (f:Product {gin: $feeder_gin, category: 'Feeder'})
                MATCH (f)-[:COMPATIBLE_WITH]-(fa:Product {category: 'Feeder Accessories'})
                RETURN fa.gin as gin, fa.item_name as name
                LIMIT 10
            """, {"feeder_gin": "0460520880"})
            records = [rec async for rec in result]

            if records:
                print(f"Feeder Accessories compatible with RobustFeed U6:")
                for rec in records:
                    print(f"  - {rec['name']} (GIN: {rec['gin']})")
            else:
                print("❌ NO Feeder Accessories compatible with RobustFeed U6!")
            print()

        # Show sample feeder accessories with ANY feeder
        async with driver.session() as session:
            result = await session.run("""
                MATCH (f:Product {category: 'Feeder'})-[:COMPATIBLE_WITH]-(fa:Product {category: 'Feeder Accessories'})
                WITH DISTINCT fa, collect(DISTINCT f.item_name) as compatible_feeders
                RETURN fa.gin as gin, fa.item_name as name, compatible_feeders
                LIMIT 5
            """)
            records = [rec async for rec in result]

            if records:
                print("Sample Feeder Accessories with their compatible feeders:")
                for rec in records:
                    feeders = ", ".join(rec['compatible_feeders'][:3])
                    print(f"  - {rec['name']}")
                    print(f"    Compatible with: {feeders}")
                    print()
            else:
                print("❌ NO Feeder Accessories found with ANY feeder!")

    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(check_feeder_accessories())
