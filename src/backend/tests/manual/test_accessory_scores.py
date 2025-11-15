#!/usr/bin/env python3
"""
Test that PowerSource and Feeder Accessories now show Lucene scores.
"""

import asyncio
import os
from dotenv import load_dotenv

# Set up environment
load_dotenv()

from app.services.neo4j.product_search import Neo4jProductSearch

async def test_accessory_scores():
    """Test that accessories show Lucene scores"""

    neo4j_uri = os.getenv("NEO4J_URI", "neo4j+ssc://0a8008b4.databases.neo4j.io")
    neo4j_username = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    product_search = Neo4jProductSearch(neo4j_uri, neo4j_username, neo4j_password)

    try:
        print("=" * 80)
        print("TESTING LUCENE SCORES FOR ACCESSORIES")
        print("=" * 80)
        print()

        # Test 1: PowerSource Accessories with Lucene search
        print("Test 1: PowerSource Accessories - Lucene Search")
        print("-" * 80)

        # Simulate response_json with PowerSource selected
        response_json = {
            "PowerSource": {
                "gin": "0446200880",
                "name": "Aristo 500ix",
                "category": "Powersource"
            }
        }

        results = await product_search.search_powersource_accessories_smart(
            master_parameters={},
            response_json=response_json,
            user_message="trolley",  # Lucene search term
            limit=5
        )

        print(f"Found {len(results.products)} products")
        if results.products:
            print("\nTop 5 PowerSource Accessories (with Lucene scores):")
            for i, product in enumerate(results.products, 1):
                print(f"  {i}. {product.name}")
                # Check if score is in the name (e.g., "Product Name (Score: 4.2)")
                if "(Score:" in product.name:
                    print(f"      ✅ Lucene score detected!")
                else:
                    print(f"      ❌ NO Lucene score")
        else:
            print("  ❌ No products found")
        print()

        # Test 2: Feeder Accessories with Lucene search
        print("Test 2: Feeder Accessories - Lucene Search")
        print("-" * 80)

        # Simulate response_json with PowerSource + Feeder selected
        response_json = {
            "PowerSource": {
                "gin": "0446200880",
                "name": "Aristo 500ix",
                "category": "Powersource"
            },
            "Feeder": {
                "gin": "0445800887",
                "name": "RobustFeed U6 OW",
                "category": "Feeder"
            }
        }

        results = await product_search.search_feeder_accessories_smart(
            master_parameters={},
            response_json=response_json,
            user_message="strain relief",  # Lucene search term
            limit=5
        )

        print(f"Found {len(results.products)} products")
        if results.products:
            print("\nTop 5 Feeder Accessories (with Lucene scores):")
            for i, product in enumerate(results.products, 1):
                print(f"  {i}. {product.name}")
                # Check if score is in the name
                if "(Score:" in product.name:
                    print(f"      ✅ Lucene score detected!")
                else:
                    print(f"      ❌ NO Lucene score")
        else:
            print("  ❌ No products found")
        print()

        print("=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)
        print("\n✅ If you see '(Score: X.XX)' in product names above, Lucene is working!")
        print("❌ If you DON'T see scores, the fix didn't work.")

    finally:
        await product_search.close()

if __name__ == "__main__":
    asyncio.run(test_accessory_scores())
