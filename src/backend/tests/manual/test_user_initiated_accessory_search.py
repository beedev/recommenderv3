#!/usr/bin/env python3
"""
Test user-initiated PowerSource Accessories search with actual user message.
This simulates when a user TYPES a search term like "trolley" or "strain relief".
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from app.services.neo4j.product_search import Neo4jProductSearch

async def test_user_initiated_search():
    """Test user-initiated accessory search (when user types)"""

    neo4j_uri = os.getenv("NEO4J_URI", "neo4j+ssc://0a8008b4.databases.neo4j.io")
    neo4j_username = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    product_search = Neo4jProductSearch(neo4j_uri, neo4j_username, neo4j_password)

    try:
        print("=" * 80)
        print("TESTING USER-INITIATED ACCESSORY SEARCH")
        print("Simulating: User types 'trolley' after PowerSource is selected")
        print("=" * 80)
        print()

        # Simulate PowerSource already selected
        response_json = {
            "PowerSource": {
                "gin": "0445400883",
                "name": "Aristo Mig U5000iw, WC CE",
                "category": "Powersource"
            }
        }

        # Test 1: User types "trolley"
        print("Test 1: User types 'trolley'")
        print("-" * 80)

        results = await product_search.search_powersource_accessories_smart(
            master_parameters={},
            response_json=response_json,
            user_message="trolley",  # User's actual typed message
            limit=5,
            offset=0
        )

        print(f"\n📊 Results: {len(results.products)} products")
        if results.products:
            print("Products returned:")
            for i, product in enumerate(results.products, 1):
                has_score = "(Score:" in product.name
                status = "✅ HAS SCORE" if has_score else "❌ NO SCORE"
                print(f"   {i}. {product.name} {status}")
        else:
            print("❌ No products found")
        print()

        # Test 2: User types "strain relief"
        print("Test 2: User types 'strain relief'")
        print("-" * 80)

        results2 = await product_search.search_powersource_accessories_smart(
            master_parameters={},
            response_json=response_json,
            user_message="strain relief",  # User's actual typed message
            limit=5,
            offset=0
        )

        print(f"\n📊 Results: {len(results2.products)} products")
        if results2.products:
            print("Products returned:")
            for i, product in enumerate(results2.products, 1):
                has_score = "(Score:" in product.name
                status = "✅ HAS SCORE" if has_score else "❌ NO SCORE"
                print(f"   {i}. {product.name} {status}")
        else:
            print("❌ No products found")
        print()

        # Test 3: User types generic term "cable"
        print("Test 3: User types 'cable'")
        print("-" * 80)

        results3 = await product_search.search_powersource_accessories_smart(
            master_parameters={},
            response_json=response_json,
            user_message="cable",  # User's actual typed message
            limit=5,
            offset=0
        )

        print(f"\n📊 Results: {len(results3.products)} products")
        if results3.products:
            print("Products returned:")
            for i, product in enumerate(results3.products, 1):
                has_score = "(Score:" in product.name
                status = "✅ HAS SCORE" if has_score else "❌ NO SCORE"
                print(f"   {i}. {product.name} {status}")
        else:
            print("❌ No products found")
        print()

        print("=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)
        print()
        print("EXPECTED BEHAVIOR:")
        print("  ✅ All products should have '(Score: X.X)' in their names")
        print("  ✅ This proves Lucene is working for user-typed searches")
        print()
        print("IF NO SCORES:")
        print("  ❌ Issue is in user-initiated search handler")
        print("  ❌ Need to check lines 1935-1940, 2005-2010 in state_orchestrator.py")

    finally:
        await product_search.close()

if __name__ == "__main__":
    asyncio.run(test_user_initiated_search())
