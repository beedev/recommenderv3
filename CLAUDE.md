# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Table of Contents

- [Documentation Quick Links](#documentation-quick-links)
- [Project Overview](#project-overview)
- [Development Commands](#development-commands)
  - [Running the Application](#running-the-application)
  - [Testing](#testing)
  - [Database Operations](#database-operations)
  - [Production Deployment (Linux)](#production-deployment-linux)
- [Architecture Overview](#architecture-overview)
  - [Core State Flow (S1→SN)](#core-state-flow-s1sn)
  - [Data Flow Architecture](#data-flow-architecture)
  - [Multi-Agent Orchestration](#multi-agent-orchestration)
  - [Database Architecture](#database-architecture)
  - [Configuration Files](#configuration-files)
- [Project Structure](#project-structure)
- [API Endpoints](#api-endpoints)
- [Frontend Architecture](#frontend-architecture)
- [Important Development Notes](#important-development-notes)
- [Running Without Redis](#running-without-redis)
- [Environment Variables Reference](#environment-variables-reference)
- [Troubleshooting](#troubleshooting)
- [Version Information](#version-information)

---

## Project Overview

**ESAB Welding Equipment Configurator (Recommender_v2)** - A production-ready AI-powered welding equipment configurator using a configuration-driven state-machine architecture with multi-agent orchestration. The system guides users through a sequential configurable state flow (S1→SN) to build compatible welding equipment packages.

**Key Architecture**: 3-Agent System coordinated by State Machine
- **Agent 1**: Parameter Extractor (LLM-based intent understanding)
- **Agent 2**: Product Search (Neo4j graph database)
- **Agent 3**: Response Generator (Template + LLM multilingual output)

**Port**: 8000 (production-ready backend API)

---

## Documentation Quick Links

### 📚 Core Documentation
- **[Testing Guide](docs/testing-guide.md)** - Comprehensive testing best practices, patterns, and examples
- **[Testing Organization Review](docs/testing-organization-review.md)** - Test structure migration and reorganization details
- **[Deployment Guide](docs/deployment/README.md)** - Complete deployment documentation for all environments
- **[Operations Runbook](docs/operations/runbook.md)** - Day-to-day operations, monitoring, and maintenance

### 🏗️ Architecture Documentation
- **[Corrected State Flow Architecture](docs/CORRECTED_STATE_FLOW_ARCHITECTURE.md)** - S1→SN dynamic state machine detailed flow
- **[Master Parameter JSON Architecture](docs/MASTER_PARAMETER_JSON_ARCHITECTURE.md)** - Data models and schema
- **[Multilingual Flow](docs/MULTILINGUAL_FLOW.md)** - Translation and internationalization architecture
- **[LangGraph Integration](docs/LANGGRAPH_INTEGRATION.md)** - Optional agent orchestration with LangGraph
- **[LLM Entity Extraction Architecture](docs/LLM_ENTITY_EXTRACTION_ARCHITECTURE.md)** - Parameter extraction design

### 🧪 Test Documentation
- **[Test Suite README](src/backend/tests/README.md)** - How to run tests, test structure, and fixtures
- **[Manual Tests](src/backend/tests/manual/README.md)** - Manual test scripts and debugging tools
- **[Test Results](src/backend/test-results/README.md)** - Test artifacts and reports organization

### 🚀 Deployment Documentation
- **[Docker Deployment](docs/deployment/docker.md)** - Containerized deployment guide
- **[Linux Systemd Deployment](docs/deployment/linux-systemd.md)** - Production Linux deployment
- **[Local Deployment](deployment/local/README.md)** - Manual local development setup
- **[Database Setup](docs/deployment/database-setup.md)** - Neo4j, PostgreSQL, and Redis configuration
- **[Redis Configuration](deployment/Redis-Config.md)** - Production Redis + RedisInsight setup and security hardening
- **[Quick Start](docs/deployment/quick-start.md)** - Get running in 5 minutes
- **[Troubleshooting](docs/deployment/troubleshooting.md)** - Common deployment issues and solutions

### ⚙️ Configuration Documentation
- **[Environment Variables](deployment/env/README.md)** - .env configuration templates and examples
- **[Frontend Configuration](docs/deployment/frontend-config.md)** - Frontend deployment and configuration

---

## Development Commands

### Running the Application

```bash
# Navigate to backend directory
cd src/backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
# Create .env file at: src/backend/.env
# Copy from deployment/env/.env.example and configure:
# - OPENAI_API_KEY
# - NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
# - REDIS_URL or REDIS_HOST/REDIS_PORT
# - POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
# - LANGSMITH_API_KEY (optional)
# See deployment/env/README.md for complete configuration guide

# Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Or run directly
python -m app.main
```

### Testing

#### Automated Tests

```bash
cd src/backend

# Run all automated tests
pytest

# Run specific test suites
pytest tests/unit -v              # Unit tests only (fast, < 100ms each)
pytest tests/integration -v       # Integration tests (< 5s each)
pytest tests/e2e -v               # End-to-end tests (> 5s each)

# Run with coverage
pytest --cov=app --cov-report=html
# View coverage: open test-results/coverage/html/index.html

# Run by marker
pytest -m unit                    # Only unit tests
pytest -m integration             # Only integration tests
pytest -m "not slow"              # Skip slow tests
pytest -m requires_neo4j          # Only tests requiring Neo4j

# Run with verbose output and logging
pytest -v --log-cli-level=DEBUG

# Generate reports for CI/CD
pytest --junit-xml=test-results/reports/junit/results.xml \
       --cov-report=xml:test-results/coverage/coverage.xml
```

**Test Structure:**
```
tests/
├── unit/           # Fast isolated tests with mocked dependencies (< 100ms)
├── integration/    # Multi-component tests with real services (< 5s)
├── e2e/           # Complete workflow tests (> 5s)
└── manual/        # Manual test scripts (excluded from pytest)
```

See [Testing Guide](docs/testing-guide.md) for detailed testing practices.

#### Manual Testing

```bash
# Manual testing via Swagger UI
# Navigate to: http://localhost:8000/docs

# Health check
curl http://localhost:8000/health

# Test configurator endpoint
curl -X POST http://localhost:8000/api/v1/configurator/message \
  -H "Content-Type: application/json" \
  -d '{"message": "I need a 500A MIG welder", "language": "en"}'

# Run manual test scripts (not run by pytest)
cd src/backend
python tests/manual/test_local_neo4j.py        # Test Neo4j connection
python tests/manual/test_explicit_selection.py # Test selection flow

# See manual test documentation
cat tests/manual/README.md

# Interactive Chat Flow Tester (for offline testing without server)
python test_chat_flow.py
```

#### Local Chat Flow Tester (test_chat_flow.py)

**Interactive testing tool** for offline conversation flow testing without starting the server.

**Location**: `src/backend/test_chat_flow.py`

**Usage**:
```bash
cd src/backend
python test_chat_flow.py

# Choose from 5 test modes: Quick Test, Full Flow, Multi-language, Interactive, or Run All
```

**Key Features**:
- ✅ No server restart needed
- ✅ State visualization
- ✅ Multi-language support (Spanish, French)
- ✅ Compound request testing
- ✅ Offline development

### Viewing HTML Test Interfaces

The application includes interactive HTML test interfaces for manual testing:

```bash
# Start the server
cd src/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Access the HTML interfaces in your browser:
# Main configurator interface:
http://localhost:8000/static/index.html

# Configurator-specific testing:
http://localhost:8000/static/test_configurator.html

# Parameter extraction testing:
http://localhost:8000/static/test_extraction.html
```

**How it works:**
- Static files are mounted from `src/frontend/` directory via FastAPI's `StaticFiles`
- Configuration is in `src/backend/app/main.py` (line 239)
- All HTML files in `src/frontend/` are accessible at `/static/<filename>`
- Frontend uses modular JavaScript with ESAB namespace (common.js, translations.js)

### Database Operations

```bash
# Start required services
# - Neo4j (Desktop or Docker on ports 7474/7687)
# - PostgreSQL (port 5432)
# - Redis (port 6379)

# Check Neo4j connection
cypher-shell -u neo4j -p password "RETURN 1;"

# Check PostgreSQL connection
psql -U postgres -d pconfig -c "SELECT 1;"

# Check Redis connection
redis-cli ping
```

### Production Deployment (Linux)

```bash
# Automated deployment (Linux)
cd deployment
chmod +x deploy.sh
sudo ./deploy.sh install

# Start/stop services (systemd)
sudo systemctl start esab-recommender.target   # Start both backend and frontend
sudo systemctl stop esab-recommender.target    # Stop both
sudo systemctl restart esab-recommender.target # Restart both
sudo systemctl status esab-recommender.target  # Check status

# View logs
sudo journalctl -u esab-recommender.service -f
sudo journalctl -u esab-recommender-frontend.service -f

# Update deployment
sudo ./deployment/deploy.sh update
```

**Log Files Location:**
- Main log: `/home/azureuser/esab_recommender-bh/logs/esab-recommender.log`
- Error log: `/home/azureuser/esab_recommender-bh/logs/esab-recommender-error.log`

**View Logs:**
```bash
# File logs (recommended)
tail -f /home/azureuser/esab_recommender-bh/logs/esab-recommender.log

# Systemd journal
sudo journalctl -u esab-recommender.service -f
```

For detailed deployment instructions, see [deployment/README.md](deployment/README.md).

## Architecture Overview

### Core State Flow (S1→SN)

The configurator follows a dynamic configuration-driven sequential state machine:

1. **S1 - Power Source Selection** (MANDATORY)
   - Must complete before proceeding
   - Loads component applicability configuration
   - Sets Y/N flags for which components are needed

2. **S2 - Feeder Selection** (Conditional)
   - Only shown if applicability.Feeder = "Y"
   - Auto-skipped if "N"

3. **S3 - Cooler Selection** (Conditional)
   - Only shown if applicability.Cooler = "Y"

4. **S4 - Interconnector Selection** (Conditional)
   - Only shown if applicability.Interconnector = "Y"

5. **S5 - Torch Selection** (Conditional)
   - Only shown if applicability.Torch = "Y"

6. **S6 - Accessories Selection** (Optional)
   - Multi-select state
   - Always available

7. **S7 - Finalize**
   - Validates configuration
   - Minimum requirement: PowerSource selected
   - Generates final package summary

### Data Flow Architecture

```
User Message → API Endpoint (/api/v1/configurator/message)
    ↓
Session Management (Redis retrieval/creation)
    ↓
StateByStateOrchestrator.process_message()
    ↓
┌─────────────────────────────────────────────────────────┐
│ Agent Pipeline                                           │
│                                                          │
│ 1. ParameterExtractor (LLM)                             │
│    - Extracts welding parameters from natural language   │
│    - Updates MasterParameterJSON                         │
│    - Uses OpenAI GPT-4                                   │
│    ↓                                                      │
│ 2. Neo4jProductSearch (Graph DB)                        │
│    - Searches for compatible products                    │
│    - Validates COMPATIBLE_WITH relationships             │
│    - Returns ranked results                              │
│    ↓                                                      │
│ 3. MessageGenerator (Templates + LLM)                   │
│    - Generates user-friendly responses                   │
│    - Supports 7 languages (en, es, fr, de, pt, it, sv)  │
│    - Context-aware state prompts                         │
└─────────────────────────────────────────────────────────┘
    ↓
Response + Updated ConversationState
    ↓
Session Storage (Redis with TTL=3600s)
    ↓
Response to Client
```

### Key Data Structures

#### MasterParameterJSON
Dynamically created from `app/config/master_parameter_schema.json`. Tracks user requirements by component:

```python
{
  "power_source": {
    "product_name": "Aristo 500ix",
    "process": "MIG (GMAW)",
    "current_output": "500 A",
    "material": "Steel"
  },
  "feeder": {
    "product_name": "RobustFeed",
    "cooling_type": "Water-cooled"
  },
  # ... other components
}
```

#### ResponseJSON
The user's selection "cart":

```python
{
  "PowerSource": SelectedProduct(...),
  "Feeder": SelectedProduct(...),
  "Cooler": SelectedProduct(...),
  "Interconnector": SelectedProduct(...),
  "Torch": SelectedProduct(...),
  "Accessories": [SelectedProduct(...)],
  "applicability": ComponentApplicability(...)
}
```

#### ConversationState
Complete session state combining MasterParameterJSON, ResponseJSON, conversation history, and current state.

### Multi-Agent Orchestration

**StateByStateOrchestrator** (`app/services/orchestrator/state_orchestrator.py`)
- Coordinates all 3 agents
- Manages state transitions
- Handles component applicability logic
- Processes special commands ("skip", "done", "finalize")

**Agent 1: ParameterExtractor** (`app/services/intent/parameter_extractor.py`)
- Technology: OpenAI GPT-4
- Input: User message + current state + existing parameters
- Output: Updated MasterParameterJSON dict
- Tracked by LangSmith (@traceable decorator)

**Agent 2: Neo4jProductSearch** (`app/services/neo4j/product_search.py`)
- Technology: Neo4j async driver
- Searches PowerSource, Feeder, Cooler, Interconnector, Torch, Accessory nodes
- Validates COMPATIBLE_WITH relationships
- Returns filtered and ranked products

**Agent 3: MessageGenerator** (`app/services/response/message_generator.py`)
- Technology: Template-based + LLM translation
- Generates state-specific prompts
- Formats search results
- Multilingual support via MultilingualTranslator

### Neo4j Product Search Service

**Agent 2** is the core product search engine powered by Neo4j graph database (`app/services/neo4j/product_search.py`).

**Technology Stack:**
- Neo4j async driver for non-blocking I/O
- Cypher query language for graph traversal
- RapidFuzz library for fuzzy product name matching
- Priority-based ranking with relationship weights

**Core Search Methods (S1→S7 Flow):**

1. **`search_power_source()`** - S1: Power source selection (mandatory first step)
   - Searches PowerSource nodes by specifications (current, voltage, process, material)
   - No compatibility validation required (first component)
   - Returns up to 10 results ranked by priority

2. **`search_feeder()`** - S2: Wire feeder selection
   - Searches Feeder nodes compatible with selected PowerSource
   - Validates bidirectional COMPATIBLE_WITH relationships
   - Filters by cooling type, wire size, manufacturer

3. **`search_cooler()`** - S3: Cooling system selection
   - Searches Cooler nodes compatible with selected PowerSource
   - Filters by cooling capacity, voltage, coolant type

4. **`search_interconnector()`** - S4: Interconnector cable selection
   - Searches Interconnector nodes with triple compatibility check
   - Must be compatible with PowerSource, Feeder (if selected), and Cooler (if selected)
   - Filters by cable length, connector type

5. **`search_torch()`** - S5: Welding torch selection
   - Searches Torch nodes compatible with selected Feeder
   - Filters by amperage rating, cooling type, cable length

6. **`search_accessories()`** - S6: Accessory selection (multi-select)
   - Searches Accessory nodes compatible with any selected components
   - Supports category filtering (cables, consumables, safety gear)
   - Multi-select state (can add multiple accessories)

**Advanced Search Methods (Specialized Queries):**

7. **`search_remotes()`** - Remote control units compatible with PowerSource/Feeder
8. **`search_connectivity()`** - Connectivity accessories (WiFi modules, cables)
9. **`search_feeder_wears()`** - Feeder wear parts (liners, drive rolls, contact tips)
10. **`search_powersource_accessories()`** - PowerSource-specific accessories
11. **`search_feeder_accessories()`** - Feeder-specific accessories
12. **`search_powersource_conditional_accessories()`** - PowerSource accessories with conditions
13. **`search_feeder_conditional_accessories()`** - Feeder accessories with conditions
14. **`search_remote_accessories()`** - Remote control accessories
15. **`search_remote_conditional_accessories()`** - Remote accessories with conditions
16. **`search_interconn_accessories()`** - Interconnector-specific accessories

**Key Features:**

1. **Compatibility Validation** - Validates bidirectional COMPATIBLE_WITH relationships in Neo4j
   - PowerSource ↔ Feeder compatibility
   - PowerSource ↔ Cooler compatibility
   - PowerSource/Feeder/Cooler ↔ Interconnector compatibility
   - Feeder ↔ Torch compatibility

2. **Priority Ranking** - Orders results by relationship priority scores
   - Lower priority = better match (1 = top priority)
   - Uses `MIN(r.priority)` for multiple relationship paths
   - Falls back to alphabetical if no priority set

3. **LLM Search Term Filtering** - Dynamic Cypher WHERE clause generation
   - Extracts search terms from MasterParameterJSON
   - Generates Neo4j property filters (e.g., `f.description_catalogue CONTAINS 'water-cooled'`)
   - Supports multi-term filtering with AND logic

4. **Fuzzy Product Name Matching** - RapidFuzz-based name normalization
   - Matches "Aristo 500ix" to "Aristo 500 ix" or "Aristo500ix"
   - 85% similarity threshold (configurable)
   - Applied to PowerSource, Feeder, and Cooler only

5. **Fallback Logic** - Two-tier search strategy
   - Primary query: WITH search term filters (precise matching)
   - Fallback query: WITHOUT search term filters (show all compatible)
   - User feedback: "No exact matches found. Showing all compatible products."

**Data Models:**
- `ProductResult` - Individual product with GIN, name, category, description
- `SearchResults` - List of products + metadata (total count, search parameters)

**Performance:**
- Async architecture for concurrent searches
- Connection pooling via Neo4j driver
- Indexed properties: `gin` (primary key), `category`, `item_name`
- Typical query time: < 100ms for compatibility search

**For complete technical documentation**, see [docs/PRODUCT_SEARCH_SERVICE.md](docs/PRODUCT_SEARCH_SERVICE.md).

### Compound Request Handling (Proactive Search)

**New in v2.1** - The configurator now supports multi-component requests, allowing users to specify multiple components in a single message instead of going through the sequential S1→SN flow.

**Examples of Compound Requests**:
```
✅ "Aristo 500ix with RobustFeed U6"
✅ "500A MIG welder for aluminum with water-cooled feeder"
✅ "I need Warrior 500i plus cooler and torch"
✅ "Aristo 500ix, RobustFeed, and Cool 50"
```

**How It Works**:

1. **Detection Phase**
   - ParameterExtractor fills multiple components in MasterParameterJSON
   - Orchestrator detects compound request when 1+ components have specifications
   - Method: `_detect_compound_request(master_parameters)`

2. **Validation Phase**
   - Validates PowerSource dependency rule
   - PowerSource can be requested standalone
   - Downstream components (Feeder, Cooler, etc.) REQUIRE PowerSource first
   - Method: `_validate_compound_request(master_parameters)`
   - Returns helpful error if validation fails

3. **Parallel Search Phase**
   - Searches all specified components simultaneously
   - Uses existing Neo4j search for each component type
   - Applies component applicability rules
   - Method: `_process_compound_request(...)`

4. **Auto-Selection Phase**
   - **Exact Match (1 result)**: Auto-selects and adds to ResponseJSON
   - **Multiple Matches (2+ results)**: Queues for user disambiguation
   - **No Matches**: Falls back to showing all compatible products
   - Significantly reduces interaction steps for users

5. **State Progression**
   - Skips states for auto-selected components
   - Moves to first component needing disambiguation
   - Or proceeds to next unselected applicable component
   - Or advances to FINALIZE if all components handled

**Validation Rules**:
- ✅ PowerSource only: `"I need Aristo 500ix"`
- ✅ PowerSource + Downstream: `"Aristo 500ix with RobustFeed U6"`
- ❌ Downstream without PowerSource: `"I need RobustFeed U6"` → Prompts for PowerSource

**User Experience Comparison**:

```python
# BEFORE (Sequential Flow - 6 interactions)
User: "I want Aristo 500ix with RobustFeed U6"
Bot: "Let me help you select a power source..." [Shows options]
User: "Aristo 500ix"
Bot: "Power source selected. Now for feeders..." [Shows feeders]
User: "RobustFeed U6"
Bot: "Feeder selected. Would you like a cooler?"

# AFTER (Compound Request - 1 interaction)
User: "I want Aristo 500ix with RobustFeed U6"
Bot: "✅ PowerSource: Aristo 500ix (GIN: 0446200880) - Auto-selected
     ✅ Feeder: RobustFeed U6 (GIN: 0460520880) - Auto-selected

     Current Package:
     • PowerSource: Aristo 500ix
     • Feeder: RobustFeed U6

     Next: Would you like to add a Cooler? [Y/N/skip]"
```

**Implementation Details**:
- File: `app/services/orchestrator/state_orchestrator.py`
- Methods:
  - `_detect_compound_request()` - Lines ~150-180
  - `_validate_compound_request()` - Lines ~180-220
  - `_process_compound_request()` - Lines ~220-400
  - `_generate_compound_response()` - Lines ~400-450
- Backward Compatible: Sequential flow still works exactly as before
- No breaking changes to API or data models

**See Also**:
- [Corrected State Flow Architecture](docs/CORRECTED_STATE_FLOW_ARCHITECTURE.md) - Compound request flow diagram
- [Testing Guide](docs/testing-guide.md) - Compound request testing examples

### Database Architecture

**Redis (Hot Storage)**
- Session data with TTL (default 3600s)
- Key format: `session:{session_id}`
- Fast retrieval for active conversations
- Managed by `RedisSessionStorage`

**PostgreSQL (Archival)**
- Long-term storage for completed sessions
- Table: `archived_sessions`
- Stores full conversation history + agent logs
- Used for analytics and reporting
- Managed by `PostgresArchivalService`

**Neo4j (Product Database)**
- Graph database with nodes: PowerSource, Feeder, Cooler, Interconnector, Torch, Accessory
- Relationships: `COMPATIBLE_WITH`
- Properties store product specifications
- Read-only from configurator perspective

### Configuration Files

**component_applicability.json**
Defines which components are applicable (Y/N) for each power source. Example:

```json
{
  "power_sources": {
    "0446200880": {
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
```

**master_parameter_schema.json**
Defines all available components and their features. Used to dynamically create MasterParameterJSON model at runtime.

**product_names.json**
Pre-computed list of product names for LLM prompt context and fuzzy matching.

## Project Structure

```
src/
├── backend/
│   ├── app/
│   │   ├── main.py                          # FastAPI entry point, lifespan management
│   │   ├── api/v1/configurator.py           # REST endpoints (message, select, state, session)
│   │   ├── models/
│   │   │   ├── conversation.py              # ConversationState, MasterParameterJSON, ResponseJSON
│   │   │   └── graph_state.py               # LangGraph state models (optional)
│   │   ├── config/
│   │   │   ├── schema_loader.py             # Dynamic schema loading utility
│   │   │   ├── component_applicability.json # Y/N component rules per power source
│   │   │   ├── master_parameter_schema.json # Component feature definitions
│   │   │   └── product_names.json           # Product lookup cache
│   │   ├── database/
│   │   │   ├── database.py                  # Redis + PostgreSQL managers
│   │   │   ├── redis_session_storage.py     # Session storage service
│   │   │   └── postgres_archival.py         # Archival service
│   │   └── services/
│   │       ├── orchestrator/
│   │       │   └── state_orchestrator.py    # Main S1→SN orchestrator
│   │       ├── intent/
│   │       │   └── parameter_extractor.py   # Agent 1: LLM parameter extraction
│   │       ├── neo4j/
│   │       │   └── product_search.py        # Agent 2: Graph product search
│   │       ├── response/
│   │       │   └── message_generator.py     # Agent 3: Response generation
│   │       ├── multilingual/
│   │       │   └── translator.py            # LLM-based translation
│   │       ├── observability/
│   │       │   └── langsmith_service.py     # LangSmith tracing
│   │       └── graph/
│   │           └── configurator_graph.py    # Optional LangGraph workflow
│   ├── tests/                                 # Test suite
│   │   ├── unit/                              # Unit tests (< 100ms, mocked deps)
│   │   │   ├── models/                        # Model tests
│   │   │   ├── api/                           # API tests
│   │   │   ├── database/                      # Database service tests
│   │   │   └── services/                      # Service layer tests
│   │   ├── integration/                       # Integration tests (< 5s, real services)
│   │   │   ├── test_api_endpoints.py
│   │   │   ├── test_session_management.py
│   │   │   └── test_configurator_flow.py
│   │   ├── e2e/                               # End-to-end tests (> 5s, full workflows)
│   │   │   ├── test_complete_workflow.py
│   │   │   └── test_state_transitions.py
│   │   ├── manual/                            # Manual test scripts (excluded from pytest)
│   │   │   ├── test_local_neo4j.py
│   │   │   ├── test_explicit_selection.py
│   │   │   └── README.md                      # Manual testing guide
│   │   ├── conftest.py                        # Global fixtures
│   │   ├── unit/conftest.py                   # Unit test fixtures (mocks)
│   │   └── integration/conftest.py            # Integration fixtures (real services)
│   ├── test-results/                          # Test execution artifacts (gitignored)
│   │   ├── coverage/                          # Coverage reports (HTML, XML)
│   │   ├── reports/                           # Test reports (JUnit, HTML)
│   │   ├── logs/                              # Test execution logs
│   │   └── README.md                          # Test results guide
│   ├── requirements.txt
│   ├── pytest.ini                             # Pytest configuration
│   └── clean-test-results.sh                  # Cleanup script
│
└── frontend/
    ├── index.html                       # Main configurator interface (with i18n, cart)
    ├── test_configurator.html           # Simple configurator test interface
    ├── test_extraction.html             # Parameter extraction testing
    ├── config.js                        # Environment detection & configuration (227 lines)
    ├── common.js                        # Shared JavaScript modules (850 lines)
    │                                    # - ESAB.Config: Configuration access
    │                                    # - ESAB.UserManager: User ID management
    │                                    # - ESAB.SessionManager: Session lifecycle
    │                                    # - ESAB.APIHelpers: API request utilities
    │                                    # - ESAB.UIHelpers: UI utilities (markdown, loading)
    │                                    # - ESAB.CartManager: Shopping cart functionality
    ├── translations.js                  # Internationalization (300+ lines)
    │                                    # - ESAB.Translations: i18n for 7 languages
    │                                    # - Supported: en, es, fr, de, pt, it, sv
    └── CONFIG.md                        # Frontend configuration guide
                                         # - Environment detection documentation
                                         # - Azure/AWS deployment instructions
                                         # - Manual configuration examples
                                         # - Troubleshooting guide

deployment/
├── docker/                              # Docker deployment
│   ├── docker-compose.yml               # Multi-container setup
│   ├── Dockerfile                       # Backend container
│   └── README.md                        # Docker deployment guide
├── local/                               # Local development deployment
│   ├── start_servers.sh                 # Start backend + frontend
│   ├── stop_servers.sh                  # Stop servers
│   └── README.md                        # Local deployment guide
├── systemd/                             # Production Linux deployment
│   ├── esab-recommender.service         # Backend systemd service
│   ├── esab-recommender-frontend.service # Frontend systemd service
│   ├── esab-recommender.target          # Combined service target
│   ├── deploy.sh                        # Automated deployment script
│   └── README.md                        # Systemd deployment guide
├── database/                            # Database setup scripts
│   ├── neo4j/                           # Neo4j setup
│   ├── postgres/                        # PostgreSQL setup
│   └── README.md                        # Database setup guide
├── env/                                 # Environment templates
│   ├── .env.development.example
│   ├── .env.production.example
│   └── README.md                        # Environment config guide
└── README.md                            # Main deployment guide

docs/
├── deployment/                          # Deployment documentation
│   ├── README.md                        # Deployment overview
│   ├── docker.md                        # Docker deployment
│   ├── linux-systemd.md                 # Linux production deployment
│   ├── database-setup.md                # Database configuration
│   ├── quick-start.md                   # Quick start guide
│   └── troubleshooting.md               # Troubleshooting guide
├── operations/                          # Operations documentation
│   └── runbook.md                       # Operations runbook
├── testing-organization-review.md        # Test reorganization details
├── testing-guide.md                     # Testing best practices
├── CORRECTED_STATE_FLOW_ARCHITECTURE.md
├── LANGGRAPH_INTEGRATION.md
├── LLM_ENTITY_EXTRACTION_ARCHITECTURE.md
├── MASTER_PARAMETER_JSON_ARCHITECTURE.md
└── MULTILINGUAL_FLOW.md
```

## API Endpoints

**POST /api/v1/configurator/message**
Process user message in current conversation state.

Request:
```json
{
  "session_id": "optional-uuid",  // null for new session
  "message": "I need a 500A MIG welder",
  "reset": false,                 // force new session
  "language": "en"                // ISO 639-1 code
}
```

Response:
```json
{
  "session_id": "uuid",
  "message": "AI response text",
  "current_state": "power_source_selection",
  "master_parameters": {...},
  "response_json": {...},
  "products": [...],              // search results if available
  "awaiting_selection": true,
  "can_finalize": false
}
```

### Compound Request Examples

See [Testing Guide](docs/testing-guide.md) for detailed API examples.

**Quick Example - Auto-Selection**:
```json
Request: {"message": "Aristo 500ix with RobustFeed U6", "language": "en"}
Response: {
  "current_state": "cooler_selection",
  "response_json": {
    "PowerSource": {"gin": "0446200880", "name": "Aristo 500ix"},
    "Feeder": {"gin": "0460520880", "name": "RobustFeed U6"}
  },
  "awaiting_selection": false  // Both auto-selected
}
```

**POST /api/v1/configurator/select**
Explicitly select a product.

**GET /api/v1/configurator/state/{session_id}**
Retrieve current session state.

**DELETE /api/v1/configurator/session/{session_id}**
Delete active session from Redis.

**POST /api/v1/configurator/archive/{session_id}**
Archive completed session to PostgreSQL.

**GET /health**
System health check for all services.

## Frontend Architecture

### Overview

The frontend is a modular JavaScript application served as static files from `src/frontend/`. All HTML files use a shared ESAB namespace for common functionality.

**Key Features:**
- Modular JavaScript architecture (ESAB namespace)
- Automatic environment detection (dev/staging/production)
- Multi-language support (7 languages)
- User ID management with localStorage persistence
- Session resumption across page reloads
- Responsive UI with markdown formatting

### ESAB Module System

All shared JavaScript is organized under the `window.ESAB` namespace to avoid global pollution.

#### ESAB.Config (`common.js`)
Configuration access with environment detection:

```javascript
ESAB.Config.API_BASE          // e.g., "http://localhost:8000"
ESAB.Config.FRONTEND_BASE     // Frontend origin
ESAB.Config.ENVIRONMENT       // "development" | "staging" | "production"
ESAB.Config.DEBUG             // true/false
ESAB.Config.apiEndpoint(path) // Build full API URLs
ESAB.Config.getConfig()       // Get full config object
```

#### ESAB.UserManager (`common.js`)
User ID management with localStorage:

```javascript
ESAB.UserManager.getUserId()           // Get or create user ID
ESAB.UserManager.updateUserDisplay(id) // Update UI badge
ESAB.UserManager.switchUser()          // Clear and reload
ESAB.UserManager.getCurrentUserId()    // Get without prompting
ESAB.UserManager.setUserId(id)         // Set explicitly
```

#### ESAB.SessionManager (`common.js`)
Session lifecycle management:

```javascript
ESAB.SessionManager.startNewSession(callbacks)  // Reset session
ESAB.SessionManager.initSession(userId, apiEndpoint, callbacks)  // Resume or create
```

#### ESAB.APIHelpers (`common.js`)
Standardized API request utilities:

```javascript
ESAB.APIHelpers.makeRequest(endpoint, method, body)  // Generic request
ESAB.APIHelpers.sendMessage(sessionId, userId, message, language, apiEndpoint)
ESAB.APIHelpers.selectProduct(sessionId, userId, gin, productData, apiEndpoint)
```

#### ESAB.UIHelpers (`common.js`)
UI utilities for consistent behavior:

```javascript
ESAB.UIHelpers.formatMarkdown(text)     // Convert markdown to HTML
ESAB.UIHelpers.escapeHtml(text)         // Escape HTML characters
ESAB.UIHelpers.createLoadingSpinner()   // Loading indicator HTML
ESAB.UIHelpers.setButtonLoading(btn, isLoading)  // Button state
ESAB.UIHelpers.scrollToBottom(element)  // Auto-scroll chat
ESAB.UIHelpers.addMessageToChat(container, text, isUser, products)
```

#### ESAB.CartManager (`common.js`)
Shopping cart functionality:

```javascript
ESAB.CartManager.updateCart(responseJson, cartContentId, ...)  // Update cart display
ESAB.CartManager.generateCartHTML(responseJson)  // Generate HTML
ESAB.CartManager.getComponentCount(responseJson)  // Count items
ESAB.CartManager.getComponentIcon(componentKey)  // Get emoji icon
```

#### ESAB.Translations (`translations.js`)
Internationalization support:

```javascript
ESAB.Translations.get(lang)               // Get translations for language
ESAB.Translations.getSupportedLanguages() // ["en", "es", "fr", ...]
ESAB.Translations.getLanguageName(lang)   // "English", "Español", ...
ESAB.Translations.isSupported(lang)       // Check if language available
ESAB.Translations.updateUILanguage(lang)  // Update all UI text
ESAB.Translations.changeLanguage(selectId, callback)  // Language switcher
ESAB.Translations.initLanguage(selectId, defaultLang) // Initialize on load
```

### Frontend Configuration (`config.js`)

The configuration system automatically detects the deployment environment and configures URLs accordingly.

**Environment Detection Rules:**
- `localhost`, `127.0.0.1`, `192.168.x`, `10.x` → Development
- Hostnames with "staging", "dev", "test" → Staging
- All other hostnames → Production

**Configuration Priority (highest to lowest):**
1. URL Parameters (`?apiBase=http://...`)
2. Manual Config (`MANUAL_CONFIG` object in config.js)
3. Environment Defaults (`ENVIRONMENT_DEFAULTS`)
4. Auto-Detection (hostname-based)

**Manual Configuration Example:**

Edit `src/frontend/config.js`:

```javascript
const MANUAL_CONFIG = {
    API_BASE: 'http://your-server-ip:8000',  // Override API URL
    FRONTEND_BASE: null,  // Auto-detect
    ENVIRONMENT: 'production',  // Override environment
    DEBUG: false  // Disable debug logs
};
```

**For detailed deployment instructions**, see `src/frontend/CONFIG.md`:
- Azure VM deployment (internal vs public IP)
- Azure App Service setup
- AWS EC2 deployment
- Docker deployment
- On-premises server configuration
- Troubleshooting guide

### HTML File Organization

**index.html** - Main configurator interface
- Full S1→SN dynamic workflow with state display
- Multi-language support (7 languages)
- Shopping cart with component visualization
- Session resumption
- User ID management

**test_configurator.html** - Simple test interface
- Minimal configurator for API testing
- No cart, no language selection
- Useful for debugging state transitions

**test_extraction.html** - Parameter extraction testing
- Test parameter extraction in isolation
- View MasterParameterJSON changes
- Debug LLM entity extraction

### Multilingual Support (Frontend)

The frontend supports 7 languages via `translations.js`:
- English (en)
- Spanish (es)
- French (fr)
- German (de)
- Portuguese (pt)
- Italian (it)
- Swedish (sv)

**To add a new language:**

1. Edit `src/frontend/translations.js`
2. Add translation dictionary:
   ```javascript
   const translations = {
       // ... existing languages
       nl: {  // Dutch
           pageTitle: '🔧 Aanbeveler V2 - S1→SN Configurator',
           pageSubtitle: 'Stapsgewijze lasapparatuur configuratiesysteem',
           // ... all other keys
       }
   };
   ```
3. Add language name:
   ```javascript
   const languageNames = {
       // ... existing
       'nl': 'Nederlands'
   };
   ```
4. Test by selecting language in dropdown

**Note:** Backend also supports multilingual via `MultilingualTranslator` service.

### User ID and Session Management

**User ID Persistence:**
- Stored in `localStorage` as `esab_user_id`
- Persists across page reloads
- Prompt on first visit (or auto-generate)
- Can be switched via UI button

**Session Resumption:**
- On page load, frontend sends `message: "resume"` with `user_id`
- Backend finds user's latest session in Redis
- If found: Restores state, cart, conversation history
- If not found: Creates new session

**Multi-User Support:**
- Backend tracks sessions per user via Redis SETs
- Key format: `user:{user_id}:sessions`
- Each user can have multiple sessions
- Frontend always resumes latest session

## Important Development Notes

### Adding New Components
1. Update `master_parameter_schema.json` with new component and features
2. Update `component_applicability.json` with Y/N rules
3. Add state to `ConfiguratorState` enum in `models/conversation.py`
4. Add handler in `StateByStateOrchestrator` if custom logic needed
5. Update `ResponseJSON` model if new component needs special handling

**Reference**: See [Master Parameter JSON Architecture](docs/MASTER_PARAMETER_JSON_ARCHITECTURE.md) for detailed data model design.

### Modifying State Transitions
State transition logic is in `ConversationState.get_next_state()`. It automatically skips states where applicability = "N". To modify:
1. Edit `get_next_state()` in `models/conversation.py`
2. Update component_map in that method if adding new states
3. Test state skipping with various power source configurations

**Reference**: See [Corrected State Flow Architecture](docs/CORRECTED_STATE_FLOW_ARCHITECTURE.md) for detailed state transition diagrams.

### Working with Compound Requests

**New in v2.1** - Users can specify multiple components in a single message. The orchestrator automatically detects, validates, and processes compound requests.

**Examples**: `"Aristo 500ix with RobustFeed U6"`, `"500A MIG welder for aluminum with water-cooled feeder"`

**Validation Rules**:
- ✅ PowerSource standalone: `"I need Aristo 500ix"`
- ✅ PowerSource + Downstream: `"Aristo 500ix with RobustFeed U6"`
- ❌ Downstream without PowerSource: Prompts for PowerSource first

**Auto-Selection**:
- **1 result**: Auto-selects, skips state
- **2+ results**: Disambiguation required
- **0 results**: Shows all compatible products

**Implementation**: `state_orchestrator.py` (~lines 150-450)

**Testing**: Use `test_chat_flow.py` or `tests/integration/test_configurator_flow.py`

**Reference**: [Corrected State Flow Architecture](docs/CORRECTED_STATE_FLOW_ARCHITECTURE.md)

### Working with Sessions
- Sessions are stored in Redis with 1-hour TTL by default
- TTL is refreshed on each message
- Modify TTL in `main.py`: `init_redis_session_storage(redis_client, ttl=3600)`
- Sessions can be archived to PostgreSQL for long-term storage
- Archived sessions include full conversation history and agent traces

### Multilingual Support (Backend)
Supported languages: en, es, fr, de, pt, it, sv

**Note:** Frontend multilingual is handled separately via `src/frontend/translations.js` (see Frontend Architecture section).

To add a new language to **backend**:
1. Add to `LANGUAGE_NAMES` dict in `services/multilingual/translator.py`
2. Update language detection logic if needed
3. Test with sample queries in that language

**Reference**: See [Multilingual Flow](docs/MULTILINGUAL_FLOW.md) for complete translation architecture and design.

To add a new language to **frontend**:
1. See "Multilingual Support (Frontend)" section above
2. Edit `src/frontend/translations.js` with translation dictionary

### LangSmith Observability
Enable tracing by setting environment variables:
```bash
LANGSMITH_API_KEY=ls_...
LANGSMITH_PROJECT=Recommender
LANGSMITH_TRACING=true
```

Functions decorated with `@traceable` will log to LangSmith. Key functions:
- `ParameterExtractor.extract_parameters()`
- `MultilingualTranslator.translate()`
- Add to other functions as needed for debugging

**Reference**: See [LangGraph Integration](docs/LANGGRAPH_INTEGRATION.md) for optional agent orchestration using LangGraph.

### Component Applicability Logic
After S1 (PowerSource) selection:
1. System looks up power source GIN in `component_applicability.json`
2. Loads applicability flags (Y/N for each component)
3. Stores in `ResponseJSON.applicability`
4. State machine uses these flags to auto-skip or show component states

If a power source is missing from config:
- Default: All components are applicable ("Y")
- Add new power sources to config as they're added to Neo4j

### Neo4j Query Patterns
Product searches use compatibility relationships:

```cypher
MATCH (ps:PowerSource {gin: $selected_ps_gin})
MATCH (feeder:Feeder)-[:COMPATIBLE_WITH]->(ps)
WHERE feeder.property CONTAINS $value
RETURN feeder
```

Modify search logic in `Neo4jProductSearch` methods for each component type.

## Running Without Redis

Set `ENABLE_REDIS_CACHING=false` to use in-memory session storage (dev/testing only).

**What Works**: All features except persistence across restarts, distributed sessions, and product list caching.

**Limitations**:
- ❌ No persistence across restarts
- ❌ Single-worker only (`--workers 1`)
- ❌ No distributed sessions

**Verification**:
```bash
curl http://localhost:8000/health  # Check session_storage.type = "in-memory"
python tests/manual/test_redis_disabled.py  # Run test
```

**Production**: Not recommended. Use `--workers 1` if required. See deployment docs for details.

## Environment Variables Reference

For complete environment configuration, see [Environment Variables Guide](deployment/env/README.md).

**Required**:
- `OPENAI_API_KEY` - OpenAI API key for GPT-4
- `NEO4J_URI` - Neo4j connection URI
  - Local: `neo4j://localhost:7687`
  - Neo4j Aura (cloud): `bolt+s://xxxxx.databases.neo4j.io`
- `NEO4J_USERNAME` - Neo4j username (default: neo4j)
- `NEO4J_PASSWORD` - Neo4j password

**Database**:
- `REDIS_URL` or `REDIS_HOST`/`REDIS_PORT` - Redis connection
- `REDIS_PASSWORD` - Redis password (optional)
- `REDIS_DB` - Redis database number (default: 0)
- `ENABLE_REDIS_CACHING` - Enable Redis (default: true)
- `CACHE_TTL` - Session TTL in seconds (default: 3600)
- `POSTGRES_HOST` - PostgreSQL host (default: localhost)
- `POSTGRES_PORT` - PostgreSQL port (default: 5432)
- `POSTGRES_DB` - Database name (default: pconfig)
- `POSTGRES_USER` - Database user (default: postgres)
- `POSTGRES_PASSWORD` - Database password

**Optional**:
- `LANGSMITH_API_KEY` - LangSmith API key for observability
- `LANGSMITH_PROJECT` - LangSmith project name (default: Recommender)
- `LANGSMITH_TRACING` - Enable tracing (default: true)
- `SECRET_KEY` - Application secret key
- `JWT_SECRET_KEY` - JWT secret key

## Troubleshooting

**Service won't start or hangs on restart**
- Check if it's actually working despite systemd status: `curl http://localhost:8000/health`
- Service may take 40-60 seconds to start with 4 workers - this is normal
- If timeout occurs, increase `TimeoutStartSec=120` in service file
- Change `Type=notify` to `Type=exec` in service file
- Check environment variables are set correctly
- Verify databases are running (Neo4j Aura, PostgreSQL, Redis)
- Check file logs: `tail -f /home/azureuser/esab_recommender-bh/logs/esab-recommender.log`
- Check journal logs: `sudo journalctl -u esab-recommender.service -n 100`
- Verify port 8000 is not in use: `sudo netstat -tlnp | grep 8000`
- Verify venv exists: `ls -la /home/azureuser/esab_recommender-bh/src/backend/venv/bin/uvicorn`

**Database connection errors**
- Test connections individually (see Database Operations section)
- Check firewall rules for database ports
- Verify credentials in src/backend/.env file

**LLM extraction failures**
- Verify OPENAI_API_KEY is valid
- Check OpenAI API quotas and rate limits
- Review LangSmith traces if enabled
- Check parameter extractor logs for prompt issues

**State transitions not working**
- Verify component_applicability.json has entry for selected power source
- Check ResponseJSON.applicability is set after S1
- Review ConversationState.get_next_state() logic
- Check orchestrator logs for state transition errors

**Redis session not persisting**
- Check Redis connection: `redis-cli ping`
- Verify CACHE_TTL is reasonable (not too short)
- Check Redis memory limits and eviction policy
- Review redis_session_storage logs

**For more troubleshooting help**, see:
- [Deployment Troubleshooting Guide](docs/deployment/troubleshooting.md) - Complete troubleshooting documentation
- [Redis Quick Troubleshooting](docs/deployment/redis-guide.md) - Common Redis issues and quick solutions
- [Operations Runbook](docs/operations/runbook.md) - Operational procedures and issue resolution

## Version Information

- **Current Version**: 2.0 (Recommender_v2)
- **Python**: 3.11+ (3.12+ fully supported)
- **FastAPI**: 0.104.1
- **OpenAI**: 2.0+
- **LangChain**: 0.3.0+
- **LangGraph**: 0.6.0+
- **Neo4j**: 5.14.1
- **PostgreSQL**: 12+
- **Redis**: 5.0+

**Legacy Version**: v1 runs on port 8000 with different architecture (Trinity package formation). This is a clean-room reimplementation.

**Critical Development Rules**:
- requirements.txt is in **TWO places** (`src/backend/` and root), always update both files
- **Never commit automatically** to git - user commits manually
- **Always move *.md files** to docs/ directory (except README.md, CLAUDE.md, AGENTS.md)

## Non-Obvious Architecture Patterns

For detailed coverage of complex architectural patterns that require understanding multiple files, see:

**[Architecture Patterns Guide](docs/ARCHITECTURE_PATTERNS.md)**

Key topics covered:
- 🏗️ Dynamic State Machine (runtime-generated from JSON)
- ⚙️ Configuration Service (LRU caching, hot reload)
- 📊 Structured Logging (correlation IDs, distributed tracing)
- 🎯 GIN Manager (backend contract layer)
- 🔍 Product Ranking System (deterministic ordering)
- 💬 Conversation Manager (intent tracking)
- 🔎 Advanced Search (Lucene, multilingual)
- ⏭️ Skip Tracking System
- 🔗 Integrated Components
- 🌐 Error Handling (multilingual messages)
- 🏭 Development vs Production
- 📁 Critical File Patterns