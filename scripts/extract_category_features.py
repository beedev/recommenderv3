#!/usr/bin/env python3
"""
Extract core features and their ranges from Neo4j for each product category.
This data will be used to guide users in formulating better search queries.
"""

import asyncio
import json
import os
import re
from typing import Dict, List, Any, Set
from collections import defaultdict
from neo4j import AsyncGraphDatabase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")


class CategoryFeatureExtractor:
    """Extract features and ranges from Neo4j product categories"""

    def __init__(self):
        self.driver = AsyncGraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )
        self.category_features = {}

    async def close(self):
        """Close Neo4j connection"""
        await self.driver.close()

    async def discover_categories(self) -> List[str]:
        """Discover all product categories in the database"""
        query = """
        MATCH (n:Product)
        WHERE n.category IS NOT NULL
        RETURN DISTINCT n.category AS category
        ORDER BY category
        """

        async with self.driver.session() as session:
            result = await session.run(query)
            categories = [record["category"] async for record in result]
            return categories

    def extract_numeric_value(self, text: str) -> float:
        """Extract numeric value from text (e.g., '500 A' -> 500.0)"""
        if not text:
            return None

        # Handle ranges like "200-300"
        if '-' in str(text) and not str(text).startswith('-'):
            parts = str(text).split('-')
            try:
                return float(re.sub(r'[^\d.]', '', parts[0]))
            except:
                return None

        # Extract first number
        match = re.search(r'(\d+\.?\d*)', str(text))
        if match:
            try:
                return float(match.group(1))
            except:
                return None
        return None

    def categorize_values(self, values: List[Any], property_name: str) -> Dict[str, Any]:
        """Categorize values as numeric range or categorical list"""
        if not values:
            return {"type": "empty", "values": []}

        # Remove None values
        values = [v for v in values if v is not None and str(v).strip()]

        if not values:
            return {"type": "empty", "values": []}

        # Check if numeric property
        numeric_keywords = ['current', 'voltage', 'output', 'capacity', 'amperage',
                           'rating', 'size', 'length', 'diameter', 'weight', 'duty']
        is_numeric_property = any(keyword in property_name.lower() for keyword in numeric_keywords)

        # Try to extract numeric values
        numeric_values = []
        for v in values:
            num_val = self.extract_numeric_value(v)
            if num_val is not None:
                numeric_values.append(num_val)

        # If >= 50% of values are numeric and it's a numeric property, treat as range
        if len(numeric_values) >= len(values) * 0.5 and is_numeric_property:
            unique_nums = sorted(set(numeric_values))
            if len(unique_nums) > 1:
                return {
                    "type": "numeric_range",
                    "min": min(unique_nums),
                    "max": max(unique_nums),
                    "values": unique_nums,
                    "display": f"{min(unique_nums):.0f} - {max(unique_nums):.0f}"
                }
            else:
                return {
                    "type": "numeric_single",
                    "value": unique_nums[0],
                    "display": f"{unique_nums[0]:.0f}"
                }

        # Otherwise, treat as categorical
        unique_values = sorted(set(str(v) for v in values))

        # Limit to top 15 most common values if too many
        if len(unique_values) > 15:
            from collections import Counter
            value_counts = Counter(str(v) for v in values)
            unique_values = [v for v, _ in value_counts.most_common(15)]

        return {
            "type": "categorical",
            "values": unique_values,
            "count": len(unique_values),
            "display": ", ".join(unique_values[:10]) + ("..." if len(unique_values) > 10 else "")
        }

    async def get_category_properties(self, category: str) -> List[str]:
        """Get all properties for a given category"""
        # Database uses Product label with category property
        query = """
        MATCH (n:Product)
        WHERE n.category = $category
        WITH n LIMIT 100
        UNWIND keys(n) AS key
        RETURN DISTINCT key
        ORDER BY key
        """

        async with self.driver.session() as session:
            result = await session.run(query, category=category)
            properties = [record["key"] async for record in result]
            return properties

    async def get_property_values(self, category: str, property_name: str) -> List[Any]:
        """Get all unique values for a property in a category"""
        # Database uses Product label with category property
        query = """
        MATCH (n:Product)
        WHERE n.category = $category
          AND n['{property_name}'] IS NOT NULL
        RETURN DISTINCT n['{property_name}'] AS value
        LIMIT 1000
        """.format(property_name=property_name)

        async with self.driver.session() as session:
            result = await session.run(query, category=category)
            values = [record["value"] async for record in result]
            return values

    async def analyze_category(self, category: str, priority_properties: List[str] = None) -> Dict[str, Any]:
        """Analyze a category and extract feature information"""
        print(f"\n{'='*60}")
        print(f"Analyzing {category}...")
        print(f"{'='*60}")

        # Get all properties
        all_properties = await self.get_category_properties(category)
        print(f"Found {len(all_properties)} properties: {all_properties[:10]}...")

        # Define which properties to skip
        skip_properties = {'gin', 'category', 'item_name', 'description_catalogue',
                          'description_web', 'name', 'image_url', 'id', 'created_at',
                          'updated_at', 'sku', 'model', 'slug'}

        # Filter properties
        relevant_properties = [p for p in all_properties if p not in skip_properties]

        # Prioritize properties if specified
        if priority_properties:
            # Put priority properties first
            priority_props = [p for p in priority_properties if p in relevant_properties]
            other_props = [p for p in relevant_properties if p not in priority_properties]
            relevant_properties = priority_props + other_props

        # Analyze each property
        features = {}
        for prop in relevant_properties[:20]:  # Limit to top 20 properties
            print(f"  Analyzing property: {prop}")
            values = await self.get_property_values(category, prop)

            if values:
                categorized = self.categorize_values(values, prop)
                features[prop] = categorized

                # Print summary
                if categorized['type'] == 'numeric_range':
                    print(f"    ✓ Range: {categorized['display']}")
                elif categorized['type'] == 'categorical':
                    print(f"    ✓ Options ({categorized['count']}): {categorized['display'][:80]}")

        return {
            "category": category,
            "total_properties": len(all_properties),
            "analyzed_properties": len(features),
            "features": features
        }

    async def extract_all_categories(self) -> Dict[str, Any]:
        """Extract features for all product categories"""

        # First, discover what categories actually exist in the database
        print("Discovering categories in database...")
        discovered_categories = await self.discover_categories()
        print(f"Found categories: {discovered_categories}")

        # Define priority properties for known categories
        priority_properties_map = {
            "PowerSource": ["current_output", "voltage_input", "process", "material",
                           "duty_cycle", "wire_diameter", "power_factor", "efficiency"],
            "Feeder": ["wire_diameter", "cooling_type", "wire_type", "duty_cycle",
                      "feed_speed", "motor_type", "drive_type"],
            "Cooler": ["cooling_capacity", "flow_rate", "voltage", "coolant_type",
                      "tank_capacity", "pump_type"],
            "Interconnector": ["cable_length", "current_rating", "connector_type",
                              "cable_diameter", "voltage_rating"],
            "Torch": ["amperage_rating", "cooling_type", "cable_length",
                     "duty_cycle", "handle_type", "trigger_type"],
            "Accessory": ["accessory_type", "compatibility", "material", "size"]
        }

        results = {}

        # Analyze each discovered category
        for category in discovered_categories:
            try:
                priority_props = priority_properties_map.get(category, [])
                result = await self.analyze_category(category, priority_properties=priority_props)
                results[category] = result
            except Exception as e:
                print(f"❌ Error analyzing {category}: {e}")
                import traceback
                traceback.print_exc()
                results[category] = {
                    "category": category,
                    "error": str(e)
                }

        return results

    def generate_prompt_guidance(self, category_data: Dict[str, Any]) -> str:
        """Generate user-friendly prompt guidance from category data"""
        category = category_data['category']
        features = category_data.get('features', {})

        if not features:
            return f"Available {category} options in our catalog."

        lines = [f"\n📋 Available {category} Features:"]

        for prop_name, prop_data in list(features.items())[:10]:  # Top 10 features
            # Format property name
            display_name = prop_name.replace('_', ' ').title()

            if prop_data['type'] == 'numeric_range':
                lines.append(f"  • {display_name}: {prop_data['display']}")
            elif prop_data['type'] == 'categorical':
                # Show first few options
                values = prop_data['values'][:5]
                display = ", ".join(values)
                if len(prop_data['values']) > 5:
                    display += f" (+ {len(prop_data['values']) - 5} more)"
                lines.append(f"  • {display_name}: {display}")

        return "\n".join(lines)


