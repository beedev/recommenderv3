#!/usr/bin/env python3
"""
Pattern Discovery Script for Welding Equipment Database

Scans Neo4j Product database to discover all number+unit patterns.
Example patterns: 500A, 30mm, 380V, 60%, etc.

Output: results/discovered_patterns.json
"""

import asyncio
import os
import sys
import re
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# Add parent directory to path to import from src/backend
parent_dir = Path(__file__).parent.parent / 'src' / 'backend'
sys.path.insert(0, str(parent_dir))

from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

# Load environment variables from src/backend/.env
env_path = parent_dir / '.env'
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Loaded environment from: {env_path}")
else:
    load_dotenv()  # Try current directory
    print("⚠️  Using environment from current directory")

# Neo4j connection details
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

if not all([NEO4J_URI, NEO4J_PASSWORD]):
    print("❌ ERROR: Neo4j credentials not found in environment")
    print("   Please ensure NEO4J_URI and NEO4J_PASSWORD are set")
    sys.exit(1)


class PatternDiscovery:
    """Discovers all number+unit patterns in Neo4j product database"""

    # Regex to match: number (with optional decimal) + unit
    # Examples: 500A, 500 A, 30mm, 30.5mm, 380V, 60%, etc.
    PATTERN_REGEX = r'\b(\d+(?:\.\d+)?)\s*([A-Za-z°%]+(?:/[A-Za-z]+)?)\b'

    def __init__(self, driver):
        self.driver = driver
        self.unit_patterns = Counter()  # {unit: count}
        self.unit_examples = defaultdict(set)  # {unit: {example1, example2, ...}}
        self.total_products = 0
        self.total_patterns_found = 0

    async def discover_patterns(self):
        """
        Scan all Product nodes and extract number+unit patterns.
        """
        print("\n" + "=" * 80)
        print("PATTERN DISCOVERY - Scanning Neo4j Database")
        print("=" * 80)
        print(f"URI: {NEO4J_URI}")
        print(f"User: {NEO4J_USERNAME}")
        print()

        # Query all products
        query = """
        MATCH (p:Product)
        RETURN p.item_name as name,
               p.description_ruleset as description,
               p.attributes_ruleset as attributes,
               p.category as category
        """

        print("🔍 Querying Neo4j for all products...")

        async with self.driver.session() as session:
            result = await session.run(query)
            records = [record async for record in result]

            self.total_products = len(records)
            print(f"✅ Found {self.total_products} products")
            print()

            print("🔍 Extracting patterns from product descriptions...")

            for idx, record in enumerate(records, 1):
                if idx % 100 == 0:
                    print(f"   Processed {idx}/{self.total_products} products...")

                # Get all text fields
                texts = [
                    record['description'] or '',
                    record['attributes'] or '',
                ]

                # Extract patterns from all text fields
                for text in texts:
                    self._extract_patterns_from_text(text)

            print(f"✅ Processed all {self.total_products} products")
            print()

    def _extract_patterns_from_text(self, text: str):
        """Extract all number+unit patterns from text"""

        matches = re.findall(self.PATTERN_REGEX, text, re.IGNORECASE)

        for number, unit in matches:
            # Normalize unit (lowercase, strip spaces)
            unit_normalized = unit.lower().strip()

            # Skip if unit is too long (likely not a real unit)
            if len(unit_normalized) > 20:
                continue

            # Count this unit
            self.unit_patterns[unit_normalized] += 1
            self.total_patterns_found += 1

            # Store example (full match: number + unit)
            example = f"{number}{unit}"
            if len(self.unit_examples[unit_normalized]) < 5:  # Keep max 5 examples
                self.unit_examples[unit_normalized].add(example)

    def generate_report(self):
        """Generate discovery report"""

        print("=" * 80)
        print("PATTERN DISCOVERY REPORT")
        print("=" * 80)
        print(f"Total products scanned: {self.total_products}")
        print(f"Total patterns found: {self.total_patterns_found}")
        print(f"Unique units discovered: {len(self.unit_patterns)}")
        print()

        # Sort by frequency
        sorted_patterns = self.unit_patterns.most_common()

        print("TOP 50 MOST COMMON UNITS:")
        print("-" * 80)
        print(f"{'Unit':<30} {'Count':>10} {'Examples'}")
        print("-" * 80)

        for idx, (unit, count) in enumerate(sorted_patterns[:50], 1):
            examples = list(self.unit_examples[unit])[:3]
            examples_str = ", ".join(examples)
            print(f"{idx:2}. {unit:<26} {count:>10}   {examples_str}")

        if len(sorted_patterns) > 50:
            print(f"\n... and {len(sorted_patterns) - 50} more units")

        print()

        return sorted_patterns

    def save_results(self, output_file: str):
        """Save discovery results to JSON file"""

        sorted_patterns = self.unit_patterns.most_common()

        output_data = {
            "scan_date": datetime.now().isoformat(),
            "total_products_scanned": self.total_products,
            "total_patterns_found": self.total_patterns_found,
            "unique_units_discovered": len(self.unit_patterns),
            "neo4j_uri": NEO4J_URI,
            "patterns": [
                {
                    "unit": unit,
                    "count": count,
                    "examples": list(self.unit_examples[unit])
                }
                for unit, count in sorted_patterns
            ]
        }

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # Write JSON file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"✅ Results saved to: {output_file}")
        print(f"   File size: {os.path.getsize(output_file):,} bytes")


async def main():
    """Main execution function"""

    print("\n" + "=" * 80)
    print("WELDING EQUIPMENT PATTERN DISCOVERY")
    print("=" * 80)
    print()

    # Connect to Neo4j
    print("🔌 Connecting to Neo4j...")
    driver = AsyncGraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )

    try:
        # Verify connection
        async with driver.session() as session:
            result = await session.run("RETURN 1 as test")
            await result.single()

        print("✅ Connected to Neo4j")
        print()

        # Run pattern discovery
        discovery = PatternDiscovery(driver)
        await discovery.discover_patterns()

        # Generate report
        discovery.generate_report()

        # Save results
        output_file = os.path.join(
            os.path.dirname(__file__),
            'results',
            'discovered_patterns.json'
        )
        discovery.save_results(output_file)

        print()
        print("=" * 80)
        print("NEXT STEPS")
        print("=" * 80)
        print("1. Review the discovered patterns in results/discovered_patterns.json")
        print("2. Run generate_synonyms.py to group patterns into synonym categories")
        print("3. Review and edit results/welding-synonyms.txt")
        print("4. Upload synonym file to Neo4j and configure custom analyzer")
        print()

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        await driver.close()
        print("🔌 Disconnected from Neo4j")


if __name__ == "__main__":
    asyncio.run(main())
