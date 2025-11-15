"""Check what node labels exist in Neo4j database"""
import asyncio
import os
from dotenv import load_dotenv
from app.services.neo4j.product_search import Neo4jProductSearch

load_dotenv()

async def check_labels():
    """Query Neo4j for all node labels"""

    # Get credentials from env
    uri = os.getenv('NEO4J_URI')
    username = os.getenv('NEO4J_USERNAME')
    password = os.getenv('NEO4J_PASSWORD')

    search_service = Neo4jProductSearch(uri, username, password)

    # Query for all labels
    query = '''
    CALL db.labels() YIELD label
    RETURN label
    ORDER BY label
    '''

    result = await search_service.driver.execute_query(query)

    print('\n' + '='*80)
    print('=== All Node Labels in Database ===')
    print('='*80 + '\n')

    for record in result.records:
        label = record["label"]

        # Count nodes with this label
        count_query = f'MATCH (n:{label}) RETURN count(n) as count'
        count_result = await search_service.driver.execute_query(count_query)
        count = count_result.records[0]["count"]

        print(f'  • {label}: {count} nodes')

    # Also try searching for products with different case variations
    print('\n' + '='*80)
    print('=== Searching for Product Nodes (Case Variations) ===')
    print('='*80 + '\n')

    variations = ['PowerSource', 'Powersource', 'powersource', 'POWERSOURCE', 'Product']

    for variation in variations:
        try:
            query = f'MATCH (n:{variation}) RETURN count(n) as count'
            result = await search_service.driver.execute_query(query)
            count = result.records[0]["count"]
            print(f'  {variation}: {count} nodes')
        except Exception as e:
            print(f'  {variation}: Error - {str(e)[:50]}')

    # Try to find Warrior 400i specifically
    print('\n' + '='*80)
    print('=== Searching for "Warrior 400i" Product ===')
    print('='*80 + '\n')

    # Search across all labels
    all_labels_query = '''
    CALL db.labels() YIELD label
    RETURN label
    '''
    all_labels = await search_service.driver.execute_query(all_labels_query)

    found = False
    for record in all_labels.records:
        label = record["label"]

        # Search for Warrior in this label
        warrior_query = f'''
        MATCH (n:{label})
        WHERE n.item_name CONTAINS 'Warrior' OR n.description_catalogue CONTAINS 'Warrior'
        RETURN n.gin, n.item_name, labels(n) as labels
        LIMIT 5
        '''

        try:
            warrior_result = await search_service.driver.execute_query(warrior_query)
            if warrior_result.records:
                found = True
                print(f'\nFound Warrior products under label: {label}')
                for rec in warrior_result.records:
                    print(f'  GIN: {rec["n.gin"]}')
                    print(f'  Name: {rec["n.item_name"]}')
                    print(f'  Labels: {rec["labels"]}')
                    print('-' * 60)
        except:
            pass

    if not found:
        print('  ❌ No Warrior products found in any label!')

    await search_service.close()

if __name__ == '__main__':
    asyncio.run(check_labels())
