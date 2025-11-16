"""
STAGE 4 Remote Search Debug Test

Tests the complete flow with user's actual GINs to identify where PowerSource/Feeder are lost.

User's Test Data:
- PowerSource: Warrior 500i CC/CV 380 - 415V (GIN: 0465350883)
- Feeder: Robust Feed Pro Water Cooled (GIN: 0445800881)
- Cooler: Cool 2 (GIN: 0465427880)

Expected Flow:
1. S1: Select PowerSource (0465350883)
2. S2: Select Feeder (0445800881)
3. S3: Select Cooler (0465427880)
4. S4: Select FeederAccessories (trigger STAGE 4 auto-advance)
5. S5: Remote search should return 4 products

Debug Focus:
- Track ResponseJSON.PowerSource and ResponseJSON.Feeder through STAGE 4 flow
- Identify exact point where GINs are lost
- Capture debug logs showing state transitions
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src/backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.models.conversation import ResponseJSON, SelectedProduct, ConversationState, ConfiguratorState
from app.services.orchestrator.state_orchestrator import StateByStateOrchestrator
from app.services.search.orchestrator import SearchOrchestrator
from app.services.search.strategies.cypher_strategy import CypherSearchStrategy
from app.database.database import get_neo4j_driver
from app.services.search.consolidator import ResultConsolidator
from app.services.config.config_service import ConfigService
from app.services.processors.base import ProcessorRegistry

# Configure logging to show DEBUG level
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('stage4_remote_debug.log')
    ]
)

# Reduce noise from other loggers
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def test_stage4_remote_flow():
    """
    Test complete flow with user's actual GINs to trigger STAGE 4 and Remote search.
    """
    print("=" * 100)
    print("STAGE 4 REMOTE SEARCH DEBUG TEST")
    print("=" * 100)
    print()

    # Initialize services
    driver = await get_neo4j_driver()
    cypher_strategy = CypherSearchStrategy(driver, {"enabled": True})
    consolidator = ResultConsolidator({})
    search_orchestrator = SearchOrchestrator(
        strategies=[cypher_strategy],
        consolidator=consolidator,
        config={"execution_mode": "parallel", "fallback_on_error": True}
    )
    config_service = ConfigService()
    processor_registry = ProcessorRegistry(config_service, search_orchestrator)

    # Initialize State Orchestrator
    state_orchestrator = StateByStateOrchestrator(
        search_orchestrator=search_orchestrator,
        config_service=config_service,
        processor_registry=processor_registry
    )

    # Create conversation state
    conversation_state = ConversationState()
    conversation_state.session_id = "test-stage4-remote"
    conversation_state.current_state = ConfiguratorState.POWER_SOURCE_SELECTION

    print("📋 TEST DATA:")
    print(f"   PowerSource: Warrior 500i CC/CV 380 - 415V (GIN: 0465350883)")
    print(f"   Feeder: Robust Feed Pro Water Cooled (GIN: 0445800881)")
    print(f"   Cooler: Cool 2 (GIN: 0465427880)")
    print()

    # ===== STEP 1: Select PowerSource =====
    print("=" * 100)
    print("STEP 1: SELECT POWERSOURCE (0465350883)")
    print("=" * 100)

    response_step1 = await state_orchestrator.select_product(
        user_message="",
        gin="0465350883",
        product_data={
            "gin": "0465350883",
            "name": "Warrior 500i CC/CV 380 - 415V",
            "category": "PowerSource"
        },
        conversation_state=conversation_state,
        language="en"
    )

    print(f"✅ PowerSource selected: {response_step1['response_json'].PowerSource}")
    print(f"   Next state: {response_step1['current_state']}")
    print()

    # ===== STEP 2: Select Feeder =====
    print("=" * 100)
    print("STEP 2: SELECT FEEDER (0445800881)")
    print("=" * 100)

    response_step2 = await state_orchestrator.select_product(
        user_message="",
        gin="0445800881",
        product_data={
            "gin": "0445800881",
            "name": "Robust Feed Pro Water Cooled",
            "category": "Feeder"
        },
        conversation_state=conversation_state,
        language="en"
    )

    print(f"✅ Feeder selected: {response_step2['response_json'].Feeder}")
    print(f"   Next state: {response_step2['current_state']}")
    print()

    # ===== STEP 3: Select Cooler =====
    print("=" * 100)
    print("STEP 3: SELECT COOLER (0465427880)")
    print("=" * 100)

    response_step3 = await state_orchestrator.select_product(
        user_message="",
        gin="0465427880",
        product_data={
            "gin": "0465427880",
            "name": "Cool 2",
            "category": "Cooler"
        },
        conversation_state=conversation_state,
        language="en"
    )

    print(f"✅ Cooler selected: {response_step3['response_json'].Cooler}")
    print(f"   Next state: {response_step3['current_state']}")
    print()

    # ===== STEP 4: Search and Select FeederAccessories (to trigger STAGE 4) =====
    print("=" * 100)
    print("STEP 4: SEARCH FEEDER ACCESSORIES")
    print("=" * 100)

    # Search for FeederAccessories
    feeder_acc_results = await search_orchestrator.search(
        component_type="feeder_accessories",
        user_message="",
        master_parameters={},
        selected_components=conversation_state.response_json,
        limit=10,
        offset=0
    )

    print(f"   Found {feeder_acc_results.get('total_count')} FeederAccessories")

    if feeder_acc_results.get('products'):
        # Select first FeederAccessory to trigger STAGE 4 auto-advance
        first_acc = feeder_acc_results['products'][0]
        print(f"   Selecting: {first_acc.get('name')} (GIN: {first_acc.get('gin')})")
        print()

        print("=" * 100)
        print("STEP 5: SELECT FEEDER ACCESSORY (TRIGGER STAGE 4)")
        print("=" * 100)

        response_step4 = await state_orchestrator.select_product(
            user_message="",
            gin=first_acc.get('gin'),
            product_data=first_acc,
            conversation_state=conversation_state,
            language="en"
        )

        print(f"✅ FeederAccessory selected: {first_acc.get('name')}")
        print(f"   Current state: {response_step4['current_state']}")
        print(f"   Products returned: {len(response_step4.get('products', []))}")
        print()

        # ===== STEP 5: Check if Remote search happened =====
        print("=" * 100)
        print("STEP 6: CHECK REMOTE SEARCH RESULTS")
        print("=" * 100)

        if response_step4['current_state'] == 'remote_selection':
            remote_products = response_step4.get('products', [])
            print(f"✅ Advanced to Remote selection")
            print(f"   Products found: {len(remote_products)}")

            if len(remote_products) == 0:
                print(f"   ❌ ERROR: Zero Remote products (expected 4)")
                print(f"   ResponseJSON.PowerSource: {conversation_state.response_json.PowerSource}")
                print(f"   ResponseJSON.Feeder: {conversation_state.response_json.Feeder}")
                print()
                print(f"   🔍 CHECK DEBUG LOGS FOR STAGE 4 FLOW:")
                print(f"      - Look for '🔍 STAGE 4 CHECK'")
                print(f"      - Look for '🔍 STAGE 4 TRIGGERED'")
                print(f"      - Look for '🔍 CALLING NEXT STATE SEARCH'")
                print(f"      - Look for '🔍 DEPENDENCY FOUND/MISSING'")
            else:
                print(f"   ✅ SUCCESS: Found {len(remote_products)} Remote products")
                for i, product in enumerate(remote_products[:5], 1):
                    print(f"      {i}. {product.get('name')} (GIN: {product.get('gin')})")
        else:
            print(f"   ❌ ERROR: Did not advance to Remote selection")
            print(f"      Current state: {response_step4['current_state']}")
            print(f"      ResponseJSON.PowerSource: {conversation_state.response_json.PowerSource}")
            print(f"      ResponseJSON.Feeder: {conversation_state.response_json.Feeder}")

    else:
        print(f"   ❌ ERROR: No FeederAccessories found to trigger STAGE 4")
        print(f"      Cannot proceed with test")

    print()
    print("=" * 100)
    print("TEST COMPLETE - Check stage4_remote_debug.log for detailed debug logs")
    print("=" * 100)

    await driver.close()


if __name__ == "__main__":
    asyncio.run(test_stage4_remote_flow())
