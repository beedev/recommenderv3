#!/usr/bin/env python3
"""
Standalone script to compare Cypher, Lucene, Vector, and LLM search results.
Shows detailed product rankings for all four strategies.

LLM Strategy now uses Combined mode (Lucene+Vector → Deduplication → LLM Reranking).
"""
import asyncio
import os
import sys
import time
from pathlib import Path
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

# Add app to path
sys.path.insert(0, os.path.dirname(__file__))

from app.services.search.strategies.cypher_strategy import CypherSearchStrategy
from app.services.search.strategies.lucene_strategy import LuceneSearchStrategy
from app.services.search.strategies.vector_strategy import VectorSearchStrategy
from app.services.search.strategies.llm_strategy import LLMSearchStrategy
from app.services.neo4j.product_search import Neo4jProductSearch
from app.config.schema_loader import load_component_config
from app.database.database import neo4j_manager


async def main():
    # Configuration
    NEO4J_URI = os.getenv("NEO4J_URI")
    NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    if not all([NEO4J_URI, NEO4J_PASSWORD, OPENAI_API_KEY]):
        print("❌ Missing environment variables. Please set:")
        print("   - NEO4J_URI")
        print("   - NEO4J_PASSWORD")
        print("   - OPENAI_API_KEY")
        sys.exit(1)

    # Get query from command line or use default
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = "I want a machine strictly for MMA (Stick) and Live TIG (no MIG required)."

    print("=" * 80)
    print("🔍 SEARCH STRATEGY COMPARISON TEST")
    print("=" * 80)
    print(f"\nQuery: {query}\n")

    # Initialize services
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    component_config = load_component_config()

    # Initialize centralized Neo4j manager
    await neo4j_manager.init_neo4j(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)
    neo4j_driver = await neo4j_manager.get_driver()
    product_search = Neo4jProductSearch(driver=neo4j_driver)

    cypher_strategy = CypherSearchStrategy(
        config={"enabled": True, "weight": 0.4},
        neo4j_product_search=product_search
    )
    lucene_strategy = LuceneSearchStrategy(
        config={"enabled": True, "weight": 0.6, "min_score": 0.3},
        neo4j_product_search=product_search
    )
    vector_strategy = VectorSearchStrategy(
        config={"enabled": True, "weight": 1.0, "min_score": 0.6, "embedding_model": "text-embedding-3-large", "embedding_dims": 3072},
        neo4j_product_search=product_search,
        openai_client=openai_client
    )
    llm_strategy = LLMSearchStrategy(
        config={"enabled": True, "weight": 0.3, "retrieval_method": "combined", "retrieval_limit": 10, "model": "gpt-4o-mini"},
        neo4j_product_search=product_search,
        openai_client=openai_client
    )

    # 1. CYPHER SEARCH
    print("1️⃣  Running Cypher search...", end=" ", flush=True)
    cypher_start = time.time()
    cypher_result = await cypher_strategy.search(
        component_type="power_source",
        user_message=query,
        master_parameters={},
        selected_components={},
        limit=10
    )
    cypher_time = (time.time() - cypher_start) * 1000
    print(f"✅ ({cypher_time:.0f}ms)\n")

    # 2. LUCENE SEARCH
    print("2️⃣  Running Lucene search...", end=" ", flush=True)
    lucene_start = time.time()
    lucene_result = await lucene_strategy.search(
        component_type="power_source",
        user_message=query,
        master_parameters={},
        selected_components={},
        limit=10
    )
    lucene_time = (time.time() - lucene_start) * 1000
    print(f"✅ ({lucene_time:.0f}ms)\n")

    # 3. VECTOR SEARCH
    print("3️⃣  Running Vector search...")
    print("   → Generating embedding (text-embedding-3-large, 3072 dims)... ", end="", flush=True)
    vector_start = time.time()
    vector_result = await vector_strategy.search(
        component_type="power_source",
        user_message=query,
        master_parameters={},
        selected_components={},
        limit=10
    )
    vector_time = (time.time() - vector_start) * 1000
    print(f"✅ ({vector_time:.0f}ms)\n")

    # 4. LLM SEARCH (Combined: Lucene+Vector → Dedup → LLM Reranking)
    print("4️⃣  Running LLM search (Combined: Lucene+Vector → Dedup → LLM reranking)...", end=" ", flush=True)
    llm_start = time.time()
    llm_result = await llm_strategy.search(
        component_type="power_source",
        user_message=query,
        master_parameters={},
        selected_components={},
        limit=10
    )
    llm_time = (time.time() - llm_start) * 1000
    print(f"✅ ({llm_time:.0f}ms)\n")

    # DISPLAY RESULTS
    print("\n" + "=" * 80)
    print("📊 DETAILED RESULTS")
    print("=" * 80)

    # CYPHER RESULTS
    print("\n" + "┌" + "─" * 78 + "┐")
    print("│ " + "CYPHER SEARCH (Compatibility-based)".ljust(77) + "│")
    print("├" + "─" * 78 + "┤")

    if cypher_result.products:
        for i, product in enumerate(cypher_result.products, 1):
            # Handle both ProductResult objects and dicts
            if hasattr(product, 'name'):
                name = product.name[:40].ljust(40)
                gin = product.gin
                score = product.specifications.get('cypher_score', 1.0)
            else:
                name = product.get('name', 'Unknown')[:40].ljust(40)
                gin = product.get('gin', 'N/A')
                score = product.get('specifications', {}).get('cypher_score', 1.0)
            print(f"│ {i:2d}. {name} │ GIN: {gin} │ Score: {score:.2f} │")

        # Calculate average score
        if hasattr(cypher_result.products[0], 'specifications'):
            avg_score = sum(p.specifications.get('cypher_score', 1.0) for p in cypher_result.products) / len(cypher_result.products)
        else:
            avg_score = sum(p.get('specifications', {}).get('cypher_score', 1.0) for p in cypher_result.products) / len(cypher_result.products)
        print("├" + "─" * 78 + "┤")
        print(f"│ Total: {len(cypher_result.products):2d} products │ Avg Score: {avg_score:.2f} │ Time: {cypher_time:.0f}ms".ljust(77) + "│")
    else:
        print("│ No results found".ljust(77) + "│")

    print("└" + "─" * 78 + "┘")

    # LUCENE RESULTS
    print("\n" + "┌" + "─" * 78 + "┐")
    print("│ " + "LUCENE SEARCH (Keyword-based)".ljust(77) + "│")
    print("├" + "─" * 78 + "┤")

    if lucene_result.products:
        for i, product in enumerate(lucene_result.products, 1):
            # Handle both ProductResult objects and dicts
            if hasattr(product, 'name'):
                name = product.name[:40].ljust(40)
                gin = product.gin
                score = product.specifications.get('lucene_score', 0.0)
            else:
                name = product.get('name', 'Unknown')[:40].ljust(40)
                gin = product.get('gin', 'N/A')
                score = product.get('specifications', {}).get('lucene_score', 0.0)
            print(f"│ {i:2d}. {name} │ GIN: {gin} │ Score: {score:.2f} │")

        # Calculate average score
        if hasattr(lucene_result.products[0], 'specifications'):
            avg_score = sum(p.specifications.get('lucene_score', 0.0) for p in lucene_result.products) / len(lucene_result.products)
        else:
            avg_score = sum(p.get('specifications', {}).get('lucene_score', 0.0) for p in lucene_result.products) / len(lucene_result.products)
        print("├" + "─" * 78 + "┤")
        print(f"│ Total: {len(lucene_result.products):2d} products │ Avg Score: {avg_score:.2f} │ Time: {lucene_time:.0f}ms".ljust(77) + "│")
    else:
        print("│ No results found".ljust(77) + "│")

    print("└" + "─" * 78 + "┘")

    # VECTOR RESULTS
    print("\n" + "┌" + "─" * 78 + "┐")
    print("│ " + "VECTOR SEARCH (Semantic similarity, 3072-dim)".ljust(77) + "│")
    print("├" + "─" * 78 + "┤")

    if vector_result.products:
        for i, product in enumerate(vector_result.products, 1):
            name = product["name"][:40].ljust(40)
            gin = product["gin"]
            score = vector_result.scores.get(gin, 0.0)
            print(f"│ {i:2d}. {name} │ GIN: {gin} │ Sim: {score:.3f} │")

        avg_score = sum(vector_result.scores.values()) / len(vector_result.scores)
        print("├" + "─" * 78 + "┤")
        print(f"│ Total: {len(vector_result.products):2d} products │ Avg Similarity: {avg_score:.3f} │ Time: {vector_time:.0f}ms".ljust(77) + "│")
    else:
        print("│ No results found".ljust(77) + "│")

    print("└" + "─" * 78 + "┘")

    # LLM RESULTS
    print("\n" + "┌" + "─" * 78 + "┐")
    print("│ " + "LLM SEARCH (Lucene+Vector → Dedup → GPT-4o-mini reranking)".ljust(77) + "│")
    print("├" + "─" * 78 + "┤")

    if llm_result.products:
        for i, product in enumerate(llm_result.products, 1):
            # Handle both ProductResult objects and dicts
            if hasattr(product, 'name'):
                name = product.name[:40].ljust(40)
                gin = product.gin
                score = product.specifications.get('llm_score', 0)
                reasoning = product.specifications.get('llm_reasoning', '')[:30]
            else:
                name = product.get('name', 'Unknown')[:40].ljust(40)
                gin = product.get('gin', 'N/A')
                score = product.get('specifications', {}).get('llm_score', 0)
                reasoning = product.get('specifications', {}).get('llm_reasoning', '')[:30]
            print(f"│ {i:2d}. {name} │ GIN: {gin} │ LLM: {score:3.0f}/100 │")

        # Calculate average score
        if hasattr(llm_result.products[0], 'specifications'):
            avg_score = sum(p.specifications.get('llm_score', 0) for p in llm_result.products) / len(llm_result.products)
        else:
            avg_score = sum(p.get('specifications', {}).get('llm_score', 0) for p in llm_result.products) / len(llm_result.products)
        print("├" + "─" * 78 + "┤")
        print(f"│ Total: {len(llm_result.products):2d} products │ Avg Score: {avg_score:.1f}/100 │ Time: {llm_time:.0f}ms".ljust(77) + "│")
    else:
        print("│ No results found".ljust(77) + "│")

    print("└" + "─" * 78 + "┘")

    # ANALYSIS
    print("\n" + "=" * 80)
    print("🎯 ANALYSIS")
    print("=" * 80)

    # Top-1 comparison
    print("\n📌 Top-1 Results:")
    if cypher_result.products:
        p = cypher_result.products[0]
        name = p.name if hasattr(p, 'name') else p.get('name', 'Unknown')
        gin = p.gin if hasattr(p, 'gin') else p.get('gin', 'N/A')
        print(f"   Cypher: {name} (GIN: {gin})")
    if lucene_result.products:
        p = lucene_result.products[0]
        name = p.name if hasattr(p, 'name') else p.get('name', 'Unknown')
        gin = p.gin if hasattr(p, 'gin') else p.get('gin', 'N/A')
        print(f"   Lucene: {name} (GIN: {gin})")
    if vector_result.products:
        p = vector_result.products[0]
        name = p.get('name', 'Unknown')
        gin = p.get('gin', 'N/A')
        print(f"   Vector: {name} (GIN: {gin})")
    if llm_result.products:
        p = llm_result.products[0]
        name = p.name if hasattr(p, 'name') else p.get('name', 'Unknown')
        gin = p.gin if hasattr(p, 'gin') else p.get('gin', 'N/A')
        score = p.specifications.get('llm_score', 0) if hasattr(p, 'specifications') else p.get('specifications', {}).get('llm_score', 0)
        print(f"   LLM:    {name} (GIN: {gin}) [Score: {score:.0f}/100]")

    # Top-5 overlap
    print("\n📊 Top-5 Overlap:")
    cypher_top5 = {(p.gin if hasattr(p, 'gin') else p.get('gin')) for p in cypher_result.products[:5]}
    lucene_top5 = {(p.gin if hasattr(p, 'gin') else p.get('gin')) for p in lucene_result.products[:5]}
    vector_top5 = {p.get('gin') for p in vector_result.products[:5]}
    llm_top5 = {(p.gin if hasattr(p, 'gin') else p.get('gin')) for p in llm_result.products[:5]}

    cypher_lucene = len(cypher_top5 & lucene_top5)
    cypher_vector = len(cypher_top5 & vector_top5)
    lucene_vector = len(lucene_top5 & vector_top5)
    cypher_llm = len(cypher_top5 & llm_top5)
    lucene_llm = len(lucene_top5 & llm_top5)
    vector_llm = len(vector_top5 & llm_top5)

    print(f"   Cypher ∩ Lucene: {cypher_lucene}/5 products ({cypher_lucene * 20}%)")
    print(f"   Cypher ∩ Vector: {cypher_vector}/5 products ({cypher_vector * 20}%)")
    print(f"   Cypher ∩ LLM:    {cypher_llm}/5 products ({cypher_llm * 20}%)")
    print(f"   Lucene ∩ Vector: {lucene_vector}/5 products ({lucene_vector * 20}%)")
    print(f"   Lucene ∩ LLM:    {lucene_llm}/5 products ({lucene_llm * 20}%)")
    print(f"   Vector ∩ LLM:    {vector_llm}/5 products ({vector_llm * 20}%)")

    # Performance
    print("\n⚡ Performance:")
    times = [("Cypher", cypher_time), ("Lucene", lucene_time), ("Vector", vector_time), ("LLM", llm_time)]
    fastest = min(times, key=lambda x: x[1])

    for name, t in times:
        if name == fastest[0]:
            print(f"   {name}: {t:.0f}ms (fastest)")
        elif name == "Vector":
            print(f"   {name}: {t:.0f}ms (embedding + search)")
        elif name == "LLM":
            print(f"   {name}: {t:.0f}ms (Lucene retrieval + LLM reranking)")
        else:
            print(f"   {name}: {t:.0f}ms")

    print("\n" + "=" * 80)

    # Cleanup
    await neo4j_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
