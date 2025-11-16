"""
Debug script to trace Remote search flow
"""
import asyncio
import logging
from app.models.conversation import ResponseJSON, SelectedProduct
from app.services.search.orchestrator import SearchOrchestrator
from app.services.search.strategies.cypher_strategy import CypherSearchStrategy
from app.services.neo4j.driver import get_neo4j_driver
from app.services.search.consolidator import ResultConsolidator

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] %(name)s - %(message)s'
)

async def test_remote_search():
    print("="*80)
    print("REMOTE SEARCH DEBUG TEST")
    print("="*80)

    # Set up search infrastructure
    driver = await get_neo4j_driver()
    cypher_strategy = CypherSearchStrategy(driver, {"enabled": True})
    consolidator = ResultConsolidator({})
    search_orchestrator = SearchOrchestrator(
        strategies=[cypher_strategy],
        consolidator=consolidator,
        config={"execution_mode": "parallel", "fallback_on_error": True}
    )

    # Create selected components (PowerSource + Feeder)
    response_json = ResponseJSON()
    response_json.PowerSource = SelectedProduct(
        gin="0465350883",
        name="Aristo U5000i",
        category="PowerSource"
    )
    response_json.Feeder = SelectedProduct(
        gin="0445800881",
        name="MXF 65",
        category="Feeder"
    )

    print("\n1. SELECTED COMPONENTS:")
    print(f"   PowerSource: {response_json.PowerSource}")
    print(f"   Feeder: {response_json.Feeder}")

    # Call search_orchestrator.search() for Remote
    print("\n2. CALLING SEARCH ORCHESTRATOR:")
    print(f"   component_type: remote")
    print(f"   selected_components type: {type(response_json)}")
    print(f"   selected_components: {response_json}")

    results = await search_orchestrator.search(
        component_type="remote",
        user_message="",
        master_parameters={},
        selected_components=response_json,  # Pass ResponseJSON object
        limit=10,
        offset=0
    )

    print("\n3. SEARCH RESULTS:")
    print(f"   Total count: {results.get('total_count')}")
    print(f"   Products found: {len(results.get('products', []))}")
    print(f"   Compatibility validated: {results.get('compatibility_validated')}")

    if results.get('products'):
        print("\n4. PRODUCTS:")
        for i, product in enumerate(results['products'], 1):
            print(f"   {i}. {product.get('name')} (GIN: {product.get('gin')})")
    else:
        print("\n4. ❌ NO PRODUCTS FOUND!")
        print(f"   Zero results message: {results.get('zero_results_message')}")
        if 'metadata' in results:
            print(f"   Metadata: {results['metadata']}")

    await driver.close()
    print("\n" + "="*80)

if __name__ == "__main__":
    asyncio.run(test_remote_search())
