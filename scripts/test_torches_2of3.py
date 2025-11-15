#!/usr/bin/env python3
"""
Test Torches category with 2 out of 3 consensus threshold
"""
import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from extract_features_llm import LLMFeatureExtractor

async def test_torches():
    """Test extraction on Torches category"""
    print("="*80)
    print("TESTING TORCHES CATEGORY WITH 2/3 CONSENSUS")
    print("="*80)

    extractor = LLMFeatureExtractor()

    try:
        # Get Torches products
        print("\n📦 Fetching Torches products from Neo4j...")
        products = await extractor.get_category_products("Torches", limit=50)
        print(f"   Found {len(products)} Torches products")

        # Extract features with multi-call consensus
        print("\n🤖 Extracting features with 3 LLM calls (2/3 consensus)...")
        features = await extractor.extract_features_with_llm("Torches", products)

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
        for feat in features.get("key_features", [])[:5]:
            print(f"  • {feat}")

        # Check for hallucination
        print("\n" + "="*80)
        print("HALLUCINATION CHECK")
        print("="*80)

        hallucination_found = False
        for feat in features.get("categorical_features", []):
            if feat.get("name") == "Material Compatibility":
                print("❌ HALLUCINATION DETECTED: Material Compatibility found in results!")
                print(f"   Options: {feat.get('options', [])}")
                hallucination_found = True

        if not hallucination_found:
            print("✅ SUCCESS: No Material Compatibility hallucination detected!")

        # Save results for comparison
        output = {
            "category": "Torches",
            "product_count": len(products),
            "consensus_threshold": "2 out of 3",
            "features": features,
            "guidance": extractor.format_feature_guidance("Torches", features)
        }

        output_file = "test_torches_2of3_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Results saved to: {output_file}")

    finally:
        await extractor.close()

    print("\n" + "="*80)
    print("✅ TEST COMPLETE")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_torches())
