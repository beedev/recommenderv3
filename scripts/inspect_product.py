#!/usr/bin/env python3
"""
Inspect a sample product to see all properties
"""

import asyncio
import os
import json
from neo4j import AsyncGraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")


async def inspect_products():
    """Inspect sample products from each category"""
    driver = AsyncGraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )

    try:
        async with driver.session() as session:
            # Get sample from each category
            categories = ['Powersource', 'Feeder', 'Cooler', 'Torch', 'Interconn']

            for category in categories:
                print("\n" + "="*80)
                print(f"SAMPLE {category} PRODUCT")
                print("="*80)

                query = """
                MATCH (n:Product)
                WHERE n.category = $category
                RETURN n
                LIMIT 1
                """

                result = await session.run(query, category=category)
                async for record in result:
                    node = record["n"]

                    print(f"\nProduct Name: {node.get('item_name', 'N/A')}")
                    print(f"GIN: {node.get('gin', 'N/A')}")
                    print(f"\nAll Properties ({len(node.keys())}):")

                    for key in sorted(node.keys()):
                        value = node[key]
                        # Limit length of long values
                        if isinstance(value, str) and len(value) > 100:
                            value = value[:100] + "..."
                        print(f"  {key}: {value}")

                    # Check for relationships
                    print(f"\nRelationships:")
                    rel_query = """
                    MATCH (n:Product {gin: $gin})-[r]->(m)
                    RETURN type(r) AS rel_type, labels(m) AS target_labels, m.item_name AS target_name
                    LIMIT 10
                    """

                    rel_result = await session.run(rel_query, gin=node['gin'])
                    async for rel_record in rel_result:
                        print(f"  -> {rel_record['rel_type']} -> {rel_record['target_labels']} ({rel_record['target_name']})")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(inspect_products())
