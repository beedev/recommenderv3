"""
Local NLP Chat Flow Tester
Test the complete conversation flow without starting the server
"""

# =====================================================================
# Disable SSL verification for local testing
# =====================================================================
import os
import ssl
os.environ['SSL_CERT_FILE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
ssl._create_default_https_context = ssl._create_unverified_context

# =====================================================================
# Imports and environment setup
# =====================================================================
import asyncio
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import all necessary components
from app.models.conversation import ConversationState, ConfiguratorState
from app.services.intent.parameter_extractor import ParameterExtractor
from app.services.neo4j.product_search import Neo4jProductSearch
from app.services.response.message_generator import MessageGenerator
from app.services.orchestrator.state_orchestrator import StateByStateOrchestrator


class ChatTester:
    """Interactive chat tester for local testing"""
    
    def __init__(self):
        """Initialize all services"""
        print("\nInitializing services...")

        # Load credentials
        openai_api_key = os.getenv("OPENAI_API_KEY")
        neo4j_uri = os.getenv("NEO4J_URI")
        neo4j_username = os.getenv("NEO4J_USERNAME")
        neo4j_password = os.getenv("NEO4J_PASSWORD")
        
        # Load component applicability config
        config_path = os.path.join(
            os.path.dirname(__file__),
            "app/config/powersource_state_specifications.json"
        )
        with open(config_path, 'r') as f:
            self.powersource_state_specifications_config = json.load(f)
        
        # Initialize services
        self.parameter_extractor = ParameterExtractor(openai_api_key)
        self.product_search = Neo4jProductSearch(neo4j_uri, neo4j_username, neo4j_password)
        self.message_generator = MessageGenerator()
        
        # Initialize orchestrator
        self.orchestrator = StateByStateOrchestrator(
            parameter_extractor=self.parameter_extractor,
            product_search=self.product_search,
            message_generator=self.message_generator,
            powersource_state_specifications_config=self.powersource_state_specifications_config
        )
        
        print("All services initialized!\n")
    
    async def close(self):
        """Close connections"""
        await self.product_search.close()
    
    def print_separator(self, title=""):
        """Print a section separator"""
        print("\n" + "=" * 70)
        if title:
            print(f"  {title}")
            print("=" * 70)
    
    def print_state(self, conversation_state: ConversationState):
        """Print current conversation state"""
        self.print_separator("CURRENT STATE")
        print(f"State: {conversation_state.current_state.value}")
        print(f"Language: {conversation_state.language}")
        print(f"Message Count: {len(conversation_state.conversation_history)}")
        
        # Show master parameters
        master_dict = conversation_state.master_parameters.dict()
        filled_params = {k: v for k, v in master_dict.items() if v and k != 'last_updated'}
        if filled_params:
            print("\nMaster Parameters:")
            for component, params in filled_params.items():
                if params:
                    print(f"  - {component}: {params}")
        
        # Show selected products
        rj = conversation_state.response_json
        if rj.PowerSource or rj.Feeder or rj.Cooler:
            print("\nSelected Products:")
            if rj.PowerSource:
                ps = rj.PowerSource
                print(f"  - PowerSource: {ps.name} (GIN: {ps.gin})")
            if rj.Feeder:
                f = rj.Feeder
                print(f"  - Feeder: {f.name} (GIN: {f.gin})")
            if rj.Cooler:
                c = rj.Cooler
                print(f"  - Cooler: {c.name} (GIN: {c.gin})")
            if rj.Interconnector:
                i = rj.Interconnector
                print(f"  - Interconnector: {i.name} (GIN: {i.gin})")
            if rj.Torch:
                t = rj.Torch
                print(f"  - Torch: {t.name} (GIN: {t.gin})")
            if rj.Accessories:
                print(f"  - Accessories: {len(rj.Accessories)} items")
    
    async def send_message(self, conversation_state: ConversationState, user_message: str):
        """Send message through orchestrator"""
        self.print_separator("USER MESSAGE")
        print(f"You: {user_message}\n")
        
        result = await self.orchestrator.process_message(conversation_state, user_message)
        
        # AI response
        self.print_separator("AI RESPONSE")
        print(f"Assistant: {result.get('message', '')}\n")
        
        # Products found
        if result.get('products'):
            print(f"Found {len(result['products'])} products:")
            for i, product in enumerate(result['products'][:5], 1):
                print(f"  {i}. {product['name']} (GIN: {product['gin']})")
                desc = product.get('description', '')
                if desc:
                    short_desc = desc[:80] + "..." if len(desc) > 80 else desc
                    print(f"     {short_desc}")
            print()
        
        return result
    
    async def run_scenario(self, scenario_name: str, messages: list):
        """Run a predefined test scenario"""
        self.print_separator(f"SCENARIO: {scenario_name}")
        conversation_state = ConversationState(session_id=f"test-{scenario_name}")
        
        for msg in messages:
            result = await self.send_message(conversation_state, msg)
            self.print_state(conversation_state)
            await asyncio.sleep(0.5)
        
        return conversation_state
    
    async def interactive_mode(self):
        """Interactive CLI chat"""
        self.print_separator("INTERACTIVE CHAT MODE")
        print("Type your messages below. Commands:")
        print("  - 'state' : Show current conversation state")
        print("  - 'reset' : Start new conversation")
        print("  - 'quit'  : Exit tester\n")
        
        conversation_state = ConversationState(session_id="interactive-session")
        
        while True:
            try:
                user_input = input("\nYou: ").strip()
                if not user_input:
                    continue
                
                if user_input.lower() == 'quit':
                    print("\nGoodbye!")
                    break
                if user_input.lower() == 'state':
                    self.print_state(conversation_state)
                    continue
                if user_input.lower() == 'reset':
                    conversation_state = ConversationState(session_id="interactive-session")
                    print("\nConversation reset!")
                    continue
                
                await self.send_message(conversation_state, user_input)
            
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")
                import traceback
                traceback.print_exc()


async def main():
    """Entry point"""
    print("\n" + "=" * 70)
    print("  RECOMMENDER V2 - LOCAL NLP CHAT FLOW TESTER")
    print("=" * 70)
    
    tester = ChatTester()
    
    try:
        print("\nChoose test mode:")
        print("  1. Quick Test - Simple power source query")
        print("  2. Full Flow Test - Complete S1→S7 flow")
        print("  3. Multi-language Test")
        print("  4. Interactive Mode")
        print("  5. Run All Scenarios\n")
        
        choice = input("Enter choice (1-5): ").strip()
        
        if choice == "1":
            await tester.run_scenario("Quick Test", ["I need a 500A MIG welder"])
        
        elif choice == "2":
            await tester.run_scenario(
                "Full Flow",
                [
                    "I need a 500A MIG welder for aluminum",
                    "I want the Aristo 500ix",
                    "I need a water-cooled feeder",
                    "Add RobustFeed U6",
                    "I need a cooler",
                    "Add Cool 2",
                    "skip", "skip", "skip", "finalize"
                ]
            )
        
        elif choice == "3":
            conversation_state = ConversationState(session_id="spanish-test", language="es")
            await tester.send_message(conversation_state, "Necesito un soldador MIG de 500A")
            tester.print_state(conversation_state)
        
        elif choice == "4":
            await tester.interactive_mode()
        
        elif choice == "5":
            print("\nRunning all scenarios...\n")
            await tester.run_scenario("Basic Query", ["I need a 500A welder"])
            await tester.run_scenario("Specific Product", ["I want the Aristo 500ix", "yes"])
            await tester.run_scenario("Skip Flow", ["I need a welder", "Aristo 500ix", "skip", "skip", "skip", "skip"])
            print("\nAll scenarios completed!")
        
        else:
            print("Invalid choice")
    
    finally:
        await tester.close()
        print("\nTest complete!\n")


if __name__ == "__main__":
    asyncio.run(main())
