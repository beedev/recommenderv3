#!/usr/bin/env python3
"""
Recreate Lucene productIndex to include ALL Product categories.

This script will:
1. Drop existing productIndex (if exists)
2. Create new productIndex with proper configuration
3. Verify all categories are indexed
"""

import asyncio
import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://0a8008b4.databases.neo4j.io")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

async def recreate_lucene_index():
    """Recreate Lucene productIndex"""

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    try:
        print("=" * 80)
        print("RECREATING LUCENE PRODUCTINDEX")
        print("=" * 80)
        print()

        # Step 1: Check current index
        print("Step 1: Check current productIndex")
        print("-" * 80)

        async with driver.session() as session:
            result = await session.run("""
                SHOW INDEXES
                YIELD name, type
                WHERE name = 'productIndex'
                RETURN name, type
            """)
            records = [rec async for rec in result]

            if records:
                print(f"✅ Found existing productIndex: {records[0]['type']}")
            else:
                print("ℹ️ No existing productIndex found")
        print()

        # Step 2: Drop existing index
        print("Step 2: Drop existing productIndex (if exists)")
        print("-" * 80)

        try:
            async with driver.session() as session:
                await session.run("DROP INDEX productIndex IF EXISTS")
                print("✅ Dropped existing productIndex")
        except Exception as e:
            print(f"⚠️ Could not drop index: {e}")
        print()

        # Step 3: Create new index
        print("Step 3: Create new productIndex")
        print("-" * 80)

        async with driver.session() as session:
            # Create full-text index on Product nodes
            # Index properties: item_name, description_ruleset, gin, category
            await session.run("""
                CREATE FULLTEXT INDEX productIndex IF NOT EXISTS
                FOR (p:Product)
                ON EACH [p.item_name, p.description_ruleset, p.gin, p.category]
            """)
            print("✅ Created new productIndex")
            print("   Indexed properties: item_name, description_ruleset, gin, category")
            print("   Indexed label: Product")
        print()

        # Step 4: Wait for index to be populated (Neo4j indexes asynchronously)
        print("Step 4: Wait for index population...")
        print("-" * 80)
        print("⏳ Waiting 5 seconds for Neo4j to populate index...")
        await asyncio.sleep(5)
        print("✅ Wait complete")
        print()

        # Step 5: Verify index is working
        print("Step 5: Verify productIndex is working")
        print("-" * 80)

        async with driver.session() as session:
            # Test search
            result = await session.run("""
                CALL db.index.fulltext.queryNodes("productIndex", "welding")
                YIELD node, score
                RETURN DISTINCT node.category as category, count(*) as count
                ORDER BY category
            """)
            records = [rec async for rec in result]

            if records:
                print(f"✅ productIndex working! Found {len(records)} categories:")
                for rec in records:
                    print(f"   - {rec['category']}: {rec['count']} products")
            else:
                print("❌ productIndex not working - no results found")
        print()

        # Step 6: Check specific categories
        print("Step 6: Check key categories")
        print("-" * 80)

        test_categories = [
            ("Torches", "torch"),
            ("Powersource Accessories", "trolley"),
            ("Feeder Accessories", "strain relief")
        ]

        for category, search_term in test_categories:
            async with driver.session() as session:
                result = await session.run("""
                    CALL db.index.fulltext.queryNodes("productIndex", $search_term)
                    YIELD node, score
                    WHERE node.category = $category
                    RETURN count(*) as count
                """, {"search_term": search_term, "category": category})
                record = await result.single()
                count = record["count"]

                if count > 0:
                    print(f"   ✅ {category}: {count} products found with '{search_term}'")
                else:
                    print(f"   ❌ {category}: NO products found with '{search_term}'")
        print()

        print("=" * 80)
        print("LUCENE INDEX RECREATION COMPLETE")
        print("=" * 80)
        print()
        print("✅ If all checks passed, the index is ready to use!")
        print("⚠️ If checks failed, you may need to wait longer for index population")
        print("   or check Neo4j logs for errors.")

    except Exception as e:
        print(f"❌ Error recreating index: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(recreate_lucene_index())
