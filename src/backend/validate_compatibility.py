#!/usr/bin/env python3
"""
Compatibility Validation Script

Validates compatibility checks for each state:
1. Shows dependencies from component_types.json
2. Executes search with sample data
3. Shows actual Cypher/Lucene query with parameters
4. Shows results

Usage:
    python validate_compatibility.py
"""

import asyncio
import json
import logging
from typing import Dict, Any
from pathlib import Path

# Add app to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from app.services.config.configuration_service import ConfigurationService
from app.services.search.components.component_service import ComponentSearchService
from app.services.search.components.query_builder import Neo4jQueryBuilder
from app.models.conversation import ResponseJSON, SelectedProduct
from neo4j import AsyncGraphDatabase

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Load environment
from dotenv import load_dotenv
import os
load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


class QueryLogger:
    """Logs queries before execution"""

    def __init__(self):
        self.last_query = None
        self.last_params = None

    def log_query(self, query: str, params: Dict[str, Any]):
        """Store query and params"""
        self.last_query = query
        self.last_params = params

        logger.info("\n" + "=" * 100)
        logger.info("🔍 CYPHER QUERY:")
        logger.info("=" * 100)
        logger.info(query)
        logger.info("\n" + "=" * 100)
        logger.info("📊 PARAMETERS:")
        logger.info("=" * 100)
        logger.info(json.dumps(params, indent=2))
        logger.info("=" * 100 + "\n")


async def validate_state(
    component_type: str,
    component_service: ComponentSearchService,
    config_service: ConfigurationService,
    selected_components: ResponseJSON,
    master_parameters: Dict[str, Any]
):
    """Validate compatibility for a single state"""

    logger.info("\n" + "🔷" * 50)
    logger.info(f"STATE: {component_type}")
    logger.info("🔷" * 100)

    # 1. Show component configuration
    comp_config = config_service.get_component_type(component_type)
    if not comp_config:
        logger.warning(f"❌ Component type not found: {component_type}")
        return

    logger.info("\n📋 COMPONENT CONFIGURATION:")
    logger.info(f"  Category: {comp_config.get('category')}")
    logger.info(f"  Neo4j Label: {comp_config.get('neo4j_label')}")
    logger.info(f"  Requires Compatibility: {comp_config.get('requires_compatibility', False)}")
    logger.info(f"  Dependencies: {comp_config.get('dependencies', [])}")
    logger.info(f"  Lucene Enabled: {comp_config.get('lucene_enabled', False)}")

    # 2. Show selected components
    logger.info("\n🛒 SELECTED COMPONENTS:")
    for field_name in ["PowerSource", "Feeder", "Cooler", "Interconnector", "Torch"]:
        value = getattr(selected_components, field_name, None)
        if value:
            logger.info(f"  {field_name}: {value.name} (GIN: {value.gin})")

    # Show selected accessories
    for field_name in ["FeederAccessories", "RemoteAccessories", "PowerSourceAccessories"]:
        accessories = getattr(selected_components, field_name, [])
        if accessories and len(accessories) > 0:
            logger.info(f"  {field_name}: {len(accessories)} selected")
            for acc in accessories:
                logger.info(f"    - {acc.name} (GIN: {acc.gin})")

    # 3. Check dependencies
    satisfied, missing_deps, parent_info = config_service.check_dependencies_satisfied(
        component_type, selected_components
    )

    logger.info("\n🔗 DEPENDENCY CHECK:")
    logger.info(f"  Satisfied: {satisfied}")
    if not satisfied:
        logger.info(f"  Missing Dependencies: {missing_deps}")
    if parent_info:
        logger.info(f"  Parent Products:")
        for gin, name in parent_info.items():
            logger.info(f"    - {name} (GIN: {gin})")

    # 4. Execute search and show query
    try:
        search_results = await component_service.search(
            component_type=component_type,
            master_parameters=master_parameters,
            selected_components=selected_components,
            limit=5
        )

        logger.info("\n✅ SEARCH RESULTS:")
        logger.info(f"  Total Count: {search_results.total_count}")
        logger.info(f"  Has More: {search_results.has_more}")
        logger.info(f"  Compatibility Validated: {search_results.compatibility_validated}")

        if search_results.products:
            logger.info(f"\n  Products Found ({len(search_results.products)}):")
            for idx, product in enumerate(search_results.products, 1):
                logger.info(f"    {idx}. {product.name} (GIN: {product.gin})")
                logger.info(f"       Category: {product.category}")
        else:
            logger.info("  ⚠️  No products found")

        logger.info(f"\n  Filters Applied:")
        for key, value in search_results.filters_applied.items():
            logger.info(f"    {key}: {value}")

    except Exception as e:
        logger.error(f"❌ Search failed: {e}", exc_info=True)


async def main():
    """Main validation"""

    logger.info("\n" + "🚀" * 50)
    logger.info("COMPATIBILITY VALIDATION SCRIPT")
    logger.info("🚀" * 100 + "\n")

    # Initialize services
    config_service = ConfigurationService()

    # Initialize Neo4j
    driver = AsyncGraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )

    component_service = ComponentSearchService(driver)

    # Create sample selected components (typical S1→SN flow)
    selected_components = ResponseJSON(
        PowerSource=SelectedProduct(
            gin="0446200880",
            name="Aristo 500ix",
            category="Power Source"
        ),
        Feeder=SelectedProduct(
            gin="0460520880",
            name="RobustFeed U6",
            category="Feeder"
        ),
        Cooler=None,
        Interconnector=None,
        Torch=None,
        FeederAccessories=[
            SelectedProduct(
                gin="0558011712",
                name="RobustFeed Drive Roll Kit",
                category="Accessory"
            )
        ],
        RemoteAccessories=[],
        PowerSourceAccessories=[],
        FeederConditionalAccessories=[],
        RemoteConditionalAccessories=[],
        InterconnectorAccessories=[],
        ConnectivityAccessories=[]
    )

    # Sample master parameters
    master_parameters = {
        "power_source": {
            "product_name": "Aristo 500ix",
            "process": "MIG (GMAW)",
            "current_output": "500 A"
        },
        "feeder": {
            "product_name": "RobustFeed U6",
            "cooling_type": "Water-cooled"
        },
        "cooler": {},
        "interconnector": {},
        "torch": {},
        "feeder_accessories": {},
        "feeder_conditional_accessories": {},
        "remote_accessories": {},
        "remote_conditional_accessories": {}
    }

    # Get all component types
    component_types_config = config_service.get_component_types()
    component_types = component_types_config.get("component_types", {})

    # Test each state
    states_to_test = [
        "power_source",          # S1 - No compatibility needed (first component)
        "feeder",                # S2 - Compatible with PowerSource
        "cooler",                # S3 - Compatible with PowerSource
        "interconnector",        # S4 - Compatible with PowerSource, Feeder, Cooler
        "torch",                 # S5 - Compatible with Feeder
        "feeder_accessories",    # S6 - Multi-select, compatible with Feeder
        "feeder_conditional_accessories",  # Depends on feeder_accessories
        "remote_accessories",    # Multi-select
        "remote_conditional_accessories",  # Depends on remote_accessories
    ]

    for component_type in states_to_test:
        if component_type in component_types:
            await validate_state(
                component_type,
                component_service,
                config_service,
                selected_components,
                master_parameters
            )
        else:
            logger.warning(f"⚠️  Component type not found in config: {component_type}")

    # Close Neo4j driver
    await driver.close()

    logger.info("\n" + "✅" * 50)
    logger.info("VALIDATION COMPLETE")
    logger.info("✅" * 100 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
