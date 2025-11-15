#!/usr/bin/env python3
"""
Check Neo4j database schema and labels
"""

import asyncio
import os
from neo4j import AsyncGraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")


async def check_schema():
    """Check what's in the Neo4j database"""
    driver = AsyncGraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )

    try:
        async with driver.session() as session:
            print("="*60)
            print("Checking Neo4j Database Schema")
            print("="*60)

            # Get all labels
            print("\n1. Getting all node labels...")
            result = await session.run("CALL db.labels()")
            labels = [record[0] async for record in result]
            print(f"Found {len(labels)} labels: {labels}")

            # Count nodes per label
            print("\n2. Counting nodes per label...")
            for label in labels:
                result = await session.run(f"MATCH (n:{label}) RETURN count(n) AS count")
                async for record in result:
                    count = record["count"]
                    print(f"  {label}: {count} nodes")

            # Sample properties from first label
            if labels:
                sample_label = labels[0]
                print(f"\n3. Sample properties from {sample_label}...")
                result = await session.run(f"MATCH (n:{sample_label}) RETURN n LIMIT 1")
                async for record in result:
                    node = record["n"]
                    print(f"  Properties: {list(node.keys())}")
                    print(f"  Sample data:")
                    for key in list(node.keys())[:5]:
                        print(f"    {key}: {node[key]}")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(check_schema())
