"""
Conversation State Models for Dynamic S1→SN Flow
Master Parameter JSON + Response JSON + Conversation State
Enhanced with Accessory Categories Support and Mandatory Components
"""

from typing import Dict, List, Optional, Any, Union, Literal
from pydantic import BaseModel, Field, create_model, validator
from datetime import datetime
from enum import Enum
import sys
import os
import logging

from app.config.schema_loader import get_component_list

logger = logging.getLogger(__name__)

# ============================================================================
# Component Configuration Constants
# ============================================================================

# Component sequence for state progression
COMPONENT_SEQUENCE = [
    "PowerSource",
    "Feeder",
    "Cooler",
    "Interconnect",
    "Torch",
    "PowerSource Accessories",
    "Feeder Accessories",
    "Feeder Conditional Accessories",
    "Remote",
    "Remote Accessories",
    "Remote Conditional Accessories",
    "Connectivity",
    "Feeder Wears",
    "Interconnect Accessories"
]

# Mandatory components (cannot be skipped)
MANDATORY_COMPONENTS = [
    "PowerSource",
    "Feeder",
    "Cooler",
    "Interconnect",
    "Torch"
]

# Models that do NOT require Feeder and Cooler
NO_FEEDER_COOLER_MODELS = [
    "Renegade ES300",
    "Renegade ES300i",
    "Renegade ES 300i (CE)"
]

# Models where Cooler is conditional (optional based on duty cycle)
OPTIONAL_COOLER_MODELS = [
    "Aristo 500ix",
    "Warrior 400i",
    "Warrior 500i"
]

# ============================================================================
# Dynamic State Enum Generation
# ============================================================================

ConfiguratorState = None  # Will be set by init_configurator_state()


def init_configurator_state():
    """
    Initialize ConfiguratorState enum from configuration
    Called during application startup

    Returns:
        The created ConfiguratorState enum
    """
    global ConfiguratorState

    if ConfiguratorState is not None:
        logger.debug("ConfiguratorState already initialized")
        return ConfiguratorState

    try:
        from .state_factory import StateFactory

        # Create enum from config
        ConfiguratorState = StateFactory.create_configurator_state_enum()

        logger.info(f"ConfiguratorState initialized with {len(list(ConfiguratorState))} states")

        return ConfiguratorState

    except Exception as e:
        logger.error(f"Failed to initialize ConfiguratorState: {e}")
        # Fallback to hardcoded enum for backward compatibility
        logger.warning("Falling back to hardcoded ConfiguratorState enum")

        class ConfiguratorStateFallback(str, Enum):
            """Fallback S1→SN State Machine States with Accessory Categories"""
            # Core Component States (MANDATORY)
            POWER_SOURCE_SELECTION = "power_source_selection"
            FEEDER_SELECTION = "feeder_selection"
            COOLER_SELECTION = "cooler_selection"
            INTERCONNECTOR_SELECTION = "interconnector_selection"
            TORCH_SELECTION = "torch_selection"
            
            # Accessory Category States (OPTIONAL)
            POWERSOURCE_ACCESSORIES_SELECTION = "powersource_accessories_selection"
            FEEDER_ACCESSORIES_SELECTION = "feeder_accessories_selection"
            FEEDER_CONDITIONAL_ACCESSORIES = "feeder_conditional_accessories"
            INTERCONNECTOR_ACCESSORIES_SELECTION = "interconnector_accessories_selection"
            REMOTE_SELECTION = "remote_selection"
            REMOTE_ACCESSORIES_SELECTION = "remote_accessories_selection"
            REMOTE_CONDITIONAL_ACCESSORIES = "remote_conditional_accessories"
            CONNECTIVITY_SELECTION = "connectivity_selection"
            FEEDER_WEARS_SELECTION = "feeder_wears_selection"
            
            # Legacy
            ACCESSORIES_SELECTION = "accessories_selection"
            
            # Finalization
            FINALIZE = "finalize"

        ConfiguratorState = ConfiguratorStateFallback
        return ConfiguratorState


def get_configurator_state():
    """
    Get ConfiguratorState enum (initializes if not done yet)

    Returns:
        ConfiguratorState enum

    Raises:
        RuntimeError: If initialization failed
    """
    if ConfiguratorState is None:
        return init_configurator_state()

    return ConfiguratorState


