"""
Weighted Lucene Search POC - Test API Server
==============================================

Standalone FastAPI server for testing weighted keyword search vs full-text search.
Runs on port 8001 (separate from production port 8000).

Features:
- Compares full-text Lucene vs weighted keyword Lucene
- Uses real Neo4j data with existing credentials
- Mock keyword extraction (simulates LLM)
- Returns side-by-side comparison

Usage:
    python test_api_weighted_search.py

Then open test_weighted_search_ui.html in browser.
"""

import os
import sys
import time
import re
import json
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

# Load environment variables from backend/.env
import pathlib
env_path = pathlib.Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
print(f"📝 Loading .env from: {env_path}")

# OpenAI for LLM keyword extraction
try:
    from openai import AsyncOpenAI
except ImportError:
    print("❌ Error: openai package not installed")
    print("Install with: pip install openai")
    sys.exit(1)

# RapidFuzz for fuzzy product name matching
try:
    from rapidfuzz import fuzz, process
except ImportError:
    print("❌ Error: rapidfuzz package not installed")
    print("Install with: pip install rapidfuzz")
    sys.exit(1)

# Neo4j async driver
try:
    from neo4j import AsyncGraphDatabase
except ImportError:
    print("❌ Error: neo4j package not installed")
    print("Install with: pip install neo4j")
    sys.exit(1)

# ============================================================================
# FastAPI App Setup
# ============================================================================

app = FastAPI(
    title="Weighted Lucene Search POC",
    description="Compare full-text vs weighted keyword Lucene search",
    version="1.0.0"
)

# CORS for HTML file access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Neo4j Connection & LLM Client
# ============================================================================

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Flag to use LLM or mock extraction (default: true for LLM)
USE_LLM_EXTRACTION = os.getenv("USE_LLM_EXTRACTION", "true").lower() == "true"

print(f"📡 Connecting to Neo4j: {NEO4J_URI}")
driver = AsyncGraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
)

# Initialize OpenAI client
if USE_LLM_EXTRACTION:
    if not OPENAI_API_KEY:
        print("⚠️  Warning: USE_LLM_EXTRACTION=true but OPENAI_API_KEY not set")
        print("   Falling back to mock extraction")
        USE_LLM_EXTRACTION = False
        openai_client = None
    else:
        openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        print(f"🤖 OpenAI client initialized (LLM extraction enabled)")
else:
    openai_client = None
    print(f"📝 Using mock regex-based extraction")

# ============================================================================
# Product Names Database (for fuzzy matching and validation)
# ============================================================================

PRODUCT_NAMES_DB = {}
PRODUCT_NAMES_FLAT = []

def load_product_names():
    """Load product names from JSON file for fuzzy matching"""
    global PRODUCT_NAMES_DB, PRODUCT_NAMES_FLAT

    try:
        product_names_path = pathlib.Path(__file__).parent.parent.parent / "app" / "config" / "product_names.json"

        with open(product_names_path, 'r') as f:
            PRODUCT_NAMES_DB = json.load(f)

        # Create flat list for fuzzy matching
        for component_type, names in PRODUCT_NAMES_DB.items():
            for name in names:
                if name and name != "No Feeder Available" and name != "No Cooler Available":
                    PRODUCT_NAMES_FLAT.append({
                        "name": name,
                        "component_type": component_type,
                        "name_lower": name.lower()
                    })

        print(f"📦 Loaded {len(PRODUCT_NAMES_FLAT)} product names for fuzzy matching")

    except Exception as e:
        print(f"⚠️  Warning: Could not load product_names.json: {e}")
        print("   Product name validation disabled")

# Load product names at startup
load_product_names()

# ============================================================================
# Parameter Normalizations & Schema (for parameter value normalization)
# ============================================================================

PARAMETER_NORMALIZATIONS = {}
MASTER_PARAMETER_SCHEMA = {}

def load_parameter_normalizations():
    """Load parameter normalization mappings from JSON file"""
    global PARAMETER_NORMALIZATIONS

    try:
        param_norm_path = pathlib.Path(__file__).parent.parent.parent / "app" / "config" / "parameter_normalizations.json"

        with open(param_norm_path, 'r') as f:
            PARAMETER_NORMALIZATIONS = json.load(f)

        normalization_count = sum(len(v['mappings']) for v in PARAMETER_NORMALIZATIONS['normalizations'].values())
        print(f"📐 Loaded {normalization_count} parameter normalizations")

    except Exception as e:
        print(f"⚠️  Warning: Could not load parameter_normalizations.json: {e}")
        print("   Parameter normalization disabled")

