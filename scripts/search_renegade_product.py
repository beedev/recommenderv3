"""Search for Renegade products under Product label"""
import asyncio
import os
from dotenv import load_dotenv
from app.services.neo4j.product_search import Neo4jProductSearch

load_dotenv()

async def search_renegade():
    """Query Neo4j for Renegade products under Product label"""

    # Get credentials from env
    uri = os.getenv('NEO4J_URI')
    username = os.getenv('NEO4J_USERNAME')
    password = os.getenv('NEO4J_PASSWORD')

    search_service = Neo4jProductSearch(uri, username, password)

    # Search for Renegade under Product label
    query = '''
    MATCH (p:Product)
    WHERE p.item_name CONTAINS 'Renegade'
       OR toLower(p.item_name) CONTAINS 'renegade'
       OR p.description_catalogue CONTAINS 'Renegade'
       OR toLower(p.description_catalogue) CONTAINS 'renegade'
    RETURN p.gin, p.item_name, p.description_catalogue, p.category
    LIMIT 10
    '''

    result = await search_service.driver.execute_query(query)

    print('\n' + '='*80)
    print('=== Renegade Products Under "Product" Label ===')
    print('='*80 + '\n')

    if not result.records:
        print('❌ No Renegade products found in Product nodes!\n')

        # Also search for products with ≤300A current rating
        print('='*80)
        print('=== Products with ≤300A Current Rating ===')
        print('='*80 + '\n')

        query_300a = '''
        MATCH (p:Product)
        WHERE p.category = 'Powersource'
           OR p.category = 'PowerSource'
           OR p.category = 'Power Source'
        WITH p
        WHERE p.description_catalogue CONTAINS '300A'
           OR p.description_catalogue CONTAINS '300 A'
           OR p.description_catalogue CONTAINS 'A 300'
        RETURN p.gin, p.item_name, p.description_catalogue, p.category
        LIMIT 10
        '''

        result_300a = await search_service.driver.execute_query(query_300a)

        if result_300a.records:
            for i, record in enumerate(result_300a.records, 1):
                print(f'{i}. GIN: {record["p.gin"]}')
                print(f'   Name: {record["p.item_name"]}')
                print(f'   Category: {record.get("p.category", "N/A")}')
                desc = record.get("p.description_catalogue")
                if desc:
                    print(f'   Description: {desc[:300]}...')
                print('-' * 80)
        else:
            print('  No products found with 300A in description')
    else:
        for i, record in enumerate(result.records, 1):
            print(f'{i}. GIN: {record["p.gin"]}')
            print(f'   Name: {record["p.item_name"]}')
            print(f'   Category: {record.get("p.category", "N/A")}')
            desc = record.get("p.description_catalogue")
            if desc:
                print(f'   Description: {desc[:300]}...')
            print('-' * 80)

    await search_service.close()

if __name__ == '__main__':
    asyncio.run(search_renegade())
