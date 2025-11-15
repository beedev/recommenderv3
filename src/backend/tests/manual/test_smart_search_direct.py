#!/usr/bin/env python3
"""
Test _search_component_smart() directly to see why Feeder accessories fall back.
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from app.services.neo4j.product_search import Neo4jProductSearch

async def test_smart_search_direct():
    """Test _search_component_smart() directly"""

    neo4j_uri = os.getenv("NEO4J_URI", "neo4j+ssc://0a8008b4.databases.neo4j.io")
    neo4j_username = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    product_search = Neo4jProductSearch(neo4j_uri, neo4j_username, neo4j_password)

    try:
        print("=" * 80)
        print("TESTING _search_component_smart() DIRECTLY")
        print("=" * 80)
        print()

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

        print("Test: Calling _search_component_smart() for feeder_accessories")
        print(f"  - response_json: PowerSource + Feeder selected")
        print(f"  - user_message: 'strain relief'")
        print(f"  - limit: 5")
        print("-" * 80)

        # Call the smart search method directly
        results = await product_search._search_component_smart(
            component_type="feeder_accessories",
            master_parameters={},
            response_json=response_json,
            user_message="strain relief",
            limit=5,
            offset=0
        )

        print(f"\n📊 Results: {len(results.products)} products")
        print(f"Total count: {results.total_count}")
        print(f"Filters applied: {results.filters_applied}")
        print()

        if results.products:
            print("Products returned:")
            for i, product in enumerate(results.products, 1):
                print(f"   {i}. {product.name}")
                # Check if score is in the name
                if "(Score:" in product.name:
                    print(f"      ✅ Lucene score detected!")
                else:
                    print(f"      ❌ NO Lucene score - using traditional search")
        else:
            print("❌ No products found")
        print()

        # Check if Lucene was used
        if results.filters_applied.get("lucene_search"):
            print("✅ Used Lucene search (scores should be present)")
        else:
            print("❌ Did NOT use Lucene search (traditional fallback)")

        print()
        print("=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)

    finally:
        await product_search.close()

if __name__ == "__main__":
    asyncio.run(test_smart_search_direct())