def load_master_parameter_schema():
    """Load master parameter schema for component-specific features"""
    global MASTER_PARAMETER_SCHEMA

    try:
        schema_path = pathlib.Path(__file__).parent.parent.parent / "app" / "config" / "master_parameter_schema.json"

        with open(schema_path, 'r') as f:
            MASTER_PARAMETER_SCHEMA = json.load(f)

        component_count = len(MASTER_PARAMETER_SCHEMA.get('components', {}))
        print(f"📋 Loaded master parameter schema for {component_count} component types")

    except Exception as e:
        print(f"⚠️  Warning: Could not load master_parameter_schema.json: {e}")
        print("   Dynamic LLM prompts disabled")

# Load parameter normalizations and schema at startup
load_parameter_normalizations()
load_master_parameter_schema()

# ============================================================================
# Category Features for LLM Extraction (category_features_llm.json)
# ============================================================================

CATEGORY_FEATURES = {}

def load_category_features():
    """Load category features from category_features_llm.json for LLM prompt building"""
    global CATEGORY_FEATURES

    try:
        features_path = pathlib.Path(__file__).parent.parent.parent / "app" / "config" / "category_features_llm.json"

        with open(features_path, 'r') as f:
            CATEGORY_FEATURES = json.load(f)

        category_count = len(CATEGORY_FEATURES)
        print(f"🎯 Loaded {category_count} category feature definitions for LLM extraction")

    except Exception as e:
        print(f"⚠️  Warning: Could not load category_features_llm.json: {e}")
        print("   Dynamic LLM feature extraction disabled")

# Load category features at startup
load_category_features()

# Component type mapping: API component_type → category_features_llm.json category name
COMPONENT_TO_CATEGORY_MAP = {
    "power_source": "Powersource",
    "feeder": "Feeder",
    "cooler": "Cooler",
    "interconnector": "Interconn",
    "torch": "Torches",
    "accessory": "Powersource Accessories",  # Default to accessories
}

# ============================================================================
# Request/Response Models
# ============================================================================

class CompareRequest(BaseModel):
    query: str
    component_type: str = "power_source"
    limit: int = 20

class Keyword(BaseModel):
    canonical: str
    text: str
    type: str
    confidence: float
    boost: int
    validated: bool = False  # Whether validated against product_names.json
    match_type: str = None   # "exact", "fuzzy", or "llm_only"
    similarity: float = None  # Fuzzy match similarity score (0-100)

class SearchResult(BaseModel):
    lucene_query: str
    results: List[Dict[str, Any]]
    count: int
    execution_time_ms: float
    top_score: float

class ComparisonMetrics(BaseModel):
    precision_a: float
    precision_b: float
    improvement_percent: float
    speed_improvement_percent: float
    winner: str

class CompareResponse(BaseModel):
    query: str
    extracted_keywords: List[Keyword]
    test_a_fulltext: SearchResult
    test_b_weighted: SearchResult
    comparison_metrics: ComparisonMetrics

# ============================================================================
# Helper Functions (From helper script)
# ============================================================================

def boost_from_confidence(conf: float) -> int:
    """
    Convert confidence score to boost factor

    Enhanced for product name validation:
    - 0.98+ (exact match): 15x base boost
    - 0.95+ (fuzzy match): 10x base boost
    - 0.92+ (high confidence): 10x
    - 0.85+ (medium confidence): 6x
    - 0.70+ (low confidence): 3x
    - <0.70: 1x
    """
    if conf >= 0.98:
        return 15  # Exact product match
    if conf >= 0.95:
        return 10  # Fuzzy product match
    if conf >= 0.92:
        return 10  # High confidence
    if conf >= 0.85:
        return 6   # Medium confidence
    if conf >= 0.7:
        return 3   # Low confidence
    return 1       # Very low confidence

