"""
Check what fields are available in Neo4j Product nodes
"""
import asyncio
from neo4j import AsyncGraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

async def check_fields():
    NEO4J_URI = os.getenv('NEO4J_URI')
    NEO4J_USERNAME = os.getenv('NEO4J_USERNAME', 'neo4j')
    NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')

    print(f"Connecting to: {NEO4J_URI}")

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    async with driver.session() as session:
        # Get Renegade ES300i product
        result = await session.run('''
            MATCH (p:Product {gin: "0445100880"})
            RETURN p
        ''')
        records = await result.data()

        if records:
            product_node = records[0]['p']

            print('\n🔍 Product: Renegade ES300i (GIN: 0445100880)')
            print('=' * 80)
            print(f"Available fields:")
            for key in sorted(product_node.keys()):
                value = product_node[key]
                if isinstance(value, str) and len(value) > 100:
                    print(f"\n{key}: {value[:200]}...")
                else:
                    print(f"\n{key}: {value}")

            # Check specifically for attribute/competitor fields
            print('\n' + '=' * 80)
            print('🎯 Checking for competitor-related fields:')
            for key in product_node.keys():
                if any(keyword in key.lower() for keyword in ['attribute', 'competitor', 'equiv', 'match', 'similar']):
                    print(f"\n✅ Found: {key}")
                    value = product_node[key]
                    if isinstance(value, str):
                        print(f"   Value: {value[:500]}")

    await driver.close()

if __name__ == "__main__":
    asyncio.run(check_fields())
