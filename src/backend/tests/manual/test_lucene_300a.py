"""Test Lucene search for 300A products"""
import asyncio
import os
from dotenv import load_dotenv
from app.services.neo4j.product_search import Neo4jProductSearch

load_dotenv()

async def test_lucene_search():
    """Test Lucene full-text search for 300A products"""

    # Get credentials from env
    uri = os.getenv('NEO4J_URI')
    username = os.getenv('NEO4J_USERNAME')
    password = os.getenv('NEO4J_PASSWORD')

    search_service = Neo4jProductSearch(uri, username, password)

    print('\n' + '='*80)
    print('=== Testing Lucene Full-Text Search for "300A" ===')
    print('='*80 + '\n')

    # Test 1: Basic Lucene search (what the API uses)
    lucene_query = '''
    CALL db.index.fulltext.queryNodes("productIndex", "300A")
    YIELD node, score
    WHERE node.category = 'Powersource'
    RETURN node.gin, node.item_name, node.description_catalogue, score
    ORDER BY score DESC
    LIMIT 20
    '''

    print('Query: CALL db.index.fulltext.queryNodes("productIndex", "300A")')
    print('Filter: category = Powersource')
    print('-' * 80)

    result = await search_service.driver.execute_query(lucene_query)

    if not result.records:
        print('❌ No results from Lucene search!\n')
    else:
        print(f'✅ Found {len(result.records)} products\n')
        for i, record in enumerate(result.records, 1):
            gin = record["node.gin"]
            name = record["node.item_name"]
            score = record["score"]
            desc = record.get("node.description_catalogue", "")

            # Highlight if it's Warrior or Renegade
            marker = ""
            if "Warrior" in name:
                marker = "🔵 WARRIOR"
            elif "Renegade" in name:
                marker = "🟢 RENEGADE"

            print(f'{i}. {marker}')
            print(f'   GIN: {gin}')
            print(f'   Name: {name}')
            print(f'   Lucene Score: {score:.4f}')
            if desc and '300' in desc:
                # Find lines with 300
                lines_with_300 = [line for line in desc.split('\n') if '300' in line or 'A' in line]
                if lines_with_300:
                    print(f'   300A mention: {lines_with_300[0][:120]}...')
            print('-' * 80)

    # Test 2: Try broader Lucene search
    print('\n' + '='*80)
    print('=== Testing Broader Lucene Search (300 OR Powersource) ===')
    print('='*80 + '\n')

    broader_query = '''
    CALL db.index.fulltext.queryNodes("productIndex", "300 OR Powersource")
    YIELD node, score
    WHERE node.category = 'Powersource'
    RETURN node.gin, node.item_name, score
    ORDER BY score DESC
    LIMIT 10
    '''

    result2 = await search_service.driver.execute_query(broader_query)

    for i, record in enumerate(result2.records, 1):
        gin = record["node.gin"]
        name = record["node.item_name"]
        score = record["score"]

        marker = ""
        if "Warrior" in name:
            marker = "🔵 WARRIOR"
        elif "Renegade" in name:
            marker = "🟢 RENEGADE"

        print(f'{i}. {marker} GIN: {gin}, Name: {name}, Score: {score:.4f}')

    # Test 3: Check if Renegade ES300i is in the Lucene index at all
    print('\n' + '='*80)
    print('=== Checking if Renegade ES300i is indexed ===')
    print('='*80 + '\n')

    renegade_query = '''
    CALL db.index.fulltext.queryNodes("productIndex", "Renegade")
    YIELD node, score
    WHERE node.gin = '0445100880'
    RETURN node.gin, node.item_name, node.category, score
    '''

    result3 = await search_service.driver.execute_query(renegade_query)

    if result3.records:
        print('✅ Renegade ES300i IS in the Lucene index!')
        for record in result3.records:
            print(f'   GIN: {record["node.gin"]}')
            print(f'   Name: {record["node.item_name"]}')
            print(f'   Category: {record["node.category"]}')
            print(f'   Score: {record["score"]:.4f}')
    else:
        print('❌ Renegade ES300i NOT in Lucene index!')

    await search_service.close()

if __name__ == '__main__':
    asyncio.run(test_lucene_search())
