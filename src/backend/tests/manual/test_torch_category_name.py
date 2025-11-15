#!/usr/bin/env python3
"""
Check what category name is used for Torches in Neo4j database.
"""

import asyncio
import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://0a8008b4.databases.neo4j.io")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

async def check_torch_category():
    """Check torch category names in database"""

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    try:
        print("=" * 80)
        print("CHECKING TORCH CATEGORY NAMES")
        print("=" * 80)
        print()

        # Check all Product categories
        print("Test 1: All Product categories in database")
        print("-" * 80)

        async with driver.session() as session:
            result = await session.run("""
                MATCH (p:Product)
                RETURN DISTINCT p.category as category, count(*) as count
                ORDER BY category
            """)
            records = [rec async for rec in result]

            if records:
                print(f"Found {len(records)} categories:")
                for rec in records:
                    print(f"   - '{rec['category']}': {rec['count']} products")
            else:
                print("❌ No categories found")
        print()

        # Search for torch-related categories
        print("Test 2: Torch-related categories")
        print("-" * 80)

        async with driver.session() as session:
            result = await session.run("""
                MATCH (p:Product)
                WHERE toLower(p.category) CONTAINS 'torch'
                RETURN DISTINCT p.category as category, count(*) as count
                ORDER BY category
            """)
            records = [rec async for rec in result]

            if records:
                print(f"Found {len(records)} torch-related categories:")
                for rec in records:
                    print(f"   - '{rec['category']}': {rec['count']} products")
            else:
                print("❌ No torch categories found")
        print()

        # Sample some torch products
        print("Test 3: Sample torch products")
        print("-" * 80)

        async with driver.session() as session:
            result = await session.run("""
                MATCH (p:Product)
                WHERE toLower(p.category) CONTAINS 'torch'
                RETURN p.gin as gin, p.item_name as name, p.category as category
                LIMIT 10
            """)
            records = [rec async for rec in result]

            if records:
                print(f"Sample torch products:")
                for rec in records:
                    print(f"   - {rec['name']} (GIN: {rec['gin']}, Category: '{rec['category']}')")
            else:
                print("❌ No torch products found")
        print()

        print("=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)

    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(check_torch_category())