# Ensure ConfiguratorState is initialized for type annotations/defaults
ConfiguratorState = init_configurator_state()


class ComponentApplicability(BaseModel):
    """
    Component applicability flags for a power source

    Applicability Values:
    - "mandatory": Component is required and cannot be skipped
    - "conditional": Component is optional based on other selections (e.g., duty cycle)
    - "optional": Component is optional
    - "not_applicable": Component is not applicable for this power source
    - "integrated_cooler": PowerSource has built-in cooler (skip cooler selection)

    Default: Core components are MANDATORY, accessories are OPTIONAL

    Special Case - Integrated Cooler:
    When Cooler = "integrated_cooler", the chatbot will:
    - Skip cooler_selection state entirely
    - Add has_integrated_cooler: True to PowerSource data
    - Pass this flag to search_interconnector() and search_torch()
    - Ensure cooler compatibility checks are skipped in searches
    """
    # Core Components (MANDATORY by default)
    Feeder: str = "mandatory"
    Cooler: str = "mandatory"
    Interconnector: str = "mandatory"
    Torch: str = "mandatory"
    
    # Accessory Categories (OPTIONAL by default)
    PowerSourceAccessories: str = "optional"
    FeederAccessories: str = "optional"
    FeederConditionalAccessories: str = "optional"
    InterconnectorAccessories: str = "optional"
    Remotes: str = "optional"
    RemoteAccessories: str = "optional"
    RemoteConditionalAccessories: str = "optional"
    Connectivity: str = "optional"
    FeederWears: str = "optional"
    
    # Legacy
    Accessories: str = "optional"


def _create_master_parameter_json_model():
    """
    Dynamically create MasterParameterJSON model from schema
    Loads component list from master_parameter_schema.json at runtime
    """
    # Get component list from schema
    component_list = get_component_list()

    # Build field definitions dynamically
    field_definitions = {}

    for component_name in component_list:
        # Each component is a Dict[str, Any] to allow strings, lists, numbers, etc.
        # LLM can extract various types (strings, lists, numbers) and we want to be flexible
        field_definitions[component_name] = (
            Dict[str, Any],
            Field(default_factory=dict)
        )

    # Add metadata field
    field_definitions['last_updated'] = (datetime, Field(default_factory=datetime.utcnow))

    # Create dynamic model
    DynamicMasterParameterJSON = create_model(
        'MasterParameterJSON',
        __base__=BaseModel,
        __doc__="""
        Master Parameter JSON - Component-Based User Requirements
        Organizes requirements by component for accurate product search
        Each component has its own dict of features
        Components loaded dynamically from master_parameter_schema.json
        """,
        **field_definitions
    )

    # Add example configuration
    DynamicMasterParameterJSON.Config = type('Config', (), {
        'json_schema_extra': {
            "example": {
                "power_source": {
                    "product_name": "Aristo 500ix",
                    "process": "TIG (GTAW)",
                    "current_output": "500 A",
                    "material": "Aluminum"
                },
                "feeder": {
                    "product_name": "RobustFeed",
                    "cooling_type": "Water-cooled"
                },
                "cooler": {
                    "product_name": "Cool2"
                },
                "interconnector": {
                    "cable_length": "5 m"
                },
                "torch": {},
                "accessories": {}
            }
        }
    })

    return DynamicMasterParameterJSON

# Create the model at module load time (cached by schema_loader)
MasterParameterJSON = _create_master_parameter_json_model()


def _get_default_current_state():
    """
    Get default conversation state (first defined configurator state)
    """
    state_enum = get_configurator_state()
    try:
        return next(iter(state_enum))
    except StopIteration as exc:
        raise ValueError("ConfiguratorState enum has no members") from exc


class SelectedProduct(BaseModel):
    """Selected product in Response JSON"""
    gin: str
    name: str
    category: str
    description: Optional[str] = None
    specifications: Dict[str, Any] = Field(default_factory=dict)

    # ✨ INTEGRATED COOLER: Flag for PowerSources with built-in coolers
    has_integrated_cooler: Optional[bool] = False


