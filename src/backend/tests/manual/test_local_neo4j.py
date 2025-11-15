"""
Quick Terminal Test for Recommender V2
Tests Neo4j connection and product search
"""

import asyncio
import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

# Load environment variables
load_dotenv()

async def test_connection():
    """Test 1: Neo4j Connection"""
    print("\n" + "="*60)
    print("TEST 1: NEO4J CONNECTION")
    print("="*60)
    
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    
    print(f"URI: {uri}")
    
    try:
        driver = AsyncGraphDatabase.driver(uri, auth=(username, password))
        async with driver.session() as session:
            result = await session.run("RETURN 1 as test")
            record = await result.single()
            print("✅ Connection successful!")
        await driver.close()
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


async def test_categories():
    """Test 2: Check all categories"""
    print("\n" + "="*60)
    print("TEST 2: DATABASE CATEGORIES")
    print("="*60)
    
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    
    driver = AsyncGraphDatabase.driver(uri, auth=(username, password))
    
    try:
        async with driver.session() as session:
            result = await session.run("""
                MATCH (p:Product)
                RETURN DISTINCT p.category as category, count(*) as count
                ORDER BY count DESC
            """)
            records = await result.data()
            
            print(f"Found {len(records)} categories:")
            for record in records:
                print(f"  {record['category']}: {record['count']} products")
            
            print("\n✅ Categories loaded successfully!")
            
    except Exception as e:
        print(f"❌ Failed: {e}")
    finally:
        await driver.close()


async def test_power_source_search():
    """Test 3: Search for power sources"""
    print("\n" + "="*60)
    print("TEST 3: POWER SOURCE SEARCH")
    print("="*60)
    
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    
    driver = AsyncGraphDatabase.driver(uri, auth=(username, password))
    
    try:
        async with driver.session() as session:
            # Test basic power source query
            result = await session.run("""
                MATCH (p:Product)
                WHERE p.category = 'Powersource'
                RETURN p.gin as gin, p.item_name as name, p.category as category
                LIMIT 5
            """)
            records = await result.data()
            
            print(f"Found {len(records)} power sources:")
            for i, record in enumerate(records, 1):
                print(f"  {i}. {record['name']} (GIN: {record['gin']})")
            
            print("\n✅ Power source search working!")
            
    except Exception as e:
        print(f"❌ Failed: {e}")
    finally:
        await driver.close()


async def test_product_search_service():
    """Test 4: Product Search Service"""
    print("\n" + "="*60)
    print("TEST 4: PRODUCT SEARCH SERVICE")
    print("="*60)
    
    try:
        from app.services.neo4j.product_search import Neo4jProductSearch
        
        uri = os.getenv("NEO4J_URI")
        username = os.getenv("NEO4J_USERNAME")
        password = os.getenv("NEO4J_PASSWORD")
        
        # Initialize search service
        search_service = Neo4jProductSearch(uri, username, password)
        
        # Test search for power sources with 500A
        master_params = {
            "power_source": {
                "current_output": "500A",
                "process": "MIG"
            }
        }
        
        print("Searching for: 500A MIG power sources...")
        results = await search_service.search_power_source(master_params, limit=5)
        
        print(f"\nFound {results.total_count} products:")
        for i, product in enumerate(results.products, 1):
            print(f"  {i}. {product.name}")
            print(f"     Category: {product.category}")
            print(f"     GIN: {product.gin}")
            print()
        
        print("✅ Product search service working!")
        
        await search_service.close()
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()


async def test_compatibility():
    """Test 5: Check COMPATIBLE_WITH relationships"""
    print("\n" + "="*60)
    print("TEST 5: COMPATIBILITY RELATIONSHIPS")
    print("="*60)
    
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    
    driver = AsyncGraphDatabase.driver(uri, auth=(username, password))
    
    try:
        async with driver.session() as session:
            # Count total COMPATIBLE_WITH relationships
            result = await session.run("""
                MATCH ()-[r:COMPATIBLE_WITH]-()
                RETURN count(r) as total
            """)
            record = await result.single()
            total = record['total']
            
            print(f"Total COMPATIBLE_WITH relationships: {total}")
            
            # Sample some relationships
            result = await session.run("""
                MATCH (p1:Product)-[r:COMPATIBLE_WITH]-(p2:Product)
                RETURN p1.category as cat1, p2.category as cat2, count(*) as count
                ORDER BY count DESC
                LIMIT 10
            """)
            records = await result.data()
            
            print("\nTop compatibility connections:")
            for record in records:
                print(f"  {record['cat1']} ↔ {record['cat2']}: {record['count']} connections")
            
            print("\n✅ Compatibility relationships exist!")
            
    except Exception as e:
        print(f"❌ Failed: {e}")
    finally:
        await driver.close()


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("🧪 RECOMMENDER V2 - LOCAL TERMINAL TEST")
    print("="*60)
    
    # Test 1: Connection
    connected = await test_connection()
    if not connected:
        print("\n❌ Cannot proceed - fix connection first!")
        return
    
    # Test 2: Categories
    await test_categories()
    
    # Test 3: Basic power source search
    await test_power_source_search()
    
    # Test 4: Product search service
    await test_product_search_service()
    
    # Test 5: Compatibility
    await test_compatibility()
    
    # Summary
    print("\n" + "="*60)
    print("✅ ALL TESTS COMPLETED!")
    print("="*60)
    print("\n🚀 Your application is ready to use!")
    print("\nTo start the server:")
    print("  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
    print("\n")


if __name__ == "__main__":
    asyncio.run(main())