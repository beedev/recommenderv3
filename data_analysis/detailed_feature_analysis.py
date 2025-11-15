#!/usr/bin/env python3
"""
Detailed Feature Analysis - Search for specific welding equipment features

Specifically looks for:
- Voltage (V, Volts, Voltios)
- Amperage variations
- Wire diameter
- Duty cycle (%)
- And other common welding specifications
"""

import asyncio
import os
import sys
import re
from pathlib import Path
from collections import Counter, defaultdict

parent_dir = Path(__file__).parent.parent / 'src' / 'backend'
sys.path.insert(0, str(parent_dir))

from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

env_path = parent_dir / '.env'
load_dotenv(env_path if env_path.exists() else None)

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")


async def analyze_features():
    """Detailed analysis of welding equipment features"""

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    try:
        print("\n" + "=" * 80)
        print("DETAILED FEATURE ANALYSIS")
        print("=" * 80)
        print()

        # Get all products
        async with driver.session() as session:
            result = await session.run("""
                MATCH (p:Product)
                RETURN p.item_name as name,
                       p.description_ruleset as description,
                       p.attributes_ruleset as attributes,
                       p.item_name as item_name
            """)

            records = [record async for record in result]
            print(f"📊 Analyzing {len(records)} products...")
            print()

            # Feature counters
            features = {
                'voltage': Counter(),
                'amperage': Counter(),
                'power': Counter(),
                'wire_diameter': Counter(),
                'duty_cycle': Counter(),
                'frequency': Counter(),
                'phase': Counter(),
                'length': Counter(),
                'pressure': Counter(),
                'flow': Counter(),
                'temperature': Counter(),
            }

            examples = defaultdict(list)

            # Analyze each product
            for record in records:
                texts = [
                    record['item_name'] or '',      # Search product name too!
                    record['description'] or '',
                    record['attributes'] or '',
                ]

                full_text = ' '.join(texts)

                # VOLTAGE patterns
                voltage_patterns = [
                    r'\b(\d+)\s*V\b',                    # 380V, 380 V
                    r'\b(\d+)\s*Volts?\b',               # 380 Volts
                    r'\b(\d+)\s*Voltios?\b',             # Spanish
                    r'\b(\d+-\d+)\s*V\b',                # 380-460V (range)
                    r'\((\d+-\d+V)\)',                   # (380-460V)
                ]
                for pattern in voltage_patterns:
                    matches = re.findall(pattern, full_text, re.IGNORECASE)
                    for match in matches:
                        features['voltage'][match] += 1
                        if len(examples['voltage']) < 10:
                            examples['voltage'].append(f"{match} in: {record['name']}")

                # AMPERAGE patterns (detailed)
                amperage_patterns = [
                    r'\b(\d+)\s*A\b',                    # 500A, 500 A
                    r'\b(\d+)\s*Amps?\b',                # 500 Amps
                    r'\b(\d+)\s*Amperes?\b',             # 500 Ampere
                    r'\b(\d+)\s*Ampères?\b',             # 500 Ampères
                    r'\b(\d+)A\s*@\s*(\d+)%',           # 500A @60%
                    r'\b(\d+)\s*Amperes?\s*at\s*(\d+)%', # 500 Amperes at 60%
                ]
                for pattern in amperage_patterns:
                    matches = re.findall(pattern, full_text, re.IGNORECASE)
                    for match in matches:
                        match_str = match if isinstance(match, str) else ' '.join(str(m) for m in match if m)
                        features['amperage'][match_str] += 1
                        if len(examples['amperage']) < 10:
                            examples['amperage'].append(f"{match_str} in: {record['name']}")

                # WIRE DIAMETER
                wire_patterns = [
                    r'\b(\d+(?:\.\d+)?)\s*mm\s*wire',   # 1.2mm wire
                    r'\b(\d+(?:\.\d+)?)\s*mm\s*diameter',
                    r'wire.*?(\d+(?:\.\d+)?)\s*mm',
                ]
                for pattern in wire_patterns:
                    matches = re.findall(pattern, full_text, re.IGNORECASE)
                    for match in matches:
                        features['wire_diameter'][match] += 1
                        if len(examples['wire_diameter']) < 10:
                            examples['wire_diameter'].append(f"{match}mm in: {record['name']}")

                # DUTY CYCLE
                duty_patterns = [
                    r'\b(\d+)%',                         # 60%
                    r'@\s*(\d+)%',                       # @ 60%
                    r'at\s*(\d+)%',                      # at 60%
                ]
                for pattern in duty_patterns:
                    matches = re.findall(pattern, full_text, re.IGNORECASE)
                    for match in matches:
                        if 10 <= int(match) <= 100:  # Valid duty cycle range
                            features['duty_cycle'][match + '%'] += 1
                            if len(examples['duty_cycle']) < 10:
                                examples['duty_cycle'].append(f"{match}% in: {record['name']}")

                # FREQUENCY
                freq_patterns = [
                    r'\b(\d+)\s*Hz',
                    r'\b(\d+)\s*Hertz',
                ]
                for pattern in freq_patterns:
                    matches = re.findall(pattern, full_text, re.IGNORECASE)
                    for match in matches:
                        features['frequency'][match + ' Hz'] += 1

                # PHASE
                phase_patterns = [
                    r'\b(\d+)\s*phase',
                    r'\b(\d+)ph\b',
                ]
                for pattern in phase_patterns:
                    matches = re.findall(pattern, full_text, re.IGNORECASE)
                    for match in matches:
                        features['phase'][match + ' phase'] += 1

            # Print results
            print("=" * 80)
            print("FEATURE DISCOVERY RESULTS")
            print("=" * 80)
            print()

            for feature_name, counter in features.items():
                if counter:
                    print(f"\n{feature_name.upper().replace('_', ' ')}")
                    print("-" * 60)
                    print(f"Unique values: {len(counter)}")
                    print(f"Total occurrences: {sum(counter.values())}")
                    print()
                    print("Top 10 values:")
                    for value, count in counter.most_common(10):
                        print(f"  {value:30s} - {count:3d} occurrences")

                    if examples[feature_name]:
                        print()
                        print("Examples:")
                        for ex in examples[feature_name][:5]:
                            print(f"  • {ex}")
                else:
                    print(f"\n{feature_name.upper().replace('_', ' ')}: ❌ NOT FOUND")

            print()
            print("=" * 80)
            print("ANALYSIS COMPLETE")
            print("=" * 80)

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(analyze_features())