class ResponseJSON(BaseModel):
    """
    Response JSON - Selected Products "Cart"
    Tracks user's selected products across S1→SN
    Enhanced with Accessory Categories
    """

    # Core Components (single selection - MANDATORY by default)
    # Now supports "skipped" literal to track explicitly skipped components
    PowerSource: Union[SelectedProduct, Literal["skipped"], None] = None
    Feeder: Union[SelectedProduct, Literal["skipped"], None] = None
    Cooler: Union[SelectedProduct, Literal["skipped"], None] = None
    Interconnector: Union[SelectedProduct, Literal["skipped"], None] = None
    Torch: Union[SelectedProduct, Literal["skipped"], None] = None

    # Accessory Categories (multiple selection - OPTIONAL)
    # Now supports "skipped" literal to track explicitly skipped categories
    PowerSourceAccessories: Union[List[SelectedProduct], Literal["skipped"]] = Field(default_factory=list)
    FeederAccessories: Union[List[SelectedProduct], Literal["skipped"]] = Field(default_factory=list)
    FeederConditionalAccessories: Union[List[SelectedProduct], Literal["skipped"]] = Field(default_factory=list)
    InterconnectorAccessories: Union[List[SelectedProduct], Literal["skipped"]] = Field(default_factory=list)
    Remotes: Union[List[SelectedProduct], Literal["skipped"]] = Field(default_factory=list)
    RemoteAccessories: Union[List[SelectedProduct], Literal["skipped"]] = Field(default_factory=list)
    RemoteConditionalAccessories: Union[List[SelectedProduct], Literal["skipped"]] = Field(default_factory=list)
    Connectivity: Union[List[SelectedProduct], Literal["skipped"]] = Field(default_factory=list)
    FeederWears: Union[List[SelectedProduct], Literal["skipped"]] = Field(default_factory=list)

    # Legacy (for backward compatibility)
    Accessories: Union[List[SelectedProduct], Literal["skipped"]] = Field(default_factory=list)

    # Component Applicability (set after S1 PowerSource selection)
    applicability: Optional[ComponentApplicability] = None

    # Component Status Tracking (selected/skipped)
    # Tracks status for all component categories
    # - "selected": Component has been chosen by user
    # - "skipped": Component not selected (user skipped, not applicable, or not yet reached)
    component_statuses: Dict[str, str] = Field(default_factory=lambda: {
        "PowerSource": "skipped",
        "Feeder": "skipped",
        "Cooler": "skipped",
        "Interconnector": "skipped",
        "Torch": "skipped",
        "PowerSourceAccessories": "skipped",
        "FeederAccessories": "skipped",
        "FeederConditionalAccessories": "skipped",
        "InterconnectorAccessories": "skipped",
        "Remotes": "skipped",
        "RemoteAccessories": "skipped",
        "RemoteConditionalAccessories": "skipped",
        "Connectivity": "skipped",
        "FeederWears": "skipped",
        "Accessories": "skipped"
    })

    def get_component_status(self, component_key: str) -> str:
        """
        Get status for a component

        Args:
            component_key: Component name (e.g., "PowerSource", "Feeder")

        Returns:
            Status string: "selected" or "skipped"
        """
        return self.component_statuses.get(component_key, "skipped")

    def set_component_status(self, component_key: str, status: str):
        """
        Set status for a component

        Args:
            component_key: Component name (e.g., "PowerSource", "Feeder")
            status: Status to set ("selected" or "skipped")
        """
        if status not in ["selected", "skipped"]:
            logger.warning(f"Invalid component status '{status}', using 'skipped'")
            status = "skipped"

        self.component_statuses[component_key] = status

    def mark_component_selected(self, component_key: str):
        """Mark a component as selected"""
        self.set_component_status(component_key, "selected")

    def mark_component_skipped(self, component_key: str):
        """Mark a component as skipped"""
        self.set_component_status(component_key, "skipped")

    def get_all_component_statuses(self) -> Dict[str, str]:
        """Get all component statuses as a dict"""
        return self.component_statuses.copy()

    class Config:
        json_schema_extra = {
            "example": {
                "PowerSource": {
                    "gin": "0446200880",
                    "name": "Aristo 500ix CE",
                    "category": "PowerSource"
                },
                "Feeder": {
                    "gin": "0123456789",
                    "name": "RobustFeed U6",
                    "category": "Feeder"
                },
                "Cooler": {
                    "gin": "0987654321",
                    "name": "Cool50-2",
                    "category": "Cooler"
                },
                "PowerSourceAccessories": [
                    {
                        "gin": "0111111111",
                        "name": "Power Cable Extension",
                        "category": "Powersource Accessories"
                    }
                ],
                "Remotes": [
                    {
                        "gin": "0222222222",
                        "name": "Digital Remote Control",
                        "category": "Remotes"
                    }
                ],
                "applicability": {
                    "Feeder": "mandatory",
                    "Cooler": "conditional",
                    "Interconnector": "mandatory",
                    "Torch": "mandatory",
                    "PowerSourceAccessories": "optional",
                    "FeederAccessories": "optional",
                    "Remotes": "optional"
                },
                "component_statuses": {
                    "PowerSource": "selected",
                    "Feeder": "selected",
                    "Cooler": "selected",
                    "Interconnector": "skipped",
                    "Torch": "skipped",
                    "PowerSourceAccessories": "skipped",
                    "FeederAccessories": "skipped",
                    "FeederConditionalAccessories": "skipped",
                    "InterconnectorAccessories": "skipped",
                    "Remotes": "selected",
                    "RemoteAccessories": "skipped",
                    "RemoteConditionalAccessories": "skipped",
                    "Connectivity": "skipped",
                    "FeederWears": "skipped",
                    "Accessories": "skipped"
                }
            }
        }


