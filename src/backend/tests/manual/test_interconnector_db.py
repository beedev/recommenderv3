#!/usr/bin/env python3
"""
Test script to investigate Interconnector database content and search issues.
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

async def investigate_interconnectors():
    """Check what Interconnector products exist in Neo4j"""

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    try:
        print("=" * 80)
        print("INVESTIGATING INTERCONNECTOR PRODUCTS IN NEO4J")
        print("=" * 80)
        print()

        # 1. Count total Interconnectors
        print("1. Total Interconnectors in database:")
        async with driver.session() as session:
            result = await session.run("""
                MATCH (i:Product {category: 'Interconn'})
                RETURN count(i) as total
            """)
            record = await result.single()
            total = record["total"] if record else 0
            print(f"   Total: {total}")
            print()

        # 2. Check for air-cooled or gas-cooled interconnectors
        print("2. Interconnectors by cooling type (description search):")
        async with driver.session() as session:
            result = await session.run("""
                MATCH (i:Product {category: 'Interconn'})
                WHERE i.description_catalogue IS NOT NULL
                RETURN i.gin as gin,
                       i.item_name as name,
                       i.description_catalogue as description
                LIMIT 10
            """)
            records = [rec async for rec in result]
            print(f"   Found {len(records)} interconnectors")
            print()

            for i, rec in enumerate(records, 1):
                desc = (rec["description"] or "")[:200]
                print(f"   {i}. GIN: {rec['gin']}")
                print(f"      Name: {rec['name']}")
                print(f"      Description: {desc}...")
                print()

        # 3. Check compatibility with specific PowerSource
        print("3. Interconnectors compatible with Aristo 500ix (GIN: 0446200880):")
        async with driver.session() as session:
            result = await session.run("""
                MATCH (ps:Product {gin: '0446200880', category: 'Powersource'})<-[:COMPATIBLE_WITH]-(i:Product {category: 'Interconn'})
                RETURN i.gin as gin,
                       i.item_name as name,
                       i.description_catalogue as description
                LIMIT 10
            """)
            records = [rec async for rec in result]
            print(f"   Found {len(records)} compatible interconnectors")
            print()

            if records:
                for i, rec in enumerate(records, 1):
                    desc = (rec["description"] or "")[:150]
                    print(f"   {i}. GIN: {rec['gin']}")
                    print(f"      Name: {rec['name']}")
                    print(f"      Description: {desc}...")
                    print()
            else:
                print("   ⚠️ NO interconnectors found compatible with Aristo 500ix!")
                print()

        # 4. Check Lucene index
        print("4. Testing Lucene search for 'air cooled 5m':")
        async with driver.session() as session:
            result = await session.run("""
                CALL db.index.fulltext.queryNodes("productIndex", "air cooled 5m")
                YIELD node, score
                WHERE node.category = 'Interconn'
                RETURN node.gin as gin,
                       node.item_name as name,
                       score,
                       node.description_catalogue as description
                ORDER BY score DESC
                LIMIT 5
            """)
            records = [rec async for rec in result]
            print(f"   Found {len(records)} results")
            print()

            if records:
                for i, rec in enumerate(records, 1):
                    desc = (rec["description"] or "")[:150]
                    print(f"   {i}. GIN: {rec['gin']} (Score: {rec['score']:.2f})")
                    print(f"      Name: {rec['name']}")
                    print(f"      Description: {desc}...")
                    print()
            else:
                print("   ⚠️ NO Lucene results for 'air cooled 5m'!")
                print()

        # 5. Check for any Interconnector with "cable" in name
        print("5. Interconnectors with 'cable' in name:")
        async with driver.session() as session:
            result = await session.run("""
                MATCH (i:Product {category: 'Interconn'})
                WHERE toLower(i.item_name) CONTAINS 'cable'
                   OR toLower(i.description_catalogue) CONTAINS 'cable'
                RETURN i.gin as gin,
                       i.item_name as name,
                       i.description_catalogue as description
                LIMIT 5
            """)
            records = [rec async for rec in result]
            print(f"   Found {len(records)} results")
            print()

            if records:
                for i, rec in enumerate(records, 1):
                    desc = (rec["description"] or "")[:150]
                    print(f"   {i}. GIN: {rec['gin']}")
                    print(f"      Name: {rec['name']}")
                    print(f"      Description: {desc}...")
                    print()
            else:
                print("   ⚠️ NO interconnectors with 'cable' in name!")
                print()

        print("=" * 80)
        print("DIAGNOSIS")
        print("=" * 80)

        if total == 0:
            print("❌ PROBLEM: No Interconnector nodes exist in the database!")
            print("   Solution: Import Interconnector products to Neo4j")
        elif len(records) == 0:
            print("❌ PROBLEM: No Interconnectors are compatible with Aristo 500ix!")
            print("   Solution: Create COMPATIBLE_WITH relationships")
        else:
            print("✅ Database has Interconnectors")
            print("ℹ️  Next: Check why Lucene search isn't finding them")

    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(investigate_interconnectors())
