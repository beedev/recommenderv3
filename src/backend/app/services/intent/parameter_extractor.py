"""
Enhanced Parameter Extraction Service for S1→SN Flow
Extracts user requirements using LLM-based parameter extraction
Component-based structure with product name knowledge
Schema-driven component list from master_parameter_schema.json

ENHANCEMENTS FROM DOCUMENT 4:
- Removed unused 'available_products' parameter for cleaner API
- Added optional fallback config for better testability
"""

import logging
import json
import os
from typing import Dict, List, Optional, Any
from openai import AsyncOpenAI
from langsmith import traceable
import sys

from app.config.schema_loader import get_component_list
from app.services.config.configuration_service import get_config_service

logger = logging.getLogger(__name__)


class ParameterExtractor:
    """
    LLM-based parameter extraction for welding requirements
    Component-based extraction with product name recognition
    
    ENHANCED FEATURES:
    - Clean API (no unused parameters)
    - Optional fallback config (works without config_service)
    - All original Document 3 functionality preserved
    """

    def __init__(self, openai_api_key: str, config_service=None):
        """
        Initialize parameter extractor with OpenAI client
        
        Args:
            openai_api_key: OpenAI API key
            config_service: Optional config service (will use fallback if not provided)
        
        ENHANCED: Now supports optional config_service for better testability
        """
        self.client = AsyncOpenAI(api_key=openai_api_key)
        
        # ORIGINAL: Use config service (with optional fallback)
        if config_service is None:
            try:
                self.config_service = get_config_service()
                logger.info("Using provided config service")
            except Exception as e:
                logger.warning(f"Config service not available, using fallback config: {e}")
                self.config_service = self._get_fallback_config()
        else:
            self.config_service = config_service

        # ORIGINAL: Load product names for fuzzy matching
        self.product_names = self._load_product_names()

        logger.info("Parameter Extractor initialized with product name knowledge")

    def _get_fallback_config(self):
        """
        Create fallback configuration when ConfigurationService is unavailable.

        Provides minimal configuration for standalone operation and testing without
        requiring full configuration infrastructure. Enables fuzzy matching and LLM
        configuration using reasonable defaults.

        Returns:
            FallbackConfig: Simple config object with methods:
                - get_fuzzy_match_config(): Returns fuzzy match settings from component_types.json
                - get_llm_config(name): Returns default LLM settings (GPT-4, temp=0.3, max_tokens=2000)
                - get_prompt(name): Returns basic system prompt for parameter extraction

        Note:
            This fallback allows the ParameterExtractor to work in environments where
            the full ConfigurationService is not available (e.g., unit tests, standalone scripts).

        Raises:
            Exception: If component_types.json cannot be loaded for fuzzy matching config

        Examples:
            >>> extractor = ParameterExtractor(api_key, config_service=None)
            >>> # Automatically uses fallback config
            >>> fuzzy_config = extractor.config_service.get_fuzzy_match_config()
            >>> fuzzy_config["enabled"]
            True
        """
        class FallbackConfig:
            """Simple fallback config for testing/standalone operation"""

            def get_fuzzy_match_config(self):
                # Rationalized Nov 15, 2025: components_enabled no longer in search_config
                # Load from component_types.json instead
                from app.config.schema_loader import load_component_config
                component_types = load_component_config()
                enabled_components = [
                    key for key, data in component_types.items()
                    if data.get("fuzzy_matching_enabled", False)
                ]
                return {
                    "enabled": True,
                    "components_enabled": enabled_components
                }
            
            def get_llm_config(self, name):
                return {
                    "model": "gpt-4",
                    "temperature": 0.3,
                    "max_tokens": 2000
                }
            
            def get_prompt(self, name):
                return "You are a welding equipment expert. Extract technical parameters from user queries into component-based JSON structure."
        
        logger.info("Using fallback configuration")
        return FallbackConfig()

    def _load_product_names(self) -> Dict[str, List[str]]:
        """
        Load product names from llm_context.json filtered by fuzzy matching configuration.

        Loads product names for fuzzy matching and selection intent detection. Only includes
        components enabled for fuzzy matching in component_types.json to avoid huge prompts.

        Returns:
            Dict[str, List[str]]: Product names organized by component category.
                Example: {
                    "power_source": ["Aristo 500ix CE", "Warrior 400i CC/CV", ...],
                    "feeder": ["RobustFeed U6 Water-cooled Euro", ...],
                    "cooler": ["Cool2 Cooling Unit", ...]
                }

        Note:
            - Consolidated Nov 15, 2025: Moved from product_names.json to llm_context.json
            - Only loads components with fuzzy_matching_enabled=true in component_types.json
            - Returns empty dict if llm_context.json cannot be loaded (logs warning)

        Examples:
            >>> extractor = ParameterExtractor(api_key)
            >>> extractor.product_names["power_source"][:2]
            ["Aristo 500ix CE", "Warrior 400i CC/CV"]
            >>> len(extractor.product_names)  # Only enabled components
            3
        """
        try:
            config_path = os.path.join(
                os.path.dirname(__file__),
                "../../config/llm_context.json"
            )

            with open(config_path, "r") as f:
                llm_context = json.load(f)
                all_products = llm_context.get("product_names", {})
                competitor_products = llm_context.get("competitor_product_names", {})

            # Get components enabled for fuzzy matching from component_types.json (rationalized Nov 15, 2025)
            fuzzy_config = self.config_service.get_fuzzy_match_config()
            # For backward compatibility, try to get from fuzzy_config first, else load from component_types
            components_enabled = fuzzy_config.get("components_enabled")
            if not components_enabled:
                from app.config.schema_loader import load_component_config
                component_types = load_component_config()
                components_enabled = [
                    key for key, data in component_types.items()
                    if data.get("fuzzy_matching_enabled", False)
                ]

            # Only include enabled components to avoid huge prompts
            limited_products = {}
            for component in components_enabled:
                if component in all_products:
                    limited_products[component] = all_products[component]

            # Also include competitor mapping if available
            if competitor_products:
                limited_products["_competitor_mapping"] = competitor_products

            logger.info(f"Loaded product names: {sum(len(v) for v in limited_products.values())} total (components: {components_enabled})")
            return limited_products

        except Exception as e:
            logger.warning(f"Could not load product names: {e}")
            return {}

    @traceable(name="extract_parameters", run_type="llm")
    async def extract_parameters(
        self,
        user_message: str,
        current_state: str,
        master_parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract parameters from user message using LLM
        Returns complete updated MasterParameterJSON

        Args:
            user_message: User's natural language input
            current_state: Current state (e.g., "power_source_selection")
            master_parameters: Existing MasterParameterJSON dict

        Returns:
            Updated complete MasterParameterJSON dict with optional _selection_metadata

        ENHANCED: Added selection intent detection for numbers and product names
        FIXED (Nov 15, 2025): Clear current state component before extraction to prevent accumulation
        """

        try:
            logger.info(f"Extracting parameters for state: {current_state}")

            # ✨ NEW: Check for selection intent BEFORE LLM call
          #  selection_metadata = self._detect_selection_intent(user_message)
          #  if selection_metadata and selection_metadata.get("is_selection"):
          #      logger.info(f"Selection detected: {selection_metadata}")
          #      # Return master parameters with selection metadata
          #      result = dict(master_parameters)
          #      result["_selection_metadata"] = selection_metadata
          #      return result

            # 🔧 FIX (Nov 15, 2025): Clear current state's component to prevent accumulation
            # User requirement: "Within a state, each new query should REPLACE parameters, not accumulate"
            # Example: In PowerSource state, "Aristo" then "Renegade" → show only Renegade
            master_parameters_cleared = self._clear_current_state_component(
                master_parameters,
                current_state
            )

            # Build extraction prompt based on current state
            prompt = self._build_extraction_prompt(
                user_message,
                current_state,
                master_parameters_cleared
            )

            # ORIGINAL: Get LLM config for parameter extraction
            llm_config = self.config_service.get_llm_config("parameter_extraction")
            system_prompt = self.config_service.get_prompt("parameter_extraction_system")

            # ORIGINAL: Call OpenAI for parameter extraction
            response = await self.client.chat.completions.create(
                model=llm_config.get("model", "gpt-4"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=llm_config.get("temperature", 0.3),
                max_tokens=llm_config.get("max_tokens", 2000)
            )

            # Parse LLM response
            extracted_text = response.choices[0].message.content
            updated_master = self._parse_llm_response(extracted_text, master_parameters)

            logger.info(f"Extraction complete. Updated components: {list(updated_master.keys())}")
            return updated_master

        except Exception as e:
            logger.error(f"Parameter extraction failed: {e}")

            # Return unchanged master_parameters on error
            return master_parameters

    def _detect_selection_intent(self, user_message: str) -> Optional[Dict[str, Any]]:
        """
        Detect if user input is a product selection (number index or product name).

        Fast pre-LLM detection for common selection patterns to avoid unnecessary LLM calls.
        Matches pure numbers (1-10), numbers with context ("option 2"), and explicit product
        names from the loaded product catalog.

        Args:
            user_message: User's input text to analyze

        Returns:
            Optional[Dict[str, Any]]: Selection metadata dict if selection detected, None otherwise.
                Structure when detected:
                {
                    "is_selection": True,
                    "selected_index": int (1-10) or None,
                    "selected_product_name": str or None,
                    "skip_intent": False
                }

        Detection Patterns:
            Pattern 1 - Pure number: "2", "3" (range 1-10)
            Pattern 2 - Number with context: "option 2", "3rd one", "give me 1", "i want 4"
            Pattern 3 - Explicit product name: Partial match against loaded product names

        Examples:
            >>> extractor._detect_selection_intent("2")
            {"is_selection": True, "selected_index": 2, "selected_product_name": None, ...}

            >>> extractor._detect_selection_intent("option 3")
            {"is_selection": True, "selected_index": 3, "selected_product_name": None, ...}

            >>> extractor._detect_selection_intent("Aristo 500ix")
            {"is_selection": True, "selected_index": None, "selected_product_name": "Aristo 500ix CE", ...}

            >>> extractor._detect_selection_intent("I need 500A MIG welder")
            None  # Not a selection, requires LLM extraction

        Note:
            Selection metadata is returned to extract_parameters() which attaches it to
            MasterParameterJSON as "_selection_metadata" for orchestrator processing.
        """
        import re

        message = user_message.strip().lower()

        # Pattern 1: Pure number (e.g., "2", "3")
        if re.match(r'^\d+$', message):
            index = int(message)
            if 1 <= index <= 10:  # Reasonable range
                logger.info(f" Pure number selection detected: {index}")
                return {
                    "is_selection": True,
                    "selected_index": index,
                    "selected_product_name": None,
                    "skip_intent": False
                }

        # Pattern 2: Number with context (e.g., "option 2")
        number_patterns = [
            r'^\s*(?:option|number|item|product|choice)\s+(\d+)\s*$',
            r'^\s*(\d+)\s*(?:st|nd|rd|th)?\s*(?:option|one)?\s*$',
            r'^\s*i\s*(?:want|need|choose|select|pick)\s+(\d+)\s*$',
            r'^\s*give\s+me\s+(\d+)\s*$'
        ]

        for pattern in number_patterns:
            match = re.match(pattern, message)
            if match:
                index = int(match.group(1))
                if 1 <= index <= 10:
                    logger.info(f" Number selection with context detected: {index}")
                    return {
                        "is_selection": True,
                        "selected_index": index,
                        "selected_product_name": None,
                        "skip_intent": False
                    }

        # Pattern 3: Explicit product name (partial match)
        for category, names in self.product_names.items():
            for product_name in names:
                if product_name.lower() in message:
                    logger.info(f" Product name selection detected: {product_name}")
                    return {
                        "is_selection": True,
                        "selected_index": None,
                        "selected_product_name": product_name,
                        "skip_intent": False
                    }

        return None

    def _clear_current_state_component(
        self,
        master_parameters: Dict[str, Any],
        current_state: str
    ) -> Dict[str, Any]:
        """
        Clear component parameters for current state to prevent accumulation.

        Implements replacement behavior: within a state, each new query replaces previous
        parameters instead of accumulating them. Prevents "Aristo" + "Renegade" showing
        both products when user only wants the latest request.

        Args:
            master_parameters: Existing MasterParameterJSON dict
            current_state: Current configurator state (e.g., "power_source_selection")

        Returns:
            Dict[str, Any]: Modified master_parameters with current state's component cleared to empty dict {}

        State-to-Component Mapping:
            - power_source_selection → power_source
            - feeder_selection → feeder
            - cooler_selection → cooler
            - interconnector_selection → interconnector
            - torch_selection → torch
            - accessories_selection → accessories
            - (and other accessory/remote states)

        Examples:
            >>> master_params = {"power_source": {"product_name": "Aristo 500ix"}, "feeder": {}}
            >>> cleared = extractor._clear_current_state_component(master_params, "power_source_selection")
            >>> cleared["power_source"]
            {}  # Cleared for replacement
            >>> cleared["feeder"]
            {}  # Unchanged (different state)

        Note:
            User requirement (Nov 15, 2025): "Within a state, each new query should REPLACE
            parameters, not accumulate. For example, in PowerSource state, asking for 'Aristo'
            then 'Renegade' should show only Renegade, not both."

            States that don't map to a component (e.g., "finalize") return parameters unchanged.
        """
        # Map state to component
        state_to_component = {
            "power_source_selection": "power_source",
            "feeder_selection": "feeder",
            "cooler_selection": "cooler",
            "interconnector_selection": "interconnector",
            "torch_selection": "torch",
            "accessories_selection": "accessories",
            "powersource_accessories_selection": "powersource_accessories",
            "feeder_accessories_selection": "feeder_accessories",
            "feeder_conditional_accessories_selection": "feeder_conditional_accessories",
            "interconnector_accessories_selection": "interconnector_accessories",
            "remote_selection": "remote",
            "remote_accessories_selection": "remote_accessories",
            "remote_conditional_accessories_selection": "remote_conditional_accessories",
            "connectivity_selection": "connectivity"
        }

        # Get component for current state
        component_to_clear = state_to_component.get(current_state)

        if component_to_clear:
            # Make a copy to avoid modifying original
            cleared_params = dict(master_parameters)

            # Clear the component
            if component_to_clear in cleared_params:
                logger.info(f"🔄 Clearing '{component_to_clear}' parameters for state '{current_state}' (preventing accumulation)")
                cleared_params[component_to_clear] = {}

            return cleared_params
        else:
            # State doesn't map to a component (e.g., finalize), return as-is
            logger.debug(f"State '{current_state}' does not map to a component, keeping all parameters")
            return master_parameters

    def _build_extraction_prompt(
        self,
        user_message: str,
        current_state: str,
        master_parameters: Dict[str, Any]
    ) -> str:
        """
        Build comprehensive LLM prompt for parameter extraction from user query.

        Creates a massive ~750-line prompt with state-specific guidance, technical pattern examples,
        product name fuzzy matching instructions, and operator extraction rules. This is the core
        intelligence behind converting natural language to structured MasterParameterJSON.

        Args:
            user_message: User's natural language input (e.g., "500A MIG welder for aluminum")
            current_state: Current configurator state (e.g., "power_source_selection")
            master_parameters: Existing MasterParameterJSON dict (for context preservation)

        Returns:
            str: Complete prompt for OpenAI GPT-4 with:
                - State-specific extraction guidance
                - Technical specification patterns (current, voltage, duty cycle, etc.)
                - Product name fuzzy matching instructions
                - Comparison operator extraction rules (lte, gte, lt, gt, eq, range, approx)
                - Compound request handling
                - Known product names reference (from llm_context.json)
                - Existing parameters for context
                - Output format instructions

        Prompt Sections:
            1. State-Specific Guidance: Focused extraction based on current state
            2. Product Name Reference: Top 10 known products per component (fuzzy matching)
            3. Technical Specification Patterns: Current/duty cycle, process types, voltage, features
            4. Comparison Operators: lte, gte, lt, gt, eq, range, approx with keyword examples
            5. Compound Request Handling: Multi-component extraction in single message
            6. Output Format: JSON structure with all components + english_query field

        Examples:
            State-specific guidance:
            >>> # power_source_selection state
            >>> prompt = extractor._build_extraction_prompt(
            ...     "500A @60% MIG welder",
            ...     "power_source_selection",
            ...     master_params
            ... )
            >>> "Process types: MIG (GMAW)" in prompt
            True
            >>> "Current ratings with duty cycles" in prompt
            True

            Product name fuzzy matching:
            >>> "Aristo 500ix CE" in prompt  # Known product name
            True
            >>> "FUZZY MATCHING & INFERENCE RULES" in prompt
            True

            Operator extraction:
            >>> "max 300A" in prompt  # Example for lte operator
            True
            >>> "at least 500A" in prompt  # Example for gte operator
            True

        Note:
            This is one of the most critical methods in the system. The prompt quality
            directly determines extraction accuracy. Enhanced Nov 15, 2025 with:
            - Better duty cycle extraction
            - Comparison operator support
            - Improved product name fuzzy matching
            - GIN number detection
            - Multilingual query translation
        """

        # Enhanced state-specific extraction guidance with detailed patterns
        state_guidance = {
            "power_source_selection": """
FOCUS: Extract requirements for POWER SOURCE component
Look for:
  - Process types: MIG (GMAW), MAG, MMA/Stick, TIG (GTAW), DC TIG, Lift TIG, pulse
  - Current ratings with duty cycles: "500A @60%", "300A at 40%", "400A at 100%"
  - Voltage specifications: "380-460V", "dual voltage", "230-480V", "single/three phase"
  - Inverter technology: "inverter", "inverter-based", "portable inverter"
  - Advanced features: "synergic", "pulse", "super pulse", "double pulse", "multiprocess"
  - Design attributes: "portable", "heavy duty", "robust", "compact", "high power-to-weight"
  - Applications: "shipyard", "industrial", "on-site", "robotic", "field work"
  - Integration: "robot interface", "cloud connectivity", "WeldCloud"
  - Cooling: "integrated cooling", "integrated water cooling", "built-in cooler"
  - Accessories included: "with cables", "welding and return cables"
Product Names: Extract specific model names (e.g., "Warrior 400i", "Aristo 500ix", "Renegade ES 300i")
""",
            "feeder_selection": """
FOCUS: Extract requirements for FEEDER component
Look for:
  - Process type: MIG, MAG, GMAW, wire feed
  - Material: aluminum, steel, stainless steel
  - Thickness: "6mm", "3-12mm", "thin", "thick"
  - Cooling type: "water cooled", "liquid cooled", "gas cooled", "air cooled"
  - Wire diameter: "0.8-1.6mm", "1.0mm", "1.2mm"
  - Features: "synergic", "digital", "push-pull", "SuperPulse"
Product Names: Extract specific feeder models (e.g., "RobustFeed U6", "Pulse U82")
""",
            "cooler_selection": """
FOCUS: Extract requirements for STANDALONE COOLER component (NOT integrated cooling)
⚠️ IMPORTANT: If user mentions "integrated cooling" or "built-in cooler", extract as power_source.cooling_type="integrated", NOT as a separate cooler component.
Look for STANDALONE coolers only:
  - Duty cycle: "60%", "100%", high duty cycle
  - Application: shipyard, industrial, heavy duty
  - Environment: indoor, outdoor, harsh conditions
  - Cooling capacity: cooling power (for standalone units)
  - Type: "water cooled", "liquid cooled" (for standalone units)
Product Names: Extract specific cooler models (e.g., "Cool2", "Cool3")
""",
            "interconnector_selection": """
FOCUS: Extract requirements for INTERCONNECTOR component
Look for:
  - Cable length: "5m", "10m", "15m"
  - Current rating: "300A", "500A"
  - Cooling type: "gas cooled", "liquid cooled", "water cooled"
  - Cross-section: cable thickness specifications
""",
            "torch_selection": """
FOCUS: Extract requirements for TORCH component
Look for:
  - Process type: MIG, MAG, TIG
  - Current rating: "300A", "500A"
  - Cooling type: "water cooled", "air cooled", "gas cooled"
  - Swan neck angle: "45°", "60°"
  - Features: "robotic", "manual", "ergonomic"
""",
            "accessories_selection": """
FOCUS: Extract requirements for ACCESSORIES component
Look for:
  - Accessory type: cables, remote control, wire spool, gas hose
  - Compatibility: specific product compatibility
  - Cable length: "5m", "10m"
  - Remote control features: digital, analog, pendant
  - Additional features: "with cables included"
"""
        }

        guidance = state_guidance.get(current_state, "Extract any welding-related requirements")

        # Build product name reference
        product_reference = ""
        if self.product_names:
            product_reference = "\n\nKNOWN PRODUCT NAMES (for reference):\n"

            if self.product_names.get("power_source"):
                product_reference += "\nPower Sources:\n"
                product_reference += "\n".join([f"  - {name}" for name in self.product_names["power_source"][:10]])
                if len(self.product_names["power_source"]) > 10:
                    product_reference += f"\n  ... and {len(self.product_names['power_source']) - 10} more"

            if self.product_names.get("feeder"):
                product_reference += "\n\nFeeders:\n"
                product_reference += "\n".join([f"  - {name}" for name in self.product_names["feeder"][:10]])
                if len(self.product_names["feeder"]) > 10:
                    product_reference += f"\n  ... and {len(self.product_names['feeder']) - 10} more"

            if self.product_names.get("cooler"):
                product_reference += "\n\nCoolers:\n"
                product_reference += "\n".join([f"  - {name}" for name in self.product_names["cooler"][:10]])
                if len(self.product_names["cooler"]) > 10:
                    product_reference += f"\n  ... and {len(self.product_names['cooler']) - 10} more"
#added code to handle competitor data. 
            if self.product_names.get("_competitor_mapping"):
                product_reference += "\n\nCOMPETITOR TO ESAB MAPPING:\n"
                product_reference += "If user mentions a competitor, use the ESAB equivalent:\n\n"
                
                # Reverse the mapping: competitor -> ESAB
                competitor_to_esab = {}
                for esab_prod, competitors_str in self.product_names["_competitor_mapping"].items():
                    for competitor in competitors_str.split(','):
                        competitor = competitor.strip()
                        competitor_to_esab[competitor] = esab_prod
                
                # Show the reversed mapping (limit to 20 for brevity)
                for i, (competitor, esab) in enumerate(list(competitor_to_esab.items())[:20]):
                    product_reference += f"  '{competitor}' → '{esab}'\n"
                
                if len(competitor_to_esab) > 20:
                    product_reference += f"  ... and {len(competitor_to_esab) - 20} more mappings\n"
                product_reference += "\n"

        master_params_dict = master_parameters.dict() if hasattr(master_parameters, 'dict') else master_parameters
        serializable_params = {
            k: v for k, v in master_params_dict.items()
            if k != "last_updated" and not isinstance(v, type(master_params_dict.get("last_updated")))
        }

        prompt = f"""
TASK: Extract welding equipment requirements from user query and update the Master Parameter JSON.

USER QUERY: "{user_message}"

CURRENT STATE: {current_state}

{guidance}

EXISTING MASTER PARAMETER JSON:
{json.dumps(serializable_params, indent=2)}
{product_reference}

COMPREHENSIVE EXTRACTION INSTRUCTIONS:

1. COMPONENT-BASED EXTRACTION:
   - Each component (power_source, feeder, cooler, interconnector, torch, accessories) has its own dict.
   - Extract requirements into the appropriate component dict based on current state.
   - Use string keys and string values (e.g., {{"current_rating": "500A @60%", "process": "MIG (GMAW)"}}).

2. TECHNICAL SPECIFICATION PATTERNS (CRITICAL):

   a) CURRENT & DUTY CYCLE WITH COMPARISON OPERATORS:
      - "500A @60%" → {{"current_rating": "500A", "duty_cycle": "60%"}}
      - "300A at 40%" → {{"current_rating": "300A", "duty_cycle": "40%"}}
      - "400A at 100%" → {{"current_rating": "400A", "duty_cycle": "100%"}}
      - "max 300A" → {{"current_rating": {{"value": 300, "operator": "lte", "unit": "A"}}}}
      - "at least 500A" → {{"current_rating": {{"value": 500, "operator": "gte", "unit": "A"}}}}
      - "more than 400A" → {{"current_rating": {{"value": 400, "operator": "gt", "unit": "A"}}}}
      - "less than 300A" → {{"current_rating": {{"value": 300, "operator": "lt", "unit": "A"}}}}
      - "exactly 380V" → {{"voltage": {{"value": 380, "operator": "eq", "unit": "V"}}}}
      - "300-500A" → {{"current_rating": {{"min": 300, "max": 500, "operator": "range", "unit": "A"}}}}
      - "around 500A" → {{"current_rating": {{"value": 500, "operator": "approx", "unit": "A"}}}}
      - Always extract BOTH current and duty cycle when present together

      OPERATOR KEYWORDS (extract when present):
      * "lte" (≤): max, maximum, up to, no more than, at most
      * "gte" (≥): min, minimum, at least, no less than
      * "lt" (<): less than, below, under, smaller than, thinner than
      * "gt" (>): more than, above, over, greater than, bigger than, thicker than, larger than
      * "eq" (=): exactly, only, precisely
      * "range": between X and Y, X-Y, X to Y
      * "approx" (≈): around, about, approximately, roughly (or no operator → default)

   b) PROCESS TYPES:
      - "MIG" → {{"process": "MIG (GMAW)"}}
      - "MMA" or "Stick" → {{"process": "MMA/Stick"}}
      - "TIG" or "DC TIG" or "Lift TIG" → {{"process": "TIG (GTAW)"}}
      - "multiprocess" → {{"multiprocess": "true"}}
      - Always normalize process names to standard format
   
   c) VOLTAGE:
      - "380-460V" → {{"voltage": "380-460V"}}
      - "dual voltage" → {{"voltage": "dual voltage"}}
      - "230-480V" → {{"voltage": "230-480V"}}
      - Extract exact voltage ranges when specified

    d) ADVANCED FEATURES:
      - "synergic" → {{"synergic": "true"}}
      - "pulse" → {{"pulse": "true"}}
      - "super pulse" → {{"super_pulse": "true"}}
      - "double pulse" → {{"double_pulse": "true"}}
      - "inverter" or "inverter-based" → {{"inverter": "true"}}
   
   e) COOLING TYPE (POWER SOURCE ONLY):  # ADD THIS SECTION
      - "integrated cooling" → {{"cooling_type": "integrated"}}
      - "integrated water cooling" → {{"cooling_type": "integrated"}}
      - "built-in cooler" → {{"cooling_type": "integrated"}}
      - "with integrated cooling unit" → {{"cooling_type": "integrated"}}
      ⚠️ Do NOT extract integrated cooling as a separate cooler component!
   
   f) DESIGN ATTRIBUTES:  # This was previously "e", now "f"
      - "portable" → {{"design": "portable"}}
      - "heavy duty" → {{"design": "heavy duty"}}
      - "compact" → {{"design": "compact"}}
      - "robust" → {{"design": "robust"}}
   
   f) APPLICATIONS & ENVIRONMENT (VERY IMPORTANT):
      - "shipyard" → {{"application": "shipyard"}}
      - "industrial" → {{"application": "industrial"}}
      - "on-site" or "field work" → {{"application": "on-site"}}
      - "robotic" → {{"application": "robotic"}}
      - Extract ALL application contexts mentioned

