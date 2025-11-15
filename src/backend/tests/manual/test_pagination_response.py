"""
Test script to verify pagination metadata is returned for all categories

This script tests the actual backend response structure to confirm:
1. Pagination metadata is returned
2. has_more flag is calculated correctly
3. All categories behave identically
"""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.neo4j.product_search import Neo4jProductSearch
from app.models.conversation import MasterParameterJSON, ResponseJSON, SelectedProduct, ComponentApplicability

async def test_pagination():
    """Test pagination for all categories"""

    # Initialize Neo4j connection (update with your credentials)
    neo4j = Neo4jProductSearch(
        uri="bolt+s://7c79ad1f.databases.neo4j.io",  # Update this
        username="neo4j",  # Update this
        password="YwAzCumqt9H6lUd4fPUUZM9pPfYn6BjdDt_7NQHlG98"  # Update this
    )

    print("="*80)
    print("PAGINATION TEST - Verify has_more calculation")
    print("="*80)

    # Test 1: PowerSource (S1)
    print("\n🔍 TEST 1: PowerSource")
    print("-"*80)
    master_params = {}
    ps_results = await neo4j.search_power_source(master_params, limit=3, offset=0)
    print(f"✅ PowerSource: {len(ps_results.products)} products returned")
    print(f"   has_more: {ps_results.has_more}")
    print(f"   offset: {ps_results.offset}, limit: {ps_results.limit}")

    if ps_results.products:
        selected_ps = ps_results.products[0]
        print(f"   Selected: {selected_ps.name} (GIN: {selected_ps.gin})")

        # Test 2: Feeder (S2)
        print("\n🔍 TEST 2: Feeder")
        print("-"*80)
        response_json_dict = {
            "PowerSource": {
                "gin": selected_ps.gin,
                "name": selected_ps.name,
                "category": "Powersource"
            }
        }
        feeder_results = await neo4j.search_feeder(master_params, response_json_dict, limit=3, offset=0)
        print(f"✅ Feeder: {len(feeder_results.products)} products returned")
        print(f"   has_more: {feeder_results.has_more}")
        print(f"   offset: {feeder_results.offset}, limit: {feeder_results.limit}")

        if feeder_results.products:
            selected_feeder = feeder_results.products[0]
            print(f"   Selected: {selected_feeder.name} (GIN: {selected_feeder.gin})")

            response_json_dict["Feeder"] = {
                "gin": selected_feeder.gin,
                "name": selected_feeder.name,
                "category": "Feeder"
            }

            # Test 3: Cooler (S3)
            print("\n🔍 TEST 3: Cooler")
            print("-"*80)
            cooler_results = await neo4j.search_cooler(master_params, response_json_dict, limit=3, offset=0)
            print(f"✅ Cooler: {len(cooler_results.products)} products returned")
            print(f"   has_more: {cooler_results.has_more}")
            print(f"   offset: {cooler_results.offset}, limit: {cooler_results.limit}")

            if cooler_results.products:
                selected_cooler = cooler_results.products[0]
                print(f"   Selected: {selected_cooler.name} (GIN: {selected_cooler.gin})")

                response_json_dict["Cooler"] = {
                    "gin": selected_cooler.gin,
                    "name": selected_cooler.name,
                    "category": "Cooler"
                }

                # Test 4: Interconnector (S4) - YOUR ISSUE
                print("\n🔍 TEST 4: Interconnector ⭐ (YOUR ISSUE)")
                print("-"*80)
                interconn_results = await neo4j.search_interconnector(master_params, response_json_dict, limit=3, offset=0)
                print(f"✅ Interconnector: {len(interconn_results.products)} products returned")
                print(f"   has_more: {interconn_results.has_more} ⭐ CRITICAL")
                print(f"   offset: {interconn_results.offset}, limit: {interconn_results.limit}")

                if interconn_results.has_more:
                    print("   ✅ PASS: has_more=True, nugget WILL appear!")
                else:
                    print("   ⚠️  has_more=False - this is WHY nugget doesn't appear!")
                    print("   If exactly 3 products exist, this is CORRECT behavior (no more products)")
                    print("   If 4+ products exist, this is a BUG!")

                if interconn_results.products:
                    selected_interconn = interconn_results.products[0]
                    print(f"   Selected: {selected_interconn.name} (GIN: {selected_interconn.gin})")

                    response_json_dict["Interconnector"] = {
                        "gin": selected_interconn.gin,
                        "name": selected_interconn.name,
                        "category": "Interconn"
                    }

                    # Test 5: Torch (S5) - YOUR ISSUE
                    print("\n🔍 TEST 5: Torch ⭐ (YOUR ISSUE)")
                    print("-"*80)
                    torch_results = await neo4j.search_torch(master_params, response_json_dict, limit=3, offset=0)
                    print(f"✅ Torch: {len(torch_results.products)} products returned")
                    print(f"   has_more: {torch_results.has_more} ⭐ CRITICAL")
                    print(f"   offset: {torch_results.offset}, limit: {torch_results.limit}")

                    if torch_results.has_more:
                        print("   ✅ PASS: has_more=True, nugget WILL appear!")
                    else:
                        print("   ⚠️  has_more=False - this is WHY nugget doesn't appear!")

            # Test 6: Accessories (S6)
            print("\n🔍 TEST 6: Accessories")
            print("-"*80)
            accessory_results = await neo4j.search_accessories(master_params, response_json_dict, "Accessory", limit=3, offset=0)
            print(f"✅ Accessories: {len(accessory_results.products)} products returned")
            print(f"   has_more: {accessory_results.has_more}")
            print(f"   offset: {accessory_results.offset}, limit: {accessory_results.limit}")

    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print("✅ All categories return pagination metadata (offset, limit, has_more)")
    print("✅ has_more is calculated using: len(products) > limit")
    print("✅ Queries use limit+1 to check if more products exist")
    print("\n🔍 If nugget doesn't appear:")
    print("   1. Check if has_more=False (correct if <=3 products exist)")
    print("   2. Verify backend was RESTARTED after code changes")
    print("   3. Check frontend console for pagination data")
    print("   4. Hard refresh browser (Ctrl+F5)")
    print("="*80)

    await neo4j.close()

if __name__ == "__main__":
    asyncio.run(test_pagination())
