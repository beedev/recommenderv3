#!/usr/bin/env python3
"""
Test Powersource Accessories category with product name extraction enabled
Check if product names contain extractable specifications
"""
import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from extract_features_llm import LLMFeatureExtractor

async def test_powersource_accessories():
    """Test extraction on Powersource Accessories category with product name analysis"""
    print("="*80)
    print("TESTING POWERSOURCE ACCESSORIES WITH PRODUCT NAME EXTRACTION")
    print("Checking if product names contain extractable specifications")
    print("="*80)

    extractor = LLMFeatureExtractor()

    try:
        # Get Powersource Accessories products
        print("\n📦 Fetching Powersource Accessories products from Neo4j...")
        products = await extractor.get_category_products("Powersource Accessories", limit=50)
        print(f"   Found {len(products)} Powersource Accessories products")

        # Show ALL product names to see what we're working with
        print("\n📋 Product names (showing all to check for specs):")
        for i, product in enumerate(products, 1):
            print(f"   {i:2d}. {product['name']}")

        # Extract features with multi-call consensus
        print("\n🤖 Extracting features with 3 LLM calls (2/3 consensus)...")
        print("   Analyzing product NAMES for any extractable specs...")
        features = await extractor.extract_features_with_llm("Powersource Accessories", products)

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

        print(f"\n✨ Key Features: {len(features.get('key_features', []))}")
        for kf in features.get("key_features", []):
            print(f"  • {kf}")

        # Summary
        print("\n" + "="*80)
        print("EXTRACTION SUMMARY")
        print("="*80)

        total_features = (
            len(features.get('numeric_specs', [])) +
            len(features.get('categorical_features', [])) +
            len(features.get('capabilities', [])) +
            len(features.get('key_features', []))
        )

        if total_features == 0:
            print("⚠️  NO FEATURES EXTRACTED")
            print("   This is expected if product names are just SKUs/part numbers")
            print("   without meaningful specifications.")
        else:
            print(f"✅ {total_features} features extracted successfully!")

        # Save results
        output = {
            "category": "Powersource Accessories",
            "product_count": len(products),
            "all_product_names": [p['name'] for p in products],
            "consensus_threshold": "2 out of 3",
            "features": features,
            "guidance": extractor.format_feature_guidance("Powersource Accessories", features)
        }

        output_file = "test_powersource_accessories_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Results saved to: {output_file}")

    finally:
        await extractor.close()

if __name__ == "__main__":
    asyncio.run(test_powersource_accessories())
