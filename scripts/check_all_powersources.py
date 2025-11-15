"""List all PowerSource products in Neo4j"""
import asyncio
import os
from dotenv import load_dotenv
from app.services.neo4j.product_search import Neo4jProductSearch

load_dotenv()

async def list_all_powersources():
    """Query Neo4j for all PowerSource products"""

    # Get credentials from env
    uri = os.getenv('NEO4J_URI')
    username = os.getenv('NEO4J_USERNAME')
    password = os.getenv('NEO4J_PASSWORD')

    search_service = Neo4jProductSearch(uri, username, password)

    # Query for all PowerSource products
    query = '''
    MATCH (p:PowerSource)
    RETURN p.gin, p.item_name, p.description_catalogue
    ORDER BY p.item_name
    '''

    result = await search_service.driver.execute_query(query)

    print('\n' + '='*80)
    print(f'=== All PowerSource Products ({len(result.records)} total) ===')
    print('='*80 + '\n')

    for i, record in enumerate(result.records, 1):
        print(f'{i}. GIN: {record["p.gin"]}')
        print(f'   Name: {record["p.item_name"]}')
        desc = record["p.description_catalogue"]
        if desc:
            # Extract current rating if present
            if 'A' in desc:
                desc_lines = desc.split('\n')
                relevant_lines = [line for line in desc_lines if 'A' in line or 'current' in line.lower()]
                if relevant_lines:
                    print(f'   Current Info: {relevant_lines[0][:150]}')
        print('-' * 80)

    await search_service.close()

if __name__ == '__main__':
    asyncio.run(list_all_powersources())
