#!/usr/bin/env python3
"""
Synonym Generation Script

Reads discovered_patterns.json and groups similar units into synonym categories.
Generates welding-synonyms.txt in Lucene synonym format.

Output: results/welding-synonyms.txt
Output: results/synonym_groups.json
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict


class SynonymGenerator:
    """Groups discovered patterns into synonym categories"""

    def __init__(self, patterns_file: str):
        self.patterns_file = patterns_file
        self.patterns = []
        self.synonym_groups = defaultdict(set)

    def load_patterns(self):
        """Load discovered patterns from JSON file"""

        if not os.path.exists(self.patterns_file):
            print(f"❌ ERROR: Patterns file not found: {self.patterns_file}")
            print("   Please run discover_patterns.py first")
            sys.exit(1)

        with open(self.patterns_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.patterns = data['patterns']

        print(f"✅ Loaded {len(self.patterns)} unique units from {self.patterns_file}")
        print(f"   Scanned {data['total_products_scanned']} products")
        print(f"   Found {data['total_patterns_found']} pattern occurrences")
        print()

    def group_patterns(self):
        """
        Group similar units into synonym categories.

        Categories based on welding equipment domain knowledge.
        """

        print("🔧 Grouping patterns into synonym categories...")
        print()

        for pattern in self.patterns:
            unit = pattern['unit']
            unit_lower = unit.lower()

            # AMPERAGE
            if self._is_amperage(unit_lower):
                self.synonym_groups['amperage'].add(unit_lower)

            # VOLTAGE
            elif self._is_voltage(unit_lower):
                self.synonym_groups['voltage'].add(unit_lower)

            # POWER
            elif self._is_power(unit_lower):
                self.synonym_groups['power'].add(unit_lower)

            # LENGTH - Millimeters
            elif self._is_length_mm(unit_lower):
                self.synonym_groups['length_mm'].add(unit_lower)

            # LENGTH - Meters
            elif self._is_length_m(unit_lower):
                self.synonym_groups['length_m'].add(unit_lower)

            # LENGTH - Centimeters
            elif self._is_length_cm(unit_lower):
                self.synonym_groups['length_cm'].add(unit_lower)

            # WEIGHT
            elif self._is_weight(unit_lower):
                self.synonym_groups['weight'].add(unit_lower)

            # PRESSURE
            elif self._is_pressure(unit_lower):
                self.synonym_groups['pressure'].add(unit_lower)

            # FLOW
            elif self._is_flow(unit_lower):
                self.synonym_groups['flow'].add(unit_lower)

            # TEMPERATURE
            elif self._is_temperature(unit_lower):
                self.synonym_groups['temperature'].add(unit_lower)

            # FREQUENCY
            elif self._is_frequency(unit_lower):
                self.synonym_groups['frequency'].add(unit_lower)

            # PERCENTAGE / DUTY CYCLE
            elif self._is_percentage(unit_lower):
                self.synonym_groups['percentage'].add(unit_lower)

            # SPEED
            elif self._is_speed(unit_lower):
                self.synonym_groups['speed'].add(unit_lower)

            # ANGLE
            elif self._is_angle(unit_lower):
                self.synonym_groups['angle'].add(unit_lower)

            # TIME
            elif self._is_time(unit_lower):
                self.synonym_groups['time'].add(unit_lower)

            # WIRE GAUGE
            elif self._is_wire_gauge(unit_lower):
                self.synonym_groups['wire_gauge'].add(unit_lower)

            # Uncategorized (for manual review)
            else:
                self.synonym_groups['uncategorized'].add(unit_lower)

        # Print summary
        print("📊 Grouping Summary:")
        print("-" * 60)
        for category, units in sorted(self.synonym_groups.items()):
            if units:
                print(f"  {category:20s}: {len(units):3d} units")
        print()

    # ========================================================================
    # CLASSIFICATION METHODS
    # ========================================================================

    def _is_amperage(self, unit: str) -> bool:
        """Check if unit is amperage-related"""
        keywords = ['a', 'amp', 'ampere', 'ampère', 'amperio']
        # Exclude: ma (milliampere), ka (kiloampere) if standalone
        if unit in keywords:
            return True
        return any(kw in unit for kw in keywords[1:])  # Check longer forms

    def _is_voltage(self, unit: str) -> bool:
        """Check if unit is voltage-related"""
        keywords = ['v', 'volt', 'voltio']
        # Exclude: mv, kv if standalone
        if unit in keywords:
            return True
        return any(kw in unit for kw in keywords[1:])

    def _is_power(self, unit: str) -> bool:
        """Check if unit is power-related"""
        keywords = ['w', 'watt', 'kw', 'kilowatt', 'mw', 'megawatt']
        return any(kw in unit for kw in keywords)

    def _is_length_mm(self, unit: str) -> bool:
        """Check if unit is millimeters"""
        return 'mm' in unit or 'millimeter' in unit or 'millimetre' in unit

    def _is_length_m(self, unit: str) -> bool:
        """Check if unit is meters (not millimeters)"""
        # Must have 'm' but NOT 'mm'
        if 'mm' in unit or 'cm' in unit:
            return False
        keywords = ['m', 'meter', 'metre']
        return unit in keywords or any(kw in unit for kw in keywords[1:])

    def _is_length_cm(self, unit: str) -> bool:
        """Check if unit is centimeters"""
        return 'cm' in unit or 'centimeter' in unit or 'centimetre' in unit

    def _is_weight(self, unit: str) -> bool:
        """Check if unit is weight-related"""
        keywords = ['kg', 'kilogram', 'g', 'gram', 'lb', 'lbs', 'pound', 'ton', 'tonne']
        # Exclude: single 'g' if very common (might be gauge)
        if unit == 'g':
            return False  # Too ambiguous
        return any(kw in unit for kw in keywords)

    def _is_pressure(self, unit: str) -> bool:
        """Check if unit is pressure-related"""
        keywords = ['bar', 'psi', 'pa', 'pascal', 'mpa', 'kpa']
        return any(kw in unit for kw in keywords)

    def _is_flow(self, unit: str) -> bool:
        """Check if unit is flow rate-related"""
        keywords = ['l/min', 'l/h', 'liter/min', 'litre/min', 'lpm', 'cfm', 'gpm']
        return any(kw in unit for kw in keywords)

    def _is_temperature(self, unit: str) -> bool:
        """Check if unit is temperature-related"""
        keywords = ['c', 'celsius', 'f', 'fahrenheit', '°c', '°f', 'k', 'kelvin']
        return unit in keywords or any(kw in unit for kw in keywords)

    def _is_frequency(self, unit: str) -> bool:
        """Check if unit is frequency-related"""
        keywords = ['hz', 'hertz', 'khz', 'mhz']
        return any(kw in unit for kw in keywords)

    def _is_percentage(self, unit: str) -> bool:
        """Check if unit is percentage-related"""
        return '%' in unit or 'percent' in unit

    def _is_speed(self, unit: str) -> bool:
        """Check if unit is speed-related"""
        keywords = ['m/min', 'mm/s', 'cm/s', 'rpm', 'ipm', 'mph', 'km/h']
        return any(kw in unit for kw in keywords)

    def _is_angle(self, unit: str) -> bool:
        """Check if unit is angle-related"""
        keywords = ['deg', 'degree', '°', 'rad', 'radian']
        return any(kw in unit for kw in keywords)

    def _is_time(self, unit: str) -> bool:
        """Check if unit is time-related"""
        keywords = ['s', 'sec', 'second', 'min', 'minute', 'h', 'hr', 'hour', 'ms', 'millisecond']
        if unit == 's':  # Too ambiguous
            return False
        return any(kw in unit for kw in keywords)

    def _is_wire_gauge(self, unit: str) -> bool:
        """Check if unit is wire gauge-related"""
        keywords = ['awg', 'gauge', 'ga']
        return any(kw in unit for kw in keywords)

    # ========================================================================
    # OUTPUT GENERATION
    # ========================================================================

    def generate_synonym_file(self, output_file: str):
        """Generate Lucene synonym file"""

        print(f"📝 Generating synonym file: {output_file}")

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            # Header
            f.write("# Welding Equipment Lucene Synonym File\n")
            f.write(f"# Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Source: {self.patterns_file}\n")
            f.write("#\n")
            f.write("# Format: synonym1, synonym2, synonym3\n")
            f.write("# Lucene will treat all terms in a line as equivalent\n")
            f.write("#\n\n")

            # Write each category
            for category in sorted(self.synonym_groups.keys()):
                if category == 'uncategorized':
                    continue  # Skip uncategorized for now

                units = self.synonym_groups[category]
                if not units:
                    continue

                # Category header
                f.write(f"# {category.upper().replace('_', ' ')}\n")

                # Write synonyms (comma-separated)
                sorted_units = sorted(units)
                f.write(", ".join(sorted_units) + "\n\n")

            # Write uncategorized at the end (for manual review)
            if self.synonym_groups['uncategorized']:
                f.write("# UNCATEGORIZED (Manual Review Required)\n")
                f.write("# These units need manual classification:\n")
                for unit in sorted(self.synonym_groups['uncategorized']):
                    f.write(f"# {unit}\n")
                f.write("\n")

        print(f"✅ Synonym file created: {output_file}")
        print(f"   File size: {os.path.getsize(output_file):,} bytes")
        print()

    def save_synonym_groups(self, output_file: str):
        """Save synonym groups to JSON for programmatic access"""

        output_data = {
            "generation_date": datetime.now().isoformat(),
            "source_file": self.patterns_file,
            "total_categories": len([g for g in self.synonym_groups.values() if g]),
            "total_synonyms": sum(len(g) for g in self.synonym_groups.values()),
            "groups": {
                category: sorted(list(units))
                for category, units in self.synonym_groups.items()
                if units
            }
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"✅ Synonym groups saved: {output_file}")


def main():
    """Main execution function"""

    print("\n" + "=" * 80)
    print("SYNONYM GENERATION")
    print("=" * 80)
    print()

    # Input and output files
    script_dir = Path(__file__).parent
    patterns_file = script_dir / 'results' / 'discovered_patterns.json'
    synonym_file = script_dir / 'results' / 'welding-synonyms.txt'
    groups_file = script_dir / 'results' / 'synonym_groups.json'

    # Generate synonyms
    generator = SynonymGenerator(str(patterns_file))
    generator.load_patterns()
    generator.group_patterns()
    generator.generate_synonym_file(str(synonym_file))
    generator.save_synonym_groups(str(groups_file))

    print()
    print("=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("1. Review results/welding-synonyms.txt")
    print("2. Check UNCATEGORIZED section for manual classification")
    print("3. Add/remove synonyms as needed")
    print("4. Run verify_neo4j_capabilities.py to check Neo4j compatibility")
    print("5. Upload synonym file to Neo4j and configure custom analyzer")
    print()


if __name__ == "__main__":
    main()
