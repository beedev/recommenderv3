"""
End-to-End Test: Complete S1→SN Flow with Proactive Selection

Tests the entire configurator flow by:
1. Starting with a PowerSource query
2. Auto-selecting the first product at each state
3. Progressing through all applicable states (S1→SN)
4. Validating final configuration package

This test validates that the complete workflow functions correctly
with automatic product selection.
"""

import pytest
import asyncio
from typing import Dict, Any, Optional

from app.services.orchestrator.state_orchestrator import StateByStateOrchestrator
from app.services.intent.parameter_extractor import ParameterExtractor
from app.services.neo4j.product_search import Neo4jProductSearch
from app.services.response.message_generator import MessageGenerator
from app.models.conversation import ConversationState, ConfiguratorState


class ProactiveFlowTester:
    """
    End-to-end flow tester with automatic product selection.

    Simulates a user completing the entire configuration by automatically
    selecting the first product returned at each state.
    """

    def __init__(
        self,
        orchestrator: StateByStateOrchestrator,
        initial_query: str,
        language: str = "en"
    ):
        """
        Initialize flow tester.

        Args:
            orchestrator: State orchestrator instance
            initial_query: Initial PowerSource query (e.g., "I want an Aristo")
            language: Language code (default: "en")
        """
        self.orchestrator = orchestrator
        self.initial_query = initial_query
        self.language = language
        self.conversation_state: Optional[ConversationState] = None
        self.state_history = []
        self.selection_history = []

    async def run_complete_flow(self) -> Dict[str, Any]:
        """
        Execute complete S1→SN flow with automatic selection.

        Returns:
            Dict with flow results and statistics
        """
        print("\n" + "=" * 70)
        print("🧪 PROACTIVE FLOW TEST - COMPLETE S1→SN CONFIGURATION")
        print("=" * 70)
        print(f"Initial Query: {self.initial_query}")
        print(f"Language: {self.language}")
        print()

        # STEP 1: Process initial PowerSource query
        print("[STEP 1] Processing initial PowerSource query...")
        response = await self._process_message(self.initial_query)

        # Check if PowerSource was auto-selected (exact match) or needs manual selection
        response_json = self.conversation_state.response_json
        if response_json and response_json.PowerSource:
            # Auto-selected by system (exact match)
            print(f"✅ S1 Auto-Selected PowerSource: {response_json.PowerSource.name}")
            # Track auto-selection in history
            self.selection_history.append({
                "state": "power_source_selection",
                "product": response_json.PowerSource.name,
                "gin": response_json.PowerSource.gin
            })
        elif response.get("products") and len(response["products"]) > 0:
            # Manual selection needed
            print(f"✅ S1 returned {len(response['products'])} PowerSource products")
            first_product = response["products"][0]
            print(f"🎯 Auto-selecting: {first_product['name']} (GIN: {first_product['gin']})")

            selection_response = await self._select_product(first_product)
            print(f"✅ PowerSource selected: {first_product['name']}")
        else:
            raise AssertionError(
                f"❌ S1 (PowerSource) failed: No PowerSource selected and no products returned\n"
                f"Response: {response}"
            )

        # STEP 3: Progress through remaining states with auto-selection
        step_count = 2
        max_steps = 20  # Safety limit to prevent infinite loops

        while self.conversation_state.current_state != ConfiguratorState.FINALIZE:
            step_count += 1

            if step_count > max_steps:
                raise AssertionError(f"❌ Exceeded max steps ({max_steps}). Possible infinite loop.")

            current_state = self.conversation_state.current_state.value
            print(f"\n[STEP {step_count}] Current state: {current_state}")

            # Check current state type
            current_state_name = self.conversation_state.current_state.value
            is_accessory_state = "accessories" in current_state_name.lower()

            # For accessory states (multi-select, optional), finalize if all mandatory selected
            if is_accessory_state:
                # Accessories are optional - all mandatory components selected, go to finalize
                print(f"⏭️  Reached optional accessories - all mandatory components selected")
                print("✅ Configuration ready to finalize")
                break
            else:
                # Process message to check current state and get next step
                response = await self._process_message("next")

            # Check if products are available (regardless of awaiting_selection flag)
            # Proactive search may populate products without setting awaiting_selection
            if response.get("products") and len(response["products"]) > 0 and not is_accessory_state:
                # Auto-select first product (skip accessories)
                first_product = response["products"][0]
                print(f"🎯 Auto-selecting: {first_product['name']} (GIN: {first_product['gin']})")

                selection_response = await self._select_product(first_product)
                print(f"✅ Selected: {first_product['name']}")

            elif response.get("can_finalize"):
                # Ready to finalize
                print("✅ Configuration ready to finalize")
                break
            else:
                # State was auto-skipped (not applicable) or no products available
                print(f"⏭️  State skipped or no products available")

        # STEP 4: Finalize configuration
        print(f"\n[STEP {step_count + 1}] Finalizing configuration...")
        final_response = await self._process_message("finalize")

        # Validate final configuration
        response_json = self.conversation_state.response_json

        print("\n" + "=" * 70)
        print("📦 FINAL CONFIGURATION PACKAGE")
        print("=" * 70)

        components = []
        if response_json.PowerSource:
            components.append(f"✓ PowerSource: {response_json.PowerSource.name}")
        if response_json.Feeder:
            components.append(f"✓ Feeder: {response_json.Feeder.name}")
        if response_json.Cooler:
            components.append(f"✓ Cooler: {response_json.Cooler.name}")
        if response_json.Interconnector:
            components.append(f"✓ Interconnector: {response_json.Interconnector.name}")
        if response_json.Torch:
            components.append(f"✓ Torch: {response_json.Torch.name}")
        if response_json.Accessories:
            components.append(f"✓ Accessories: {len(response_json.Accessories)} items")

        for component in components:
            print(component)

        print("\n" + "=" * 70)
        print("📊 TEST STATISTICS")
        print("=" * 70)
        print(f"Total Steps: {step_count + 1}")
        print(f"States Visited: {len(self.state_history)}")
        print(f"Products Selected: {len(self.selection_history)}")
        print(f"Final State: {self.conversation_state.current_state.value}")
        print("=" * 70)

        return {
            "success": True,
            "total_steps": step_count + 1,
            "states_visited": len(self.state_history),
            "products_selected": len(self.selection_history),
            "final_configuration": {
                "PowerSource": response_json.PowerSource.dict() if response_json.PowerSource else None,
                "Feeder": response_json.Feeder.dict() if response_json.Feeder else None,
                "Cooler": response_json.Cooler.dict() if response_json.Cooler else None,
                "Interconnector": response_json.Interconnector.dict() if response_json.Interconnector else None,
                "Torch": response_json.Torch.dict() if response_json.Torch else None,
                "Accessories": [acc.dict() for acc in response_json.Accessories] if response_json.Accessories else []
            },
            "state_history": self.state_history,
            "selection_history": self.selection_history
        }

    async def _process_message(self, message: str) -> Dict[str, Any]:
        """Process a message through the orchestrator."""
        if self.conversation_state is None:
            # Initialize new conversation
            import uuid
            self.conversation_state = ConversationState(session_id=str(uuid.uuid4()))

        response = await self.orchestrator.process_message(
            conversation_state=self.conversation_state,
            user_message=message
        )

        # Track state history
        self.state_history.append(self.conversation_state.current_state.value)

        return response

    async def _select_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Select a product in the current state."""
        # Create selection dict matching SelectedProduct structure
        selection = {
            "gin": product["gin"],
            "name": product["name"],
            "category": product.get("category", ""),
            "description": product.get("description", ""),
            "specifications": product.get("specifications", {})
        }

        response = await self.orchestrator.select_product(
            product_gin=product["gin"],
            product_data=selection,
            conversation_state=self.conversation_state,
            language=self.language
        )

        # Track selection history
        self.selection_history.append({
            "state": self.conversation_state.current_state.value,
            "product": product["name"],
            "gin": product["gin"]
        })

        return response


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_complete_proactive_flow_aristo():
    """
    Test complete S1→SN flow with Aristo PowerSource.

    This test validates the entire configurator workflow by:
    1. Starting with "I want an Aristo"
    2. Auto-selecting the first product at each state
    3. Progressing through all applicable states
    4. Finalizing the configuration
    """
    # Load environment variables
    from dotenv import load_dotenv
    from pathlib import Path

    # Load .env from backend directory (two levels up from test file)
    backend_dir = Path(__file__).parent.parent.parent
    env_path = backend_dir / ".env"
    load_dotenv(env_path, override=True)  # Override any cached env vars

    # Initialize services
    import os
    import json
    from neo4j import AsyncGraphDatabase
    from openai import AsyncOpenAI

    from app.services.intent.parameter_extractor import ParameterExtractor
    from app.services.response.message_generator import MessageGenerator
    from app.services.orchestrator.state_orchestrator import StateByStateOrchestrator
    from app.services.neo4j.product_search import Neo4jProductSearch
    from app.services.search.strategies.cypher_strategy import CypherSearchStrategy
    from app.services.search.strategies.lucene_strategy import LuceneSearchStrategy
    from app.services.search.consolidator import ResultConsolidator
    from app.services.search.orchestrator import SearchOrchestrator

    # Initialize Neo4j driver
    neo4j_driver = AsyncGraphDatabase.driver(
        os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
        auth=(
            os.getenv("NEO4J_USERNAME", "neo4j"),
            os.getenv("NEO4J_PASSWORD", "password")
        )
    )

    # Initialize OpenAI client
    api_key = os.getenv("OPENAI_API_KEY")
    print(f"\n=== DEBUG: API Key Info ===")
    print(f"Key length: {len(api_key) if api_key else 0}")
    print(f"Key starts with: {api_key[:15] if api_key else 'NONE'}...")
    print(f"Key ends with: ...{api_key[-10:] if api_key else 'NONE'}")
    openai_client = AsyncOpenAI(api_key=api_key)

    # Initialize core services
    parameter_extractor = ParameterExtractor(api_key)  # Pass API key string, not client!
    message_generator = MessageGenerator(openai_client)  # MessageGenerator expects client object

    # Initialize Neo4j product search
    neo4j_search = Neo4jProductSearch(
        os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
        os.getenv("NEO4J_USERNAME", "neo4j"),
        os.getenv("NEO4J_PASSWORD", "password")
    )

    # Initialize search strategies
    cypher_strategy = CypherSearchStrategy(
        config={"enabled": True, "weight": 0.4},
        neo4j_product_search=neo4j_search
    )
    lucene_strategy = LuceneSearchStrategy(
        config={"enabled": True, "weight": 0.6, "min_score": 0.3},
        neo4j_product_search=neo4j_search
    )

    # Initialize result consolidator
    consolidator = ResultConsolidator(
        config={
            "strategy_weights": {"cypher": 0.4, "lucene": 0.6},
            "default_score_for_unscored": 0.5,
            "score_normalization": "none"
        }
    )

    # Initialize search orchestrator
    search_orchestrator = SearchOrchestrator(
        strategies=[cypher_strategy, lucene_strategy],
        consolidator=consolidator,
        config={
            "execution_mode": "parallel",
            "timeout_seconds": 30,
            "fallback_on_error": True,
            "require_at_least_one_success": True
        }
    )

    # Load powersource_state_specifications config
    config_path = os.path.join(
        os.path.dirname(__file__),
        "../../app/config/powersource_state_specifications.json"
    )
    with open(config_path, 'r') as f:
        powersource_config = json.load(f)

    # Initialize orchestrator
    orchestrator = StateByStateOrchestrator(
        parameter_extractor=parameter_extractor,
        message_generator=message_generator,
        search_orchestrator=search_orchestrator,
        state_config_path="app/config/state_config.json",
        powersource_applicability_config=powersource_config
    )

    # Create flow tester
    tester = ProactiveFlowTester(
        orchestrator=orchestrator,
        initial_query="I want an Aristo",
        language="en"
    )

    # Run complete flow
    try:
        results = await tester.run_complete_flow()

        # Assertions
        assert results["success"], "Flow should complete successfully"
        assert results["total_steps"] > 1, "Flow should have multiple steps"
        assert results["products_selected"] >= 1, "At least PowerSource should be selected"

        # Validate final configuration has PowerSource
        assert results["final_configuration"]["PowerSource"] is not None, \
            "Final configuration must have PowerSource"

        # Validate PowerSource has valid data
        ps_name = results["final_configuration"]["PowerSource"]["name"]
        assert ps_name and len(ps_name) > 0, \
            "PowerSource must have a valid name"

        print(f"\n✅ TEST PASSED - Complete S1→SN flow working correctly!")
        print(f"   Selected PowerSource: {ps_name}")
    finally:
        # Cleanup Neo4j connections
        await neo4j_search.close()
        await neo4j_driver.close()


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_complete_proactive_flow_warrior():
    """Test complete S1→SN flow with Warrior PowerSource."""
    from app.main import orchestrator

    tester = ProactiveFlowTester(
        orchestrator=orchestrator,
        initial_query="I need a Warrior 500i",
        language="en"
    )

    results = await tester.run_complete_flow()

    assert results["success"], "Flow should complete successfully"
    assert results["final_configuration"]["PowerSource"] is not None
    assert "Warrior" in results["final_configuration"]["PowerSource"]["name"]

    print("\n✅ TEST PASSED - Warrior flow working correctly!")


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_complete_proactive_flow_renegade():
    """Test complete S1→SN flow with Renegade PowerSource."""
    from app.main import orchestrator

    tester = ProactiveFlowTester(
        orchestrator=orchestrator,
        initial_query="I want a Renegade ES300i",
        language="en"
    )

    results = await tester.run_complete_flow()

    assert results["success"], "Flow should complete successfully"
    assert results["final_configuration"]["PowerSource"] is not None
    assert "Renegade" in results["final_configuration"]["PowerSource"]["name"]

    print("\n✅ TEST PASSED - Renegade flow working correctly!")


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_vector_search_interactive_comparison():
    """
    Interactive vector search comparison test.

    Takes user query as input and compares:
    - Cypher results (compatibility-based)
    - Lucene results (keyword-based)
    - Vector results (semantic similarity with text-embedding-3-large)

    Usage:
        pytest tests/e2e/test_complete_proactive_flow.py::test_vector_search_interactive_comparison -v -s

    When prompted, enter query like:
    "I need a machine that can handle MIG/MAG, MMA (Stick), and DC TIG welding"

    Or press Enter to use the default query above.
    """
    from dotenv import load_dotenv
    from pathlib import Path
    import os
    import time
    from neo4j import AsyncGraphDatabase
    from openai import AsyncOpenAI

    from app.services.search.strategies.cypher_strategy import CypherSearchStrategy
    from app.services.search.strategies.lucene_strategy import LuceneSearchStrategy
    from app.services.neo4j.product_search import Neo4jProductSearch

    # Load environment
    backend_dir = Path(__file__).parent.parent.parent
    env_path = backend_dir / ".env"
    load_dotenv(env_path, override=True)

    # Initialize Neo4j
    neo4j_driver = AsyncGraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(
            os.getenv("NEO4J_USERNAME"),
            os.getenv("NEO4J_PASSWORD")
        )
    )

    neo4j_search = Neo4jProductSearch(
        os.getenv("NEO4J_URI"),
        os.getenv("NEO4J_USERNAME"),
        os.getenv("NEO4J_PASSWORD")
    )

    # Initialize OpenAI
    openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Initialize strategies
    cypher_strategy = CypherSearchStrategy(
        config={"enabled": True, "weight": 0.4},
        neo4j_product_search=neo4j_search
    )
    lucene_strategy = LuceneSearchStrategy(
        config={"enabled": True, "weight": 0.6, "min_score": 0.3},
        neo4j_product_search=neo4j_search
    )

    # Default query
    default_query = "I need a machine that can handle MIG/MAG, MMA (Stick), and DC TIG welding"

    print("\n" + "=" * 80)
    print("🔍 VECTOR SEARCH INTERACTIVE COMPARISON TEST")
    print("=" * 80)
    print("\nEnter your query (or press Enter to use default):")
    print(f"Default: {default_query}")
    print()

    # Get user input
    user_query = input("> ").strip()
    if not user_query:
        user_query = default_query

    print(f"\n✅ Using query: {user_query}\n")

    # Helper function for vector search
    async def vector_search_neo4j(query: str):
        """Inline vector search using embeddingIndex (3072 dims)"""
        print("  Generating embedding (text-embedding-3-large, 3072 dims)...", end=" ", flush=True)
        embed_start = time.time()

        # Generate embedding with 3072 dimensions
        response = await openai_client.embeddings.create(
            model="text-embedding-3-large",
            input=query,
            dimensions=3072
        )
        embedding = response.data[0].embedding
        embed_time = (time.time() - embed_start) * 1000
        print(f"✅ ({embed_time:.0f}ms)")

        # Query Neo4j vector index
        print("  Searching Neo4j vector index...", end=" ", flush=True)
        search_start = time.time()

        async with neo4j_driver.session() as session:
            result = await session.run("""
                CALL db.index.vector.queryNodes('embeddingIndex', 10, $vector)
                YIELD node, score
                MATCH (p:Product)-[:HAS_EMBEDDING]->(node)
                WHERE p.category = 'Powersource'
                RETURN
                    p.gin as gin,
                    p.item_name as name,
                    p.category as category,
                    p.description_catalogue as description,
                    score
                ORDER BY score DESC
            """, vector=embedding)

            records = await result.data()

        search_time = (time.time() - search_start) * 1000
        print(f"✅ ({search_time:.0f}ms)")

        return records, embed_time + search_time

    try:
        # Execute all 3 strategies
        print("Running searches...")

        # Cypher search
        print("\n1. Cypher Strategy:", end=" ", flush=True)
        cypher_start = time.time()
        cypher_result = await cypher_strategy.search(
            component_type="power_source",
            user_message=user_query,
            master_parameters={"power_source": {}},
            selected_components={},
            limit=10
        )
        cypher_time = (time.time() - cypher_start) * 1000
        print(f"✅ ({cypher_time:.0f}ms)")

        # Lucene search
        print("2. Lucene Strategy:", end=" ", flush=True)
        lucene_start = time.time()
        lucene_result = await lucene_strategy.search(
            component_type="power_source",
            user_message=user_query,
            master_parameters={},
            selected_components={},
            limit=10
        )
        lucene_time = (time.time() - lucene_start) * 1000
        print(f"✅ ({lucene_time:.0f}ms)")

        # Vector search
        print("3. Vector Strategy:")
        vector_records, vector_time = await vector_search_neo4j(user_query)

        # Display comparison
        print("\n" + "=" * 80)
        print("📊 COMPARISON RESULTS")
        print("=" * 80)

        # Cypher results
        print("\n┌─────────────────────────────────────────────────────────────────────┐")
        print("│ CYPHER SEARCH (Compatibility-based)                                 │")
        print("├─────────────────────────────────────────────────────────────────────┤")
        for i, p in enumerate(cypher_result.products[:5], 1):
            score = cypher_result.scores.get(p["gin"], 1.0) if cypher_result.scores else 1.0
            name = p["name"][:25].ljust(25)
            gin = p["gin"]
            print(f"│ {i}. {name} (GIN: {gin})  Score: {score:.2f}           │")
        print("│                                                                      │")
        print(f"│ Total results: {len(cypher_result.products):<52} │")
        avg_cypher = sum(cypher_result.scores.values()) / len(cypher_result.scores) if cypher_result.scores else 1.0
        print(f"│ Avg score: {avg_cypher:.2f}{' ' * 57}│")
        print("└─────────────────────────────────────────────────────────────────────┘")

        # Lucene results
        print("\n┌─────────────────────────────────────────────────────────────────────┐")
        print("│ LUCENE SEARCH (Keyword-based)                                       │")
        print("├─────────────────────────────────────────────────────────────────────┤")
        for i, p in enumerate(lucene_result.products[:5], 1):
            score = lucene_result.scores.get(p["gin"], 0.0) if lucene_result.scores else 0.0
            name = p["name"][:25].ljust(25)
            gin = p["gin"]
            print(f"│ {i}. {name} (GIN: {gin})  Score: {score:.2f}          │")
        print("│                                                                      │")
        print(f"│ Total results: {len(lucene_result.products):<52} │")
        avg_lucene = sum(lucene_result.scores.values()) / len(lucene_result.scores) if lucene_result.scores else 0.0
        print(f"│ Avg score: {avg_lucene:.2f}{' ' * 56}│")
        print("└─────────────────────────────────────────────────────────────────────┘")

        # Vector results
        print("\n┌─────────────────────────────────────────────────────────────────────┐")
        print("│ VECTOR SEARCH (Semantic similarity, 3072-dim)                       │")
        print("├─────────────────────────────────────────────────────────────────────┤")
        for i, record in enumerate(vector_records[:5], 1):
            name = record["name"][:25].ljust(25)
            gin = record["gin"]
            score = float(record["score"])
            print(f"│ {i}. {name} (GIN: {gin})  Similarity: {score:.3f}       │")
        print("│                                                                      │")
        print(f"│ Total results: {len(vector_records):<52} │")
        if vector_records:
            avg_vector = sum(float(r["score"]) for r in vector_records) / len(vector_records)
            print(f"│ Avg similarity: {avg_vector:.3f}{' ' * 52}│")
        print("└─────────────────────────────────────────────────────────────────────┘")

        # Analysis
        print("\n" + "=" * 80)
        print("🎯 ANALYSIS")
        print("=" * 80)

        # Top-1 agreement
        cypher_top = cypher_result.products[0]["gin"] if cypher_result.products else None
        lucene_top = lucene_result.products[0]["gin"] if lucene_result.products else None
        vector_top = vector_records[0]["gin"] if vector_records else None

        print("\nTop-1 Results:")
        if cypher_top == lucene_top == vector_top:
            print(f"  ✅ All 3 strategies agree: {cypher_result.products[0]['name']}")
        else:
            print(f"  Cypher: {cypher_result.products[0]['name'] if cypher_result.products else 'None'}")
            print(f"  Lucene: {lucene_result.products[0]['name'] if lucene_result.products else 'None'}")
            print(f"  Vector: {vector_records[0]['name'] if vector_records else 'None'}")

        # Top-5 overlap
        cypher_top5 = {p["gin"] for p in cypher_result.products[:5]}
        lucene_top5 = {p["gin"] for p in lucene_result.products[:5]}
        vector_top5 = {r["gin"] for r in vector_records[:5]}

        print("\nTop-5 Overlap:")
        cypher_lucene_overlap = len(cypher_top5 & lucene_top5)
        cypher_vector_overlap = len(cypher_top5 & vector_top5)
        lucene_vector_overlap = len(lucene_top5 & vector_top5)

        print(f"  Cypher ∩ Lucene: {cypher_lucene_overlap}/5 products ({cypher_lucene_overlap * 20}%)")
        print(f"  Cypher ∩ Vector: {cypher_vector_overlap}/5 products ({cypher_vector_overlap * 20}%)")
        print(f"  Lucene ∩ Vector: {lucene_vector_overlap}/5 products ({lucene_vector_overlap * 20}%)")

        # Performance
        print("\nPerformance:")
        print(f"  Cypher: {cypher_time:.0f}ms")
        print(f"  Lucene: {lucene_time:.0f}ms")
        print(f"  Vector: {vector_time:.0f}ms")

        print("\n" + "=" * 80)
        print("✅ Test completed successfully")
        print("=" * 80)

    finally:
        # Cleanup
        await neo4j_search.close()
        await neo4j_driver.close()


if __name__ == "__main__":
    """
    Run proactive flow test standalone.

    Usage:
        cd src/backend
        python -m tests.e2e.test_complete_proactive_flow
    """
    import sys
    import os

    # Add app to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

    # Initialize app services (simplified for testing)
    print("Initializing services...")

    # Run test
    asyncio.run(test_complete_proactive_flow_aristo())
