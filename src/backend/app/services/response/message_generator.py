"""
Simplified Response Generator for Enhanced S1→SN Flow
Generates user-friendly messages based on current state
Supports 9 Accessory Categories + Core Components
ANTI-HALLUCINATION SAFEGUARDS: ESAB-only responses, competitor blocking
LLM-POWERED FEATURE GUIDANCE: Shows available features and specs per category
"""

import logging
import json
import os
from typing import Dict, List, Optional, Any
from openai import AsyncOpenAI
from app.models.product_search import ProductResult, SearchResults
from ..multilingual.translator import get_translator, MultilingualTranslator
from ..config.configuration_service import get_config_service
from ..config.prompt_service import get_prompt_service

logger = logging.getLogger(__name__)


class MessageGenerator:
    """
    Simple message generator for conversational responses
    Tailored to enhanced S1→SN state-by-state flow with accessory categories
    Supports multilingual responses via LLM translation
    ANTI-HALLUCINATION: ESAB-only domain restrictions
    """

    def __init__(self, openai_api_key: Optional[str] = None):
        """Initialize message generator"""
        self.translator = get_translator()
        self.openai_client = AsyncOpenAI(api_key=openai_api_key)
        self.config_service = get_config_service()
        self.prompt_service = get_prompt_service()

        # Load LLM-extracted category features for intelligent guidance
        self.category_features = self._load_category_features()

        logger.info("✅ Message Generator initialized with multilingual support + Accessory Categories + Anti-Hallucination Guards + LLM Feature Guidance")

    # =========================================================================
    # PHASE 1.5: Q&A CAPABILITY WITH ANTI-HALLUCINATION SAFEGUARDS
    # =========================================================================
    
    # 🔒 COMPETITOR BLOCKING - Prevents hallucination about other brands
    COMPETITOR_KEYWORDS = [
        "lincoln", "miller", "fronius", "panasonic", "ewm",
        "kemppi", "hypertherm", "otc", "riland", "eset", "thermal arc"
    ]

    # 🔒 ESAB-ONLY SYSTEM PROMPT - Restricts LLM to domain knowledge
    ESAB_ONLY_SYSTEM_PROMPT = """
You are an ESAB Welding Configurator assistant.
You must answer ONLY using ESAB product data or the user's configuration context.
Never mention, compare with, or suggest non-ESAB brands such as Lincoln, Miller, Fronius, etc.
If the user asks about other brands or generic "best" products, reply:
"Sorry, I can only recommend ESAB welding equipment and accessories compatible with your setup."
Be concise, factual, and stay strictly within ESAB's ecosystem.
"""

    def _is_competitor_query(self, text: str) -> bool:
        """
        🔒 LAYER 1: Detect if user mentioned another manufacturer
        Prevents hallucination about competitor products
        """
        return any(brand in text.lower() for brand in self.COMPETITOR_KEYWORDS)

    async def generate_response(
        self,
        message_type: str,
        state: str,
        products: List[Dict[str, Any]] = None,
        selected_product: Dict[str, Any] = None,
        language: str = "en",
        custom_message: str = None,
        error_type: str = None,
        details: str = "",
        response_json: Dict[str, Any] = None,
        zero_results_message: str = None,
        compatibility_skip_message: str = None,
    ) -> str:
        """
        Unified response generation router - maps message types to appropriate methods.

        Args:
            message_type: Type of message ("selection", "auto_selection", "search_results", "error", "finalize", "skip")
            state: Current configurator state
            products: List of products (for search_results)
            selected_product: Selected product (for selection/auto_selection)
            language: Response language
            custom_message: Optional custom message to prepend
            error_type: Error type (for error messages)
            details: Error details (for error messages)
            response_json: Response JSON (for finalize)
            zero_results_message: Message to display when no products found
            compatibility_skip_message: Message explaining compatibility validation yielded no results

        Returns:
            Generated message string
        """
        # Convert Pydantic model to dict if needed (similar to parameter_extractor.py fix)
        if selected_product and hasattr(selected_product, 'dict'):
            selected_product = selected_product.dict()

        if message_type in ["selection", "auto_selection"]:
            # Use custom message if provided, otherwise generate confirmation
            if custom_message:
                return custom_message
            elif selected_product:
                component_type = selected_product.get("category", "Component")
                return self.generate_selection_confirmation(
                    component_type,
                    selected_product.get("name", ""),
                    selected_product.get("gin", "")
                )
            else:
                return "Selection confirmed."

        elif message_type == "search_results":
            # Prepend compatibility skip message if provided
            prefix = f"{compatibility_skip_message}\n\n" if compatibility_skip_message else ""

            # Generate search results message from product list
            if products and len(products) > 0:
                # Format product list (simplified version)
                component_name = self._get_component_name(state)
                message = f"Here are the {component_name} options:\n\n"

                # List top 5 products
                for idx, product in enumerate(products[:5], 1):
                    message += f"{idx}. **{product.get('name', 'Unknown')}** (GIN: {product.get('gin', 'N/A')})\n"

                message += f"\n✅ Please select a {component_name} or say 'skip' if not needed."
                return prefix + message
            elif zero_results_message:
                return prefix + zero_results_message
            else:
                state_prompt = await self.generate_state_prompt(state, response_json or {}, language)
                return prefix + state_prompt

        elif message_type == "error":
            # Generate error message
            return self.generate_error_message(error_type or "unknown", details)

        elif message_type == "finalize":
            # Generate finalization message
            finalize_prompt = await self.generate_state_prompt("finalize", response_json or {}, language)

            # Prepend compatibility skip message if provided
            if compatibility_skip_message:
                return f"{compatibility_skip_message}\n\n{finalize_prompt}"

            return finalize_prompt

        elif message_type == "skip":
            # Generate skip confirmation
            component_key = state.replace("_selection", "")
            return self.generate_skip_confirmation(component_key, component_key)

        else:
            # Unknown message type - return generic message
            return f"Message type '{message_type}' not recognized."

    async def generate_qa_response(
        self,
        question: str,
        context: Dict[str, Any],
        language: str = "en",
    ) -> str:
        """
        Generate LLM-powered answer to user questions.
        🔒 THREE-LAYER ANTI-HALLUCINATION PROTECTION:
        - Layer 1: Competitor query blocking
        - Layer 2: Vague query normalization with ESAB fallbacks
        - Layer 3: ESAB-only system prompt enforcement

        Args:
            question: User's question
            context: Current session context with keys:
                - current_state: Current configuration state
                - response_json: Selected components
                - master_parameters: User requirements
            language: Target language for response

        Returns:
            Natural language answer maintaining conversational flow
        """
        try:
            # 🔒 LAYER 1 — Competitor guard (prevent brand hallucination)
            if self._is_competitor_query(question):
                logger.info("🚫 Competitor query blocked for domain safety")
                return (
                    "Sorry, I can only recommend ESAB welding equipment and accessories "
                    "compatible with your current setup."
                )

            # 🔒 LAYER 2 — Normalize vague "best/good/suggest" questions
            # Prevents hallucination by providing concrete ESAB examples
            lower_q = question.lower()
            if any(keyword in lower_q for keyword in ["best", "good", "suggest", "recommend"]):
                # Optional quick ESAB-based fallback from Neo4j
                try:
                    from ..neo4j.product_search import Neo4jProductSearch
                    search = Neo4jProductSearch("bolt://localhost:7687", "neo4j", "test")
                    products = await search._simple_neo4j_search("PowerSource", ["aristo"], [])
                    if products:
                        top = ", ".join(p.name for p in products[:3])
                        return f"ESAB offers excellent power sources such as {top}."
                except Exception:
                    pass
                
                # Fallback to hardcoded ESAB examples
                return (
                    "ESAB offers several high-performance power sources such as "
                    "Aristo 500ix, Warrior 500i, and Renegade ES300i."
                )

            # 🔒 LAYER 3 — Build contextual prompt with ESAB-only enforcement
            prompt = self._build_qa_prompt(question, context)

            # Get response from model with ESAB-only system prompt
            answer = await self._call_llm_for_qa(prompt, language)

            if not answer.endswith(('.', '!', '?')):
                answer += '.'

            logger.info(f"✅ Q&A response generated for question: {question[:50]}...")
            return answer

        except Exception as e:
            logger.error(f"❌ Q&A generation failed: {e}", exc_info=True)
            return self._fallback_qa_response(question)

    async def _call_llm_for_qa(self, prompt: str, language: str) -> str:
        """
        Call OpenAI for Q&A responses.
        🔒 USES ESAB-ONLY SYSTEM PROMPT to prevent hallucination
        """
        # Use ESAB-restricted system prompt
        system_prompt = self.ESAB_ONLY_SYSTEM_PROMPT
        
        if language != "en":
            system_prompt += f"\nRespond in {language}."

        response = await self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,  # Lower temperature for more factual responses
            max_tokens=300,
            timeout=10.0
        )

        return response.choices[0].message.content.strip()

    def _build_qa_prompt(self, question: str, context: Dict[str, Any]) -> str:
        """
        Build context-aware prompt for Q&A.
        Includes current state and selected components.
        """
        current_state = context.get("current_state", "unknown")
        selected_components = context.get("response_json", {})
        master_params = context.get("master_parameters", {})

        # Format selected components
        selections_text = self._format_selections(selected_components)

        # Format user requirements
        requirements_text = self._format_requirements(
            master_params.dict() if hasattr(master_params, "dict") else master_params
        )

        # Build comprehensive prompt
        prompt = f"""Answer this welding equipment question:

Question: {question}

Current Configuration Context:
- Stage: {self._get_component_name(current_state)}
- Selected Components: {selections_text}
- User Requirements: {requirements_text}

Provide a helpful, specific answer that:
1. Directly addresses the question
2. References their configuration if relevant
3. Uses welding industry terminology appropriately
4. Stays focused on their current selection stage

Answer:"""

        return prompt

    def _format_selections(self, response_json: Dict[str, Any]) -> str:
        """Format selected components for context display"""
        if hasattr(response_json, 'dict'):
            response_json = response_json.dict()
        elif hasattr(response_json, '__dict__'):
            response_json = vars(response_json)
        
        if not response_json:
            return "None selected yet"

        selections = []
        component_map = {
            "PowerSource": "Power Source",
            "Feeder": "Feeder",
            "Cooler": "Cooler",
            "Interconnector": "Interconnector",
            "Torch": "Torch",
            "Accessories": "Accessories",
            "PowerSourceAccessories": "PowerSource Accessories",
            "FeederAccessories": "Feeder Accessories",
            "FeederConditionalAccessories": "Feeder Conditional Accessories",
            "InterconnectorAccessories": "Interconnector Accessories",
            "Remotes": "Remote Controls",
            "RemoteAccessories": "Remote Accessories",
            "RemoteConditionalAccessories": "Remote Conditional Accessories",
            "Connectivity": "Connectivity Modules",
            "FeederWears": "Feeder Wear Parts"
        }

        for comp_key, data in response_json.items():
            if not data:
                continue

            display_name = component_map.get(comp_key, comp_key)

            if isinstance(data, dict):
                name = data.get("name", "Unknown")
                selections.append(f"{display_name}: {name}")
            elif isinstance(data, list) and data:
                count = len(data)
                selections.append(f"{display_name}: {count} items")

        return ", ".join(selections) if selections else "None selected yet"

    def _format_requirements(self, master_parameters: Dict[str, Any]) -> str:
        """Format user requirements for context"""
        if not master_parameters:
            return "Not specified yet"

        requirements = []

        # Power source requirements
        ps_params = master_parameters.get("power_source", {})
        if ps_params:
            process = ps_params.get("welding_process")
            amperage = ps_params.get("amperage")
            if process:
                requirements.append(f"Process: {process}")
            if amperage:
                requirements.append(f"Amperage: {amperage}")

        return ", ".join(requirements) if requirements else "Not specified yet"

    def _fallback_qa_response(self, question: str) -> str:
        """Fallback response when LLM fails"""
        return (
            "I understand you have a question, but I'm having trouble "
            "generating a detailed response right now. \n\n"
            "You can:\n"
            "- Try rephrasing your question\n"
            "- Continue with the configuration and ask later\n"
            "- Request help from a specialist\n\n"
            "Would you like to continue with your configuration?"
        )

    # =========================================================================
    # STATE PROMPT GENERATION
    # =========================================================================

    async def generate_state_prompt(
        self,
        current_state: str,
        master_parameters: Dict[str, Any],
        response_json: Dict[str, Any],
        language: str = "en"
    ) -> str:
        """
        Generate prompt message for current state using configuration
        Fully config-driven for enhanced S1→SN flow with accessory categories
        Supports translation to user's language
        """
        # Generate English prompt using configuration
        try:
            # Handle accessory category states with dynamic prompts
            if current_state in self._get_accessory_states():
                english_prompt = self._build_accessory_prompt(
                    current_state, master_parameters, response_json
                )
            # Handle finalize state - build JSON summary
            elif current_state == "finalize":
                state_config = self.config_service.get_state_prompt_config(current_state)
                english_prompt = self._build_finalize_prompt(response_json, state_config)
            else:
                # Get state config from configuration for core components
                state_config = self.config_service.get_state_prompt_config(current_state)

                # Build context for template rendering
                context = self._build_prompt_context(current_state, master_parameters, response_json, state_config)

                # Use simple prompt or template-based
                if "prompt_simple" in state_config:
                    # Use simple prompt template
                    english_prompt = state_config["prompt_simple"]

                    # For dynamic prompts (feeder, cooler), check if details exist
                    if current_state in ["feeder_selection", "cooler_selection"]:
                        english_prompt = self._build_component_prompt(
                            current_state, master_parameters, response_json, state_config
                        )
                    else:
                        # Format with power source name if available
                        if "{power_source_name}" in english_prompt and response_json.get("PowerSource"):
                            english_prompt = english_prompt.format(
                                power_source_name=response_json["PowerSource"].get("name", "Unknown")
                            )
                else:
                    # Render template with context
                    english_prompt = self.prompt_service.render_template(
                        state_config.get("prompt_template", ""),
                        **context
                    )

        except Exception as e:
            logger.error(f"Failed to generate state prompt for {current_state}: {e}")
            english_prompt = f"Please provide information for {current_state.replace('_', ' ')}."

        # ❌ REMOVED: Feature guidance moved to generate_search_results_message()
        # Feature guidance now appears AFTER products are shown, not in initial prompt
        # This matches user's requirement: guidance helps refine search after seeing options

        # Translate if not English
        if language != "en":
            try:
                translated_prompt = await self.translator.translate(
                    english_prompt,
                    language,
                    context=f"State: {current_state} - Welding equipment configurator prompt"
                )
                return translated_prompt
            except Exception as e:
                logger.error(f"Translation failed for {language}: {e}, returning English")
                return english_prompt

        return english_prompt

    async def generate_search_results_message(
        self,
        current_state: str,
        search_results: SearchResults,
        master_parameters: Dict[str, Any],
        language: str = "en"
    ) -> str:
        """
        Generate message presenting search results to user using configuration
        Supports translation to user's language
        Enhanced for accessory categories
        """

        if not search_results.products:
            return await self._generate_no_results_message(current_state, language)

        # Get component name from configuration
        component_name = self._get_component_name(current_state)

        message = f"Here are the {component_name} options matching your requirements"

        # Add compatibility note if validated
        if search_results.compatibility_validated:
            message += " that are compatible with your selected components"

        message += ":\n\n"

        # List products (names and GINs stay in English for consistency)
        for idx, product in enumerate(search_results.products[:5], 1):  # Show top 5
            message += f"{idx}. **{product.name}** (GIN: {product.gin})\n"

        # Add selection instruction based on state type
        if current_state in self._get_accessory_states():
            # Accessory categories allow multiple selections
            message += f"\n✅ select a {component_name}:"
            message += "\n- Or say 'next' to move to the next category"
            message += "\n- Say 'done' to finalize your configuration"
        else:
            # Core components (single selection)
            message += f"\n✅ select a {component_name}:"

            # PowerSource cannot be skipped (check from config)
            power_source_config = self.config_service.get_component_type("power_source")
            if power_source_config and power_source_config.get("state_name") != current_state:
                feeder_source_config = self.config_service.get_component_type("feeder")
                if feeder_source_config and feeder_source_config.get('state_name') != current_state:
                    cooler_source_config = self.config_service.get_component_type("cooler")
                    if cooler_source_config and cooler_source_config.get('state_name') != current_state:   
                        message += "\n- Or say 'skip' if not needed"

        # Translate if not English
        if language != "en":
            try:
                translated_message = await self.translator.translate(
                    message,
                    language,
                    context="Product search results message"
                )
                return translated_message
            except Exception as e:
                logger.error(f"Translation failed for {language}: {e}, returning English")
                return message

        return message

    def generate_selection_confirmation(
        self,
        component_type: str,
        product_name: str,
        product_gin: str
    ) -> str:
        """Generate confirmation message for product selection"""

        return f"✅ Selected **{product_name}** (GIN: {product_gin}) for {component_type}."

    def generate_skip_confirmation(self, component_type: str, key: str) -> str:
        """Generate confirmation message for skipping a component"""
        if key.lower().strip() == 'skip':
            return f"⏭️ Skipped {component_type}."
        return f"⏭️ Moved to next category from {component_type}."

    def generate_error_message(self, error_type: str, details: str = "") -> str:
        """Generate user-friendly error messages from configuration"""

        return self.prompt_service.format_error_message(error_type, details)

    # =========================================================================
    # ACCESSORY CATEGORY PROMPT BUILDERS (9 Categories)
    # =========================================================================

    def _get_accessory_states(self) -> List[str]:
        """Return list of all accessory category states"""
        return [
            "powersource_accessories_selection",
            "feeder_accessories_selection",
            "feeder_conditional_accessories",
            "interconnector_accessories_selection",
            "remote_selection",
            "remote_accessories_selection",
            "remote_conditional_accessories",
            "connectivity_selection",
            "feeder_wears_selection"
        ]

    def _build_accessory_prompt(
        self,
        current_state: str,
        master_parameters: Dict[str, Any],
        response_json: Dict[str, Any]
    ) -> str:
        """
        Build dynamic prompt for accessory categories
        Uses selected component context to generate relevant prompts
        """

        # Map state to prompt builder
        prompt_builders = {
            "powersource_accessories_selection": self._build_powersource_accessories_prompt,
            "feeder_accessories_selection": self._build_feeder_accessories_prompt,
            "feeder_conditional_accessories": self._build_feeder_conditional_accessories_prompt,
            "interconnector_accessories_selection": self._build_interconnector_accessories_prompt,
            "remote_selection": self._build_remote_prompt,
            "remote_accessories_selection": self._build_remote_accessories_prompt,
            "remote_conditional_accessories": self._build_remote_conditional_accessories_prompt,
            "connectivity_selection": self._build_connectivity_prompt,
            "feeder_wears_selection": self._build_feeder_wears_prompt
        }

        builder = prompt_builders.get(current_state)
        if builder:
            return builder(response_json)

        return f"Would you like to add accessories for this component? or say 'skip' to move to next category or say 'done' finalize configuration."

    def _build_powersource_accessories_prompt(self, response_json: Dict[str, Any]) -> str:
        """Generate PowerSource Accessories prompt"""

        power_source = response_json.get("PowerSource", {})
        ps_name = power_source.get("name", "your power source")

        return f"""🔌 **PowerSource Accessories**

Would you like to add accessories for **{ps_name}**?

or say 'skip' to move to next category.
or say 'done' finalize configuration."""

    def _build_feeder_accessories_prompt(self, response_json: Dict[str, Any]) -> str:
        """Generate Feeder Accessories prompt"""

        feeder = response_json.get("Feeder", {})

        if not feeder:
            return "⏭️ No feeder selected. Skipping feeder accessories."

        feeder_name = feeder.get("name", "your feeder")

        return f"""📦 **Feeder Accessories**

Would you like accessories for **{feeder_name}**?

or say 'skip' to move to next category.
or say 'done' finalize configuration"""

    def _build_feeder_conditional_accessories_prompt(self, response_json: Dict[str, Any]) -> str:
        """Generate Feeder Conditional Accessories prompt"""

        feeder_accessories = response_json.get("FeederAccessories", [])

        if not feeder_accessories:
            return "⏭️ No feeder accessories selected. Skipping conditional accessories."

        last_accessory = feeder_accessories[-1] if feeder_accessories else {}
        accessory_name = last_accessory.get("name", "your feeder accessory")

        return f"""🔗 **Conditional Accessories**

Your selected accessory **{accessory_name}** may have additional compatible items.

Would you like to see compatible conditional accessories? or say 'skip' to move to next category or say 'done' finalize configuration."""

    def _build_interconnector_accessories_prompt(self, response_json: Dict[str, Any]) -> str:
        """Generate Interconnector Accessories prompt"""

        interconnector = response_json.get("Interconnector", {})

        if not interconnector:
            return "⏭️ No interconnector selected. Skipping interconnector accessories."

        ic_name = interconnector.get("name", "your interconnector")

        return f"""🔌 **Interconnector Accessories**

Would you like accessories for **{ic_name}**?

or say 'skip' to move to next category
or say 'done' finalize configuration."""

    def _build_remote_prompt(self, response_json: Dict[str, Any]) -> str:
        """Generate Remote Control prompt"""

        power_source = response_json.get("PowerSource", {})
        ps_name = power_source.get("name", "your power source")

        return f"""🎮 **Remote Controls**

Would you like to add a remote control for **{ps_name}**?

or say 'skip' to move to next category
or say 'done' finalize configuration."""

    def _build_remote_accessories_prompt(self, response_json: Dict[str, Any]) -> str:
        """Generate Remote Accessories prompt"""

        remotes = response_json.get("Remotes", [])

        if not remotes:
            return "⏭️ No remote control selected. Skipping remote accessories."

        last_remote = remotes[-1] if remotes else {}
        remote_name = last_remote.get("name", "your remote control")

        return f"""📦 **Remote Accessories**

Would you like accessories for **{remote_name}**?

or say 'skip' to move to next category
or say 'done' finalize configuration."""

    def _build_remote_conditional_accessories_prompt(self, response_json: Dict[str, Any]) -> str:
        """Generate Remote Conditional Accessories prompt"""

        remote_accessories = response_json.get("RemoteAccessories", [])

        if not remote_accessories:
            return "⏭️ No remote accessories selected. Skipping conditional accessories."

        last_accessory = remote_accessories[-1] if remote_accessories else {}
        accessory_name = last_accessory.get("name", "your remote accessory")

        return f"""🔗 **Remote Conditional Accessories**

Your selected accessory **{accessory_name}** may have additional compatible items.

Would you like to see compatible accessories? or say 'skip' to move to next category or say 'done' finalize configuration."""

    def _build_connectivity_prompt(self, response_json: Dict[str, Any]) -> str:
        """Generate Connectivity Modules prompt"""

        power_source = response_json.get("PowerSource", {})
        ps_name = power_source.get("name", "your power source")

        return f"""🌐 **Connectivity Modules**

Would you like to add connectivity modules for **{ps_name}**?

or say 'skip' to move to next category
or say 'done' finalize configuration."""

    def _build_feeder_wears_prompt(self, response_json: Dict[str, Any]) -> str:
        """Generate Feeder Wear Parts prompt"""

        feeder = response_json.get("Feeder", {})

        if not feeder:
            return "⏭️ No feeder selected. Skipping feeder wear parts."

        feeder_name = feeder.get("name", "your feeder")

        return f"""🔧 **Feeder Wear Parts**

Would you like wear parts for **{feeder_name}**?

or say 'skip' to move to next category
or say 'done' finalize configuration."""

    # =========================================================================
    # PRIVATE HELPER METHODS
    # =========================================================================

    def _build_finalize_prompt(
        self,
        response_json: Dict[str, Any],
        state_config: Dict[str, Any]
    ) -> str:
        """
        Simplified finalize prompt.
        Returns a user-friendly message while the package is being generated.
        """
        return (
            "⏳ Please wait, your package is being generated... "
            "Once it is ready, you can click on the packages to view or edit them."
        )

    # def _build_finalize_prompt(
    #     self,
    #     response_json: Dict[str, Any],
    #     state_config: Dict[str, Any]
    # ) -> str:
    #     """
    #     Build finalize prompt as human-readable text instead of JSON.
    #     Includes all core and accessory components with skip status and details.
    #     Uses finalize_header and finalize_footer from state_prompts.json.
    #     """
    #     lines = []

    #     # Helper for formatting selected items
    #     def format_item(item: Dict[str, Any], prefix: str = "  - ") -> str:
    #         name = item.get("name", "Unknown Name")
    #         gin = item.get("gin", "Unknown GIN")
    #         # desc = item.get("description")
    #         # desc_part = f" → {desc}" if desc else ""
    #         return f"{prefix}{name} ({gin})"

    #     # Core components
    #     for component_type in ["PowerSource", "Feeder", "Cooler", "Interconnector", "Torch"]:
    #         component_data = response_json.get(component_type)
    #         if component_data is None:
    #             continue
    #         elif component_data == "skipped":
    #             lines.append(f"• {component_type}:  Skipped")
    #         elif isinstance(component_data, dict):
    #             name = component_data.get("name", "Unknown")
    #             gin = component_data.get("gin", "N/A")
    #             # desc = component_data.get("description")
    #             lines.append(f"• {component_type}:  {name} ({gin})")
    #             # if desc:
    #             #     lines.append(f"    ↳ {desc}")

    #     # Accessory categories
    #     accessory_categories = [
    #         "PowerSourceAccessories",
    #         "FeederAccessories",
    #         "FeederConditionalAccessories",
    #         "InterconnectorAccessories",
    #         "Remotes",
    #         "RemoteAccessories",
    #         "RemoteConditionalAccessories",
    #         "Connectivity",
    #         "FeederWears",
    #         "Accessories",  # Legacy
    #     ]

    #     for category in accessory_categories:
    #         category_data = response_json.get(category)
    #         if not category_data:
    #             continue

    #         if category_data == "skipped":
    #             lines.append(f"• {category}:  Skipped")
    #         elif isinstance(category_data, list) and len(category_data) > 0:
    #             lines.append(f"• {category}:")
    #             for item in category_data:
    #                 lines.append(format_item(item))

    #     # Combine header, content, and footer
    #     header = state_config.get("finalize_header", "📋 **Final Configuration Summary:**")
    #     footer = state_config.get("finalize_footer", "\n✨ Your configuration is ready!")

    #     body = "\n".join(lines)
    #     return f"{header}\n\n{body}\n{footer}"

    def _get_component_name(self, state: str) -> str:
        """
        Get friendly component name from state using configuration
        Enhanced with accessory category names
        """

        # Special mapping for accessory categories
        accessory_names = {
            "powersource_accessories_selection": "PowerSource Accessory",
            "feeder_accessories_selection": "Feeder Accessory",
            "feeder_conditional_accessories": "Feeder Conditional Accessory",
            "interconnector_accessories_selection": "Interconnector Accessory",
            "remote_selection": "Remote Control",
            "remote_accessories_selection": "Remote Accessory",
            "remote_conditional_accessories": "Remote Conditional Accessory",
            "connectivity_selection": "Connectivity Module",
            "feeder_wears_selection": "Feeder Wear Part"
        }

        if state in accessory_names:
            return accessory_names[state]

        # Find component by state_name in config
        component_types = self.config_service.get_component_types()
        for comp_key, comp_data in component_types.get("component_types", {}).items():
            if comp_data.get("state_name") == state:
                return comp_data.get("display_name", "Component")

        return "Component"

    def _load_category_features(self) -> Dict[str, Any]:
        """
        Load LLM-extracted category features from llm_context.json
        Consolidated Nov 15, 2024: Moved from category_features_llm.json to llm_context.json
        Returns empty dict if file not found
        """
        try:
            # Build path to LLM context file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            llm_context_file = os.path.join(
                current_dir, "..", "..", "config", "llm_context.json"
            )

            if not os.path.exists(llm_context_file):
                logger.warning(f"⚠️ LLM context file not found at {llm_context_file}")
                return {}

            with open(llm_context_file, 'r', encoding='utf-8') as f:
                llm_context = json.load(f)
                features = llm_context.get("category_features", {})

            logger.info(f"✅ Loaded LLM-extracted features for {len(features)} categories")
            return features

        except Exception as e:
            logger.error(f"❌ Failed to load category features: {e}")
            return {}

    def _get_category_features(self, state: str) -> Optional[str]:
        """
        Get formatted feature guidance text for a category based on state
        Returns None if no features available

        Args:
            state: Current configurator state (e.g., "power_source_selection")

        Returns:
            Formatted feature guidance text ready for display
        """
        # Map state to category name
        state_to_category = {
            "power_source_selection": "Powersource",
            "feeder_selection": "Feeder",
            "cooler_selection": "Cooler",
            "interconnector_selection": "Interconn",
            "torch_selection": "Torches",
            "powersource_accessories_selection": "Powersource Accessories",
            "feeder_accessories_selection": "Feeder Accessories",
            "feeder_conditional_accessories": "Feeder Conditional Accessories",
            "interconnector_accessories_selection": "Interconn Accessories",
            "remote_selection": "Remotes",
            "remote_accessories_selection": "Remote Accessories",
            "remote_conditional_accessories": "Remote Conditional Accessories",
            "connectivity_selection": "Connectivity",
            "feeder_wears_selection": "Feeder Wears"
        }

        category = state_to_category.get(state)
        if not category:
            return None

        # Get features for this category
        category_data = self.category_features.get(category)
        if not category_data:
            return None

        # Return pre-formatted guidance text
        return category_data.get("guidance", "")

    def _build_prompt_context(
        self,
        current_state: str,
        master_parameters: Dict[str, Any],
        response_json: Dict[str, Any],
        state_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build context dictionary for template rendering"""

        context = {
            "step_number": state_config.get("step_number", ""),
            "title": state_config.get("title", ""),
            "processes": self.prompt_service.get_welding_process_examples(),
            "materials": self.prompt_service.get_material_examples(),
        }

        # Add power source name if available
        if response_json.get("PowerSource"):
            context["power_source_name"] = response_json["PowerSource"].get("name", "Unknown")

        return context

    def _build_component_prompt(
        self,
        current_state: str,
        master_parameters: Dict[str, Any],
        response_json: Dict[str, Any],
        state_config: Dict[str, Any]
    ) -> str:
        """Build dynamic prompt for feeder/cooler with existing details"""

        component_key = current_state.replace("_selection", "")
        component_params = master_parameters.get(component_key, {})
        product_name = component_params.get("product_name")
        cooling_type = component_params.get("cooling_type")

        # Get power source name
        power_source_name = "Unknown"
        if response_json.get("PowerSource"):
            power_source_name = response_json["PowerSource"].get("name", "Unknown")

        # Check if we have details
        if product_name or (component_key == "feeder" and cooling_type):
            # Use prompt_with_details if available
            if "prompt_with_details" in state_config:
                prompt = state_config["prompt_with_details"]

                # Build details string
                details = []
                if product_name:
                    details.append(f"Product: **{product_name}**")
                if cooling_type:
                    details.append(f"Cooling: {cooling_type}")

                details_str = ", ".join(details)

                return prompt.format(
                    power_source_name=power_source_name,
                    product_name=product_name or "",
                    details=details_str
                )

        # Use simple prompt
        prompt_simple = state_config.get("prompt_simple", "")
        return prompt_simple.format(power_source_name=power_source_name)

    async def _generate_no_results_message(self, current_state: str, language: str = "en") -> str:
        """Generate message when no search results found"""

        component_name = self._get_component_name(current_state)

        # Check if this is an accessory category (can be skipped)
        is_accessory = current_state in self._get_accessory_states()

        if is_accessory:
            english_message = f"""
⚠️ No {component_name} options found matching your requirements.

This component is optional. You can:
- Skip this category (say 'skip')
- Adjust your requirements
- Continue to the next category

Say 'skip' to continue or 'done' to finalize."""
        else:
            english_message = f"""
⚠️ No {component_name} options found matching your requirements.

This could mean:
- No compatible products available
- Requirements may need adjustment
- Or you can skip this component (if optional)

Would you like to:
1. Adjust your requirements
2. Skip this component (if optional)
"""

        # Translate if not English
        if language != "en":
            try:
                return await self.translator.translate(
                    english_message,
                    language,
                    context="No search results found message"
                )
            except Exception as e:
                logger.error(f"Translation failed for {language}: {e}, returning English")

        return english_message


# Dependency injection
_message_generator = None

def get_message_generator() -> MessageGenerator:
    """Get singleton message generator instance"""
    global _message_generator
    if _message_generator is None:
        _message_generator = MessageGenerator()
    return _message_generator
