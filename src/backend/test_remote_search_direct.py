"""
Direct test of Remote search with ComponentSearchService.

Tests the query_builder.py fix for invalid Cypher syntax (WHERE before MATCH clauses).

User's Test Data:
- PowerSource: Warrior 500i CC/CV 380 - 415V (GIN: 0465350883)
- Feeder: Robust Feed Pro Water Cooled (GIN: 0445800881)
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add src/backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.models.conversation import ResponseJSON, SelectedProduct
from app.services.search.components.component_service import ComponentSearchService
from app.services.config.configuration_service import ConfigurationService

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_remote_search_direct():
    """
    Test Remote search with PowerSource and Feeder GINs to verify Cypher query fix.
    """
    print("=" * 80)
    print("TESTING REMOTE SEARCH - CYPHER QUERY FIX")
    print("=" * 80)
    print()

    # Initialize services
    config_service = ConfigurationService()
    component_service = ComponentSearchService(config_service)

    # Create ResponseJSON with selected PowerSource and Feeder
    response_json = ResponseJSON()
    response_json.PowerSource = SelectedProduct(
        gin="0465350883",
        name="Warrior 500i CC/CV 380 - 415V",
        category="PowerSource"
    )
    response_json.Feeder = SelectedProduct(
        gin="0445800881",
        name="Robust Feed Pro Water Cooled",
        category="Feeder"
    )

    print("📋 SELECTED COMPONENTS:")
    print(f"   PowerSource: {response_json.PowerSource.name} (GIN: {response_json.PowerSource.gin})")
    print(f"   Feeder: {response_json.Feeder.name} (GIN: {response_json.Feeder.gin})")
    print()

    # Search for Remote products
    print("=" * 80)
    print("SEARCHING FOR REMOTE PRODUCTS")
    print("=" * 80)

    results = await component_service.search(
        component_type="remote",
        master_parameters={},
        selected_components=response_json.model_dump(),
        limit=10,
        offset=0
    )

    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"Total products found: {results.get('total_count', 0)}")
    print()

    products = results.get('products', [])
    if products:
        print("✅ SUCCESS! Remote search returned products:")
        for i, product in enumerate(products, 1):
            print(f"   {i}. {product.get('name')} (GIN: {product.get('gin')})")
        print()
        if len(products) >= 4:
            print(f"✅ EXPECTED: Found {len(products)} products (expected ≥4)")
        else:
            print(f"⚠️  WARNING: Found {len(products)} products (expected ≥4)")
    else:
        print("❌ FAILED: Remote search returned 0 products")
        print("   The Cypher query fix did not work")

    print()
    print("=" * 80)
    print("CHECK SERVER LOGS FOR CYPHER QUERY DETAILS:")
    print("   grep '🔍 EXECUTING NEO4J CYPHER QUERY' server.log | tail -20")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_remote_search_direct())