def extract_keywords_mock(query: str) -> List[Dict[str, Any]]:
    """
    Mock keyword extraction (simulates LLM)
    Real implementation would call OpenAI API

    Extracts:
    - Process types: MIG, MAG, MMA, Stick, TIG, GTAW
    - Numeric specs: 500A, 60%, etc.
    - Attributes: portable, compact, etc.
    """
    keywords = []
    query_lower = query.lower()

    # ─────────────────────────────────────────────────────────────
    # PROCESS PATTERNS (High confidence, high boost)
    # ─────────────────────────────────────────────────────────────
    process_patterns = {
        r'\bmig\b': ("MIG/MAG", "MIG", 0.96),
        r'\bmag\b': ("MIG/MAG", "MAG", 0.96),
        r'\bgmaw\b': ("MIG/MAG", "GMAW", 0.96),
        r'\bmma\b': ("MMA", "MMA", 0.95),
        r'\bstick\b': ("MMA", "Stick", 0.95),
        r'\bsmaw\b': ("MMA", "SMAW", 0.95),
        r'\btig\b': ("DC TIG", "TIG", 0.94),
        r'\bgtaw\b': ("DC TIG", "GTAW", 0.94),
        r'\bdc\s*tig\b': ("DC TIG", "DC TIG", 0.95),
        r'\blift\s*tig\b': ("DC TIG", "Lift TIG", 0.93),
    }

    seen_canonicals = set()
    for pattern, (canonical, text, conf) in process_patterns.items():
        if re.search(pattern, query_lower):
            if canonical not in seen_canonicals:
                keywords.append({
                    "canonical": canonical,
                    "text": text,
                    "type": "PROCESS",
                    "confidence": conf,
                    "boost": boost_from_confidence(conf)
                })
                seen_canonicals.add(canonical)

    # ─────────────────────────────────────────────────────────────
    # NUMERIC SPECS (Current, voltage, etc.)
    # ─────────────────────────────────────────────────────────────
    # Current rating (e.g., "500A", "400 amps")
    current_match = re.search(r'(\d+)\s*a(?:mp(?:s|ere)?)?', query_lower)
    if current_match:
        current_value = current_match.group(1)
        keywords.append({
            "canonical": f"{current_value}A",
            "text": f"{current_value}A",
            "type": "SPEC",
            "confidence": 0.92,
            "boost": boost_from_confidence(0.92)
        })

    # Duty cycle (e.g., "60%", "100 percent")
    duty_match = re.search(r'(\d+)\s*(?:%|percent)', query_lower)
    if duty_match:
        duty_value = duty_match.group(1)
        keywords.append({
            "canonical": f"{duty_value}%",
            "text": f"{duty_value}%",
            "type": "SPEC",
            "confidence": 0.90,
            "boost": boost_from_confidence(0.90)
        })

    # Voltage (e.g., "380V", "400 volts")
    voltage_match = re.search(r'(\d+)\s*v(?:olt(?:s)?)?', query_lower)
    if voltage_match:
        voltage_value = voltage_match.group(1)
        keywords.append({
            "canonical": f"{voltage_value}V",
            "text": f"{voltage_value}V",
            "type": "SPEC",
            "confidence": 0.88,
            "boost": boost_from_confidence(0.88)
        })

    # ─────────────────────────────────────────────────────────────
    # ATTRIBUTES (Design, features, etc.)
    # ─────────────────────────────────────────────────────────────
    attribute_patterns = {
        r'\bportable\b': ("portable", "portable", 0.90),
        r'\bcompact\b': ("compact", "compact", 0.88),
        r'\bwater[- ]?cool(?:ed)?\b': ("water-cooled", "water-cooled", 0.92),
        r'\binverter\b': ("inverter", "inverter", 0.85),
        r'\bsynergic\b': ("synergic", "synergic", 0.83),
        r'\bpulse\b': ("pulse", "pulse", 0.80),
        r'\bheavy[- ]?duty\b': ("heavy duty", "heavy duty", 0.85),
        r'\brobust\b': ("robust", "robust", 0.82),
    }

    for pattern, (canonical, text, conf) in attribute_patterns.items():
        if re.search(pattern, query_lower):
            keywords.append({
                "canonical": canonical,
                "text": text,
                "type": "ATTRIBUTE",
                "confidence": conf,
                "boost": boost_from_confidence(conf)
            })

    # ─────────────────────────────────────────────────────────────
    # MULTIPROCESS DETECTION (2+ processes mentioned)
    # ─────────────────────────────────────────────────────────────
    process_count = len([k for k in keywords if k["type"] == "PROCESS"])
    if process_count >= 2:
        keywords.append({
            "canonical": "multiprocess",
            "text": "multiprocess",
            "type": "ATTRIBUTE",
            "confidence": 0.88,
            "boost": boost_from_confidence(0.88)
        })

    # ─────────────────────────────────────────────────────────────
    # APPLICATION CONTEXT
    # ─────────────────────────────────────────────────────────────
    application_patterns = {
        r'\bshipyard\b': ("shipyard", "shipyard", 0.85),
        r'\bindustrial\b': ("industrial", "industrial", 0.82),
        r'\bon[- ]?site\b': ("on-site", "on-site", 0.84),
        r'\bfield\s*work\b': ("on-site", "field work", 0.83),
        r'\brobotic\b': ("robotic", "robotic", 0.86),
    }

    for pattern, (canonical, text, conf) in application_patterns.items():
        if re.search(pattern, query_lower):
            keywords.append({
                "canonical": canonical,
                "text": text,
                "type": "APPLICATION",
                "confidence": conf,
                "boost": boost_from_confidence(conf)
            })

    return keywords


