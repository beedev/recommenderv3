#!/usr/bin/env python3
"""
LLM-Powered Feature Extraction from Neo4j Product Database with Multi-Call Consensus

Uses OpenAI GPT-4 with STRICT anti-hallucination constraints and multi-call consensus
to extract ONLY explicitly stated features from product descriptions.

Key improvements:
1. Multi-call consensus (3 LLM calls, include features appearing in 2+ calls)
2. Strict anti-hallucination prompt (NO assumptions, NO general knowledge)
3. Increased product sampling (30 products instead of 10)
4. Increased description length (500 chars instead of 200)
5. Full validation to prevent KeyErrors
6. Safety checks in all formatting operations
"""

import asyncio
import json
import os
from typing import Dict, List, Any
from collections import defaultdict
from neo4j import AsyncGraphDatabase
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class LLMFeatureExtractor:
    """Extract features using LLM intelligence with multi-call consensus"""

    def __init__(self):
        self.neo4j_driver = AsyncGraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )
        self.openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        self.extracted_features = {}

    async def close(self):
        """Close connections"""
        await self.neo4j_driver.close()

    async def get_categories(self) -> List[str]:
        """Get all product categories"""
        query = """
        MATCH (n:Product)
        WHERE n.category IS NOT NULL
        RETURN DISTINCT n.category AS category
        ORDER BY category
        """
        async with self.neo4j_driver.session() as session:
            result = await session.run(query)
            return [record["category"] async for record in result]

    async def get_category_products(self, category: str, limit: int = 50) -> List[Dict]:
        """Get product descriptions for a category"""
        query = """
        MATCH (n:Product {category: $category})
        RETURN
            n.item_name AS name,
            n.description_catalogue AS desc_catalogue,
            n.description_ruleset AS desc_ruleset,
            n.clean_description AS clean_desc,
            n.attributes_ruleset AS attributes
        LIMIT $limit
        """

        async with self.neo4j_driver.session() as session:
            result = await session.run(query, category=category, limit=limit)
            products = []
            async for record in result:
                products.append({
                    "name": record["name"],
                    "desc_catalogue": record["desc_catalogue"],
                    "desc_ruleset": record["desc_ruleset"],
                    "clean_desc": record["clean_desc"],
                    "attributes": record["attributes"]
                })
            return products

    async def _call_llm_once(self, prompt: str) -> Dict[str, Any]:
        """Single LLM call for feature extraction"""
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a technical product analyst. Extract ONLY explicitly stated features from product descriptions. DO NOT add assumptions or general industry knowledge."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Low temperature for consistent extraction
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            return self._validate_feature_structure(result)

        except Exception as e:
            print(f"   ⚠️  LLM call failed: {e}")
            return {
                "numeric_specs": [],
                "categorical_features": [],
                "capabilities": [],
                "key_features": []
            }

    def _validate_feature_structure(self, features: Dict) -> Dict:
        """Ensure all required keys exist to prevent KeyErrors"""
        validated = {
            "numeric_specs": [],
            "categorical_features": [],
            "capabilities": [],
            "key_features": []
        }

        # Validate numeric specs
        for spec in features.get("numeric_specs", []):
            if all(k in spec for k in ["name", "display"]):
                validated["numeric_specs"].append(spec)

        # Validate categorical features
        for feat in features.get("categorical_features", []):
            if all(k in feat for k in ["name", "display", "options"]):
                validated["categorical_features"].append(feat)

        # Validate capabilities
        for cap in features.get("capabilities", []):
            if all(k in cap for k in ["name", "display"]):
                validated["capabilities"].append(cap)

        # Key features are simple strings
        validated["key_features"] = features.get("key_features", [])

        return validated

    def _build_consensus(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build consensus from multiple LLM calls - only include features appearing in 2+ calls"""

        if not results:
            return {"numeric_specs": [], "categorical_features": [], "capabilities": [], "key_features": []}

        print(f"   🔍 Building consensus from {len(results)} LLM calls...")

        # For each feature type, find intersection
        consensus = {
            "numeric_specs": self._consensus_numeric_specs(results),
            "categorical_features": self._consensus_categorical(results),
            "capabilities": self._consensus_capabilities(results),
            "key_features": self._consensus_key_features(results)
        }

        print(f"   ✅ Consensus: {len(consensus['numeric_specs'])} numeric, "
              f"{len(consensus['categorical_features'])} categorical, "
              f"{len(consensus['capabilities'])} capabilities, "
              f"{len(consensus['key_features'])} key features")

        return consensus

    def _consensus_numeric_specs(self, results: List[Dict]) -> List[Dict]:
        """Only include numeric specs that appear in 2+ calls"""
        if not results:
            return []

        # Group by spec name
        spec_groups = defaultdict(list)
        for result in results:
            for spec in result.get("numeric_specs", []):
                spec_groups[spec.get("name", "")].append(spec)

        # Only keep specs that appear in 2+ calls (majority consensus)
        consensus_specs = []
        for name, specs in spec_groups.items():
            if len(specs) >= 2 and name:  # Appears in 2+ calls
                consensus_specs.append(specs[0])  # Use first occurrence

        return consensus_specs

    def _consensus_categorical(self, results: List[Dict]) -> List[Dict]:
        """Only include categorical features that appear in 2+ calls"""
        if not results:
            return []

        # Group by feature name
        feat_groups = defaultdict(list)
        for result in results:
            for feat in result.get("categorical_features", []):
                feat_groups[feat.get("name", "")].append(feat)

        # Only keep features that appear in 2+ calls (majority consensus)
        consensus_feats = []
        for name, feats in feat_groups.items():
            if len(feats) >= 2 and name:
                # Use intersection of options (only options that appear in ALL matching calls)
                all_options = [set(f.get("options", [])) for f in feats]
                common_options = set.intersection(*all_options) if all_options else set()

                if common_options:
                    consensus_feats.append({
                        "name": name,
                        "options": sorted(list(common_options)),
                        "display": ", ".join(sorted(common_options))
                    })

        return consensus_feats

    def _consensus_capabilities(self, results: List[Dict]) -> List[Dict]:
        """Only include capabilities that appear in 2+ calls"""
        if not results:
            return []

        # Group by capability name
        cap_groups = defaultdict(list)
        for result in results:
            for cap in result.get("capabilities", []):
                cap_groups[cap.get("name", "")].append(cap)

        # Only keep capabilities that appear in 2+ calls (majority consensus)
        consensus_caps = []
        for name, caps in cap_groups.items():
            if len(caps) >= 2 and name:
                consensus_caps.append(caps[0])

        return consensus_caps

    def _consensus_key_features(self, results: List[Dict]) -> List[str]:
        """Only include key features that appear in 2+ calls"""
        if not results:
            return []

        # Count occurrences of each feature
        feature_counts = defaultdict(int)
        for result in results:
            for feat in result.get("key_features", []):
                feature_counts[feat] += 1

        # Only keep features that appear in 2+ calls (majority consensus)
        consensus_features = [
            feat for feat, count in feature_counts.items()
            if count >= 2
        ]

        return consensus_features

    async def extract_features_with_llm(self, category: str, products: List[Dict], num_calls: int = 3) -> Dict[str, Any]:
        """Use LLM with multi-call consensus to extract features (default: 3 calls)"""

        print(f"\n🤖 Analyzing {len(products)} {category} products with GPT-4 (consensus from {num_calls} calls)...")

        # Prepare product summaries (analyze up to 30 products)
        sample_size = min(len(products), 30)
        product_summaries = []
        for i, product in enumerate(products[:sample_size], 1):
            summary = f"{i}. {product['name']}\n"

            # Combine ALL description fields
            desc_parts = []
            if product.get('clean_desc'):
                desc_parts.append(product['clean_desc'])
            if product.get('desc_catalogue'):
                desc_parts.append(product['desc_catalogue'])
            if product.get('desc_ruleset'):
                desc_parts.append(product['desc_ruleset'])

            combined_desc = " | ".join(filter(None, desc_parts))
            if combined_desc:
                summary += f"   Description: {combined_desc[:500]}...\n"

            if product.get('attributes'):
                summary += f"   Attributes: {product['attributes'][:200]}...\n"

            product_summaries.append(summary)

        products_text = "\n".join(product_summaries)

        # LLM prompt for feature extraction with STRICT anti-hallucination rules
        prompt = f"""🚨 CRITICAL EXTRACTION RULES - YOU MUST FOLLOW EXACTLY:

1. EXTRACT features from TWO sources:
   ✅ Product NAMES (item_name) - Extract explicit specs like "3m", "500A", "Water-cooled"
   ✅ Product DESCRIPTIONS - Extract detailed specifications

2. ALLOWED extractions from product names:
   ✅ "Cable 3m" or "Interconnector 3m" → Extract "Cable Length: 3m"
   ✅ "PSA-500A" or "500A Accessory" → Extract "Current Rating: 500A"
   ✅ "Water-cooled Feeder" → Extract "Cooling Type: Water"
   ✅ "Air-cooled 400A" → Extract "Cooling Type: Air" + "Current: 400A"
   ✅ Numbers with units (3m, 5m, 500A, 400V) → Extract as numeric specs

3. DO NOT add features based on:
   ❌ General welding industry knowledge
   ❌ Assumptions about what products "should" support
   ❌ Category name alone (e.g., "MIG" category doesn't mean "Steel compatible")
   ❌ Context from other similar products

4. STRICT EXAMPLES:
   ✅ Name: "Cable 3m", Description: "High quality" → Extract "Cable Length: 3m"
   ✅ Description says "Water-cooled system" → Extract "Cooling Type: Water"
   ✅ Description says "430A output" → Extract "Current Output: 430A"
   ❌ Torch product, NO material mentioned anywhere → DO NOT add "Steel, Aluminum"
   ❌ NO voltage mentioned → DO NOT assume "380V-460V"
   ❌ Product name is just "MIG Torch" → DO NOT assume "Steel compatibility"

5. When in doubt → LEAVE IT OUT. Empty arrays are better than hallucinations.

PRODUCTS TO ANALYZE ({len(product_summaries)} {category} products):
{products_text}

Return a JSON object with this structure (include ONLY features explicitly mentioned):
{{
  "numeric_specs": [
    {{
      "name": "Current Output",
      "min": 200,
      "max": 600,
      "unit": "A",
      "display": "200A - 600A"
    }}
  ],
  "categorical_features": [
    {{
      "name": "Cooling Type",
      "options": ["Air", "Water"],
      "display": "Air or Water"
    }}
  ],
  "capabilities": [
    {{
      "name": "Supported Processes",
      "values": ["MIG/GMAW"],
      "display": "MIG"
    }}
  ],
  "key_features": [
    "Portable design",
    "IP44 protection rating"
  ]
}}

REMEMBER: If a feature is NOT explicitly mentioned in the descriptions → DO NOT include it.
"""

        # Call LLM multiple times
        print(f"   📞 Calling LLM {num_calls} times for consensus...")
        results = []
        for i in range(num_calls):
            print(f"   📞 Call {i+1}/{num_calls}...")
            result = await self._call_llm_once(prompt)
            results.append(result)

            # Show what this call extracted
            print(f"      • {len(result.get('numeric_specs', []))} numeric specs")
            print(f"      • {len(result.get('categorical_features', []))} categorical features")
            print(f"      • {len(result.get('capabilities', []))} capabilities")
            print(f"      • {len(result.get('key_features', []))} key features")

        # Build consensus (only features appearing in 2+ calls)
        consensus = self._build_consensus(results)

        return consensus

    def format_feature_guidance(self, category: str, features: Dict[str, Any]) -> str:
        """Format features into user-friendly guidance"""
        lines = [f"\n📋 {category} - Available Features & Specifications:"]

        # Numeric specifications
        if features.get("numeric_specs"):
            lines.append("\n  🔢 Specifications:")
            for spec in features["numeric_specs"]:
                # Safety check before accessing keys
                if 'name' in spec and 'display' in spec:
                    lines.append(f"    • {spec['name']}: {spec['display']}")

        # Categorical features
        if features.get("categorical_features"):
            lines.append("\n  🏷️  Options:")
            for feat in features["categorical_features"]:
                # Safety check before accessing keys
                if 'name' in feat and 'display' in feat:
                    lines.append(f"    • {feat['name']}: {feat['display']}")

        # Capabilities
        if features.get("capabilities"):
            lines.append("\n  ⚡ Capabilities:")
            for cap in features["capabilities"]:
                # Safety check before accessing keys
                if 'name' in cap and 'display' in cap:
                    lines.append(f"    • {cap['name']}: {cap['display']}")

        # Key features
        if features.get("key_features"):
            lines.append("\n  ✨ Key Features:")
            for feat in features["key_features"][:5]:
                lines.append(f"    • {feat}")

        return "\n".join(lines)

    async def extract_all_categories(self, categories: List[str] = None) -> Dict[str, Any]:
        """Extract features for all categories using LLM with multi-call consensus"""

        if categories is None:
            categories = await self.get_categories()

        all_features = {}

        for category in categories:
            print(f"\n{'='*70}")
            print(f"Processing: {category}")
            print(f"{'='*70}")

            try:
                # Get product data
                products = await self.get_category_products(category, limit=50)

                if not products:
                    print(f"   ⚠️  No products found for {category}")
                    continue

                print(f"   Found {len(products)} products")

                # Extract features with LLM (multi-call consensus)
                features = await self.extract_features_with_llm(category, products)

                all_features[category] = {
                    "category": category,
                    "product_count": len(products),
                    "features": features,
                    "guidance": self.format_feature_guidance(category, features)
                }

            except Exception as e:
                print(f"   ❌ Error processing {category}: {e}")
                import traceback
                traceback.print_exc()
                all_features[category] = {
                    "category": category,
                    "error": str(e)
                }

        return all_features


async def main():
    """Main execution with human review"""
    print("="*80)
    print("LLM-POWERED FEATURE EXTRACTION WITH MULTI-CALL CONSENSUS")
    print("Using GPT-4 with strict anti-hallucination constraints")
    print("Only features appearing in 2+ LLM calls will be included")
    print("="*80)

    extractor = LLMFeatureExtractor()

    try:
        # Get categories
        all_categories = await extractor.get_categories()
        print(f"\nFound {len(all_categories)} categories: {all_categories}")

        # Ask user which categories to process
        print("\n" + "="*80)
        print("SELECT CATEGORIES TO PROCESS")
        print("="*80)
        print("Options:")
        print("  1. All categories (may take 15-30 minutes with 3 LLM calls per category)")
        print("  2. Primary categories only (Powersource, Feeder, Cooler, Torch, Interconn)")
        print("  3. Single category (specify)")
        print("  4. Cancel")

        choice = input("\nYour choice (1-4): ").strip()

        if choice == "1":
            categories_to_process = all_categories
        elif choice == "2":
            categories_to_process = ["Powersource", "Feeder", "Cooler", "Torches", "Interconn"]
        elif choice == "3":
            print(f"\nAvailable: {', '.join(all_categories)}")
            cat = input("Enter category name: ").strip()
            if cat in all_categories:
                categories_to_process = [cat]
            else:
                print(f"❌ Invalid category: {cat}")
                return
        else:
            print("Cancelled.")
            return

        # Extract features
        print(f"\n🚀 Processing {len(categories_to_process)} categories with multi-call consensus...")
        results = await extractor.extract_all_categories(categories_to_process)

        # Display results
        print("\n" + "="*80)
        print("EXTRACTED FEATURES - REVIEW")
        print("="*80)

        for category, data in results.items():
            if "error" not in data:
                print(data["guidance"])

        # Ask to save
        print("\n" + "="*80)
        print("SAVE RESULTS?")
        print("="*80)

        save = input("Save to category_features_llm.json? (y/n): ").strip().lower()

        if save == 'y':
            output_file = "app/config/category_features_llm.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            print(f"\n✅ Saved to: {output_file}")

            # Generate summary
            print("\n" + "="*80)
            print("SUMMARY")
            print("="*80)

            for category, data in results.items():
                if "error" not in data:
                    features = data["features"]
                    print(f"\n{category}:")
                    print(f"  Products analyzed: {data['product_count']}")
                    print(f"  Numeric specs: {len(features.get('numeric_specs', []))}")
                    print(f"  Categorical features: {len(features.get('categorical_features', []))}")
                    print(f"  Capabilities: {len(features.get('capabilities', []))}")
                    print(f"  Key features: {len(features.get('key_features', []))}")
        else:
            print("\n❌ Results not saved. You can re-run the script to try again.")

    finally:
        await extractor.close()

    print("\n" + "="*80)
    print("✅ LLM Feature Extraction Complete!")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