async def main():
    """Main execution"""
    print("="*80)
    print("CATEGORY FEATURE EXTRACTION - Neo4j Product Database")
    print("="*80)

    extractor = CategoryFeatureExtractor()

    try:
        # Extract features for all categories
        results = await extractor.extract_all_categories()

        # Save to JSON file
        output_file = "app/config/category_features.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n{'='*80}")
        print(f"✅ Category features saved to: {output_file}")
        print(f"{'='*80}")

        # Generate and display prompt guidance
        print("\n" + "="*80)
        print("GENERATED PROMPT GUIDANCE")
        print("="*80)

        for category, data in results.items():
            if 'error' not in data:
                guidance = extractor.generate_prompt_guidance(data)
                print(guidance)

        # Generate summary statistics
        print("\n" + "="*80)
        print("SUMMARY STATISTICS")
        print("="*80)

        for category, data in results.items():
            if 'error' not in data:
                print(f"\n{category}:")
                print(f"  Total Properties: {data['total_properties']}")
                print(f"  Analyzed Features: {data['analyzed_properties']}")

                # Count feature types
                features = data.get('features', {})
                numeric_count = sum(1 for f in features.values() if f['type'] in ['numeric_range', 'numeric_single'])
                categorical_count = sum(1 for f in features.values() if f['type'] == 'categorical')

                print(f"  Numeric Features: {numeric_count}")
                print(f"  Categorical Features: {categorical_count}")

    finally:
        await extractor.close()

    print("\n" + "="*80)
    print("✅ Extraction Complete!")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
