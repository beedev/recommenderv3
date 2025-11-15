"""Check Renegade product data in Neo4j"""
import asyncio
import os
from dotenv import load_dotenv
from app.services.neo4j.product_search import Neo4jProductSearch

load_dotenv()

async def check_renegade():
    """Query Neo4j for Renegade products"""

    # Get credentials from env
    uri = os.getenv('NEO4J_URI')
    username = os.getenv('NEO4J_USERNAME')
    password = os.getenv('NEO4J_PASSWORD')

    search_service = Neo4jProductSearch(uri, username, password)

    # Query for Renegade products
    query = '''
    MATCH (p:PowerSource)
    WHERE p.item_name CONTAINS 'Renegade'
    RETURN p.gin, p.item_name, p.description_catalogue
    ORDER BY p.item_name
    LIMIT 10
    '''

    result = await search_service.driver.execute_query(query)

    print('\n' + '='*80)
    print('=== Renegade Products in Neo4j ===')
    print('='*80 + '\n')

    if not result.records:
        print('❌ No Renegade products found in database!\n')
    else:
        for i, record in enumerate(result.records, 1):
            print(f'{i}. GIN: {record["p.gin"]}')
            print(f'   Name: {record["p.item_name"]}')
            desc = record["p.description_catalogue"]
            if desc:
                print(f'   Description: {desc[:300]}...' if len(desc) > 300 else f'   Description: {desc}')
            else:
                print('   Description: None')
            print('-' * 80)

    # Now query for products with ≤300A current rating
    print('\n' + '='*80)
    print('=== PowerSource Products with ≤300A Current Rating ===')
    print('='*80 + '\n')

    query_300a = '''
    MATCH (p:PowerSource)
    WHERE p.description_catalogue CONTAINS '300' OR p.description_catalogue CONTAINS '300A'
       OR p.description_catalogue CONTAINS 'A' AND p.description_catalogue CONTAINS '300'
    RETURN p.gin, p.item_name, p.description_catalogue
    ORDER BY p.item_name
    LIMIT 20
    '''

    result_300a = await search_service.driver.execute_query(query_300a)

    for i, record in enumerate(result_300a.records, 1):
        print(f'{i}. GIN: {record["p.gin"]}')
        print(f'   Name: {record["p.item_name"]}')
        desc = record["p.description_catalogue"]
        if desc:
            # Highlight 300A mentions
            desc_short = desc[:400] if len(desc) > 400 else desc
            print(f'   Description: {desc_short}')
        print('-' * 80)

    await search_service.close()

if __name__ == '__main__':
    asyncio.run(check_renegade())
