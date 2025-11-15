#!/usr/bin/env python3
"""
Test Interconn category with product name extraction enabled
This should capture cable lengths from product names like "Cable 3m"
"""
import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from extract_features_llm import LLMFeatureExtractor

async def test_interconn():
    """Test extraction on Interconn category with product name analysis"""
    print("="*80)
    print("TESTING INTERCONN CATEGORY WITH PRODUCT NAME EXTRACTION")
    print("This should capture cable lengths from product names")
    print("="*80)

    extractor = LLMFeatureExtractor()

    try:
        # Get Interconn products
        print("\n📦 Fetching Interconn products from Neo4j...")
        products = await extractor.get_category_products("Interconn", limit=50)
        print(f"   Found {len(products)} Interconn products")

        # Show sample product names to see what we're working with
        print("\n📋 Sample product names:")
        for i, product in enumerate(products[:5], 1):
            print(f"   {i}. {product['name']}")

        # Extract features with multi-call consensus
        print("\n🤖 Extracting features with 3 LLM calls (2/3 consensus)...")
        print("   Analyzing product NAMES for cable lengths (e.g., '3m', '5m')...")
        features = await extractor.extract_features_with_llm("Interconn", products)

        # Display results
        print("\n" + "="*80)
        print("CONSENSUS RESULTS (2 out of 3 LLM calls)")
        print("="*80)

        print(f"\n📊 Numeric Specs: {len(features.get('numeric_specs', []))}")
        for spec in features.get("numeric_specs", []):
            print(f"  • {spec.get('name', 'Unknown')}: {spec.get('display', 'N/A')}")

        print(f"\n🏷️  Categorical Features: {len(features.get('categorical_features', []))}")
        for feat in features.get("categorical_features", []):
            print(f"  • {feat.get('name', 'Unknown')}: {feat.get('display', 'N/A')}")

        print(f"\n⚡ Capabilities: {len(features.get('capabilities', []))}")
        for cap in features.get("capabilities", []):
            print(f"  • {cap.get('name', 'Unknown')}: {cap.get('display', 'N/A')}")

        # Check if cable length was extracted
        print("\n" + "="*80)
        print("CABLE LENGTH EXTRACTION CHECK")
        print("="*80)

        cable_length_found = False
        for spec in features.get("numeric_specs", []):
            if "cable" in spec.get("name", "").lower() or "length" in spec.get("name", "").lower():
                print(f"✅ SUCCESS: Cable Length found!")
                print(f"   Name: {spec.get('name')}")
                print(f"   Display: {spec.get('display')}")
                print(f"   Min: {spec.get('min')}, Max: {spec.get('max')}, Unit: {spec.get('unit')}")
                cable_length_found = True
                break

        if not cable_length_found:
            print("⚠️  WARNING: No Cable Length numeric spec found")
            print("   Check if product names actually contain cable length info")

        # Save results for comparison
        output = {
            "category": "Interconn",
            "product_count": len(products),
            "sample_product_names": [p['name'] for p in products[:10]],
            "consensus_threshold": "2 out of 3",
            "features": features,
            "guidance": extractor.format_feature_guidance("Interconn", features)
        }

        output_file = "test_interconn_with_names_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Results saved to: {output_file}")

    finally:
        await extractor.close()

if __name__ == "__main__":
    asyncio.run(test_interconn())
