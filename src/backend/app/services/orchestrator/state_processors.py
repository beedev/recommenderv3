"""
State Processors for Dynamic State Machine
Provides extensible processor registry for handling different state types
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Type
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProcessorResult:
    """Result from state processing"""
    success: bool
    message: str
    products: Optional[List[Dict[str, Any]]] = None
    awaiting_selection: bool = False
    transition_to_next: bool = False
    error: Optional[str] = None

    @classmethod
    def success_result(cls, message: str, products: Optional[List[Dict[str, Any]]] = None, awaiting_selection: bool = False):
        """Create success result"""
        return cls(
            success=True,
            message=message,
            products=products,
            awaiting_selection=awaiting_selection,
            transition_to_next=False
        )

    @classmethod
    def error_result(cls, error: str):
        """Create error result"""
        return cls(
            success=False,
            message=error,
            error=error
        )

    @classmethod
    def transition_result(cls, message: str):
        """Create transition result (move to next state)"""
        return cls(
            success=True,
            message=message,
            transition_to_next=True
        )


class BaseStateProcessor(ABC):
    """
    Abstract base class for state processors

    Each processor handles the logic for a specific type of state
    (single selection, multi selection, custom logic, etc.)
    """

    def __init__(self, state_name: str, component_key: str, api_key: str):
        """
        Initialize processor

        Args:
            state_name: State identifier (e.g., "feeder_selection")
            component_key: Component key (e.g., "feeder")
            api_key: API key for ResponseJSON (e.g., "Feeder")
        """
        self.state_name = state_name
        self.component_key = component_key
        self.api_key = api_key
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def process(
        self,
        conversation_state: Any,
        user_message: str,
        orchestrator: Any
    ) -> ProcessorResult:
        """
        Process state logic

        Args:
            conversation_state: Current conversation state
            user_message: User's message
            orchestrator: Reference to orchestrator for accessing services

        Returns:
            ProcessorResult with outcome
        """
        pass

    def can_handle(self, state_name: str) -> bool:
        """Check if this processor can handle the given state"""
        return self.state_name == state_name


class SingleSelectionProcessor(BaseStateProcessor):
    """
    Processor for single-selection states (Feeder, Cooler, Interconnector, Torch)

    Handles:
    - Product search with compatibility validation
    - Single product selection
    - Explicit selection by index
    """

    async def process(
        self,
        conversation_state: Any,
        user_message: str,
        orchestrator: Any
    ) -> ProcessorResult:
        """
        Process single-selection component state for Feeder, Cooler, Interconnector, or Torch.

        Orchestrates complete workflow for single-selection states in the S1→SN configurator flow:
        parameter extraction → product search → compatibility validation → result presentation.
        Handles both natural language queries and explicit numeric selections (e.g., "option 2").

        This processor is the standard handler for S2-S5 states where users select exactly one
        component from compatible products. Each search enforces Neo4j COMPATIBLE_WITH relationship
        validation with previously selected components.

        Args:
            conversation_state: Current conversation state containing:
                - current_state: ConfiguratorState enum value
                - master_parameters: MasterParameterJSON with user requirements
                - response_json: ResponseJSON with previously selected components
                - language: ISO 639-1 language code (e.g., "en", "es")
            user_message: User's input text, either:
                - Natural language query: "water-cooled feeder for aluminum"
                - Explicit selection: "2", "option 3", "select #1"
                - Navigation command: "skip", "back"
            orchestrator: StateOrchestrator instance providing access to:
                - parameter_extractor: Agent 1 for LLM parameter extraction
                - product_search: Agent 2 for Neo4j component-specific search
                - message_generator: Agent 3 for response generation

        Returns:
            ProcessorResult with one of three outcomes:
                1. **Awaiting Selection** (awaiting_selection=True):
                   - success=True, products=[...], message="Search results..."
                   - User needs to select from multiple compatible products
                2. **Transition Ready** (transition_to_next=True):
                   - success=True, message="Selected X. Moving to next..."
                   - Product selected, ready to advance to next state
                3. **Error** (success=False):
                   - error="No compatible products found"
                   - Search failed or no compatible products available

        Processing Workflow:
            1. **Parameter Extraction**: Extract component requirements from user message using LLM
            2. **Selection Detection**: Check if user provided explicit numeric selection
            3. **Explicit Selection Path**: If numeric → _handle_explicit_selection()
            4. **Search Path**: If natural language → component-specific search method:
               - search_feeder() for Feeder
               - search_cooler() for Cooler
               - search_interconnector() for Interconnector
               - search_torch() for Torch
            5. **Compatibility Validation**: All searches enforce COMPATIBLE_WITH relationships
            6. **Result Generation**: Format products into numbered list with selection prompt
            7. **Response**: Return awaiting_selection=True with product list

        Component-Specific Search Methods:
            - **Feeder**: search_feeder(master_parameters, response_json)
              - Validates PowerSource compatibility
              - Filters: cooling_type, wire_size, manufacturer
            - **Cooler**: search_cooler(master_parameters, response_json)
              - Validates PowerSource compatibility
              - Filters: cooling_capacity, voltage, coolant_type
            - **Interconnector**: search_interconnector(master_parameters, response_json)
              - Triple compatibility: PowerSource + Feeder + Cooler
              - Filters: cable_length, connector_type
            - **Torch**: search_torch(master_parameters, response_json)
              - Validates Feeder compatibility
              - Filters: amperage_rating, cooling_type, cable_length

        Examples:
            >>> # Example 1: Natural language query for feeder
            >>> result = await processor.process(
            ...     conversation_state=state,  # current_state="feeder_selection"
            ...     user_message="water-cooled feeder for aluminum welding",
            ...     orchestrator=orchestrator
            ... )
            >>> result.success
            True
            >>> result.awaiting_selection
            True
            >>> len(result.products)
            3  # Found 3 compatible feeders

            >>> # Example 2: Explicit numeric selection
            >>> result = await processor.process(
            ...     conversation_state=state,
            ...     user_message="2",  # Select option #2
            ...     orchestrator=orchestrator
            ... )
            >>> result.success
            True
            >>> result.transition_to_next
            True
            >>> result.message
            'Selected feeder option #2. Advancing to the next step.'

            >>> # Example 3: No compatible products error
            >>> result = await processor.process(
            ...     conversation_state=state,
            ...     user_message="1000A feeder",  # Impossible requirement
            ...     orchestrator=orchestrator
            ... )
            >>> result.success
            False
            >>> result.error
            'No compatible feeder found. Please try different requirements.'

        Note:
            - **Compatibility Enforcement**: All searches validate Neo4j COMPATIBLE_WITH relationships
            - **Dynamic Search Method**: Uses component_key to call correct search method dynamically
            - **Pydantic Conversion**: Converts Pydantic models to dicts for service layer compatibility
            - **Product Result Conversion**: Converts ProductResult objects to dicts for JSON serialization
            - **State-Specific Logic**: Each component type has unique compatibility requirements
            - **Error Handling**: Comprehensive try/except with detailed error logging
            - **Search Fallback**: If search method not found, returns error with component name

        Raises:
            Exception: Catches all exceptions, logs with traceback, returns ProcessorResult.error_result()
        """
        try:
            self.logger.info(f"Processing single selection for {self.component_key}")

            # Extract parameters from user message
            current_state_value = conversation_state.current_state.value if hasattr(conversation_state.current_state, 'value') else conversation_state.current_state

            # Convert Pydantic model to dict for parameter extractor
            master_params_dict = conversation_state.master_parameters.model_dump() if hasattr(conversation_state.master_parameters, 'model_dump') else conversation_state.master_parameters

            extracted = await orchestrator.parameter_extractor.extract_parameters(
                user_message=user_message,
                current_state=current_state_value,
                master_parameters=master_params_dict
            )

            # Update master parameters
            conversation_state.update_master_parameters(extracted)

            # Check for explicit selection by index
            selection = orchestrator._extract_selection_number(user_message)
            if selection is not None:
                return await self._handle_explicit_selection(
                    conversation_state, selection, orchestrator
                )

            # Search for products - call specific search method based on component type
            # e.g., search_feeder(), search_cooler(), search_interconnector(), search_torch()
            search_method_name = f"search_{self.component_key}"
            search_method = getattr(orchestrator.product_search, search_method_name, None)

            if not search_method:
                return ProcessorResult.error_result(
                    f"Search method not found for component: {self.component_key}"
                )

            search_results = await search_method(
                master_parameters=conversation_state.master_parameters.model_dump(),
                response_json=conversation_state.response_json.model_dump()
            )

            if not search_results.products:
                return ProcessorResult.error_result(
                    f"No compatible {self.component_key} found. Please try different requirements."
                )

            # Generate response with search results
            message = await orchestrator.message_generator.generate_search_results_message(
                current_state=conversation_state.current_state.value,
                search_results=search_results,
                master_parameters=conversation_state.master_parameters.model_dump(),
                language=conversation_state.language
            )

            # Convert ProductResult objects to dicts for ProcessorResult
            products_list = [p.model_dump() for p in search_results.products]

            return ProcessorResult.success_result(
                message=message,
                products=products_list,
                awaiting_selection=True
            )

        except Exception as e:
            self.logger.error(f"Error in single selection processor: {e}", exc_info=True)
            return ProcessorResult.error_result(f"Error processing {self.component_key}: {str(e)}")

    async def _handle_explicit_selection(
        self,
        conversation_state: Any,
        selection: int,
        orchestrator: Any
    ) -> ProcessorResult:
        """
        Handle explicit numeric product selection for single-selection components.

        Processes user's direct numeric selection (e.g., "2", "option 3", "select #1") by
        creating a transition result that signals the orchestrator to advance to the next
        state. The actual product addition to ResponseJSON is handled by the orchestrator's
        _handle_selection() method.

        This is a lightweight method that simply acknowledges the selection and prepares
        for state transition. The heavy lifting of product validation, GIN extraction,
        and ResponseJSON update happens in the orchestrator layer.

        Args:
            conversation_state: Current conversation state (unused in this method, but
                required for interface consistency)
            selection: Numeric selection index (1-based) from user input
                - Extracted by orchestrator._extract_selection_number()
                - Examples: "2" → 2, "option 3" → 3, "select #1" → 1
            orchestrator: StateOrchestrator instance (unused in this method, but
                required for interface consistency)

        Returns:
            ProcessorResult with transition_to_next=True:
                - success=True
                - message=f"Selected {component_key} option #{selection}. Advancing to the next step."
                - transition_to_next=True (signals orchestrator to advance state)
                - products=None
                - awaiting_selection=False

        Processing Flow (Orchestrator Context):
            1. **User Input**: "2" or "option 3" or "select #1"
            2. **Orchestrator**: Extracts numeric value → calls this method
            3. **This Method**: Returns transition_result
            4. **Orchestrator**: Calls _handle_selection(selection_index)
            5. **Orchestrator**: Extracts product from last search results
            6. **Orchestrator**: Adds product to ResponseJSON
            7. **Orchestrator**: Advances to next state via get_next_state()

        Examples:
            >>> # Example 1: User selects option 2 for feeder
            >>> processor = SingleSelectionProcessor("feeder_selection", "feeder", "Feeder")
            >>> result = await processor._handle_explicit_selection(
            ...     conversation_state=state,
            ...     selection=2,
            ...     orchestrator=orchestrator
            ... )
            >>> result.success
            True
            >>> result.transition_to_next
            True
            >>> result.message
            'Selected feeder option #2. Advancing to the next step.'

            >>> # Example 2: User selects option 1 for cooler
            >>> processor = SingleSelectionProcessor("cooler_selection", "cooler", "Cooler")
            >>> result = await processor._handle_explicit_selection(
            ...     conversation_state=state,
            ...     selection=1,
            ...     orchestrator=orchestrator
            ... )
            >>> result.message
            'Selected cooler option #1. Advancing to the next step.'

        Note:
            - **No Validation**: This method does NOT validate if selection index is valid
            - **Orchestrator Responsibility**: Product validation and ResponseJSON update
              happen in orchestrator._handle_selection()
            - **Lightweight Design**: Simple acknowledgment before state transition
            - **Component-Agnostic**: Works for any single-selection component (Feeder,
              Cooler, Interconnector, Torch)
            - **Transition Signal**: transition_to_next=True tells orchestrator to:
              1. Update ResponseJSON with selected product
              2. Call conversation_state.get_next_state()
              3. Generate next state prompt
        """
        message = (
            f"Selected {self.component_key} option #{selection}. "
            "Advancing to the next step."
        )
        result = ProcessorResult.transition_result(message=message)
        return result


class MultiSelectionProcessor(BaseStateProcessor):
    """
    Processor for multi-selection states (Accessories)
    """

    async def process(
        self,
        conversation_state: Any,
        user_message: str,
        orchestrator: Any
    ) -> ProcessorResult:
        """
        Process multi-selection accessory state allowing users to select multiple products.

        Orchestrates workflow for S6 (Accessories) state where users can add multiple accessories
        to their configuration. Unlike single-selection states, this processor:
        - Allows adding multiple products to a list
        - Supports "done"/"next" commands to finish selection
        - Maintains awaiting_selection=True until user explicitly finishes

        This is the standard handler for S6 accessories_selection state where users can build
        a collection of compatible accessories. Each search validates Neo4j COMPATIBLE_WITH
        relationships with all previously selected components.

        Args:
            conversation_state: Current conversation state containing:
                - current_state: ConfiguratorState.accessories_selection
                - master_parameters: MasterParameterJSON with user requirements
                - response_json: ResponseJSON with selected components (used for compatibility)
                - language: ISO 639-1 language code (e.g., "en", "es")
            user_message: User's input text, either:
                - Natural language query: "welding cables for this setup"
                - Explicit selection: "2", "add #3", "select option 1"
                - Completion command: "done", "finish", "complete", "next"
                - Navigation command: "skip"
            orchestrator: StateOrchestrator instance providing access to:
                - parameter_extractor: Agent 1 for LLM parameter extraction
                - product_search: Agent 2 for Neo4j accessory search
                - message_generator: Agent 3 for response generation

        Returns:
            ProcessorResult with one of three outcomes:
                1. **Awaiting Selection** (awaiting_selection=True):
                   - success=True, products=[...], message="Search results..."
                   - User can select more accessories or type "done"
                2. **Transition Ready** (transition_to_next=True):
                   - success=True, message="Accessories selection complete..."
                   - User typed "done"/"next", ready to advance to FINALIZE
                3. **Error** (success=False):
                   - error="No accessories found. Type 'done' to continue."
                   - Search failed, but user can still proceed with "done"

        Processing Workflow:
            1. **Completion Check**: Check if user typed "done"/"finish"/"complete"/"next"
            2. **Early Exit**: If completion command → return transition_result
            3. **Parameter Extraction**: Extract accessory requirements from user message using LLM
            4. **Selection Detection**: Check if user provided explicit numeric selection
            5. **Explicit Selection Path**: If numeric → _handle_accessory_selection()
            6. **Search Path**: If natural language → search_accessories()
               - Validates compatibility with ALL selected components
               - Supports category filtering (cables, consumables, safety gear)
            7. **Result Generation**: Format accessories into numbered list
            8. **Response**: Return awaiting_selection=True with instruction to select or "done"

        Multi-Select Behavior:
            - **Add to List**: Each selection adds to ResponseJSON.Accessories[]
            - **No Overwrite**: Unlike single-selection, doesn't replace previous selection
            - **"Done" Command**: User must explicitly finish with "done"/"next"
            - **Optional State**: Can be skipped with "skip" command

        Accessory Search Details:
            - **Method**: search_accessories(master_parameters, response_json)
            - **Compatibility**: Validates with PowerSource, Feeder, Cooler, Interconnector, Torch
            - **Categories**: Cables, consumables, safety gear, maintenance parts
            - **Filters**: category, manufacturer, compatibility_type

        Examples:
            >>> # Example 1: Natural language accessory search
            >>> result = await processor.process(
            ...     conversation_state=state,  # current_state="accessories_selection"
            ...     user_message="welding cables and safety equipment",
            ...     orchestrator=orchestrator
            ... )
            >>> result.success
            True
            >>> result.awaiting_selection
            True
            >>> len(result.products)
            5  # Found 5 compatible accessories

            >>> # Example 2: User types "done" to finish
            >>> result = await processor.process(
            ...     conversation_state=state,
            ...     user_message="done",
            ...     orchestrator=orchestrator
            ... )
            >>> result.success
            True
            >>> result.transition_to_next
            True
            >>> result.message
            'Accessories selection complete. Moving to next step.'

            >>> # Example 3: No accessories found (soft error)
            >>> result = await processor.process(
            ...     conversation_state=state,
            ...     user_message="1000ft welding cable",  # No match
            ...     orchestrator=orchestrator
            ... )
            >>> result.success
            False
            >>> result.error
            "No accessories found. Type 'done' to continue."

        Note:
            - **Multi-Select Design**: Maintains awaiting_selection=True until "done" command
            - **Soft Errors**: "No accessories found" allows user to continue with "done"
            - **Compatibility Validation**: Searches validate with all selected components
            - **Category Support**: Can filter by accessory category in master_parameters
            - **Completion Commands**: Accepts "done", "finish", "complete", "next"
            - **Error Handling**: Comprehensive try/except with detailed error logging
            - **Pydantic Conversion**: Converts models to dicts for service layer compatibility

        Raises:
            Exception: Catches all exceptions, logs with traceback, returns ProcessorResult.error_result()
        """
        try:
            self.logger.info(f"Processing multi selection for {self.component_key}")

            # Check for "done" command
            if user_message.lower().strip() in ["done", "finish", "complete", "next"]:
                # Move to next state
                return ProcessorResult.transition_result(
                    f"Accessories selection complete. Moving to next step."
                )

            # Extract parameters
            current_state_value = conversation_state.current_state.value if hasattr(conversation_state.current_state, 'value') else conversation_state.current_state

            # Convert Pydantic model to dict for parameter extractor
            master_params_dict = conversation_state.master_parameters.model_dump() if hasattr(conversation_state.master_parameters, 'model_dump') else conversation_state.master_parameters

            extracted = await orchestrator.parameter_extractor.extract_parameters(
                user_message=user_message,
                current_state=current_state_value,
                master_parameters=master_params_dict
            )

            # Update master parameters
            conversation_state.update_master_parameters(extracted)

            # Check for explicit selection
            selection = orchestrator._extract_selection_number(user_message)
            if selection is not None:
                return await self._handle_accessory_selection(
                    conversation_state, selection, orchestrator
                )

            # Search for accessories
            search_results = await orchestrator.product_search.search_accessories(
                master_parameters=conversation_state.master_parameters.model_dump(),
                response_json=conversation_state.response_json.model_dump()
            )

            if not search_results.products:
                return ProcessorResult.error_result(
                    "No accessories found. Type 'done' to continue."
                )

            # Generate response with search results
            message = await orchestrator.message_generator.generate_search_results_message(
                current_state=conversation_state.current_state.value,
                search_results=search_results,
                master_parameters=conversation_state.master_parameters.model_dump(),
                language=conversation_state.language
            )

            # Convert ProductResult objects to dicts for ProcessorResult
            products_list = [p.model_dump() for p in search_results.products]

            return ProcessorResult.success_result(
                message=message,
                products=products_list,
                awaiting_selection=True
            )

        except Exception as e:
            self.logger.error(f"Error in multi selection processor: {e}", exc_info=True)
            return ProcessorResult.error_result(f"Error processing {self.component_key}: {str(e)}")

    async def _handle_accessory_selection(
        self,
        conversation_state: Any,
        selection: int,
        orchestrator: Any
    ) -> ProcessorResult:
        """
        Handle explicit numeric accessory selection for multi-select state.

        Processes user's direct numeric selection for accessories by creating a success result
        that maintains awaiting_selection=True state. Unlike single-selection components, this
        method keeps the user in the accessories state to allow adding more products.

        The actual product addition to ResponseJSON.Accessories[] is handled by the orchestrator's
        _handle_selection() method. This method simply acknowledges the selection and prompts
        for more accessories or "done" command.

        Args:
            conversation_state: Current conversation state (unused in this method, but
                required for interface consistency)
            selection: Numeric selection index (1-based) from user input
                - Extracted by orchestrator._extract_selection_number()
                - Examples: "2" → 2, "add #3" → 3, "select option 1" → 1
            orchestrator: StateOrchestrator instance (unused in this method, but
                required for interface consistency)

        Returns:
            ProcessorResult with awaiting_selection=True:
                - success=True
                - message=f"Added accessory #{selection}. Select more or type 'done'."
                - awaiting_selection=True (keeps user in accessories state)
                - products=None
                - transition_to_next=False

        Multi-Select Behavior:
            - **Stays in State**: Does NOT advance to next state (unlike single-selection)
            - **awaiting_selection=True**: Keeps user in accessories_selection state
            - **Prompts for More**: Message encourages selecting more or typing "done"
            - **List Addition**: Orchestrator adds to ResponseJSON.Accessories[] (not replace)

        Processing Flow (Orchestrator Context):
            1. **User Input**: "2" or "add #3" or "select option 1"
            2. **Orchestrator**: Extracts numeric value → calls this method
            3. **This Method**: Returns success_result with awaiting_selection=True
            4. **Orchestrator**: Calls _handle_selection(selection_index)
            5. **Orchestrator**: Extracts product from last search results
            6. **Orchestrator**: ADDS product to ResponseJSON.Accessories[] (list append)
            7. **Orchestrator**: Stays in accessories_selection state
            8. **User**: Can select more accessories or type "done" to finish

        Examples:
            >>> # Example 1: User selects first accessory
            >>> processor = MultiSelectionProcessor("accessories_selection", "accessories", "Accessories")
            >>> result = await processor._handle_accessory_selection(
            ...     conversation_state=state,
            ...     selection=1,
            ...     orchestrator=orchestrator
            ... )
            >>> result.success
            True
            >>> result.awaiting_selection
            True
            >>> result.transition_to_next
            False
            >>> result.message
            'Added accessory #1. Select more or type 'done'.'

            >>> # Example 2: User adds third accessory
            >>> result = await processor._handle_accessory_selection(
            ...     conversation_state=state,
            ...     selection=3,
            ...     orchestrator=orchestrator
            ... )
            >>> result.message
            'Added accessory #3. Select more or type 'done'.'

        Note:
            - **Placeholder Implementation**: Current implementation is a placeholder
            - **No Validation**: This method does NOT validate if selection index is valid
            - **Orchestrator Responsibility**: Product validation and list addition happen
              in orchestrator._handle_selection()
            - **Multi-Select Design**: Key difference from SingleSelectionProcessor is
              awaiting_selection=True instead of transition_to_next=True
            - **User Experience**: User stays in state until explicitly typing "done"
            - **Future Enhancement**: Could add confirmation of which product was added
        """
        # Placeholder for actual implementation
        return ProcessorResult.success_result(
            message=f"Added accessory #{selection}. Select more or type 'done'.",
            awaiting_selection=True
        )


class PowerSourceProcessor(BaseStateProcessor):
    """
    Special processor for S1 (Power Source Selection)

    Handles:
    - Power source search and selection
    - Loading component applicability configuration
    - Mandatory state (cannot skip)
    """

    async def process(
        self,
        conversation_state: Any,
        user_message: str,
        orchestrator: Any
    ) -> ProcessorResult:
        """
        Process S1 (Power Source Selection) - the mandatory first step in configurator workflow.

        Orchestrates the critical first state that determines component applicability for the
        entire S1→SN workflow. After PowerSource selection, the system loads applicability
        configuration to determine which downstream components are needed (Y/N flags for
        Feeder, Cooler, Interconnector, Torch, Accessories).

        This is the ONLY mandatory state in the configurator. Users cannot skip PowerSource
        selection and cannot proceed to downstream components without completing S1 first.

        Args:
            conversation_state: Current conversation state containing:
                - current_state: ConfiguratorState.power_source_selection (S1)
                - master_parameters: MasterParameterJSON with user requirements
                - response_json: ResponseJSON (empty at S1)
                - language: ISO 639-1 language code (e.g., "en", "es")
            user_message: User's input text, either:
                - Natural language query: "500A MIG welder for aluminum"
                - Explicit selection: "2", "option 3", "select #1"
                - Technical specs: "GMAW, 400A, water-cooled, industrial"
            orchestrator: StateOrchestrator instance providing access to:
                - parameter_extractor: Agent 1 for LLM parameter extraction
                - product_search: Agent 2 for Neo4j power source search
                - message_generator: Agent 3 for response generation

        Returns:
            ProcessorResult with one of three outcomes:
                1. **Awaiting Selection** (awaiting_selection=True):
                   - success=True, products=[...], message="Search results..."
                   - User needs to select from multiple power source options
                2. **Transition Ready** (transition_to_next=True):
                   - success=True, message="Selected power source. Loading applicability..."
                   - Power source selected, ready to advance to S2 (or first applicable component)
                3. **Error** (success=False):
                   - error="No power sources found matching your requirements..."
                   - Search failed, user needs to provide different specifications

        Processing Workflow:
            1. **Parameter Extraction**: Extract power source requirements from user message:
               - Welding process (MIG/TIG/Stick/Multi-process)
               - Current output (200A, 350A, 500A, etc.)
               - Voltage (230V, 460V, etc.)
               - Material type (Steel, Aluminum, Stainless, etc.)
               - Cooling type (Air-cooled, Water-cooled)
            2. **Selection Detection**: Check if user provided explicit numeric selection
            3. **Explicit Selection Path**: If numeric → _handle_power_source_selection()
            4. **Search Path**: If natural language → search_power_source()
               - No compatibility validation needed (first component)
               - Filters by specifications (current, voltage, process, material)
               - Prioritizes by configured priority scores
            5. **Result Generation**: Format power sources into numbered list
            6. **Response**: Return awaiting_selection=True with product list

        Power Source Search Details:
            - **Method**: search_power_source(master_parameters)
            - **No Compatibility Check**: First component, no previous selections to validate
            - **Filters**: process, current_output, voltage, material, cooling_type
            - **Examples**: "Aristo 500ix", "Warrior 500i", "Rebel EMP 215ic"

        Critical State Responsibilities:
            - **Component Applicability Loading**: After selection, orchestrator loads
              component_applicability.json to determine which downstream components are needed
            - **Y/N Flag Setting**: Sets ResponseJSON.applicability flags:
              - Feeder: Y/N (if Y, S2 will be shown)
              - Cooler: Y/N (if Y, S3 will be shown)
              - Interconnector: Y/N (if Y, S4 will be shown)
              - Torch: Y/N (if Y, S5 will be shown)
              - Accessories: Y (always available)
            - **State Flow Control**: Applicability flags control dynamic state skipping

        Examples:
            >>> # Example 1: Natural language query
            >>> result = await processor.process(
            ...     conversation_state=state,  # current_state="power_source_selection"
            ...     user_message="500A MIG welder for aluminum with water cooling",
            ...     orchestrator=orchestrator
            ... )
            >>> result.success
            True
            >>> result.awaiting_selection
            True
            >>> len(result.products)
            3  # Found 3 matching power sources

            >>> # Example 2: Explicit numeric selection
            >>> result = await processor.process(
            ...     conversation_state=state,
            ...     user_message="1",  # Select first power source
            ...     orchestrator=orchestrator
            ... )
            >>> result.success
            True
            >>> result.transition_to_next
            True
            >>> result.message
            'Selected power source. Loading component applicability...'

            >>> # Example 3: No matches error
            >>> result = await processor.process(
            ...     conversation_state=state,
            ...     user_message="10000A underwater nuclear welder",  # Impossible spec
            ...     orchestrator=orchestrator
            ... )
            >>> result.success
            False
            >>> result.error
            'No power sources found matching your requirements. Please try different specifications.'

        Note:
            - **Mandatory State**: Cannot be skipped, must complete before proceeding
            - **First State**: No compatibility validation needed (no previous selections)
            - **Applicability Trigger**: Selection triggers component applicability loading
            - **Dynamic State Flow**: Applicability flags determine which states shown next
            - **Configuration-Driven**: Applicability loaded from component_applicability.json
            - **Error Handling**: Comprehensive try/except with detailed error logging
            - **Pydantic Conversion**: Converts models to dicts for service layer compatibility

        Raises:
            Exception: Catches all exceptions, logs with traceback, returns ProcessorResult.error_result()
        """
        try:
            self.logger.info("Processing power source selection (S1)")

            # Extract parameters
            current_state_value = conversation_state.current_state.value if hasattr(conversation_state.current_state, 'value') else conversation_state.current_state

            # Convert Pydantic model to dict for parameter extractor
            master_params_dict = conversation_state.master_parameters.model_dump() if hasattr(conversation_state.master_parameters, 'model_dump') else conversation_state.master_parameters

            extracted = await orchestrator.parameter_extractor.extract_parameters(
                user_message=user_message,
                current_state=current_state_value,
                master_parameters=master_params_dict
            )

            # Update master parameters
            conversation_state.update_master_parameters(extracted)

            # Check for explicit selection
            selection = orchestrator._extract_selection_number(user_message)
            if selection is not None:
                return await self._handle_power_source_selection(
                    conversation_state, selection, orchestrator
                )

            # Search for power sources
            search_results = await orchestrator.product_search.search_power_source(
                master_parameters=conversation_state.master_parameters.model_dump()
            )

            if not search_results.products:
                return ProcessorResult.error_result(
                    "No power sources found matching your requirements. Please try different specifications."
                )

            # Generate response with search results
            message = await orchestrator.message_generator.generate_search_results_message(
                current_state=conversation_state.current_state.value,
                search_results=search_results,
                master_parameters=conversation_state.master_parameters.model_dump(),
                language=conversation_state.language
            )

            # Convert ProductResult objects to dicts for ProcessorResult
            products_list = [p.model_dump() for p in search_results.products]

            return ProcessorResult.success_result(
                message=message,
                products=products_list,
                awaiting_selection=True
            )

        except Exception as e:
            self.logger.error(f"Error in power source processor: {e}", exc_info=True)
            return ProcessorResult.error_result(f"Error processing power source: {str(e)}")

    async def _handle_power_source_selection(
        self,
        conversation_state: Any,
        selection: int,
        orchestrator: Any
    ) -> ProcessorResult:
        """
        Handle explicit power source selection and trigger component applicability loading.

        Processes user's direct numeric selection for power source by creating a transition
        result that signals the orchestrator to:
        1. Add selected PowerSource to ResponseJSON
        2. Load component applicability configuration from component_applicability.json
        3. Set Y/N/O flags in ResponseJSON.applicability
        4. Advance to first applicable state (S2-S6)

        This method is the critical gateway between S1 and the rest of the configurator workflow.
        The applicability configuration loaded here determines the entire downstream state flow.

        Args:
            conversation_state: Current conversation state (unused in this method, but
                required for interface consistency)
            selection: Numeric selection index (1-based) from user input
                - Extracted by orchestrator._extract_selection_number()
                - Examples: "1" → 1, "option 2" → 2, "select #3" → 3
            orchestrator: StateOrchestrator instance (unused in this method, but
                required for interface consistency)

        Returns:
            ProcessorResult with transition_to_next=True:
                - success=True
                - message="Selected power source. Loading component applicability..."
                - transition_to_next=True (signals orchestrator to load applicability)
                - products=None
                - awaiting_selection=False

        Orchestrator Actions (After This Method Returns):
            1. **Extract Product**: Get selected PowerSource from last search results
            2. **Add to ResponseJSON**: Set ResponseJSON.PowerSource with product data
            3. **Load Applicability Config**: Read component_applicability.json
            4. **Find GIN Entry**: Look up selected PowerSource GIN (e.g., "0446200880")
            5. **Set Applicability Flags**: ResponseJSON.applicability = ComponentApplicability(
                   Feeder="Y",         # Show S2 if "Y", skip if "N"
                   Cooler="Y",         # Show S3 if "Y", skip if "N"
                   Interconnector="Y", # Show S4 if "Y", skip if "N"
                   Torch="Y",          # Show S5 if "Y", skip if "N"
                   Accessories="Y"     # Always "Y"
               )
            6. **Advance State**: Call conversation_state.get_next_state()
               - Skips states where applicability="N"
               - Proceeds to first applicable component

        Component Applicability Configuration:
            File: app/config/component_applicability.json
            Structure:
            {
              "power_sources": {
                "0446200880": {  // PowerSource GIN
                  "name": "Aristo 500ix",
                  "applicability": {
                    "Feeder": "Y",
                    "Cooler": "Y",
                    "Interconnector": "Y",
                    "Torch": "Y",
                    "Accessories": "Y"
                  }
                }
              }
            }

        Dynamic State Flow Examples:
            - All Y: S1 → S2 → S3 → S4 → S5 → S6 → FINALIZE
            - Feeder N: S1 → S3 → S4 → S6 → FINALIZE (skips S2, S5)
            - Only PowerSource: S1 → S6 → FINALIZE (skips all component states)

        Examples:
            >>> # Example 1: User selects power source option 1
            >>> processor = PowerSourceProcessor("power_source_selection", "power_source", "PowerSource")
            >>> result = await processor._handle_power_source_selection(
            ...     conversation_state=state,
            ...     selection=1,
            ...     orchestrator=orchestrator
            ... )
            >>> result.success
            True
            >>> result.transition_to_next
            True
            >>> result.message
            'Selected power source. Loading component applicability...'

            >>> # After orchestrator processes this result:
            >>> # - ResponseJSON.PowerSource = {"gin": "0446200880", "name": "Aristo 500ix", ...}
            >>> # - ResponseJSON.applicability = ComponentApplicability(Feeder="Y", Cooler="Y", ...)
            >>> # - conversation_state.current_state advances to S2 (feeder_selection)

        Note:
            - **Placeholder Implementation**: Current implementation is a placeholder
            - **Critical Orchestrator Role**: Actual applicability loading happens in orchestrator
            - **No Validation**: This method does NOT validate if selection index is valid
            - **Transition Signal**: transition_to_next=True triggers orchestrator actions
            - **State Dependency**: All downstream states depend on applicability loaded here
            - **Configuration-Driven**: Applicability is fully driven by JSON config file
            - **Missing GIN Fallback**: If PowerSource GIN not found in config, defaults to all "Y"
            - **Historical Context**: This critical design pattern was established Nov 14, 2024
              to enable dynamic state flow without hardcoding component dependencies

        Raises:
            No exceptions raised directly (placeholder implementation returns success)
        """
        # This would contain the logic for:
        # 1. Selecting the power source
        # 2. Loading applicability config
        # 3. Setting up response_json.applicability
        # Placeholder for now
        return ProcessorResult.transition_result(
            f"Selected power source. Loading component applicability..."
        )


class StateProcessorRegistry:
    """
    Registry for managing state processors

    Maps state names to processor instances dynamically based on configuration
    """

    def __init__(self):
        """Initialize empty registry"""
        self._processors: Dict[str, BaseStateProcessor] = {}
        self._default_processor: Optional[BaseStateProcessor] = None
        self.logger = logging.getLogger(f"{__name__}.StateProcessorRegistry")

    def register(self, state_name: str, processor: BaseStateProcessor):
        """
        Register a processor for a state

        Args:
            state_name: State identifier
            processor: Processor instance
        """
        self._processors[state_name] = processor
        self.logger.debug(f"Registered processor for state: {state_name} ({processor.__class__.__name__})")

    def get_processor(self, state_name: str) -> Optional[BaseStateProcessor]:
        """
        Get processor for a state

        Args:
            state_name: State identifier

        Returns:
            Processor instance or None if not found
        """
        processor = self._processors.get(state_name)

        if processor is None:
            self.logger.warning(f"No processor registered for state: {state_name}")
            return self._default_processor

        return processor

    def set_default_processor(self, processor: BaseStateProcessor):
        """Set default processor for unknown states"""
        self._default_processor = processor
        self.logger.info(f"Set default processor: {processor.__class__.__name__}")

    def has_processor(self, state_name: str) -> bool:
        """Check if a processor is registered for state"""
        return state_name in self._processors

    def get_all_states(self) -> List[str]:
        """Get list of all registered state names"""
        return list(self._processors.keys())

    def clear(self):
        """Clear all registered processors"""
        self._processors.clear()
        self._default_processor = None
        self.logger.debug("Cleared processor registry")

    @classmethod
    def create_from_config(cls, config: Optional[Dict[str, Any]] = None) -> "StateProcessorRegistry":
        """
        Create registry from configuration

        Args:
            config: Component types config (loads from file if not provided)

        Returns:
            Configured registry instance
        """
        from app.models.state_factory import StateFactory

        registry = cls()

        # Load config if not provided
        if config is None:
            config = StateFactory.load_state_config()

        # Create processors based on component types
        for comp_key, comp_data in config.get("component_types", {}).items():
            state_name = comp_data.get("state_name")
            selection_type = comp_data.get("selection_type", "single")
            api_key = comp_data.get("api_key")

            if not state_name or not api_key:
                continue

            # Create appropriate processor based on selection_type
            if comp_key == "power_source":
                # Special processor for S1
                processor = PowerSourceProcessor(state_name, comp_key, api_key)
            elif selection_type == "multi":
                processor = MultiSelectionProcessor(state_name, comp_key, api_key)
            elif selection_type == "single":
                processor = SingleSelectionProcessor(state_name, comp_key, api_key)
            elif selection_type == "custom":
                # Custom processor - would load from processor_class if specified
                processor_class = comp_data.get("processor_class")
                if processor_class:
                    # Dynamic import and instantiation would go here
                    logger.warning(f"Custom processor class not yet implemented: {processor_class}")
                    processor = SingleSelectionProcessor(state_name, comp_key, api_key)
                else:
                    processor = SingleSelectionProcessor(state_name, comp_key, api_key)
            else:
                # Unknown type, use single as default
                logger.warning(f"Unknown selection_type '{selection_type}' for {comp_key}, using single")
                processor = SingleSelectionProcessor(state_name, comp_key, api_key)

            registry.register(state_name, processor)

        # Set default processor
        registry.set_default_processor(SingleSelectionProcessor("default", "unknown", "Unknown"))

        logger.info(f"Created processor registry with {len(registry.get_all_states())} processors")

        return registry


# Singleton registry instance
_registry: Optional[StateProcessorRegistry] = None


def get_processor_registry() -> StateProcessorRegistry:
    """
    Get singleton processor registry

    Returns:
        StateProcessorRegistry instance

    Raises:
        RuntimeError: If registry not initialized
    """
    global _registry

    if _registry is None:
        raise RuntimeError(
            "StateProcessorRegistry not initialized. "
            "Call init_processor_registry() during application startup."
        )

    return _registry


def init_processor_registry(config: Optional[Dict[str, Any]] = None) -> StateProcessorRegistry:
    """
    Initialize processor registry from configuration

    Args:
        config: Component types config (optional)

    Returns:
        Initialized registry
    """
    global _registry

    if _registry is not None:
        logger.debug("Processor registry already initialized")
        return _registry

    _registry = StateProcessorRegistry.create_from_config(config)
    logger.info("✅ Processor registry initialized")

    return _registry


def clear_processor_registry():
    """Clear registry (useful for testing)"""
    global _registry
    _registry = None
    logger.debug("Cleared processor registry singleton")
