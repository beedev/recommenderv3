"""
Quick Neo4j test to verify Remote products with COMPATIBLE_WITH relationships exist.
"""
import asyncio
from app.database.database import get_neo4j_driver

async def test_remote_relationships():
    driver = await get_neo4j_driver()

    # Test GINs from user
    power_source_gin = "0465350883"
    feeder_gin = "0445800881"

    query = """
    MATCH (remote:Product)
    WHERE remote.category = 'Remotes'
    OPTIONAL MATCH (remote)-[r_ps:COMPATIBLE_WITH]->(ps:Product {gin: $ps_gin})
    OPTIONAL MATCH (remote)-[r_f:COMPATIBLE_WITH]->(f:Product {gin: $f_gin})
    RETURN remote.gin AS remote_gin,
           remote.item_name AS remote_name,
           COUNT(DISTINCT r_ps) AS ps_compat,
           COUNT(DISTINCT r_f) AS f_compat
    ORDER BY (COUNT(DISTINCT r_ps) + COUNT(DISTINCT r_f)) DESC
    LIMIT 10
    """

    print(f"Searching for Remote products compatible with:")
    print(f"  PowerSource GIN: {power_source_gin}")
    print(f"  Feeder GIN: {feeder_gin}")
    print()

    async with driver.session() as session:
        result = await session.run(query, ps_gin=power_source_gin, f_gin=feeder_gin)
        records = await result.data()

        print(f"Found {len(records)} Remote products:")
        for i, record in enumerate(records, 1):
            print(f"{i}. {record['remote_name']} (GIN: {record['remote_gin']})")
            print(f"   PowerSource compat: {'YES' if record['ps_compat'] > 0 else 'NO'}")
            print(f"   Feeder compat: {'YES' if record['f_compat'] > 0 else 'NO'}")

    await driver.close()

if __name__ == "__main__":
    asyncio.run(test_remote_relationships())
