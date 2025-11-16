"""
Test script to debug competitor_brand_product_pairs field extraction
"""
import asyncio
import logging
import os
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)-8s | %(name)-40s | %(message)s'
)

# Load environment
load_dotenv()

from app.services.search.strategies.llm_strategy import LLMSearchStrategy
from app.services.search.strategies.lucene_strategy import LuceneSearchStrategy
from app.services.search.strategies.vector_strategy import VectorSearchStrategy
from app.services.neo4j.product_search import Neo4jProductSearch
from openai import AsyncOpenAI


async def main():
    print("=" * 100)
    print("TESTING COMPETITOR_BRAND_PRODUCT_PAIRS FIELD EXTRACTION")
    print("=" * 100)

    # Initialize services
    product_search = Neo4jProductSearch(
        uri=os.getenv('NEO4J_URI'),
        username=os.getenv('NEO4J_USERNAME', 'neo4j'),
        password=os.getenv('NEO4J_PASSWORD')
    )
    openai_client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    query = "Can you provide me an ESAB equivalent of Kemppi:Master 315 welding equipment?"
    print(f"\nQuery: {query}\n")

    # Test Lucene strategy
    print("\n" + "=" * 100)
    print("1. TESTING LUCENE STRATEGY")
    print("=" * 100)
    lucene_strategy = LuceneSearchStrategy(
        config={'enabled': True, 'weight': 0.5, 'min_score': 0.1},
        neo4j_product_search=product_search
    )
    lucene_result = await lucene_strategy.search(
        component_type='power_source',
        user_message=query,
        master_parameters={},
        selected_components={},
        limit=3
    )
    print(f"\n✅ Lucene found {len(lucene_result.products)} products")

    # Test Vector strategy
    print("\n" + "=" * 100)
    print("2. TESTING VECTOR STRATEGY")
    print("=" * 100)
    vector_strategy = VectorSearchStrategy(
        config={'enabled': True, 'weight': 0.6, 'min_score': 0.6, 'embedding_model': 'text-embedding-3-large', 'embedding_dims': 3072},
        neo4j_product_search=product_search,
        openai_client=openai_client
    )
    vector_result = await vector_strategy.search(
        component_type='power_source',
        user_message=query,
        master_parameters={},
        selected_components={},
        limit=3
    )
    print(f"\n✅ Vector found {len(vector_result.products)} products")

    # Test LLM combined strategy
    print("\n" + "=" * 100)
    print("3. TESTING LLM COMBINED STRATEGY (Lucene + Vector)")
    print("=" * 100)
    llm_strategy = LLMSearchStrategy(
        config={'enabled': True, 'weight': 0.3, 'retrieval_method': 'combined', 'retrieval_limit': 10, 'model': 'gpt-4o-mini'},
        neo4j_product_search=product_search,
        openai_client=openai_client
    )
    llm_result = await llm_strategy.search(
        component_type='power_source',
        user_message=query,
        master_parameters={},
        selected_components={},
        limit=5
    )
    print(f"\n✅ LLM combined found {len(llm_result.products)} products")

    # Close connections
    await product_search.close()
    await vector_strategy.close()

    print("\n" + "=" * 100)
    print("TEST COMPLETE")
    print("=" * 100)


if __name__ == "__main__":
    asyncio.run(main())