SESSION_SCHEMA_VERSION = 1


class ConversationState(BaseModel):
    """
    Complete Conversation State
    Combines Master Parameters, Response JSON, and State Machine
    Enhanced with Accessory Categories Support and Mandatory Component Rules
    """

    session_id: str
    current_state: ConfiguratorState = Field(default_factory=_get_default_current_state)

    # Core JSON structures
    master_parameters: MasterParameterJSON = Field(default_factory=MasterParameterJSON)
    response_json: ResponseJSON = Field(default_factory=ResponseJSON)

    # Ownership & Participants
    owner_user_id: Optional[str] = None
    customer_id: Optional[str] = None
    participants: List[str] = Field(default_factory=list)

    # Conversation History (stores messages with optional products)
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)

    # User Language Preference (ISO 639-1 language code)
    # Supported: en, es, fr, de, pt, it, sv
    language: str = "en"

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    schema_version: int = Field(default=SESSION_SCHEMA_VERSION)

    # Pagination State (tracks offset/total for each component state)
    # Structure: {"state_name": {"offset": 3, "total": 15, "shown": 7}}
    pagination_states: Dict[str, Dict[str, int]] = Field(default_factory=dict)

    @validator("current_state", pre=True, always=True)
    def _coerce_current_state(cls, value):
        """Ensure current_state is stored as ConfiguratorState enum"""
        state_enum = get_configurator_state()

        if value is None or value == "":
            return _get_default_current_state()

        if isinstance(value, state_enum):
            return value

        if isinstance(value, Enum):
            try:
                return state_enum(value.value)
            except Exception:
                pass

        if isinstance(value, str):
            normalized = value
            if "." in value:
                prefix, suffix = value.split(".", 1)
                if prefix.lower() == "configuratorstate" and suffix:
                    normalized = suffix
            try:
                return state_enum(normalized)
            except ValueError:
                try:
                    return state_enum[normalized.upper()]
                except KeyError as exc:
                    raise ValueError(f"Invalid configurator state: {value}") from exc

        try:
            return state_enum(value)
        except Exception as exc:
            raise ValueError(f"Invalid configurator state: {value}") from exc

    @validator("participants", pre=True, always=True)
    def _normalize_participants(cls, value):
        """Ensure participants is a list of unique non-empty strings."""
        if value is None or value == "":
            return []

        if isinstance(value, str):
            value = [value]

        normalized = []
        for participant in value:
            if not participant:
                continue
            participant_id = str(participant)
            if participant_id not in normalized:
                normalized.append(participant_id)

        return normalized

    def redis_key(self) -> str:
        """Return canonical Redis key for this session."""
        return f"configurator:sessions:{self.session_id}"

    def add_message(self, role: str, content: str, products: Optional[List[Dict[str, Any]]] = None):
        """Add message to conversation history with optional products"""
        message_entry = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }
        if products is not None:
            message_entry["products"] = products

        self.conversation_history.append(message_entry)
        self.last_updated = datetime.utcnow()

    def update_master_parameters(self, updates: Dict[str, Any]):
        """
        Update master parameters with dict merging
        For component dicts: preserves existing values and adds/updates new ones (latest value wins)
        For metadata fields: replaces with new value
        """
        for key, value in updates.items():
            # Skip metadata field - it's auto-updated
            if key == "last_updated":
                continue

            if hasattr(self.master_parameters, key):
                # Check if this is a component dict (Dict[str, Optional[str]])
                if isinstance(value, dict):
                    # Get existing component dict
                    existing_dict = getattr(self.master_parameters, key, {})

                    # Handle None case
                    if existing_dict is None:
                        existing_dict = {}

                    # Merge: preserve existing + add/update new (latest value wins)
                    merged_dict = {**existing_dict, **value}

                    # Set the merged dict
                    setattr(self.master_parameters, key, merged_dict)

                elif value is not None:
                    # Non-dict field, just set it
                    setattr(self.master_parameters, key, value)

        # Update timestamps
        self.master_parameters.last_updated = datetime.utcnow()
        self.last_updated = datetime.utcnow()

    def select_component(self, component_type: str, product: SelectedProduct):
        """
        Select a component in Response JSON
        Handles both single-selection components and multi-selection accessory categories
        Automatically marks component as "selected" in component_statuses
        """
        # Core components (single selection)
        if component_type in ["PowerSource", "Feeder", "Cooler", "Interconnector", "Torch"]:
            setattr(self.response_json, component_type, product)
            # Mark as selected
            self.response_json.mark_component_selected(component_type)

        # Accessory categories (multiple selection)
        elif component_type == "PowerSourceAccessories":
            self.response_json.PowerSourceAccessories.append(product)
            self.response_json.mark_component_selected(component_type)
        elif component_type == "FeederAccessories":
            self.response_json.FeederAccessories.append(product)
            self.response_json.mark_component_selected(component_type)
        elif component_type == "FeederConditionalAccessories":
            self.response_json.FeederConditionalAccessories.append(product)
            self.response_json.mark_component_selected(component_type)
        elif component_type == "InterconnectorAccessories":
            self.response_json.InterconnectorAccessories.append(product)
            self.response_json.mark_component_selected(component_type)
        elif component_type == "Remotes":
            self.response_json.Remotes.append(product)
            self.response_json.mark_component_selected(component_type)
        elif component_type == "RemoteAccessories":
            self.response_json.RemoteAccessories.append(product)
            self.response_json.mark_component_selected(component_type)
        elif component_type == "RemoteConditionalAccessories":
            self.response_json.RemoteConditionalAccessories.append(product)
            self.response_json.mark_component_selected(component_type)
        elif component_type == "Connectivity":
            self.response_json.Connectivity.append(product)
            self.response_json.mark_component_selected(component_type)
        elif component_type == "FeederWears":
            self.response_json.FeederWears.append(product)
            self.response_json.mark_component_selected(component_type)

        # Legacy fallback
        elif component_type == "Accessories":
            self.response_json.Accessories.append(product)
            self.response_json.mark_component_selected(component_type)

        else:
            logger.warning(f"Unknown component type: {component_type}")

        self.last_updated = datetime.utcnow()

    def set_applicability(self, applicability: ComponentApplicability):
        """Set component applicability after PowerSource selection"""
        self.response_json.applicability = applicability

    def get_next_state(self) -> Optional[ConfiguratorState]:
        """
        Determine next state based on applicability and current state
        
        Rules:
        - Mandatory components cannot be skipped
        - Conditional components can be skipped based on user choice
        - Optional components can be skipped
        - Not applicable components are automatically skipped

        Returns:
            Next state enum or None
        """
        state_enum = get_configurator_state()
        finalize_state = None

        try:
            from .state_factory import StateFactory

            # Load state sequence dynamically from config
            state_sequence = StateFactory.get_state_sequence()

            # Get current state index
            current_state_value = self.current_state.value if isinstance(self.current_state, Enum) else str(self.current_state)

            try:
                current_idx = state_sequence.index(current_state_value)
            except ValueError:
                # Invalid current state, return first state
                return state_enum(state_sequence[0]) if state_sequence else None

            # Get finalize state
            finalize_state = StateFactory.get_finalize_state()

            # Find next applicable state
            applicability = self.response_json.applicability

            for next_idx in range(current_idx + 1, len(state_sequence)):
                next_state = state_sequence[next_idx]

                # Finalize is always applicable
                if next_state == finalize_state:
                    return state_enum(next_state)

                # Check if component is applicable
                if applicability:
                    # Build component map dynamically from config
                    try:
                        state_metadata = StateFactory.get_state_metadata(next_state)
                        api_key = state_metadata.get("api_key")

                        if api_key:
                            # Get applicability value
                            applicability_value = getattr(applicability, api_key, "mandatory")
                            
                            # Check applicability rules
                            if applicability_value == "not_applicable":
                                # Auto-skip not applicable components
                                logger.info(f"Auto-skipping state {next_state} (not_applicable)")
                                continue
                            elif applicability_value in ["mandatory", "conditional", "optional"]:
                                # Component is applicable - proceed to this state
                                return state_enum(next_state)
                            else:
                                # Unknown applicability value - assume applicable
                                logger.warning(f"Unknown applicability value '{applicability_value}' for {api_key}, assuming applicable")
                                return state_enum(next_state)
                    except KeyError:
                        # State metadata not found, assume applicable
                        logger.warning(f"No metadata found for state: {next_state}, assuming applicable")
                        return state_enum(next_state)
                else:
                    # No applicability set yet (before S1 completion)
                    return state_enum(next_state)

            # Reached end of states
            return state_enum(finalize_state)

        except Exception as e:
            logger.error(f"Error in get_next_state: {e}")
            # Fallback to finalize
            try:
                if finalize_state:
                    return state_enum(finalize_state)
                return state_enum("finalize")
            except Exception:
                try:
                    return _get_default_current_state()
                except Exception:
                    return None

    def can_finalize(self) -> bool:
        """
        Check if configuration can be finalized
        
        Rules:
        - PowerSource is always required
        - For standard models: Feeder, Cooler, Interconnect, Torch are required
        - For Renegade models: Only PowerSource is required
        """
        # PowerSource is always mandatory
        if not self.response_json.PowerSource:
            return False
        
        # Check if this is a Renegade model (no Feeder/Cooler required)
        power_source_name = self.response_json.PowerSource.name
        is_renegade = any(model in power_source_name for model in NO_FEEDER_COOLER_MODELS)
        
        if is_renegade:
            # Renegade models only require PowerSource
            return True
        
        # For standard models, check mandatory components based on applicability
        applicability = self.response_json.applicability
        
        if not applicability:
            # No applicability set - require PowerSource only for now
            return True
        
        # Check mandatory components
        mandatory_checks = {
            "Feeder": (self.response_json.Feeder, applicability.Feeder),
            "Cooler": (self.response_json.Cooler, applicability.Cooler),
            "Interconnector": (self.response_json.Interconnector, applicability.Interconnector),
            "Torch": (self.response_json.Torch, applicability.Torch),
        }
        
        for component_name, (component_value, applicability_value) in mandatory_checks.items():
            if applicability_value == "mandatory" and not component_value:
                logger.info(f"Cannot finalize: {component_name} is mandatory but not selected")
                return False
        
        return True

    class Config:
        validate_assignment = True
        json_schema_extra = {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "current_state": "feeder_selection",
                "master_parameters": {
                    "power_source": {
                        "product_name": "Aristo 500ix",
                        "process": "MIG (GMAW)",
                        "current_output": "500 A"
                    },
                    "feeder": {},
                    "cooler": {},
                    "interconnector": {},
                    "torch": {},
                    "accessories": {}
                },
                "response_json": {
                    "PowerSource": {
                        "gin": "0446200880",
                        "name": "Aristo 500ix CE",
                        "category": "PowerSource"
                    },
                    "PowerSourceAccessories": [
                        {
                            "gin": "0111111111",
                            "name": "Power Cable 5m",
                            "category": "Powersource Accessories"
                        }
                    ],
                    "Remotes": [
                        {
                            "gin": "0222222222",
                            "name": "Digital Remote",
                            "category": "Remotes"
                        }
                    ],
                    "applicability": {
                        "Feeder": "mandatory",
                        "Cooler": "conditional",
                        "Interconnector": "mandatory",
                        "Torch": "mandatory"
                    }
                }
            }
        }