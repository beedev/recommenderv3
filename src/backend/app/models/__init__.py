"""Models package - Conversation state and JSON structures"""

from .conversation import (
    ConfiguratorState,
    ComponentApplicability,
    MasterParameterJSON,
    ResponseJSON,
    SelectedProduct,
    ConversationState
)

from .product_search import (
    ProductResult,
    SearchResults
)

__all__ = [
    "ConfiguratorState",
    "ComponentApplicability",
    "MasterParameterJSON",
    "ResponseJSON",
    "SelectedProduct",
    "ConversationState",
    "ProductResult",
    "SearchResults"
]
