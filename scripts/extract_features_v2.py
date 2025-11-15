#!/usr/bin/env python3
"""
Extract product features from Neo4j - Version 2
Extracts from:
1. attributes_ruleset text (comma-separated features)
2. Related Feature nodes (HAS_FEATURE relationships)
3. Related Process nodes (SUPPORTS_PROCESS relationships)
4. Related Material nodes (FOR_MATERIAL relationships)
"""

import asyncio
import json
import os
import re
from typing import Dict, List, Any, Set
from collections import Counter
from neo4j import AsyncGraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")


class FeatureExtractorV2:
    """Extract features from Neo4j using text and relationship data"""

    def __init__(self):
        self.driver = AsyncGraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )

    async def close(self):
        """Close Neo4j connection"""
        await self.driver.close()

    async def get_categories(self) -> List[str]:
        """Get all product categories"""
        query = """
        MATCH (n:Product)
        WHERE n.category IS NOT NULL
        RETURN DISTINCT n.category AS category
        ORDER BY category
        """
        async with self.driver.session() as session:
            result = await session.run(query)
            return [record["category"] async for record in result]

    async def extract_category_features(self, category: str) -> Dict[str, Any]:
        """Extract all features for a category"""
        print(f"\n{'='*70}")
        print(f"Extracting features for: {category}")
        print(f"{'='*70}")

        features_data = {
            "category": category,
            "features_from_attributes": [],
            "processes": [],
            "materials": [],
            "feature_nodes": []
        }

        async with self.driver.session() as session:
            # 1. Extract from attributes_ruleset
            print(f"1. Extracting from attributes_ruleset...")
            attr_query = """
            MATCH (n:Product {category: $category})
            WHERE n.attributes_ruleset IS NOT NULL
            RETURN n.attributes_ruleset AS attributes
            """
            result = await session.run(attr_query, category=category)
            all_attributes = []
            async for record in result:
                attr_text = record["attributes"]
                if attr_text:
                    # Split by comma and clean
                    attrs = [a.strip() for a in attr_text.split(',')]
                    all_attributes.extend(attrs)

            # Count and rank attributes
            attr_counter = Counter(all_attributes)
            features_data["features_from_attributes"] = [
                {"feature": feat, "count": count}
                for feat, count in attr_counter.most_common(30)
            ]
            print(f"   Found {len(attr_counter)} unique attributes")

            # 2. Extract supported processes
            print(f"2. Extracting supported processes...")
            process_query = """
            MATCH (n:Product {category: $category})-[:SUPPORTS_PROCESS]->(p:Process)
            RETURN DISTINCT p.item_name AS process
            """
            result = await session.run(process_query, category=category)
            processes = [record["process"] async for record in result if record["process"]]
            features_data["processes"] = processes
            print(f"   Found {len(processes)} processes: {processes}")

            # 3. Extract materials
            print(f"3. Extracting materials...")
            material_query = """
            MATCH (n:Product {category: $category})-[:FOR_MATERIAL]->(m:Material)
            RETURN DISTINCT m.item_name AS material
            """
            result = await session.run(material_query, category=category)
            materials = [record["material"] async for record in result if record["material"]]
            features_data["materials"] = materials
            print(f"   Found {len(materials)} materials: {materials}")

            # 4. Extract feature nodes
            print(f"4. Extracting feature nodes...")
            feature_query = """
            MATCH (n:Product {category: $category})-[:HAS_FEATURE]->(f:Feature)
            RETURN DISTINCT f.item_name AS feature
            """
            result = await session.run(feature_query, category=category)
            feature_nodes = [record["feature"] async for record in result if record["feature"]]
            features_data["feature_nodes"] = feature_nodes
            print(f"   Found {len(feature_nodes)} feature nodes: {feature_nodes[:10]}")

        return features_data

    def generate_prompt_guidance(self, features_data: Dict[str, Any]) -> str:
        """Generate user-friendly prompt guidance"""
        category = features_data["category"]
        lines = [f"\n📋 Available {category} Features:"]

        # Add top attributes
        attrs = features_data.get("features_from_attributes", [])
        if attrs:
            top_attrs = [a["feature"] for a in attrs[:10]]
            lines.append(f"\n  Key Features:")
            for attr in top_attrs:
                lines.append(f"    • {attr}")

        # Add processes
        processes = features_data.get("processes", [])
        if processes:
            lines.append(f"\n  Supported Processes: {', '.join(processes)}")

        # Add materials
        materials = features_data.get("materials", [])
        if materials:
            lines.append(f"\n  Supported Materials: {', '.join(materials)}")

        # Add feature highlights
        feature_nodes = features_data.get("feature_nodes", [])
        if feature_nodes:
            lines.append(f"\n  Additional Features: {', '.join(feature_nodes[:5])}")

        return "\n".join(lines)


async def main():
    """Main execution"""
    print("="*80)
    print("CATEGORY FEATURE EXTRACTION - Version 2")
    print("Extracting from: attributes, processes, materials, feature nodes")
    print("="*80)

    extractor = FeatureExtractorV2()

    try:
        # Get categories
        categories = await extractor.get_categories()
        print(f"\nFound {len(categories)} categories: {categories}")

        # Extract features for each category
        all_results = {}

        for category in categories:
            features_data = await extractor.extract_category_features(category)
            all_results[category] = features_data

        # Save to JSON
        output_file = "app/config/category_features.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)

        print(f"\n{'='*80}")
        print(f"✅ Features saved to: {output_file}")
        print(f"{'='*80}")

        # Generate and display prompt guidance
        print("\n" + "="*80)
        print("PROMPT GUIDANCE FOR EACH CATEGORY")
        print("="*80)

        for category, data in all_results.items():
            guidance = extractor.generate_prompt_guidance(data)
            print(guidance)

        # Summary statistics
        print("\n" + "="*80)
        print("SUMMARY STATISTICS")
        print("="*80)

        for category, data in all_results.items():
            print(f"\n{category}:")
            print(f"  Unique Attributes: {len(data['features_from_attributes'])}")
            print(f"  Processes: {len(data['processes'])}")
            print(f"  Materials: {len(data['materials'])}")
            print(f"  Feature Nodes: {len(data['feature_nodes'])}")

    finally:
        await extractor.close()

    print("\n" + "="*80)
    print("✅ Extraction Complete!")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
