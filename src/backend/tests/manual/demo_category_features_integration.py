"""
Demo: Category Features LLM Integration Test
==============================================

Demonstrates how category_features_llm.json is leveraged for enhanced LLM extraction.

Shows:
1. Loading category features from JSON
2. Building dynamic component-specific prompts with actual database ranges
3. Comparing prompts: without ranges vs with ranges

Usage:
    python demo_category_features_integration.py
"""

import json
import pathlib
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

def load_category_features():
    """Load category features from category_features_llm.json"""
    features_path = pathlib.Path(__file__).parent.parent.parent / "app" / "config" / "category_features_llm.json"

    with open(features_path, 'r') as f:
        return json.load(f)

def build_enhanced_prompt(category_name, features_data):
    """Build enhanced prompt using category features"""

    prompt = f"""
{'='*70}
COMPONENT: {category_name}
Products in database: {features_data.get('product_count', 'N/A')}
{'='*70}

Extract the following specifications from user queries:

"""

    features = features_data.get('features', {})
    param_num = 1

    # Numeric specs
    numeric_specs = features.get('numeric_specs', [])
    if numeric_specs:
        prompt += "\n📊 NUMERIC SPECIFICATIONS:\n"
        for spec in numeric_specs:
            prompt += f"\n{param_num}. {spec['name']}\n"
            prompt += f"   Range: {spec['display']}\n"
            prompt += f"   Unit: {spec['unit']}\n"

            # Generate examples
            if 'min' in spec and 'max' in spec:
                mid = (spec['min'] + spec['max']) / 2
                prompt += f"   Examples: {spec['min']}{spec['unit']}, {mid:.0f}{spec['unit']}, {spec['max']}{spec['unit']}\n"
            elif 'value' in spec:
                prompt += f"   Value: {spec['value']}{spec['unit']}\n"

            param_num += 1

    # Categorical features
    categorical = features.get('categorical_features', [])
    if categorical:
        prompt += "\n\n🏷️  CATEGORICAL OPTIONS:\n"
        for feat in categorical:
            prompt += f"\n{param_num}. {feat['name']}\n"
            prompt += f"   Available: {', '.join(feat['options'])}\n"
            param_num += 1

    # Capabilities
    capabilities = features.get('capabilities', [])
    if capabilities:
        prompt += "\n\n⚡ CAPABILITIES:\n"
        for cap in capabilities:
            prompt += f"\n{param_num}. {cap['name']}\n"
            prompt += f"   Supported: {', '.join(cap['values'])}\n"
            param_num += 1

    # Key features
    key_features = features.get('key_features', [])
    if key_features:
        prompt += "\n\n✨ KEY FEATURES (extract if mentioned):\n"
        for i, feature in enumerate(key_features[:8], 1):
            prompt += f"   • {feature}\n"

    prompt += f"\n{'='*70}\n"

    return prompt

def demonstrate_integration():
    """Demonstrate the integration with examples"""

    print("\n" + "="*70)
    print("🚀 Category Features LLM Integration Demo")
    print("="*70)

    # Load features
    print("\n📦 Loading category_features_llm.json...")
    category_features = load_category_features()
    print(f"✅ Loaded {len(category_features)} categories")

    # Show available categories
    print("\n📋 Available Categories:")
    for category in sorted(category_features.keys()):
        count = category_features[category].get('product_count', 0)
        print(f"   • {category}: {count} products")

    print("\n" + "="*70)
    print("📝 EXAMPLE 1: Powersource Component")
    print("="*70)

    # Show Powersource features
    powersource_data = category_features.get('Powersource', {})
    powersource_prompt = build_enhanced_prompt('Powersource', powersource_data)
    print(powersource_prompt)

    print("\n" + "="*70)
    print("📝 EXAMPLE 2: Feeder Component")
    print("="*70)

    # Show Feeder features
    feeder_data = category_features.get('Feeder', {})
    feeder_prompt = build_enhanced_prompt('Feeder', feeder_data)
    print(feeder_prompt)

    print("\n" + "="*70)
    print("🎯 KEY BENEFITS OF THIS APPROACH")
    print("="*70)
    print("""
✅ LLM knows actual database ranges (300A-500A, not just "current")
✅ LLM can validate user input ("900A" is out of range for this category)
✅ LLM knows which processes are actually supported
✅ LLM gets examples for proper unit extraction ("500 amps" → "500A")
✅ LLM can extract design features that exist in the database
✅ Different prompts for different components (Powersource vs Feeder)

📊 COMPARISON:

Without category_features_llm.json:
   "Extract: current_output, voltage, process"
   ❌ No guidance on valid ranges
   ❌ No examples for unit extraction
   ❌ Same generic prompt for all components

With category_features_llm.json:
   "Extract:
    - Current Output: 300A - 500A (examples: 300A, 400A, 500A)
    - Voltage: 230V - 480V (examples: 230V, 400V, 480V)
    - Supported Processes: MIG/MAG, MMA, DC TIG, Gouging"
   ✅ Clear ranges from actual database
   ✅ Concrete examples
   ✅ Component-specific guidance
""")

    print("\n" + "="*70)
    print("📚 NEXT STEPS")
    print("="*70)
    print("""
1. Start the test server:
   cd src/backend/tests/manual
   python test_api_weighted_search.py

2. Open the HTML UI:
   open test_weighted_search_ui.html

3. Try these test queries:

   Query 1: "I need a 500A MIG/MAG welder with water cooling"
   Expected: Extracts 500A (in valid range), MIG/MAG (supported), water-cooled

   Query 2: "Show me portable power sources for MMA and TIG"
   Expected: Extracts MMA, DC TIG (both supported), portable, multiprocess

   Query 3: "Aristo 500ix with 400V input"
   Expected: Extracts model name, 400V (in valid range)

4. Compare:
   - Test A (Full-text): Basic keyword search
   - Test B (Weighted): Enhanced with category-aware LLM extraction
""")

if __name__ == "__main__":
    demonstrate_integration()
