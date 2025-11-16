"""
Check if competitor_brand_product_pairs exists on specific product
"""
import asyncio
from neo4j import AsyncGraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

async def check_product():
    NEO4J_URI = os.getenv('NEO4J_URI')
    NEO4J_USERNAME = os.getenv('NEO4J_USERNAME', 'neo4j')
    NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')

    print(f"Connecting to: {NEO4J_URI}\n")

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    async with driver.session() as session:
        # Check the product that was missing competitor_pairs: "Renegade ES 300i (CE) with cables"
        # GIN from test output (need to find it)

        # First, let's find products with "Renegade ES 300i" in the name
        result = await session.run('''
            MATCH (p:Product)
            WHERE p.item_name CONTAINS "Renegade ES 300i"
            RETURN p.gin as gin, p.item_name as name,
                   p.competitor_brand_product_pairs IS NOT NULL as has_field,
                   p.competitor_brand_product_pairs as competitors
            ORDER BY p.item_name
        ''')
        records = await result.data()

        print(f"Found {len(records)} Renegade ES 300i products:\n")
        for record in records:
            print(f"GIN: {record['gin']}")
            print(f"Name: {record['name']}")
            print(f"Has competitor_brand_product_pairs field: {record['has_field']}")
            if record['has_field']:
                competitors = record['competitors']
                if isinstance(competitors, list):
                    print(f"Competitors ({len(competitors)}): {', '.join(competitors[:3])}{'...' if len(competitors) > 3 else ''}")
                else:
                    print(f"Competitors: {competitors}")
            else:
                print(f"⚠️  Field is MISSING!")
            print("-" * 80)

    await driver.close()

if __name__ == "__main__":
    asyncio.run(check_product())
