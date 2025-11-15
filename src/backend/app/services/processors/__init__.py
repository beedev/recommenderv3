"""
State Processors Module

Modular state processors for S1→SN configurator flow.

Each state in the configurator has a dedicated processor that handles:
- Product search via SearchOrchestrator
- State transition logic (get_next_state)
- Multi-select behavior (for accessories only)
- Proactive preview generation
- Zero-results handling

Architecture:
    StateProcessor (base.py)
        ├── PowerSourceStateProcessor (power_source.py)
        ├── FeederStateProcessor (feeder.py)
        ├── CoolerStateProcessor (cooler.py)
        ├── InterconnectorStateProcessor (interconnector.py)
        ├── TorchStateProcessor (torch.py)
        └── AccessoryStateProcessor (accessory.py)
            └── 9 accessory states via factory

Registry:
    StateProcessorRegistry (registry.py)
        - Central registry for all 14 processors
        - Dependency injection (SearchOrchestrator)
        - Configuration loading (state_config.json)
        - Processor retrieval by state name

Usage:
    # Initialize registry
    from app.services.processors import init_state_processor_registry, get_state_processor_registry

    registry = init_state_processor_registry(
        state_config_path="app/config/state_config.json",
        search_orchestrator=search_orchestrator_instance
    )

    # Get processor for current state
    processor = registry.get_processor("power_source_selection")

    # Execute search
    results = await processor.search_products(
        user_message="I need a 500A MIG welder",
        master_parameters={...},
        selected_components={},
        limit=10,
        offset=0
    )

    # Get next state
    next_state = processor.get_next_state(
        conversation_state=state,
        selection_made=True
    )
"""

from .base import StateProcessor
from .power_source import PowerSourceStateProcessor
from .feeder import FeederStateProcessor
from .cooler import CoolerStateProcessor
from .interconnector import InterconnectorStateProcessor
from .torch import TorchStateProcessor
from .accessory import AccessoryStateProcessor, create_accessory_processors
from .registry import (
    StateProcessorRegistry,
    init_state_processor_registry,
    get_state_processor_registry
)

__all__ = [
    # Base class
    "StateProcessor",

    # Primary component processors
    "PowerSourceStateProcessor",
    "FeederStateProcessor",
    "CoolerStateProcessor",
    "InterconnectorStateProcessor",
    "TorchStateProcessor",

    # Accessory processor
    "AccessoryStateProcessor",
    "create_accessory_processors",

    # Registry
    "StateProcessorRegistry",
    "init_state_processor_registry",
    "get_state_processor_registry",
]
