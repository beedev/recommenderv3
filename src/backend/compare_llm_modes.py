#!/usr/bin/env python3
"""
Compare LLM search strategy with different retrieval methods:
1. LLM + Lucene retrieval
2. LLM + Vector retrieval
3. LLM + Combined (Lucene + Vector with deduplication)
"""

import asyncio
import sys
import os
import time
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

sys.path.insert(0, '/Users/bharath/Desktop/Ayna_ESAB_Nov7/src/backend')

from openai import AsyncOpenAI
from app.services.neo4j.product_search import Neo4jProductSearch
from app.services.search.strategies.llm_strategy import LLMSearchStrategy

async def compare_llm_modes():
    """Compare LLM with Lucene vs Vector vs Combined retrieval."""

    # Initialize Neo4j
    NEO4J_URI = os.getenv("NEO4J_URI")
    NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

    product_search = Neo4jProductSearch(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)

    # Initialize OpenAI
    openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Initialize all three LLM strategies
    llm_lucene = LLMSearchStrategy(
        config={"enabled": True, "weight": 0.3, "retrieval_method": "lucene", "retrieval_limit": 10},
        neo4j_product_search=product_search,
        openai_client=openai_client
    )

    llm_vector = LLMSearchStrategy(
        config={"enabled": True, "weight": 0.3, "retrieval_method": "vector", "retrieval_limit": 10},
        neo4j_product_search=product_search,
        openai_client=openai_client
    )

    llm_combined = LLMSearchStrategy(
        config={"enabled": True, "weight": 0.3, "retrieval_method": "combined", "retrieval_limit": 10},
        neo4j_product_search=product_search,
        openai_client=openai_client
    )

    query = "I want a machine strictly for MMA (Stick) and Live TIG (no MIG required)."

    print("\n" + "="*80)
    print("🔍 LLM RETRIEVAL MODE COMPARISON")
    print("="*80)
    print(f"\nQuery: {query}\n")

    try:
        # Test 1: LLM + Lucene
        print("1️⃣  Running LLM + LUCENE...", end=" ", flush=True)
        lucene_start = time.time()
        llm_lucene_result = await llm_lucene.search(
            component_type="power_source",
            user_message=query,
            master_parameters={},
            selected_components={},
            limit=10
        )
        lucene_time = (time.time() - lucene_start) * 1000
        print(f"✅ ({lucene_time:.0f}ms)\n")

        # Test 2: LLM + Vector
        print("2️⃣  Running LLM + VECTOR...", end=" ", flush=True)
        vector_start = time.time()
        llm_vector_result = await llm_vector.search(
            component_type="power_source",
            user_message=query,
            master_parameters={},
            selected_components={},
            limit=10
        )
        vector_time = (time.time() - vector_start) * 1000
        print(f"✅ ({vector_time:.0f}ms)\n")

        # Test 3: LLM + Combined
        print("3️⃣  Running LLM + COMBINED (Lucene + Vector)...", end=" ", flush=True)
        combined_start = time.time()
        llm_combined_result = await llm_combined.search(
            component_type="power_source",
            user_message=query,
            master_parameters={},
            selected_components={},
            limit=5  # Return top 5 for combined mode
        )
        combined_time = (time.time() - combined_start) * 1000
        print(f"✅ ({combined_time:.0f}ms)\n")

        # Display Results
        print("\n" + "="*80)
        print("📊 RESULTS")
        print("="*80)

        # LLM + Lucene Results
        print("\n┌" + "─"*78 + "┐")
        print("│ " + "LLM + LUCENE (Keyword retrieval → LLM rerank)".ljust(77) + "│")
        print("├" + "─"*78 + "┤")

        for i, product in enumerate(llm_lucene_result.products[:5], 1):
            name = product.get('name', 'Unknown')[:45].ljust(45)
            gin = product.get('gin', 'N/A')
            score = product.get('specifications', {}).get('llm_score', 0)
            print(f"│ {i:2d}. {name} │ {gin} │ {score:3.0f}/100 │")

        avg_lucene = sum(p.get('specifications', {}).get('llm_score', 0) for p in llm_lucene_result.products) / len(llm_lucene_result.products) if llm_lucene_result.products else 0
        print("├" + "─"*78 + "┤")
        print(f"│ Total: {len(llm_lucene_result.products):2d} │ Avg: {avg_lucene:.1f}/100 │ Time: {lucene_time:.0f}ms".ljust(78) + "│")
        print("└" + "─"*78 + "┘")

        # LLM + Vector Results
        print("\n┌" + "─"*78 + "┐")
        print("│ " + "LLM + VECTOR (Semantic retrieval → LLM rerank)".ljust(77) + "│")
        print("├" + "─"*78 + "┤")

        for i, product in enumerate(llm_vector_result.products[:5], 1):
            name = product.get('name', 'Unknown')[:45].ljust(45)
            gin = product.get('gin', 'N/A')
            score = product.get('specifications', {}).get('llm_score', 0)
            print(f"│ {i:2d}. {name} │ {gin} │ {score:3.0f}/100 │")

        avg_vector = sum(p.get('specifications', {}).get('llm_score', 0) for p in llm_vector_result.products) / len(llm_vector_result.products) if llm_vector_result.products else 0
        print("├" + "─"*78 + "┤")
        print(f"│ Total: {len(llm_vector_result.products):2d} │ Avg: {avg_vector:.1f}/100 │ Time: {vector_time:.0f}ms".ljust(78) + "│")
        print("└" + "─"*78 + "┘")

        # LLM + Combined Results
        print("\n┌" + "─"*78 + "┐")
        print("│ " + "LLM + COMBINED (Lucene+Vector → Dedup → LLM rerank) [TOP 5]".ljust(77) + "│")
        print("├" + "─"*78 + "┤")

        for i, product in enumerate(llm_combined_result.products, 1):
            name = product.get('name', 'Unknown')[:45].ljust(45)
            gin = product.get('gin', 'N/A')
            score = product.get('specifications', {}).get('llm_score', 0)
            print(f"│ {i:2d}. {name} │ {gin} │ {score:3.0f}/100 │")

        avg_combined = sum(p.get('specifications', {}).get('llm_score', 0) for p in llm_combined_result.products) / len(llm_combined_result.products) if llm_combined_result.products else 0

        # Show deduplication stats from metadata
        metadata = llm_combined_result.metadata
        lucene_count = metadata.get('lucene_count', 0)
        vector_count = metadata.get('vector_count', 0)
        deduplicated_count = metadata.get('deduplicated_count', 0)
        duplicates_removed = metadata.get('duplicates_removed', 0)

        print("├" + "─"*78 + "┤")
        print(f"│ Lucene: {lucene_count} │ Vector: {vector_count} │ Unique: {deduplicated_count} │ Duplicates: {duplicates_removed}".ljust(78) + "│")
        print(f"│ Total: {len(llm_combined_result.products):2d} │ Avg: {avg_combined:.1f}/100 │ Time: {combined_time:.0f}ms".ljust(78) + "│")
        print("└" + "─"*78 + "┘")

        # Analysis
        print("\n" + "="*80)
        print("🎯 ANALYSIS")
        print("="*80)

        # Top-1 comparison
        print(f"\n📌 Top-1 Results:")
        if llm_lucene_result.products:
            p = llm_lucene_result.products[0]
            print(f"   LLM+Lucene:   {p.get('name', 'N/A')} (GIN: {p.get('gin', 'N/A')}) [{p.get('specifications', {}).get('llm_score', 0)}/100]")
        if llm_vector_result.products:
            p = llm_vector_result.products[0]
            print(f"   LLM+Vector:   {p.get('name', 'N/A')} (GIN: {p.get('gin', 'N/A')}) [{p.get('specifications', {}).get('llm_score', 0)}/100]")
        if llm_combined_result.products:
            p = llm_combined_result.products[0]
            print(f"   LLM+Combined: {p.get('name', 'N/A')} (GIN: {p.get('gin', 'N/A')}) [{p.get('specifications', {}).get('llm_score', 0)}/100]")

        # Top-5 overlap analysis
        lucene_top5 = {p.get('gin') for p in llm_lucene_result.products[:5]}
        vector_top5 = {p.get('gin') for p in llm_vector_result.products[:5]}
        combined_top5 = {p.get('gin') for p in llm_combined_result.products[:5]}

        print(f"\n📊 Top-5 Overlap:")
        overlap_lv = len(lucene_top5 & vector_top5)
        overlap_lc = len(lucene_top5 & combined_top5)
        overlap_vc = len(vector_top5 & combined_top5)
        print(f"   Lucene ∩ Vector:   {overlap_lv}/5 products ({overlap_lv * 20}%)")
        print(f"   Lucene ∩ Combined: {overlap_lc}/5 products ({overlap_lc * 20}%)")
        print(f"   Vector ∩ Combined: {overlap_vc}/5 products ({overlap_vc * 20}%)")

        # Performance comparison
        print(f"\n⚡ Performance:")
        print(f"   LLM+Lucene:   {lucene_time:.0f}ms")
        print(f"   LLM+Vector:   {vector_time:.0f}ms")
        print(f"   LLM+Combined: {combined_time:.0f}ms")

        fastest_time = min(lucene_time, vector_time, combined_time)
        if fastest_time == lucene_time:
            fastest = "Lucene"
        elif fastest_time == vector_time:
            fastest = "Vector"
        else:
            fastest = "Combined"

        print(f"   Fastest: {fastest}")

        # Quality comparison
        print(f"\n🏆 Quality (Average LLM Scores):")
        print(f"   LLM+Lucene:   {avg_lucene:.1f}/100")
        print(f"   LLM+Vector:   {avg_vector:.1f}/100")
        print(f"   LLM+Combined: {avg_combined:.1f}/100")

        print("\n" + "="*80)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(compare_llm_modes())
