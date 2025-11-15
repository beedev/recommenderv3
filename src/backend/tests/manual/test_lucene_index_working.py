#!/usr/bin/env python3
"""
Test that Lucene productIndex is working for all components.
"""

import asyncio
import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://0a8008b4.databases.neo4j.io")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

async def test_lucene_index():
    """Test Lucene productIndex for all components"""

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    try:
        print("=" * 80)
        print("TESTING LUCENE PRODUCTINDEX")
        print("=" * 80)
        print()

        # Test 1: Check if productIndex exists
        print("Test 1: Check if productIndex exists")
        print("-" * 80)

        async with driver.session() as session:
            result = await session.run("""
                SHOW INDEXES
                YIELD name, type, labelsOrTypes, properties
                WHERE name = 'productIndex'
                RETURN name, type, labelsOrTypes, properties
            """)
            records = [rec async for rec in result]

            if records:
                print("✅ productIndex exists:")
                for rec in records:
                    print(f"   Name: {rec['name']}")
                    print(f"   Type: {rec['type']}")
                    print(f"   Labels: {rec['labelsOrTypes']}")
                    print(f"   Properties: {rec['properties']}")
            else:
                print("❌ productIndex NOT FOUND!")
                return
        print()

        # Test 2: PowerSource Accessories with Lucene
        print("Test 2: PowerSource Accessories - Lucene Search (trolley)")
        print("-" * 80)

        async with driver.session() as session:
            result = await session.run("""
                CALL db.index.fulltext.queryNodes("productIndex", "trolley")
                YIELD node, score
                WHERE node.category = "Powersource Accessories"
                RETURN node.item_name as name, node.category as category, score
                ORDER BY score DESC
                LIMIT 5
            """)
            records = [rec async for rec in result]

            if records:
                print(f"✅ Found {len(records)} PowerSource Accessories with Lucene scores:")
                for i, rec in enumerate(records, 1):
                    print(f"   {i}. {rec['name']} (Score: {rec['score']:.2f})")
            else:
                print("❌ No PowerSource Accessories found with Lucene")
        print()

        # Test 3: Feeder Accessories with Lucene
        print("Test 3: Feeder Accessories - Lucene Search (strain relief)")
        print("-" * 80)

        async with driver.session() as session:
            result = await session.run("""
                CALL db.index.fulltext.queryNodes("productIndex", "strain relief")
                YIELD node, score
                WHERE node.category = "Feeder Accessories"
                RETURN node.item_name as name, node.category as category, score
                ORDER BY score DESC
                LIMIT 5
            """)
            records = [rec async for rec in result]

            if records:
                print(f"✅ Found {len(records)} Feeder Accessories with Lucene scores:")
                for i, rec in enumerate(records, 1):
                    print(f"   {i}. {rec['name']} (Score: {rec['score']:.2f})")
            else:
                print("❌ No Feeder Accessories found with Lucene")
        print()

        # Test 4: Torch with Lucene
        print("Test 4: Torch - Lucene Search (water cooled torch)")
        print("-" * 80)

        async with driver.session() as session:
            result = await session.run("""
                CALL db.index.fulltext.queryNodes("productIndex", "water cooled torch")
                YIELD node, score
                WHERE node.category = "Torches"
                RETURN node.item_name as name, node.category as category, score
                ORDER BY score DESC
                LIMIT 5
            """)
            records = [rec async for rec in result]

            if records:
                print(f"✅ Found {len(records)} Torches with Lucene scores:")
                for i, rec in enumerate(records, 1):
                    print(f"   {i}. {rec['name']} (Score: {rec['score']:.2f})")
            else:
                print("❌ No Torches found with Lucene")
        print()

        # Test 5: Test ALL categories to see what's indexed
        print("Test 5: Check ALL indexed categories")
        print("-" * 80)

        async with driver.session() as session:
            result = await session.run("""
                CALL db.index.fulltext.queryNodes("productIndex", "welding")
                YIELD node, score
                RETURN DISTINCT node.category as category, count(*) as count
                ORDER BY count DESC
            """)
            records = [rec async for rec in result]

            if records:
                print(f"✅ Categories indexed in productIndex:")
                for rec in records:
                    print(f"   - {rec['category']}: {rec['count']} products")
            else:
                print("❌ No categories found in index")
        print()

        print("=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)

    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(test_lucene_index())
