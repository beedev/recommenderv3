"""Test the 'max 300A' query to verify operator filtering"""
import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from app.services.intent.parameter_extractor import ParameterExtractor
from app.services.neo4j.product_search import Neo4jProductSearch
from app.services.config.configuration_service import ConfigurationService

load_dotenv()

async def test_max_300a():
    """Test query: I am satisfied with a maximum output of 300 Amps"""

    # Initialize services
    config_service = ConfigurationService()
    openai_api_key = os.getenv('OPENAI_API_KEY')
    param_extractor = ParameterExtractor(config_service=config_service, openai_api_key=openai_api_key)

    uri = os.getenv('NEO4J_URI')
    username = os.getenv('NEO4J_USERNAME')
    password = os.getenv('NEO4J_PASSWORD')

    search_service = Neo4jProductSearch(uri, username, password)

    print('\n' + '='*80)
    print('=== Testing "max 300A" Query ===')
    print('='*80 + '\n')

    # Step 1: Extract parameters
    query = "I am satisfied with a maximum output of 300 Amps"
    print(f'Query: "{query}"')
    print('-' * 80)

    result = await param_extractor.extract_parameters(
        user_message=query,
        current_state="power_source_selection",
        master_parameters={}
    )

    print('\n📋 EXTRACTED PARAMETERS:')
    print(f'{result}\n')

    # Check if operator was extracted
    power_source_params = result.get('power_source', {})
    if 'current_output' in power_source_params or 'current_rating' in power_source_params:
        param_key = 'current_output' if 'current_output' in power_source_params else 'current_rating'
        extracted = power_source_params[param_key]
        print(f'✅ Extracted constraint: {param_key} = {extracted}')

        if isinstance(extracted, dict):
            operator = extracted.get('operator', 'unknown')
            value = extracted.get('value', 'unknown')
            print(f'   Operator: {operator} (lte = ≤)')
            print(f'   Value: {value}A')
            print(f'   Expected behavior: Only show products with ≤300A current output\n')
        else:
            print(f'   ❌ String format (backward compatibility): {extracted}')
            print(f'   Will use tolerance matching instead of operator\n')
    else:
        print('❌ No current output constraint extracted!\n')

    # Step 2: Search products
    print('=' * 80)
    print('=== Searching Products ===')
    print('=' * 80 + '\n')

    products = await search_service.search_power_source_lucene(
        user_message=query,
        master_parameters=result,
        limit=10
    )

    if not products.products:
        print('❌ No products returned!\n')
    else:
        print(f'✅ Found {len(products.products)} products:\n')

        for i, product in enumerate(products.products, 1):
            # Extract current rating from description
            desc = product.description or ''
            current_rating = None

            # Try to find current rating
            if 'A' in desc:
                import re
                # Look for patterns like "500A", "300 A", "500 A at"
                matches = re.findall(r'(\d+)\s*A(?:\s|$|,|\.)', desc)
                if matches:
                    current_rating = int(matches[0])

            print(f'{i}. {product.name} (GIN: {product.gin})')
            if current_rating:
                # Check if it passes the operator constraint
                passes_constraint = current_rating <= 300
                status = '✅ PASS' if passes_constraint else '❌ FAIL'
                print(f'   Current: {current_rating}A | Constraint: ≤300A | {status}')
            else:
                print(f'   Current: Unknown')
            print(f'   Description: {desc[:100]}...\n')

    await search_service.close()

if __name__ == '__main__':
    asyncio.run(test_max_300a())
