#!/usr/bin/env python3
"""
Run full extraction on all categories with 2/3 consensus
Automated script (no user prompts)
"""
import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from extract_features_llm import LLMFeatureExtractor

async def main():
    print("="*80)
    print("FULL CATEGORY EXTRACTION WITH 2/3 CONSENSUS")
    print("Processing all 14 categories (estimated time: 15-30 minutes)")
    print("="*80)

    extractor = LLMFeatureExtractor()

    try:
        # Get all categories
        all_categories = await extractor.get_categories()
        print(f"\n📦 Found {len(all_categories)} categories:")
        for i, cat in enumerate(all_categories, 1):
            print(f"   {i}. {cat}")

        # Extract features for all categories
        print(f"\n🚀 Starting extraction...")
        print(f"   • 3 LLM calls per category")
        print(f"   • 2 out of 3 consensus required")
        print(f"   • Analyzing up to 30 products per category")
        print()

        results = await extractor.extract_all_categories(all_categories)

        # Display summary
        print("\n" + "="*80)
        print("EXTRACTION COMPLETE - SUMMARY")
        print("="*80)

        for category, data in results.items():
            if "error" not in data:
                features = data["features"]
                print(f"\n✅ {category}:")
                print(f"   Products analyzed: {data['product_count']}")
                print(f"   Numeric specs: {len(features.get('numeric_specs', []))}")
                print(f"   Categorical features: {len(features.get('categorical_features', []))}")
                print(f"   Capabilities: {len(features.get('capabilities', []))}")
                print(f"   Key features: {len(features.get('key_features', []))}")
            else:
                print(f"\n❌ {category}: {data['error']}")

        # Save results
        output_file = "../../app/config/category_features_llm.json"
        print(f"\n💾 Saving results to: {output_file}")

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Results saved successfully!")

        # Display detailed results
        print("\n" + "="*80)
        print("DETAILED FEATURE EXTRACTION RESULTS")
        print("="*80)

        for category, data in results.items():
            if "error" not in data:
                print(data["guidance"])

    finally:
        await extractor.close()

    print("\n" + "="*80)
    print("✅ FULL EXTRACTION COMPLETE!")
    print("="*80)
    print(f"\nResults saved to: app/config/category_features_llm.json")
    print("Ready to use in production!")

if __name__ == "__main__":
    asyncio.run(main())