def validate_and_enhance_product_names(keywords: List[Dict], component_type: str) -> List[Dict]:
    """
    Validate and enhance MODEL keywords against product_names.json

    Implements 3-tier boosting system:
    - Tier 1: Exact match → 0.98 confidence → 75x boost (15x base × 5x multiplier)
    - Tier 2: Fuzzy match >90% → 0.95 confidence → 40x boost (10x base × 4x multiplier)
    - Tier 3: LLM only → original confidence → 12x boost (6x base × 2x multiplier)

    Args:
        keywords: LLM-extracted keywords
        component_type: Component type (power_source, feeder, cooler, interconnector)

    Returns:
        Enhanced keywords with upgraded confidence and boost values
    """
    if not PRODUCT_NAMES_FLAT:
        print("⚠️  Product names not loaded - skipping validation")
        return keywords  # No validation available

    enhanced_keywords = []

    for kw in keywords:
        if kw['type'] == 'MODEL':
            # Try exact match first (case-insensitive)
            exact_match = next(
                (p for p in PRODUCT_NAMES_FLAT
                 if p['name_lower'] == kw['canonical'].lower()
                 and p['component_type'] == component_type),
                None
            )

            if exact_match:
                # Tier 1: Exact match - maximum boost
                kw['canonical'] = exact_match['name']  # Use official name
                kw['confidence'] = 0.98
                kw['boost'] = 75  # 15x base × 5x validated multiplier
                kw['validated'] = True
                kw['match_type'] = 'exact'
                print(f"   ✅ Exact match: '{kw['text']}' → '{exact_match['name']}' (75x boost)")
            else:
                # Try fuzzy match - use PARTIAL RATIO for partial name matching
                component_names = [p['name'] for p in PRODUCT_NAMES_FLAT if p['component_type'] == component_type]

                if component_names:
                    # Try multiple fuzzy matching strategies
                    # 1. Partial ratio (good for partial names like "Warrior" → "Warrior 500i CC/CV")
                    fuzzy_result = process.extractOne(
                        kw['canonical'],
                        component_names,
                        scorer=fuzz.partial_ratio,
                        score_cutoff=75  # Lower threshold for partial matches
                    )

                    if fuzzy_result:
                        # Tier 2: Fuzzy match - high boost
                        matched_name, score, _ = fuzzy_result
                        original_name = kw['canonical']
                        kw['canonical'] = matched_name  # REPLACE with canonical form
                        kw['confidence'] = 0.95
                        kw['boost'] = 40  # 10x base × 4x fuzzy multiplier
                        kw['validated'] = True
                        kw['match_type'] = 'fuzzy'
                        kw['similarity'] = score
                        print(f"   🔍 Fuzzy match: '{original_name}' → '{matched_name}' ({score}% similar, 40x boost)")
                    else:
                        # Tier 3: No validation - standard LLM boost
                        original_boost = kw['boost']
                        kw['boost'] = original_boost * 2  # 12x typically (6x base × 2x unvalidated)
                        kw['validated'] = False
                        kw['match_type'] = 'llm_only'
                        print(f"   📝 Unvalidated: '{kw['canonical']}' ({kw['boost']}x boost)")
                else:
                    # No product names for this component type
                    kw['validated'] = False
                    kw['match_type'] = 'llm_only'

        enhanced_keywords.append(kw)

    return enhanced_keywords


def normalize_parameter_values(keywords: List[Dict], component_type: str) -> List[Dict]:
    """
    Normalize parameter values using parameter_normalizations.json

    Similar to product name validation but for parameter values:
    - "5m" → ["5m", "5 m", "5.0m", "5 meter"]
    - "70mm" → ["70mm²", "70mm2", "70 mm²"]
    - "500A" → ["500A", "500 A", "500amp"]

    This ensures fuzzy matching works for parameter values with different formats
    """
    if not PARAMETER_NORMALIZATIONS or 'normalizations' not in PARAMETER_NORMALIZATIONS:
        print("⚠️  Parameter normalizations not loaded - skipping normalization")
        return keywords

    normalized_keywords = []
    normalizations = PARAMETER_NORMALIZATIONS['normalizations']

    # Get relevant parameters for this component type
    component_params = PARAMETER_NORMALIZATIONS.get('component_parameter_mapping', {}).get(component_type, [])

    for kw in keywords:
        keyword_type = kw['type']

        # Check if this keyword type needs normalization
        normalized = False

        for param_name in component_params:
            if param_name not in normalizations:
                continue

            param_config = normalizations[param_name]
            expected_type = param_config['parameter_type']

            # Match keyword type to parameter type
            if keyword_type == expected_type:
                # Try to find normalized form
                user_value = kw['canonical'].lower().strip()

                for canonical_value, variations in param_config['mappings'].items():
                    # Check if user's value matches any variation
                    if user_value in [v.lower() for v in variations]:
                        # Found a match - replace with canonical form
                        original_value = kw['canonical']
                        kw['canonical'] = canonical_value
                        kw['normalized'] = True
                        kw['original_value'] = original_value
                        kw['variations'] = variations  # Store all variations for Lucene query

                        # Update confidence based on normalization config
                        if 'confidence' in param_config:
                            kw['confidence'] = param_config['confidence']
                            kw['boost'] = boost_from_confidence(kw['confidence'])

                        print(f"   📐 Normalized: '{original_value}' → '{canonical_value}' ({len(variations)} variations)")
                        normalized = True
                        break

                if normalized:
                    break

        if not normalized:
            # Not normalized but might still be valid
            kw['normalized'] = False

        normalized_keywords.append(kw)

    return normalized_keywords


