#!/usr/bin/env python3
"""
Check what accessory categories exist in Neo4j.
"""

import asyncio
import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://0a8008b4.databases.neo4j.io")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

async def check_accessory_categories():
    """Query all distinct accessory categories"""

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    try:
        print("=" * 80)
        print("ACCESSORY CATEGORIES IN NEO4J")
        print("=" * 80)
        print()

        # Get all categories that contain "Accessor" or "Wears"
        async with driver.session() as session:
            result = await session.run("""
                MATCH (p:Product)
                WHERE p.category CONTAINS 'Accessor' OR p.category CONTAINS 'Wears'
                RETURN DISTINCT p.category as category, count(*) as count
                ORDER BY category
            """)

            records = [rec async for rec in result]

            print(f"Found {len(records)} accessory categories:")
            print()

            for rec in records:
                print(f"  Category: {rec['category']:<40} Count: {rec['count']}")
            print()

        # Check specifically for PowerSource and Feeder accessories
        print("=" * 80)
        print("SPECIFIC ACCESSORY TYPES")
        print("=" * 80)
        print()

        # PowerSource Accessories
        print("1. PowerSource Accessories:")
        async with driver.session() as session:
            result = await session.run("""
                MATCH (p:Product)
                WHERE p.category CONTAINS 'Powersource' AND p.category CONTAINS 'Accessor'
                RETURN p.category as category, count(*) as count
            """)
            records = [rec async for rec in result]
            if records:
                for rec in records:
                    print(f"   Category: {rec['category']} (Count: {rec['count']})")
            else:
                print("   ⚠️ No PowerSource accessories found")
            print()

        # Feeder Accessories
        print("2. Feeder Accessories:")
        async with driver.session() as session:
            result = await session.run("""
                MATCH (p:Product)
                WHERE p.category CONTAINS 'Feeder' AND p.category CONTAINS 'Accessor'
                RETURN p.category as category, count(*) as count
            """)
            records = [rec async for rec in result]
            if records:
                for rec in records:
                    print(f"   Category: {rec['category']} (Count: {rec['count']})")
            else:
                print("   ⚠️ No Feeder accessories found")
            print()

        # Sample products for each type
        print("=" * 80)
        print("SAMPLE PRODUCTS")
        print("=" * 80)
        print()

        async with driver.session() as session:
            result = await session.run("""
                MATCH (p:Product)
                WHERE p.category CONTAINS 'Powersource' AND p.category CONTAINS 'Accessor'
                RETURN p.gin as gin, p.item_name as name, p.category as category
                LIMIT 3
            """)
            records = [rec async for rec in result]
            if records:
                print("PowerSource Accessories:")
                for rec in records:
                    print(f"  - {rec['name']} (GIN: {rec['gin']}, Category: {rec['category']})")
                print()

        async with driver.session() as session:
            result = await session.run("""
                MATCH (p:Product)
                WHERE p.category CONTAINS 'Feeder' AND p.category CONTAINS 'Accessor'
                RETURN p.gin as gin, p.item_name as name, p.category as category
                LIMIT 3
            """)
            records = [rec async for rec in result]
            if records:
                print("Feeder Accessories:")
                for rec in records:
                    print(f"  - {rec['name']} (GIN: {rec['gin']}, Category: {rec['category']})")
                print()

    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(check_accessory_categories())