3. PRODUCT NAME RECOGNITION (CRITICAL - HIGHEST PRIORITY):
   - **ALWAYS check if the user mentions a specific product name from the KNOWN PRODUCT NAMES list above**
   - **This is CRITICAL for accurate product matching - exact product names enable 100x search boosting**
   - Use key "product_name" in the appropriate component dict
   - Match product names to correct component category (power_source, feeder, cooler, etc.)

   FUZZY MATCHING & INFERENCE RULES:
   - **NEVER invent or hallucinate product names that don't exist in the KNOWN PRODUCT NAMES list**
   - **ALWAYS infer and match to the CLOSEST product name from the KNOWN PRODUCT NAMES list above**
   - **Your job is to FIND the best match, not copy the user's exact words**

    MATCHING ALGORITHM (FOLLOW EXACT ORDER):
   1. **FIRST - CHECK COMPETITORS**: Look in COMPETITOR PRODUCT MAPPING above
      - If user mentions ANY competitor brand (Kemppi, Miller, Fronius, Lincoln, etc.)
      - Find which ESAB product lists that competitor
      - Extract the EXACT ESAB product name (e.g., "Aristo 500ix CE, (380-460V)")     
      **IMPORTANT**: Only use competitor mapping if the EXACT competitor product is listed above.
      If the competitor product is NOT in the mapping, do NOT include "product_name" in the JSON at all.
      WRONG: {{"product_name": "Kemppi X5 equivalent"}} ❌
      CORRECT: {{}} (no product_name field) ✅
      Example: "Kemppi X5" is NOT in mapping → Extract: {{"process": "MIG (GMAW)"}} (no product_name)
      Example: "Lincoln Electric Powertech i500S" is NOT in mapping → Do NOT map to Aristo
   2. **SECOND - GENERIC NAMES**: If no number mentioned (e.g., "Warrior", "Aristo")
      - Return ONLY the family name
   3. **THIRD - SPECIFIC MODELS**: If has number (e.g., "Warrior 400")
      - Find CLOSEST match from KNOWN PRODUCT NAMES list

   CRITICAL COMPETITOR EXAMPLES (DO THIS):
   - User: "Kemppi X3" → Look up in mapping → Extract: {{"product_name": "Aristo 500ix CE, (380-460V)"}}
   - User: "Miller XMT 350" → Look up in mapping → Extract: {{"product_name": "Warrior 500i CC/CV 380–415V"}}
   - User: "Fronius Transteel" → Look up in mapping → Extract: {{"product_name": "Aristo 500ix CE, (380-460V)"}}
   
   GENERIC NAME EXAMPLES:
   - User: "Warrior" (no number) → Extract: {{"product_name": "Warrior"}}
   - User: "Aristo" (no number) → Extract: {{"product_name": "Aristo"}}
   
   SPECIFIC MODEL EXAMPLES:
   - User: "Renegade ES30" → Extract: {{"product_name": "Renegade ES 300i Kit w/welding cables"}}
   - User: "Warrior 400" → Extract: {{"product_name": "Warrior 400i CC/CV"}}
   - User: "Cool2" → Extract: {{"product_name": "Cool2 Cooling Unit"}}

   PRIORITY ORDER:
   1. Competitor Product Match (Highest Priority if detected)
   2. Exact base name match (e.g., "Aristo 500ix" → "Aristo 500ix CE")
   3. Generic Family Name (e.g., "Warrior" → "Warrior")
   4. Partial name + number match (e.g., "ES30" → "ES 300i")
   5. If multiple matches, prefer shortest/simplest variant

   EXAMPLES (CORRECT BEHAVIOR):
   Query: "I need Aristo 500ix" → power_source: {{"product_name": "Aristo 500ix CE"}}
   Query: "Warrior 400i for MIG" → power_source: {{"product_name": "Warrior 400i CC/CV", "process": "MIG (GMAW)"}}
   Query: "RobustFeed U6" → feeder: {{"product_name": "RobustFeed U6 Water-cooled Euro"}}
   Query: "I need Cool 2" → cooler: {{"product_name": "COOL 2 Cooling Unit"}}
   Query: "Renegade ES 300i kit" → power_source: {{"product_name": "Renegade ES 300i Kit w/welding cables"}}
   Query: "Renegade ES30" → power_source: {{"product_name": "Renegade ES 300i Kit w/welding cables"}} (closest match)
   Query: "Need an Aristo with water cooled feeder" →
     power_source: {{"product_name": "Aristo 500ix CE"}},
     feeder: {{"cooling_type": "water-cooled"}}

   NEGATIVE EXAMPLES (WRONG - DON'T DO THIS):
   Query: "Renegade ES30" → ❌ {{"product_name": "Renegade ER300"}} WRONG! "ER300" is NOT in the known list
   Query: "Renegade ES30" → ✅ {{"product_name": "Renegade ES 300i Kit w/welding cables"}} CORRECT! Match to closest known name
   Query: "Aristo 500" → ❌ {{"product_name": "Aristo 500"}} WRONG! Use the full name from list
   Query: "Aristo 500" → ✅ {{"product_name": "Aristo 500ix CE"}} CORRECT! Use exact name from list

4. COMPOUND REQUESTS (Handle Multiple Components):
   - User might mention requirements for multiple components in one message.
   - Example: "I want 500A power source with water cooled feeder".
   - Extract both: 
     * power_source: {{"current_rating": "500A"}}
     * feeder: {{"cooling_type": "water-cooled"}}

5. CONTEXTUAL QUERIES (Extract ALL Context):
   - "build a system for shipyard customers" → power_source: {{"application": "shipyard"}}
   - "build a package for warrior 400i" → power_source: {{"product_name": "Warrior 400i"}}
   - Always extract application context, even if query is vague

6. PRESERVE EXISTING VALUES:
   - Start with the existing Master Parameter JSON.
   - Only update/add new information from current user query.
   - Do NOT remove or nullify existing values unless user explicitly changes them.

7. DETAILED EXTRACTION EXAMPLES:

   Query: "Portable inverter dual voltage powersource for MMA and Lift TIG welding, 300A at 40% (MMA), 300A at 60% (TIG)"
   Extract:
   {{
     "power_source": {{
       "design": "portable",
       "inverter": "true",
       "voltage": "dual voltage",
       "process": "MMA/Stick, TIG (GTAW)",
       "current_rating_mma": "300A",
       "duty_cycle_mma": "40%",
       "current_rating_tig": "300A",
       "duty_cycle_tig": "60%"
     }}
   }}

   Query: "I need a Multiprocess heavy duty synergic and pulse welding machine 500 Ampères at 60%"
   Extract:
   {{
     "power_source": {{
       "multiprocess": "true",
       "design": "heavy duty",
       "synergic": "true",
       "pulse": "true",
       "current_rating": "500A",
       "duty_cycle": "60%"
     }}
   }}

   Query: "I need Multiprocess Inverter 500A @60% for MIG CV and pulse"
   Extract:
   {{
     "power_source": {{
       "multiprocess": "true",
       "inverter": "true",
       "current_rating": "500A",
       "duty_cycle": "60%",
       "process": "MIG (GMAW)",
       "pulse": "true"
     }}
   }}

   Query: "Build a package for warrior 400i"
   Extract:
   {{
     "power_source": {{
       "product_name": "Warrior 400i"
     }}
   }}

   Query: "build a system for shipyard customers"
   Extract:
   {{
     "power_source": {{
       "application": "shipyard"
     }}
   }}

   Query: "aluminum 6mm thick water cooled" (in feeder state)
   Extract:
   {{
     "feeder": {{
       "material": "aluminum",
       "thickness": "6mm",
       "cooling_type": "water-cooled"
     }}
   }}

   Query: "I need a power source with max 300A"
   Extract:
   {{
     "power_source": {{
       "current_rating": {{"value": 300, "operator": "lte", "unit": "A"}}
     }}
   }}

   Query: "at least 500A MIG welder"
   Extract:
   {{
     "power_source": {{
       "current_rating": {{"value": 500, "operator": "gte", "unit": "A"}},
       "process": "MIG (GMAW)"
     }}
   }}

   Query: "more than 400A power source for aluminum"
   Extract:
   {{
     "power_source": {{
       "current_rating": {{"value": 400, "operator": "gt", "unit": "A"}},
       "material": "aluminum"
     }}
   }}

   Query: "less than 300A portable welder"
   Extract:
   {{
     "power_source": {{
       "current_rating": {{"value": 300, "operator": "lt", "unit": "A"}},
       "design": "portable"
     }}
   }}

   Query: "exactly 380V 3-phase power source"
   Extract:
   {{
     "power_source": {{
       "voltage": {{"value": 380, "operator": "eq", "unit": "V"}},
       "phase": "3-phase"
     }}
   }}

   Query: "between 300A and 500A MIG welder"
   Extract:
   {{
     "power_source": {{
       "current_rating": {{"min": 300, "max": 500, "operator": "range", "unit": "A"}},
       "process": "MIG (GMAW)"
     }}
   }}

   Query: "around 500A power source"
   Extract:
   {{
     "power_source": {{
       "current_rating": {{"value": 500, "operator": "approx", "unit": "A"}}
     }}
   }}

   Query: "wire feeder with thicker than 1.6mm wire diameter"
   Extract:
   {{
     "feeder": {{
       "wire_diameter": {{"value": 1.6, "operator": "gt", "unit": "mm"}}
     }}
   }}

8. GIN NUMBER DETECTION (CRITICAL):
   - If user provides a 7–10 digit number (e.g., "0465350883", "0446200880"), treat it as a GIN product identifier.
   - Add it as "product_name" in the appropriate component dict.
   - Keep leading zeros intact (do NOT modify or format it).
   - Examples:
     * "i need 0465350883" → power_source: {{"product_name": "0465350883"}}.
     * "0445400883 feeder" → feeder: {{"product_name": "0445400883"}}.

9. OUTPUT FORMAT:
   - Return COMPLETE updated Master Parameter JSON.
   - Include ALL components (power_source, feeder, cooler, interconnector, torch, accessories).
   - Use empty dict {{}} for components with no requirements.
   - Extract EVERYTHING mentioned - do not skip any details

10. ENGLISH TRANSLATION (CRITICAL FOR MULTILINGUAL SUPPORT):
   - Translate the user query to English (if not already in English)
   - Keep technical terms unchanged (e.g., "MIG", "TIG", "500A", "60%")
   - Remove only conversational words (e.g., "I need" → "", "Can you" → "")
   - Include "english_query" field in the output
   - Examples:
     * Spanish: "Necesito un soldador MIG de 500A" → "MIG welder 500A"
     * French: "J'ai besoin d'un soudeur MIG de 500A" → "MIG welder 500A"
     * English: "I need a MIG welder of 500A" → "MIG welder 500A"
     * German: "Ich brauche einen MIG-Schweißer mit 500A" → "MIG welder 500A"

CRITICAL: Extract ALL specifications, features, applications, and attributes mentioned in the query.
Do not skip or ignore any details. Be comprehensive and thorough.

RETURN COMPLETE UPDATED JSON WITH ENGLISH TRANSLATION:
{{
  "power_source": {{...}},
  "feeder": {{...}},
  "cooler": {{...}},
  "interconnector": {{...}},
  "torch": {{...}},
  "accessories": {{...}},
  "english_query": "translated English version of user query"
}}
"""
        return prompt

    def _validate_and_normalize_operators(self, component_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize comparison operator format in extracted parameters.

        Ensures operator-based parameters follow correct structure and validates operator types.
        Supports dual-mode: structured operator dict and backward-compatible string format.

        Args:
            component_data: Component dict from LLM extraction (e.g., power_source dict)

        Returns:
            Dict[str, Any]: Normalized component dict with validated operators.
                Invalid operators are logged as warnings and either corrected or skipped.

        Supported Operators:
            - lte (≤): Less than or equal (max, maximum, up to, at most)
            - gte (≥): Greater than or equal (min, minimum, at least)
            - lt (<): Less than (below, under, smaller than)
            - gt (>): Greater than (above, over, larger than)
            - eq (=): Exactly equal (only, precisely, exactly)
            - range: Between min and max (X-Y, X to Y, between X and Y)
            - approx (≈): Approximate (around, about, roughly, or no operator)

        Parameter Formats:
            Structured operator dict:
                {"value": 300, "operator": "lte", "unit": "A"}
                {"min": 300, "max": 500, "operator": "range", "unit": "A"}

            Backward-compatible string:
                "300A" (defaults to approx operator)

        Validation Rules:
            1. Operator must be in VALID_OPERATORS set
            2. Range operator requires min and max fields
            3. Non-range operators require value field
            4. Invalid operators default to "approx"
            5. Missing required fields cause parameter to be skipped (logged)

        Examples:
            Valid operator dict:
            >>> component = {"current_rating": {"value": 300, "operator": "lte", "unit": "A"}}
            >>> normalized = extractor._validate_and_normalize_operators(component)
            >>> normalized["current_rating"]["operator"]
            "lte"

            Invalid operator (corrected):
            >>> component = {"current_rating": {"value": 300, "operator": "invalid", "unit": "A"}}
            >>> normalized = extractor._validate_and_normalize_operators(component)
            >>> normalized["current_rating"]["operator"]
            "approx"  # Defaulted

            Range operator:
            >>> component = {"current_rating": {"min": 300, "max": 500, "operator": "range", "unit": "A"}}
            >>> normalized = extractor._validate_and_normalize_operators(component)
            >>> (normalized["current_rating"]["min"], normalized["current_rating"]["max"])
            (300, 500)

            String format (backward compatible):
            >>> component = {"current_rating": "300A"}
            >>> normalized = extractor._validate_and_normalize_operators(component)
            >>> normalized["current_rating"]
            "300A"  # Unchanged (string pass-through)

        Note:
            This method is critical for Neo4j query generation, as operator dicts are
            converted to Cypher WHERE clauses by the query builder.
        """
        VALID_OPERATORS = {"lte", "gte", "lt", "gt", "eq", "range", "approx"}

        normalized = {}

        # Convert Pydantic model to dict before iterating
        component_dict = component_data.dict() if hasattr(component_data, 'dict') else component_data

        for key, value in component_dict.items():
            # Check if value is dict format (potential operator format)
            if isinstance(value, dict):
                # Check if it has operator field
                if "operator" in value:
                    operator = value.get("operator", "approx")

                    # Validate operator
                    if operator not in VALID_OPERATORS:
                        logger.warning(f"Invalid operator '{operator}' for {key}, defaulting to 'approx'")
                        value["operator"] = "approx"

                    # Validate structure based on operator
                    if operator == "range":
                        # Range requires min and max
                        if "min" not in value or "max" not in value:
                            logger.warning(f"Range operator missing min/max for {key}, converting to approx")
                            if "value" in value:
                                value["operator"] = "approx"
                            else:
                                # Invalid range, skip
                                logger.warning(f"Invalid range format for {key}, skipping")
                                continue
                    else:
                        # Non-range operators require value
                        if "value" not in value:
                            logger.warning(f"Operator format missing 'value' for {key}, skipping")
                            continue

                    # Valid operator format
                    normalized[key] = value
                    logger.debug(f"Validated operator for {key}: {value}")
                else:
                    # Dict without operator field - keep as-is (nested dict)
                    normalized[key] = value
            else:
                # String or other format - keep as-is (backward compatible)
                normalized[key] = value

        return normalized

    def _parse_llm_response(
        self,
        llm_response: str,
        fallback_master: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parse LLM text response into validated MasterParameterJSON dict.

        Extracts JSON from LLM response (with or without code fences), validates structure,
        normalizes operators, and ensures all required components exist. Handles multilingual
        english_query extraction for Lucene search.

        Args:
            llm_response: Raw LLM response text (may contain ```json code fences or plain JSON)
            fallback_master: Fallback MasterParameterJSON to return on parse failure

        Returns:
            Dict[str, Any]: Complete MasterParameterJSON dict with:
                - All required components (power_source, feeder, cooler, etc.)
                - Validated and normalized operators
                - Optional _english_query field (multilingual support)
                - Empty dicts {} for unspecified components

        Parsing Steps:
            1. Extract JSON from response (try ```json fences first, then regex)
            2. Parse JSON string to dict
            3. Extract and remove english_query field (temporary metadata)
            4. Ensure all required components exist (from schema_loader)
            5. Validate and normalize operators in each component
            6. Add _english_query as temporary metadata if present
            7. Log operator count and total features extracted

        Examples:
            LLM response with code fences:
            >>> llm_response = '''```json
            ... {
            ...   "power_source": {"current_rating": "500A", "process": "MIG (GMAW)"},
            ...   "feeder": {},
            ...   "english_query": "MIG welder 500A"
            ... }
            ... ```'''
            >>> parsed = extractor._parse_llm_response(llm_response, fallback)
            >>> parsed["power_source"]["current_rating"]
            "500A"
            >>> parsed["_english_query"]
            "MIG welder 500A"

            LLM response without code fences:
            >>> llm_response = '{"power_source": {"product_name": "Aristo 500ix"}, "feeder": {}}'
            >>> parsed = extractor._parse_llm_response(llm_response, fallback)
            >>> parsed["power_source"]["product_name"]
            "Aristo 500ix"

            Parse failure (returns fallback):
            >>> llm_response = "Invalid JSON response"
            >>> parsed = extractor._parse_llm_response(llm_response, fallback)
            >>> parsed == fallback
            True

        Operator Validation:
            >>> llm_response = '''```json
            ... {
            ...   "power_source": {"current_rating": {"value": 300, "operator": "lte", "unit": "A"}},
            ...   "feeder": {}
            ... }
            ... ```'''
            >>> parsed = extractor._parse_llm_response(llm_response, fallback)
            >>> parsed["power_source"]["current_rating"]["operator"]
            "lte"  # Validated

        Note:
            - Returns fallback_master on any parsing error (logged)
            - english_query is extracted and stored as _english_query for orchestrator
            - All components from master_parameter_schema.json are included (empty if not in response)
            - Operator validation happens per-component via _validate_and_normalize_operators()
        """
        import re

        try:
            json_match = re.search(r'```json\s*(.*?)\s*```', llm_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    raise ValueError("No JSON found in LLM response")

            parsed_data = json.loads(json_str)

            # Extract english_query from LLM response (for multilingual Lucene search)
            english_query = parsed_data.pop("english_query", None)

            required_components = get_component_list()
            for component in required_components:
                if component not in parsed_data:
                    parsed_data[component] = {}

            # Validate and normalize operators for each component
            for component in required_components:
                if parsed_data[component]:  # Only process non-empty components
                    parsed_data[component] = self._validate_and_normalize_operators(parsed_data[component])
                    if parsed_data[component]:  # Log if operators found
                        operator_count = sum(1 for v in parsed_data[component].values()
                                           if isinstance(v, dict) and "operator" in v)
                        if operator_count > 0:
                            logger.info(f"Validated {operator_count} operator(s) in {component}")

            # Add english_query as temporary metadata (will be extracted by orchestrator)
            if english_query:
                parsed_data["_english_query"] = english_query
                logger.info(f"Extracted English query: '{english_query}'")

            logger.info(f"Successfully parsed LLM response with {sum(len(v) for v in parsed_data.values() if isinstance(v, dict))} total features")
            return parsed_data

        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.error(f"LLM response was: {llm_response}")
            return fallback_master


# Dependency injection
_parameter_extractor = None

async def get_parameter_extractor(openai_api_key: str, config_service=None) -> ParameterExtractor:
    """
    Get singleton parameter extractor instance
    """
    global _parameter_extractor
    if _parameter_extractor is None:
        _parameter_extractor = ParameterExtractor(openai_api_key, config_service)
    return _parameter_extractor