def build_component_specific_prompt(component_type: str) -> str:
    """
    Build dynamic LLM prompt based on component type using category_features_llm.json

    Leverages actual database ranges, examples, and capabilities to guide LLM extraction
    """
    # Base prompt (common to all components)
    base_prompt = """You are a welding equipment specification expert. Extract key welding parameters from user queries.

Extract the following types of information with confidence scores (0.0-1.0):

1. **PROCESS**: Welding processes (MIG/MAG, MMA/Stick/SMAW, DC TIG/GTAW, Lift TIG)
   - Use canonical names: "MIG/MAG", "MMA", "DC TIG"
   - Confidence: 0.90-0.96

2. **ATTRIBUTE**: Design features
   - portable, compact, water-cooled, air-cooled, inverter, synergic, pulse, etc.
   - Confidence: 0.80-0.92

3. **APPLICATION**: Use cases
   - shipyard, industrial, on-site, robotic, etc.
   - Confidence: 0.80-0.86

4. **MODEL**: Specific product names - extract EXACTLY what user said
   - Examples: "Aristo 500i", "Warrior 500i", "Cool 2", "RobustFeed"
   - Extract partial names too: "Warrior" → "Warrior"
   - IMPORTANT: Extract the FULL product name if mentioned, don't abbreviate
   - Confidence: 0.85-0.95

"""

    # Get category features from category_features_llm.json
    component_specific = ""

    if CATEGORY_FEATURES:
        category_name = COMPONENT_TO_CATEGORY_MAP.get(component_type)

        if category_name and category_name in CATEGORY_FEATURES:
            category_data = CATEGORY_FEATURES[category_name]
            features = category_data.get('features', {})

            param_num = 5

            # ============================================================
            # NUMERIC SPECS (Current, Voltage, Cable Length, etc.)
            # ============================================================
            numeric_specs = features.get('numeric_specs', [])
            if numeric_specs:
                component_specific += f"\n{'='*60}\n"
                component_specific += f"COMPONENT: {category_name} (Database: {category_data.get('product_count', 'N/A')} products)\n"
                component_specific += f"{'='*60}\n"

                for spec in numeric_specs:
                    spec_name = spec.get('name', '')
                    unit = spec.get('unit', '')
                    display = spec.get('display', '')

                    # Generate type name (e.g., "Cable Length" → "CABLE_LENGTH")
                    type_name = spec_name.upper().replace(' ', '_')

                    # Build examples from min/max or value
                    examples = []
                    if 'min' in spec and 'max' in spec:
                        min_val = spec['min']
                        max_val = spec['max']
                        # Generate 3-5 example values across the range
                        if max_val - min_val > 100:
                            examples = [f"{int(min_val)}{unit}", f"{int((min_val + max_val) / 2)}{unit}", f"{int(max_val)}{unit}"]
                        else:
                            examples = [f"{min_val}{unit}", f"{max_val}{unit}"]
                    elif 'value' in spec:
                        examples = [f"{spec['value']}{unit}"]

                    component_specific += f"\n{param_num}. **{type_name}**: {spec_name}\n"
                    component_specific += f"   - Range: {display}\n"
                    if examples:
                        component_specific += f"   - Examples: {', '.join(examples)}\n"
                    component_specific += f"   - Extract with unit: '{spec_name.lower()} 5 {unit}' → '5{unit}'\n"
                    component_specific += f"   - Confidence: 0.88-0.92\n"
                    param_num += 1

            # ============================================================
            # CATEGORICAL FEATURES (Cooling Type, etc.)
            # ============================================================
            categorical_features = features.get('categorical_features', [])
            if categorical_features:
                for feature in categorical_features:
                    feature_name = feature.get('name', '')
                    options = feature.get('options', [])

                    type_name = feature_name.upper().replace(' ', '_')

                    component_specific += f"\n{param_num}. **{type_name}**: {feature_name}\n"
                    component_specific += f"   - Available: {', '.join(options)}\n"
                    component_specific += f"   - Extract if mentioned: 'water cooled' → 'Water'\n"
                    component_specific += f"   - Confidence: 0.85-0.92\n"
                    param_num += 1

            # ============================================================
            # CAPABILITIES (Supported Processes, etc.)
            # ============================================================
            capabilities = features.get('capabilities', [])
            if capabilities:
                for capability in capabilities:
                    cap_name = capability.get('name', '')
                    values = capability.get('values', [])

                    if 'Process' in cap_name:
                        component_specific += f"\n{param_num}. **SUPPORTED_PROCESSES**: {cap_name}\n"
                        component_specific += f"   - Available in database: {', '.join(values)}\n"
                        component_specific += f"   - Extract ANY process mentioned by user\n"
                        component_specific += f"   - If 2+ processes mentioned, add 'multiprocess' ATTRIBUTE (confidence: 0.88)\n"
                        component_specific += f"   - Confidence: 0.90-0.96\n"
                        param_num += 1

            # ============================================================
            # KEY FEATURES (Portable design, Cloud connectivity, etc.)
            # ============================================================
            key_features = features.get('key_features', [])
            if key_features:
                component_specific += f"\n{param_num}. **KEY_FEATURES**: Design & Technology Features\n"
                component_specific += f"   - Available in database: {', '.join(key_features[:5])}\n"  # Show first 5
                component_specific += f"   - Extract as ATTRIBUTE type if user mentions any feature\n"
                component_specific += f"   - Confidence: 0.80-0.92\n"
                param_num += 1

    # Rules section
    rules = f"""
{'='*60}
IMPORTANT EXTRACTION RULES:
{'='*60}
- If user says "no MIG" or "not MIG" or "without MIG", DO NOT extract MIG
- Detect negation: "no", "not", "without", "except"
- If 2+ processes mentioned, add "multiprocess" ATTRIBUTE with confidence 0.88
- Extract MODEL keywords for ANY product mention, even partial names
- Extract ALL parameter values mentioned by user with correct units
- Use database ranges above to validate if values make sense
- Return empty list if no keywords found

Return JSON array ONLY (no explanation):
[
    {{"canonical": "MIG/MAG", "text": "MIG", "type": "PROCESS", "confidence": 0.96}},
    {{"canonical": "500A", "text": "500A", "type": "CURRENT_OUTPUT", "confidence": 0.92}},
    {{"canonical": "230V", "text": "230V", "type": "VOLTAGE", "confidence": 0.90}}
]"""

    return base_prompt + component_specific + rules


