"""
Script to extract product names from Neo4j by category
Run this to populate app/config/product_names.json
"""

import asyncio
import json
from neo4j import AsyncGraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()


async def extract_product_names():
    """Extract product names from Neo4j grouped by category"""

    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    driver = AsyncGraphDatabase.driver(uri, auth=(username, password))

    # Map of search keys to actual database categories
    category_mapping = {
        'power_source': 'Powersource',
        'feeder': 'Feeder',
        'cooler': 'Cooler',
        'interconnector': 'Interconn',  # Database has 'Interconn' not 'Interconnector'
        'torch': 'Torches'  # Database has 'Torches' not 'Torch'
    }
    
    product_names = {}

    try:
        async with driver.session() as session:
            for key, category in category_mapping.items():
                query = """
                MATCH (p:Product {category: $category})
                RETURN p.item_name, p.gin
                ORDER BY p.item_name
                LIMIT 100
                """

                result = await session.run(query, {"category": category})
                records = await result.data()

                # Store product names
                product_names[key] = [record["p.item_name"] for record in records if record["p.item_name"]]

                print(f"\n{category} ({key}): Found {len(product_names[key])} products")
                print(f"Sample: {product_names[key][:5]}")
            
            # Handle accessories separately - get all accessory types
            print("\n" + "="*60)
            print("Extracting Accessories (all types)...")
            print("="*60)
            accessory_query = """
            MATCH (p:Product)
            WHERE p.category CONTAINS 'Accessor' OR p.category CONTAINS 'Wears'
            RETURN p.item_name, p.gin, p.category
            ORDER BY p.item_name
            LIMIT 100
            """
            result = await session.run(accessory_query)
            records = await result.data()
            product_names['accessory'] = [record["p.item_name"] for record in records if record["p.item_name"]]
            
            print(f"Total Accessories: Found {len(product_names['accessory'])} products")
            print(f"Sample: {product_names['accessory'][:5]}")

        # Save to config file
        config_dir = "app/config"
        os.makedirs(config_dir, exist_ok=True)

        with open(f"{config_dir}/product_names.json", "w") as f:
            json.dump(product_names, f, indent=2)

        print(f"\n✅ Product names saved to {config_dir}/product_names.json")
        print(f"\nTotal categories: {len(product_names)}")
        for cat, names in product_names.items():
            print(f"  {cat}: {len(names)} products")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(extract_product_names())