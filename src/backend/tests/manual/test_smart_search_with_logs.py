#!/usr/bin/env python3
"""
Test _search_component_smart() with logging enabled to see internal flow.
"""

import asyncio
import os
import logging
from dotenv import load_dotenv

# Enable logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)

load_dotenv()

from app.services.neo4j.product_search import Neo4jProductSearch

async def test_smart_search_with_logs():
    """Test _search_component_smart() with logging"""

    neo4j_uri = os.getenv("NEO4J_URI", "neo4j+ssc://0a8008b4.databases.neo4j.io")
    neo4j_username = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    product_search = Neo4jProductSearch(neo4j_uri, neo4j_username, neo4j_password)

    try:
        print("=" * 80)
        print("TESTING WITH LOGGING ENABLED")
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

        print("Calling _search_component_smart() for feeder_accessories...")
        print()

        # Call the smart search method
        results = await product_search._search_component_smart(
            component_type="feeder_accessories",
            master_parameters={},
            response_json=response_json,
            user_message="strain relief",
            limit=5,
            offset=0
        )

        print()
        print("=" * 80)
        print(f"RESULTS: {len(results.products)} products")
        print("=" * 80)

        if results.products:
            for i, product in enumerate(results.products, 1):
                has_score = "(Score:" in product.name
                status = "✅ Lucene" if has_score else "❌ Traditional"
                print(f"{i}. {product.name} {status}")

    finally:
        await product_search.close()

if __name__ == "__main__":
    asyncio.run(test_smart_search_with_logs())