async def extract_keywords_llm(query: str, component_type: str = "power_source") -> List[Dict[str, Any]]:
    """
    LLM-based keyword extraction using OpenAI GPT-4.

    Returns list of keywords with confidence scores:
    [
        {
            "canonical": "MIG/MAG",
            "text": "MIG",
            "type": "PROCESS",
            "confidence": 0.96,
            "boost": 10
        },
        ...
    ]
    """
    if not openai_client or not USE_LLM_EXTRACTION:
        # Fallback to mock if LLM not available
        return extract_keywords_mock(query)

    try:
        # Build dynamic component-specific prompt
        system_prompt = build_component_specific_prompt(component_type)
        user_prompt = f"Extract welding keywords from: \"{query}\""

        # Call OpenAI
        response = await openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,  # Low temperature for consistency
            max_tokens=1000
        )

        # Parse LLM response
        llm_output = response.choices[0].message.content.strip()

        # Remove markdown code blocks if present
        if llm_output.startswith("```"):
            llm_output = llm_output.split("```")[1]
            if llm_output.startswith("json"):
                llm_output = llm_output[4:]
            llm_output = llm_output.strip()

        keywords = json.loads(llm_output)

        # Add boost scores based on confidence
        for kw in keywords:
            kw["boost"] = boost_from_confidence(kw["confidence"])

        # Validate and enhance product names against database
        print(f"🔍 Validating product names against database...")
        keywords = validate_and_enhance_product_names(keywords, component_type)

        # Normalize parameter values (cable_length, cross_section, etc.)
        print(f"📐 Normalizing parameter values...")
        keywords = normalize_parameter_values(keywords, component_type)

        return keywords

    except Exception as e:
        print(f"⚠️  LLM extraction failed: {e}")
        print(f"   Falling back to mock extraction")
        return extract_keywords_mock(query)


def escape_lucene_special_chars(text: str) -> str:
    """Escape special Lucene characters to prevent syntax errors"""
    # Lucene special characters that need escaping
    special_chars = ['+', '-', '&', '|', '!', '(', ')', '{', '}', '[', ']',
                    '^', '"', '~', '*', '?', ':', '\\', '/']

    result = text
    for char in special_chars:
        result = result.replace(char, f'\\{char}')

    return result

def build_fulltext_lucene_query(query: str) -> str:
    """
    Build full-text Lucene query (current approach)
    Simply removes stopwords and uses all words equally
    """
    # Basic stopword removal
    stopwords = {"i", "need", "a", "an", "the", "that", "can", "handle", "want", "with", "for", "to", "of", "and"}
    words = query.lower().split()
    filtered_words = [w for w in words if w not in stopwords and len(w) > 2]

    # Escape special characters for each word
    escaped_words = [escape_lucene_special_chars(w) for w in filtered_words]

    # Join with spaces (Lucene OR by default)
    lucene_query = " ".join(escaped_words)
    return lucene_query

