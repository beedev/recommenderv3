#!/usr/bin/env python3
"""
Demo: LLM-Powered Feature Extraction
Shows how GPT-4 intelligently extracts features from product descriptions
"""

import asyncio
import sys
sys.path.insert(0, 'docs/scripts')
from extract_features_llm import LLMFeatureExtractor


async def demo():
    """Demo extraction for Powersource category"""
    print("="*80)
    print("DEMO: LLM-Powered Feature Extraction")
    print("="*80)

    extractor = LLMFeatureExtractor()

    try:
        print("\n📊 Analyzing Powersource products...")
        print("   This will use GPT-4 to intelligently extract specifications\n")

        # Process single category
        results = await extractor.extract_all_categories(["Powersource"])

        if "Powersource" in results:
            data = results["Powersource"]

            # Display extracted features
            print("\n" + "="*80)
            print("EXTRACTED FEATURES")
            print("="*80)
            print(data["guidance"])

            # Show raw JSON structure
            print("\n" + "="*80)
            print("RAW JSON STRUCTURE (for integration)")
            print("="*80)

            import json
            print(json.dumps(data["features"], indent=2))

    finally:
        await extractor.close()

    print("\n" + "="*80)
    print("✅ Demo Complete!")
    print("="*80)
    print("\nTo run full extraction:")
    print("  python docs/scripts/extract_features_llm.py")


if __name__ == "__main__":
    asyncio.run(demo())
