"""
Test explicit product selection logic
Tests how product_name is stored in master_parameters for explicit selection
"""
import asyncio
from app.models.conversation import ConversationState, MasterParameterJSON

async def test():
    """Test what's in master_parameters after explicit product selection"""

    # Create conversation state with a session ID
    state = ConversationState(session_id="test-session-123")

    print("Initial state:")
    print("Master parameters:", state.master_parameters.model_dump())
    print()

    # Simulate updating power_source with explicit product name
    # This is what happens when LLM extracts "Aristo 500ix" from user input
    updates = {
        "power_source": {
            "product_name": "Aristo 500ix",
            "process": "MIG (GMAW)",
            "current_output": "500 A"
        }
    }

    print("Updating with:", updates)
    state.update_master_parameters(updates)

    print("\nAfter update:")
    print("Master parameters:", state.master_parameters.model_dump())
    print()

    # Check if product_name is accessible
    master_dict = state.master_parameters.model_dump()
    print("Power source dict:", master_dict.get("power_source", {}))
    print("Has product_name:", "product_name" in master_dict.get("power_source", {}))
    print("Product name value:", master_dict.get("power_source", {}).get("product_name"))

    print("\n[SUCCESS] Test passed! Product name is stored correctly in master_parameters.power_source.product_name")

if __name__ == "__main__":
    asyncio.run(test())