def build_weighted_lucene_query(keywords: List[Dict[str, Any]]) -> str:
    """
    Build weighted Lucene query with boost factors
    From helper script logic (lines 226-243)
    """
    if not keywords:
        return "*"  # Match all if no keywords

    query_parts = []

    for kw in keywords:
        canonical = kw["canonical"]
        boost = kw["boost"]
        kw_type = kw["type"]

        # Escape ALL special characters for Lucene (not just quotes)
        canonical_escaped = escape_lucene_special_chars(canonical)

        # Apply type-specific boost multipliers
        if kw_type == "MODEL":
            # Model names get 3x multiplier (boost * 3)
            final_boost = boost * 3
        elif kw_type in ("PROCESS", "SPEC"):
            # Process and specs get 1.5x multiplier
            final_boost = int(boost * 1.5)
        elif kw_type == "ATTRIBUTE":
            # Attributes use base boost
            final_boost = boost
        else:
            # Unknown type, use half boost
            final_boost = max(1, boost // 2)

        # Build query term with boost
        if " " in canonical or "-" in canonical:
            # Multi-word or hyphenated terms use phrase search
            query_parts.append(f'"{canonical_escaped}"^{final_boost}')
        else:
            # Single word
            query_parts.append(f'{canonical_escaped}^{final_boost}')

    # Combine with OR
    lucene_query = " OR ".join(query_parts)
    return lucene_query

# ============================================================================
# Neo4j Lucene Search
# ============================================================================

async def execute_lucene_search(
    lucene_query: str,
    component_type: str = "power_source",
    limit: int = 20
) -> Dict[str, Any]:
    """
    Execute Lucene search against Neo4j productIndex

    Args:
        lucene_query: Lucene query string (full-text or weighted)
        component_type: Component type (power_source, feeder, etc.)
        limit: Max results

    Returns:
        Dict with results, count, execution time, top score
    """
    # Map component_type to Neo4j category
    category_map = {
        "power_source": "Powersource",
        "feeder": "Feeder",
        "cooler": "Cooler",
        "interconnector": "Interconn",
        "torch": "Torches"
    }
    category = category_map.get(component_type, "Powersource")

    # Cypher query (same for both approaches, only lucene_query param differs)
    cypher_query = """
    CALL db.index.fulltext.queryNodes("productIndex", $lucene_query)
    YIELD node, score
    WHERE node.category = $category
    RETURN
        node.gin as gin,
        node.item_name as name,
        node.clean_description as description,
        score
    ORDER BY score DESC
    LIMIT $limit
    """

    start_time = time.time()

    try:
        async with driver.session() as session:
            result = await session.run(
                cypher_query,
                lucene_query=lucene_query,
                category=category,
                limit=limit
            )
            records = await result.data()

        execution_time_ms = (time.time() - start_time) * 1000

        # Convert records to list of dicts
        products = []
        for record in records:
            products.append({
                "gin": record["gin"],
                "name": record["name"],
                "description": record.get("description", ""),
                "score": float(record["score"])
            })

        top_score = products[0]["score"] if products else 0.0

        return {
            "lucene_query": lucene_query,
            "results": products,
            "count": len(products),
            "execution_time_ms": round(execution_time_ms, 2),
            "top_score": round(top_score, 2)
        }

    except Exception as e:
        print(f"❌ Neo4j query error: {e}")
        raise HTTPException(status_code=500, detail=f"Neo4j query failed: {str(e)}")

# ============================================================================
# Comparison Metrics
# ============================================================================

def calculate_precision(results: List[Dict], expected_keywords: List[str]) -> float:
    """
    Calculate precision based on how many results contain expected keywords
    Simple heuristic for POC (real version would use labeled data)
    """
    if not results:
        return 0.0

    relevant_count = 0
    for product in results:
        name = product["name"].lower()
        description = product.get("description", "").lower()
        combined_text = f"{name} {description}"

        # Check if any expected keyword appears
        matches = sum(1 for kw in expected_keywords if kw.lower() in combined_text)
        if matches > 0:
            relevant_count += 1

    precision = relevant_count / len(results)
    return round(precision, 3)

def calculate_comparison_metrics(
    results_a: Dict[str, Any],
    results_b: Dict[str, Any],
    keywords: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calculate comparison metrics between Test A and Test B
    """
    # Extract expected keywords for precision calculation
    expected_keywords = [kw["canonical"] for kw in keywords]

    # Calculate precision for both
    precision_a = calculate_precision(results_a["results"], expected_keywords)
    precision_b = calculate_precision(results_b["results"], expected_keywords)

    # Calculate improvement
    improvement_percent = 0.0
    if precision_a > 0:
        improvement_percent = ((precision_b - precision_a) / precision_a) * 100

    # Calculate speed improvement
    speed_improvement_percent = 0.0
    if results_a["execution_time_ms"] > 0:
        speed_improvement_percent = (
            (results_a["execution_time_ms"] - results_b["execution_time_ms"])
            / results_a["execution_time_ms"]
        ) * 100

    # Determine winner
    winner = "test_b" if precision_b > precision_a else "test_a"

    return {
        "precision_a": precision_a,
        "precision_b": precision_b,
        "improvement_percent": round(improvement_percent, 1),
        "speed_improvement_percent": round(speed_improvement_percent, 1),
        "winner": winner
    }

# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def serve_html():
    """Serve the HTML test UI at root path"""
    html_path = pathlib.Path(__file__).parent / "test_weighted_search_ui.html"
    if not html_path.exists():
        return {
            "error": "HTML file not found",
            "expected_path": str(html_path),
            "alternative": "Open file:///Users/bharath/Desktop/Ayna_ESAB_Nov7/src/backend/tests/manual/test_weighted_search_ui.html",
            "api_docs": "http://localhost:8001/docs"
        }
    return FileResponse(html_path)

@app.get("/api")
async def root():
    """API info endpoint"""
    return {
        "message": "Weighted Lucene Search POC API",
        "version": "1.0.0",
        "endpoints": {
            "/": "GET - HTML Test UI",
            "/api": "GET - API info (this page)",
            "/test/compare-search": "POST - Compare full-text vs weighted search",
            "/health": "GET - Health check",
            "/docs": "GET - Swagger documentation"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test Neo4j connection
        async with driver.session() as session:
            await session.run("RETURN 1")

        return {
            "status": "healthy",
            "neo4j_connection": "ok",
            "neo4j_uri": NEO4J_URI
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Neo4j connection failed: {str(e)}")

@app.post("/test/compare-search", response_model=CompareResponse)
async def compare_search(request: CompareRequest):
    """
    Compare full-text Lucene vs weighted keyword Lucene

    This endpoint:
    1. Extracts keywords from query (mock LLM)
    2. Builds both query types
    3. Executes both against Neo4j
    4. Returns side-by-side comparison
    """
    print(f"\n{'='*60}")
    print(f"📝 Query: {request.query[:80]}...")
    print(f"🔧 Component: {request.component_type}")
    print(f"{'='*60}\n")

    # Step 1: Extract keywords (LLM or mock)
    extraction_method = "LLM" if USE_LLM_EXTRACTION else "Mock"
    print(f"🎯 Extracting keywords ({extraction_method})...")
    keywords = await extract_keywords_llm(request.query, request.component_type)
    print(f"   Extracted {len(keywords)} keywords")
    for kw in keywords:
        print(f"   • {kw['canonical']} ({kw['type']}) - boost: {kw['boost']}x")

    # Step 2: Build queries
    print("\n🔨 Building Lucene queries...")
    fulltext_query = build_fulltext_lucene_query(request.query)
    print(f"   Test A (Full-text): {fulltext_query[:100]}...")

    weighted_query = build_weighted_lucene_query(keywords)
    print(f"   Test B (Weighted):  {weighted_query[:100]}...")

    # Step 3: Execute both searches
    print("\n🔍 Executing searches...")
    results_a = await execute_lucene_search(fulltext_query, request.component_type, request.limit)
    print(f"   Test A: {results_a['count']} results in {results_a['execution_time_ms']}ms")

    results_b = await execute_lucene_search(weighted_query, request.component_type, request.limit)
    print(f"   Test B: {results_b['count']} results in {results_b['execution_time_ms']}ms")

    # Step 4: Calculate metrics
    print("\n📊 Calculating comparison metrics...")
    metrics = calculate_comparison_metrics(results_a, results_b, keywords)
    print(f"   Precision A: {metrics['precision_a']:.1%}")
    print(f"   Precision B: {metrics['precision_b']:.1%}")
    print(f"   🏆 Winner: {metrics['winner']}")
    print(f"\n{'='*60}\n")

    # Return comparison
    return CompareResponse(
        query=request.query,
        extracted_keywords=keywords,
        test_a_fulltext=results_a,
        test_b_weighted=results_b,
        comparison_metrics=metrics
    )

# ============================================================================
# Startup/Shutdown
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Verify connections on startup"""
    print("\n" + "="*60)
    print("🚀 Weighted Lucene Search POC - Test Server")
    print("="*60)
    print(f"📡 Neo4j URI: {NEO4J_URI}")
    print(f"👤 Neo4j User: {NEO4J_USERNAME}")

    # Test connection
    try:
        async with driver.session() as session:
            result = await session.run("RETURN 1 as test")
            await result.single()
        print("✅ Neo4j connection successful")
    except Exception as e:
        print(f"❌ Neo4j connection failed: {e}")
        print("   Check your .env file and Neo4j server")

    print("\n📝 API Documentation: http://localhost:8001/docs")
    print("🌐 HTML Test UI: Open test_weighted_search_ui.html in browser")
    print("="*60 + "\n")

@app.on_event("shutdown")
async def shutdown_event():
    """Close connections on shutdown"""
    print("\n🛑 Shutting down...")
    await driver.close()
    print("✅ Neo4j connection closed")

# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )
