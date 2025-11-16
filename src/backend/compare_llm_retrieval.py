#!/usr/bin/env python3
"""
Compare LLM search strategy with different retrieval methods:
1. LLM + Lucene retrieval
2. LLM + Cypher retrieval
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
from neo4j import AsyncGraphDatabase
from app.services.neo4j.product_search import Neo4jProductSearch
from app.services.search.strategies.llm_strategy import LLMSearchStrategy

async def compare_llm_retrieval():
    """Compare LLM with Lucene vs Cypher retrieval."""

    # Initialize Neo4j
    NEO4J_URI = os.getenv("NEO4J_URI")
    NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

    product_search = Neo4jProductSearch(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)

    # Initialize OpenAI
    openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Initialize both LLM strategies
    llm_lucene = LLMSearchStrategy(
        config={"enabled": True, "weight": 0.3, "retrieval_method": "lucene", "retrieval_limit": 10},
        neo4j_product_search=product_search,
        openai_client=openai_client
    )

    llm_cypher = LLMSearchStrategy(
        config={"enabled": True, "weight": 0.3, "retrieval_method": "cypher", "retrieval_limit": 10},
        neo4j_product_search=product_search,
        openai_client=openai_client
    )

    query = "I want a machine strictly for MMA (Stick) and Live TIG (no MIG required)."

    print("\n" + "="*80)
    print("🔍 LLM RETRIEVAL METHOD COMPARISON")
    print("="*80)
    print(f"\nQuery: {query}\n")

    try:
        # Test 1: LLM + Lucene
        print("1️⃣  Running LLM + LUCENE retrieval...", end=" ", flush=True)
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

        # Test 2: LLM + Cypher
        print("2️⃣  Running LLM + CYPHER retrieval...", end=" ", flush=True)
        cypher_start = time.time()
        llm_cypher_result = await llm_cypher.search(
            component_type="power_source",
            user_message=query,
            master_parameters={},
            selected_components={},
            limit=10
        )
        cypher_time = (time.time() - cypher_start) * 1000
        print(f"✅ ({cypher_time:.0f}ms)\n")

        # Display Results
        print("\n" + "="*80)
        print("📊 RESULTS")
        print("="*80)

        # LLM + Lucene Results
        print("\n┌" + "─"*78 + "┐")
        print("│ " + "LLM + LUCENE (Keyword retrieval → LLM rerank)".ljust(77) + "│")
        print("├" + "─"*78 + "┤")

        for i, product in enumerate(llm_lucene_result.products, 1):
            name = product.get('name', 'Unknown')[:45].ljust(45)
            gin = product.get('gin', 'N/A')
            score = product.get('specifications', {}).get('llm_score', 0)
            print(f"│ {i:2d}. {name} │ {gin} │ {score:3.0f}/100 │")

        avg_lucene = sum(p.get('specifications', {}).get('llm_score', 0) for p in llm_lucene_result.products) / len(llm_lucene_result.products) if llm_lucene_result.products else 0
        print("├" + "─"*78 + "┤")
        print(f"│ Total: {len(llm_lucene_result.products):2d} │ Avg: {avg_lucene:.1f}/100 │ Time: {lucene_time:.0f}ms".ljust(78) + "│")
        print("└" + "─"*78 + "┘")

        # LLM + Cypher Results
        print("\n┌" + "─"*78 + "┐")
        print("│ " + "LLM + CYPHER (Compatibility retrieval → LLM rerank)".ljust(77) + "│")
        print("├" + "─"*78 + "┤")

        for i, product in enumerate(llm_cypher_result.products, 1):
            name = product.get('name', 'Unknown')[:45].ljust(45)
            gin = product.get('gin', 'N/A')
            score = product.get('specifications', {}).get('llm_score', 0)
            print(f"│ {i:2d}. {name} │ {gin} │ {score:3.0f}/100 │")

        avg_cypher = sum(p.get('specifications', {}).get('llm_score', 0) for p in llm_cypher_result.products) / len(llm_cypher_result.products) if llm_cypher_result.products else 0
        print("├" + "─"*78 + "┤")
        print(f"│ Total: {len(llm_cypher_result.products):2d} │ Avg: {avg_cypher:.1f}/100 │ Time: {cypher_time:.0f}ms".ljust(78) + "│")
        print("└" + "─"*78 + "┘")

        # Analysis
        print("\n" + "="*80)
        print("🎯 ANALYSIS")
        print("="*80)

        lucene_top5 = {p.get('gin') for p in llm_lucene_result.products[:5]}
        cypher_top5 = {p.get('gin') for p in llm_cypher_result.products[:5]}
        overlap = len(lucene_top5 & cypher_top5)

        print(f"\n📌 Top-1 Results:")
        if llm_lucene_result.products:
            p = llm_lucene_result.products[0]
            print(f"   LLM+Lucene: {p.get('name', 'N/A')} (GIN: {p.get('gin', 'N/A')}) [{p.get('specifications', {}).get('llm_score', 0)}/100]")
        if llm_cypher_result.products:
            p = llm_cypher_result.products[0]
            print(f"   LLM+Cypher: {p.get('name', 'N/A')} (GIN: {p.get('gin', 'N/A')}) [{p.get('specifications', {}).get('llm_score', 0)}/100]")

        print(f"\n📊 Top-5 Overlap: {overlap}/5 products ({overlap * 20}%)")

        print(f"\n⚡ Performance:")
        print(f"   LLM+Lucene: {lucene_time:.0f}ms")
        print(f"   LLM+Cypher: {cypher_time:.0f}ms")

        speed_diff = abs(lucene_time - cypher_time)
        faster = "Lucene" if lucene_time < cypher_time else "Cypher"
        print(f"   {faster} is {speed_diff:.0f}ms faster ({speed_diff/max(lucene_time, cypher_time)*100:.1f}% difference)")

        print("\n" + "="*80)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(compare_llm_retrieval())
