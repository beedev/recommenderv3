"""
Streamlined State Orchestrator - Thin Coordinator Using Modular Processors

This orchestrator delegates all state-specific logic to modular processors
via the StateProcessorRegistry. It focuses solely on coordination:
- State transitions between processors
- Skip/done/finalize command handling
- Session management
- Compound request coordination

Architecture:
- Registry pattern for processor lifecycle
- Delegation pattern for state-specific operations
- Minimal orchestration logic (~800-1000 lines vs 3,851 lines)
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from langsmith import traceable

from app.models.conversation import (
    ConversationState,
    ConfiguratorState,
    SelectedProduct,
)
from app.services.intent.parameter_extractor import ParameterExtractor
from app.services.response.message_generator import MessageGenerator
from app.services.processors.registry import StateProcessorRegistry
from app.services.search.orchestrator import SearchOrchestrator

logger = logging.getLogger(__name__)


class StateByStateOrchestrator:
    """
    Streamlined orchestrator that coordinates state flow using modular processors.

    Responsibilities:
    - Initialize processor registry
    - Route requests to appropriate processor
    - Handle state transitions
    - Process special commands (skip, done, finalize)
    - Coordinate compound requests

    Delegation:
    - All state-specific search logic → StateProcessor
    - All state-specific validation → StateProcessor
    - All state-specific messages → StateProcessor
    """

    def __init__(
        self,
        parameter_extractor: ParameterExtractor,
        message_generator: MessageGenerator,
        search_orchestrator: SearchOrchestrator,
        state_config_path: str = "app/config/state_config.json",
    ):
        """Initialize orchestrator with modular processor registry."""
        self.parameter_extractor = parameter_extractor
        self.message_generator = message_generator
        self.search_orchestrator = search_orchestrator

        # Initialize processor registry - handles all 13 state processors
        self.registry = StateProcessorRegistry(
            state_config_path=state_config_path,
            search_orchestrator=search_orchestrator,
        )

        logger.info("✅ StateByStateOrchestrator initialized with processor registry")
        logger.info(f"   Processors loaded: {len(self.registry._processors)} states")

    @traceable(name="orchestrator_process_message", run_type="chain")
    async def process_message(
        self,
        conversation_state: ConversationState,
        user_message: str,
        last_shown_products: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Process user message in current state using modular processors.

        Flow:
        1. Check for special commands (skip, done, finalize)
        2. Extract parameters via ParameterExtractor
        3. Detect compound requests
        4. Delegate to processor for current state
        5. Handle state transition
        6. Generate response via MessageGenerator

        Args:
            conversation_state: Current session state
            user_message: User's input message
            last_shown_products: Previously shown products (for selection detection)

        Returns:
            Dict with response, state, products, selection status
        """
        language = conversation_state.language or "en"
        logger.info(f"🎯 Processing message in state: {conversation_state.current_state}")

        try:
            # Handle special commands first
            if self._is_special_command(user_message):
                return await self._handle_special_command(
                    user_message, conversation_state, language
                )

            # Extract parameters using LLM
            master_parameters = await self.parameter_extractor.extract_parameters(
                user_message=user_message,
                current_state=conversation_state.current_state,
                master_parameters=conversation_state.master_parameters,
            )

            # Update conversation state with extracted parameters
            conversation_state.master_parameters = master_parameters

            # Log extracted parameters for debugging
            import json
            non_empty_params = {
                k: v for k, v in master_parameters.items()
                if v and v != {} and v != []
            }
            if non_empty_params:
                logger.info(f"🔍 LLM EXTRACTED PARAMETERS:\n{json.dumps(non_empty_params, indent=2)}")
            else:
                logger.info("🔍 LLM EXTRACTED: No parameters extracted from user message")

            # Check for compound request (multiple components specified)
            if self._is_compound_request(master_parameters, conversation_state):
                return await self._handle_compound_request(
                    master_parameters, conversation_state, language
                )

            # Delegate to processor for current state
            return await self._process_single_state(
                user_message, master_parameters, conversation_state, language
            )

        except Exception as e:
            logger.error(f"❌ Error in process_message: {e}", exc_info=True)
            return self._generate_error_response(str(e), conversation_state, language)

    @traceable(name="orchestrator_select_product", run_type="chain")
    async def select_product(
        self,
        product_gin: str,
        product_data: Dict[str, Any],
        conversation_state: ConversationState,
        language: str = "en",
    ) -> Dict[str, Any]:
        """
        Handle explicit product selection using modular processors.

        Flow:
        1. Get processor for current state
        2. Create SelectedProduct from product data
        3. Add to response_json
        4. Check if proactive display enabled for next state
        5. Generate response with selection confirmation

        Args:
            product_gin: Selected product GIN
            product_data: Product details
            conversation_state: Current session state
            language: ISO 639-1 language code

        Returns:
            Dict with response, updated state, next products
        """
        logger.info(f"✅ Product selected: {product_gin} in state {conversation_state.current_state}")

        try:
            # Get processor for current state
            processor = self.registry.get_processor(conversation_state.current_state)
            if not processor:
                raise ValueError(f"No processor found for state: {conversation_state.current_state}")

            # Create selected product
            selected_product = SelectedProduct(
                gin=product_gin,
                name=product_data.get("name", "Unknown"),
                category=product_data.get("category", ""),
                description=product_data.get("description", ""),
            )

            # Add to response_json based on component type
            component_key = processor.component_type

            if processor.is_multi_select():
                # Multi-select: Add to list
                current_list = getattr(conversation_state.response_json, component_key, [])
                if not isinstance(current_list, list):
                    current_list = []
                current_list.append(selected_product)
                setattr(conversation_state.response_json, component_key, current_list)
                logger.info(f"   Added to multi-select: {component_key} (count: {len(current_list)})")
            else:
                # Single-select: Replace
                setattr(conversation_state.response_json, component_key, selected_product)
                logger.info(f"   Set single-select: {component_key}")

            # Generate selection confirmation message
            selection_message = processor.generate_selection_message(
                product_data, is_multi_select=processor.is_multi_select()
            )

            # Check for multi-select continuation
            if processor.is_multi_select():
                # User may want to add more products in this state
                return {
                    "session_id": conversation_state.session_id,
                    "message": selection_message,
                    "current_state": conversation_state.current_state,
                    "master_parameters": conversation_state.master_parameters,
                    "response_json": conversation_state.response_json,
                    "products": [],
                    "awaiting_selection": False,
                    "can_finalize": self._can_finalize(conversation_state),
                }

            # Single-select: Move to next state
            next_state = processor.get_next_state(conversation_state, selection_made=True)
            conversation_state.current_state = next_state
            logger.info(f"   State transition: → {next_state}")

            # Check if proactive display enabled for next state
            next_products = []
            if next_state != ConfiguratorState.FINALIZE:
                next_processor = self.registry.get_processor(next_state)
                if next_processor and next_processor.should_show_proactive_preview():
                    logger.info(f"🔍 Proactive search for next state: {next_state}")
                    search_results = await next_processor.search_products(
                        user_message="",
                        master_parameters=conversation_state.master_parameters,
                        selected_components=conversation_state.response_json,
                        limit=5,  # Preview limit
                    )
                    next_products = search_results.get("products", [])
                    logger.info(f"   Found {len(next_products)} products for proactive display")

            # Generate full response
            response_message = await self.message_generator.generate_response(
                message_type="selection",
                state=next_state,
                products=next_products,
                selected_product=selected_product,
                language=language,
                custom_message=selection_message,
            )

            return {
                "session_id": conversation_state.session_id,
                "message": response_message,
                "current_state": next_state,
                "master_parameters": conversation_state.master_parameters,
                "response_json": conversation_state.response_json,
                "products": next_products,
                "awaiting_selection": len(next_products) > 0,
                "can_finalize": self._can_finalize(conversation_state),
            }

        except Exception as e:
            logger.error(f"❌ Error in select_product: {e}", exc_info=True)
            return self._generate_error_response(str(e), conversation_state, language)

    async def _process_single_state(
        self,
        user_message: str,
        master_parameters: Dict[str, Any],
        conversation_state: ConversationState,
        language: str,
    ) -> Dict[str, Any]:
        """
        Process message for single state using processor delegation.

        Args:
            user_message: User's input
            master_parameters: Extracted parameters
            conversation_state: Current state
            language: Language code

        Returns:
            Response dict
        """
        current_state = conversation_state.current_state

        # Get processor for current state
        processor = self.registry.get_processor(current_state)
        if not processor:
            raise ValueError(f"No processor found for state: {current_state}")

        logger.info(f"🔧 Delegating to processor: {processor.__class__.__name__}")

        # Delegate search to processor
        search_results = await processor.search_products(
            user_message=user_message,
            master_parameters=master_parameters,
            selected_components=conversation_state.response_json,
            limit=10,  # Regular search limit
        )

        products = search_results.get("products", [])
        logger.info(f"   Search returned {len(products)} products")

        # Auto-select if exactly 1 product found
        if len(products) == 1 and not processor.is_multi_select():
            product = products[0]
            logger.info(f"🎯 Auto-selecting single product: {product['gin']}")

            # Create selected product
            selected_product = SelectedProduct(
                gin=product["gin"],
                name=product["name"],
                category=product.get("category", ""),
                description=product.get("description", ""),
            )

            # Add to response_json
            setattr(conversation_state.response_json, processor.component_type, selected_product)

            # Move to next state
            next_state = processor.get_next_state(conversation_state, selection_made=True)
            conversation_state.current_state = next_state

            # Generate response with auto-selection
            response_message = await self.message_generator.generate_response(
                message_type="auto_selection",
                state=next_state,
                products=[],
                selected_product=selected_product,
                language=language,
            )

            return {
                "session_id": conversation_state.session_id,
                "message": response_message,
                "current_state": next_state,
                "master_parameters": master_parameters,
                "response_json": conversation_state.response_json,
                "products": [],
                "awaiting_selection": False,
                "can_finalize": self._can_finalize(conversation_state),
            }

        # Multiple products or multi-select: Show products for user selection
        response_message = await self.message_generator.generate_response(
            message_type="search_results",
            state=current_state,
            products=products,
            language=language,
            zero_results_message=search_results.get("zero_results_message"),
        )

        return {
            "session_id": conversation_state.session_id,
            "message": response_message,
            "current_state": current_state,
            "master_parameters": master_parameters,
            "response_json": conversation_state.response_json,
            "products": products,
            "awaiting_selection": len(products) > 0,
            "can_finalize": self._can_finalize(conversation_state),
        }

    def _is_special_command(self, user_message: str) -> bool:
        """Check if message is a special command (skip, done, finalize)."""
        normalized = user_message.strip().lower()
        special_commands = ["skip", "done", "finalize", "finish", "complete", "next"]
        return normalized in special_commands

    async def _handle_special_command(
        self,
        user_message: str,
        conversation_state: ConversationState,
        language: str,
    ) -> Dict[str, Any]:
        """
        Handle special commands: skip, done, finalize.

        Args:
            user_message: Command text
            conversation_state: Current state
            language: Language code

        Returns:
            Response dict
        """
        command = user_message.strip().lower()
        current_state = conversation_state.current_state

        logger.info(f"🎮 Special command: '{command}' in state {current_state}")

        # Get processor for current state
        processor = self.registry.get_processor(current_state)
        if not processor:
            raise ValueError(f"No processor found for state: {current_state}")

        # Handle finalize
        if command in ["finalize", "finish", "complete"]:
            if not self._can_finalize(conversation_state):
                response_message = await self.message_generator.generate_response(
                    message_type="error",
                    state=current_state,
                    language=language,
                    custom_message="Cannot finalize: PowerSource must be selected first.",
                )
                return {
                    "session_id": conversation_state.session_id,
                    "message": response_message,
                    "current_state": current_state,
                    "master_parameters": conversation_state.master_parameters,
                    "response_json": conversation_state.response_json,
                    "products": [],
                    "awaiting_selection": False,
                    "can_finalize": False,
                }

            # Move to finalize state
            conversation_state.current_state = ConfiguratorState.FINALIZE
            response_message = await self.message_generator.generate_response(
                message_type="finalize",
                state=ConfiguratorState.FINALIZE,
                language=language,
                response_json=conversation_state.response_json,
            )

            return {
                "session_id": conversation_state.session_id,
                "message": response_message,
                "current_state": ConfiguratorState.FINALIZE,
                "master_parameters": conversation_state.master_parameters,
                "response_json": conversation_state.response_json,
                "products": [],
                "awaiting_selection": False,
                "can_finalize": True,
            }

        # Handle skip or done
        if command in ["skip", "done", "next"]:
            # For multi-select states, "done" means move to next state
            # For single-select, "skip" means skip this component

            if not processor.can_skip() and command == "skip":
                response_message = await self.message_generator.generate_response(
                    message_type="error",
                    state=current_state,
                    language=language,
                    custom_message=f"{processor.get_component_display_name()} is mandatory and cannot be skipped.",
                )
                return {
                    "session_id": conversation_state.session_id,
                    "message": response_message,
                    "current_state": current_state,
                    "master_parameters": conversation_state.master_parameters,
                    "response_json": conversation_state.response_json,
                    "products": [],
                    "awaiting_selection": False,
                    "can_finalize": self._can_finalize(conversation_state),
                }

            # Get next state from processor
            next_state = processor.get_next_state(conversation_state, selection_made=True)
            conversation_state.current_state = next_state

            logger.info(f"   Skipped/Done: {current_state} → {next_state}")

            # Check for proactive display in next state
            next_products = []
            if next_state != ConfiguratorState.FINALIZE:
                next_processor = self.registry.get_processor(next_state)
                if next_processor and next_processor.should_show_proactive_preview():
                    search_results = await next_processor.search_products(
                        user_message="",
                        master_parameters=conversation_state.master_parameters,
                        selected_components=conversation_state.response_json,
                        limit=5,
                    )
                    next_products = search_results.get("products", [])

            # Generate response
            response_message = await self.message_generator.generate_response(
                message_type="skip",
                state=next_state,
                products=next_products,
                language=language,
            )

            return {
                "session_id": conversation_state.session_id,
                "message": response_message,
                "current_state": next_state,
                "master_parameters": conversation_state.master_parameters,
                "response_json": conversation_state.response_json,
                "products": next_products,
                "awaiting_selection": len(next_products) > 0,
                "can_finalize": self._can_finalize(conversation_state),
            }

        # Unknown command - should not reach here due to _is_special_command check
        raise ValueError(f"Unknown special command: {command}")

    def _is_compound_request(
        self, master_parameters: Dict[str, Any], conversation_state: ConversationState
    ) -> bool:
        """
        Check if request specifies multiple components.

        Compound request: User specifies 2+ components in single message.
        Example: "Aristo 500ix with RobustFeed U6"

        Args:
            master_parameters: Extracted parameters (dict)
            conversation_state: Current state

        Returns:
            True if compound request detected
        """
        # Only detect in initial state (power_source_selection)
        if conversation_state.current_state != ConfiguratorState.POWER_SOURCE_SELECTION:
            return False

        # Convert Pydantic model to dict if needed
        if not isinstance(master_parameters, dict):
            master_parameters = master_parameters.dict() if hasattr(master_parameters, 'dict') else master_parameters

        # Count components with specifications
        specified_components = 0
        for component_key, component_params in master_parameters.items():
            # Skip metadata fields
            if component_key == "last_updated":
                continue
            if component_params and isinstance(component_params, dict) and any(v for v in component_params.values() if v):
                specified_components += 1

        is_compound = specified_components >= 2
        if is_compound:
            logger.info(f"🔍 Compound request detected: {specified_components} components specified")

        return is_compound

    async def _handle_compound_request(
        self,
        master_parameters: Dict[str, Any],
        conversation_state: ConversationState,
        language: str,
    ) -> Dict[str, Any]:
        """
        Handle compound request (multiple components specified).

        Flow:
        1. Validate: PowerSource must be included
        2. Search all specified components in parallel
        3. Auto-select exact matches (1 result)
        4. Queue disambiguation for multiple matches
        5. Move to first component needing disambiguation or next unhandled component

        Args:
            master_parameters: Extracted parameters
            conversation_state: Current state
            language: Language code

        Returns:
            Response dict
        """
        logger.info("🎯 Processing compound request")

        # Validate: PowerSource must be specified
        ps_params = master_parameters.get("power_source", {})
        if not ps_params or not any(v for v in ps_params.values() if v):
            return {
                "session_id": conversation_state.session_id,
                "message": "To configure multiple components, I first need to know which Power Source you want. Please specify a power source.",
                "current_state": ConfiguratorState.POWER_SOURCE_SELECTION,
                "master_parameters": master_parameters,
                "response_json": conversation_state.response_json,
                "products": [],
                "awaiting_selection": False,
                "can_finalize": False,
            }

        # Search all specified components
        component_results: Dict[str, List[Dict[str, Any]]] = {}
        auto_selected: Dict[str, SelectedProduct] = {}
        first_disambiguation_state = None

        # Component sequence to process
        component_sequence = [
            ("power_source", ConfiguratorState.POWER_SOURCE_SELECTION),
            ("feeder", ConfiguratorState.FEEDER_SELECTION),
            ("cooler", ConfiguratorState.COOLER_SELECTION),
            ("interconnector", ConfiguratorState.INTERCONNECTOR_SELECTION),
            ("torch", ConfiguratorState.TORCH_SELECTION),
        ]

        for component_key, state in component_sequence:
            params = master_parameters.get(component_key, {})
            if not params or not any(v for v in params.values() if v):
                continue  # Component not specified

            processor = self.registry.get_processor(state)
            if not processor:
                continue

            # Search for this component
            search_results = await processor.search_products(
                user_message="",
                master_parameters=master_parameters,
                selected_components=conversation_state.response_json,
                limit=10,
            )

            products = search_results.get("products", [])
            logger.info(f"   {component_key}: {len(products)} products found")

            if len(products) == 1:
                # Exact match - auto-select
                product = products[0]
                selected_product = SelectedProduct(
                    gin=product["gin"],
                    name=product["name"],
                    category=product.get("category", ""),
                    description=product.get("description", ""),
                )
                setattr(conversation_state.response_json, processor.component_type, selected_product)
                auto_selected[component_key] = selected_product
                logger.info(f"   ✅ Auto-selected: {product['name']}")
            elif len(products) > 1:
                # Multiple matches - needs disambiguation
                component_results[component_key] = products
                if first_disambiguation_state is None:
                    first_disambiguation_state = state
                logger.info(f"   ⚠️  Disambiguation needed: {len(products)} options")
            else:
                # No matches - will show in response
                component_results[component_key] = []
                logger.info(f"   ❌ No matches found")

        # Determine next state
        if first_disambiguation_state:
            # Stop at first component needing disambiguation
            conversation_state.current_state = first_disambiguation_state
            products_to_show = component_results.get(
                self._state_to_component_key(first_disambiguation_state), []
            )
        else:
            # All specified components auto-selected - move to next unhandled component
            next_state = self._get_next_unhandled_state(conversation_state)
            conversation_state.current_state = next_state
            products_to_show = []

        # Generate compound response
        response_parts = []

        # Show auto-selections
        if auto_selected:
            for component_key, product in auto_selected.items():
                response_parts.append(f"✅ {component_key.replace('_', ' ').title()}: {product.name} (GIN: {product.gin}) - Auto-selected")

        # Show current package
        if conversation_state.response_json:
            response_parts.append("\nCurrent Package:")
            for key, value in conversation_state.response_json.items():
                if isinstance(value, SelectedProduct):
                    response_parts.append(f"• {key}: {value.name}")

        # Show disambiguation or next step
        if first_disambiguation_state:
            component_key = self._state_to_component_key(first_disambiguation_state)
            response_parts.append(f"\nFor {component_key.replace('_', ' ').title()}, I found multiple options:")
            for idx, product in enumerate(products_to_show[:5], 1):
                response_parts.append(f"{idx}. {product['name']} (GIN: {product['gin']})")
            response_parts.append("\nWhich would you like?")
        else:
            response_parts.append(f"\nNext: Would you like to add a {conversation_state.current_state.replace('_', ' ').title()}? [Y/N/skip]")

        response_message = "\n".join(response_parts)

        return {
            "session_id": conversation_state.session_id,
            "message": response_message,
            "current_state": conversation_state.current_state,
            "master_parameters": master_parameters,
            "response_json": conversation_state.response_json,
            "products": products_to_show,
            "awaiting_selection": len(products_to_show) > 0,
            "can_finalize": self._can_finalize(conversation_state),
        }

    def _state_to_component_key(self, state: str) -> str:
        """Convert state name to component key."""
        mapping = {
            ConfiguratorState.POWER_SOURCE_SELECTION: "power_source",
            ConfiguratorState.FEEDER_SELECTION: "feeder",
            ConfiguratorState.COOLER_SELECTION: "cooler",
            ConfiguratorState.INTERCONNECTOR_SELECTION: "interconnector",
            ConfiguratorState.TORCH_SELECTION: "torch",
        }
        return mapping.get(state, state.replace("_selection", ""))

    def _get_next_unhandled_state(self, conversation_state: ConversationState) -> str:
        """Get next state that hasn't been handled yet."""
        # State sequence
        sequence = [
            ConfiguratorState.FEEDER_SELECTION,
            ConfiguratorState.COOLER_SELECTION,
            ConfiguratorState.INTERCONNECTOR_SELECTION,
            ConfiguratorState.TORCH_SELECTION,
            ConfiguratorState.POWERSOURCE_ACCESSORIES_SELECTION,
            ConfiguratorState.FINALIZE,
        ]

        # Find first state not in response_json
        for state in sequence:
            processor = self.registry.get_processor(state)
            if processor and processor.component_type not in conversation_state.response_json:
                return state

        return ConfiguratorState.FINALIZE

    def _can_finalize(self, conversation_state: ConversationState) -> bool:
        """Check if configuration can be finalized (PowerSource selected)."""
        return "PowerSource" in conversation_state.response_json

    def _serialize_response_json(self, conversation_state: ConversationState) -> Dict[str, Any]:
        """
        Serialize response JSON for Neo4j queries and API responses.

        Converts Pydantic models in response_json to dictionaries.

        Args:
            conversation_state: Current session state

        Returns:
            Dict with serialized component data
        """
        response_dict = {}

        # Core components (single-select)
        if conversation_state.response_json.PowerSource:
            response_dict["PowerSource"] = conversation_state.response_json.PowerSource.dict()
        if conversation_state.response_json.Feeder:
            response_dict["Feeder"] = conversation_state.response_json.Feeder.dict()
        if conversation_state.response_json.Cooler:
            response_dict["Cooler"] = conversation_state.response_json.Cooler.dict()
        if conversation_state.response_json.Interconnector:
            response_dict["Interconnector"] = conversation_state.response_json.Interconnector.dict()
        if conversation_state.response_json.Torch:
            response_dict["Torch"] = conversation_state.response_json.Torch.dict()

        # Accessory categories (multi-select)
        if conversation_state.response_json.PowerSourceAccessories:
            response_dict["PowerSourceAccessories"] = [
                a.dict() for a in conversation_state.response_json.PowerSourceAccessories
            ]
        if conversation_state.response_json.FeederAccessories:
            response_dict["FeederAccessories"] = [
                a.dict() for a in conversation_state.response_json.FeederAccessories
            ]
        if conversation_state.response_json.FeederConditionalAccessories:
            response_dict["FeederConditionalAccessories"] = [
                a.dict() for a in conversation_state.response_json.FeederConditionalAccessories
            ]
        if conversation_state.response_json.InterconnectorAccessories:
            response_dict["InterconnectorAccessories"] = [
                a.dict() for a in conversation_state.response_json.InterconnectorAccessories
            ]
        if conversation_state.response_json.Remotes:
            response_dict["Remotes"] = [
                a.dict() for a in conversation_state.response_json.Remotes
            ]
        if conversation_state.response_json.RemoteAccessories:
            response_dict["RemoteAccessories"] = [
                a.dict() for a in conversation_state.response_json.RemoteAccessories
            ]
        if conversation_state.response_json.RemoteConditionalAccessories:
            response_dict["RemoteConditionalAccessories"] = [
                a.dict() for a in conversation_state.response_json.RemoteConditionalAccessories
            ]
        if conversation_state.response_json.Connectivity:
            response_dict["Connectivity"] = [
                a.dict() for a in conversation_state.response_json.Connectivity
            ]
        if conversation_state.response_json.FeederWears:
            response_dict["FeederWears"] = [
                a.dict() for a in conversation_state.response_json.FeederWears
            ]

        # Legacy accessories field (multi-select)
        if conversation_state.response_json.Accessories:
            response_dict["Accessories"] = [
                a.dict() for a in conversation_state.response_json.Accessories
            ]

        return response_dict

    def _generate_error_response(
        self, error_message: str, conversation_state: ConversationState, language: str
    ) -> Dict[str, Any]:
        """Generate error response dict."""
        return {
            "session_id": conversation_state.session_id,
            "message": f"An error occurred: {error_message}",
            "current_state": conversation_state.current_state,
            "master_parameters": conversation_state.master_parameters,
            "response_json": conversation_state.response_json,
            "products": [],
            "awaiting_selection": False,
            "can_finalize": self._can_finalize(conversation_state),
            "error": error_message,
        }
