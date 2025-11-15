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
        """Process single selection state"""
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
        """Handle explicit product selection"""
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
        """Process multi selection state"""
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
        """Handle accessory selection (adds to list)"""
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
        """Process power source selection"""
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
        """Handle power source selection and load applicability"""
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
