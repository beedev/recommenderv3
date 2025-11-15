# Welding Product Configurator - V2 (S1→SN Dynamic State Flow)

**Version**: 2.0
**Status**: Clean Implementation
**Architecture**: State Machine with Sequential Component Selection

---

## Overview

Recommender_v2 is a **clean room implementation** of the S1→SN configuration-driven state-by-state configurator flow.
This is a **completely separate project** from Recommender v1 to ensure zero risk to the existing working system.

### Key Differences from V1

| Feature | V1 (Recommender) | V2 (Recommender_v2) |
|---------|------------------|---------------------|
| **Flow** | All-at-once recommendations | State-by-state (S1→SN) |
| **Output** | TrinityPackage list | Response JSON (selected products) |
| **PowerSource** | Optional | **Mandatory** |
| **Compatibility** | Trinity-based | Per-component validation |
| **User Interaction** | Single query | Multi-turn conversation |
| **Port** | 8000 (legacy) | 8000 |

### ✨ New in v2.1: Compound Request Handling (Proactive Search)

Users can now specify **multiple components in a single request**, dramatically reducing interaction steps:

**Examples**:
```
✅ "Aristo 500ix with RobustFeed U6"
✅ "500A MIG welder for aluminum with water-cooled feeder"
✅ "I need Warrior 500i plus cooler and torch"
```

**Key Features**:
- 🚀 **Auto-Selection**: Exact matches (1 result) are automatically selected
- 🔍 **Smart Disambiguation**: Multiple matches queue for user choice
- ✅ **Validation**: PowerSource dependency enforced
- ⚡ **State Skipping**: Auto-selected components skip their states
- 🔄 **Backward Compatible**: Sequential flow still works as before

**Before (6 interactions)**:
```
User: "I want Aristo 500ix with RobustFeed U6"
Bot: "Let me show you power sources..." [interaction 1]
User: "Aristo 500ix" [interaction 2]
Bot: "Now for feeders..." [interaction 3]
User: "RobustFeed U6" [interaction 4]
Bot: "Would you like a cooler?" [interaction 5]
User: "skip" [interaction 6]
```

**After (1 interaction)**:
```
User: "I want Aristo 500ix with RobustFeed U6"
Bot: "✅ PowerSource: Aristo 500ix - Auto-selected
     ✅ Feeder: RobustFeed U6 - Auto-selected

     Next: Would you like a Cooler? [Y/N/skip]"
```

**See**: [Compound Request Architecture](docs/CORRECTED_STATE_FLOW_ARCHITECTURE.md#compound-request-flow-proactive-search)

---

## Architecture

### S1→SN Sequential Flow

```
S1: PowerSource (MANDATORY)
  ↓ Get Component Applicability
  ↓ Auto-fill NA components
S2: Feeder (if Y)
  ↓ Validate compatibility with S1
S3: Cooler (if Y)
  ↓ Validate compatibility with S1 + S2
S4: Interconnector (if Y)
  ↓ Validate compatibility with S1 + S2 + S3
S5: Torch (if Y)
  ↓ Validate compatibility with S2 + S3
S6: Accessories (optional)
  ↓ Category-specific compatibility
S7: Finalize
  ↓ Validate ≥3 components
  ↓ Generate packages
```

### Core Components

1. **Master Parameter JSON** - User requirements tracking
2. **Response JSON** - Selected products (cart)
3. **Component Applicability** - Y/N configuration per power source
4. **LLM Entity Extractor** - Prompt-based parameter extraction
5. **State Machine** - S1→SN orchestration
6. **Compatibility Validator** - COMPATIBLE_WITH relationship checks

---

## Documentation

📚 **[Complete Documentation Hub](docs/README.md)** - Full project documentation

**Quick Links**:
- [Quick Start Guide](docs/deployment/quick-start.md) - Get running in 5 minutes
- [API Documentation](http://localhost:8000/docs) - Interactive Swagger UI
- [Testing Guide](docs/testing-guide.md) - Comprehensive testing practices
- [Operations Runbook](docs/operations/runbook.md) - Day-to-day operations
- [Troubleshooting Guide](docs/deployment/troubleshooting.md) - Common issues

**Architecture**:
- [State Flow Architecture](docs/CORRECTED_STATE_FLOW_ARCHITECTURE.md) - S1→S7 flow
- [Product Search Service](docs/PRODUCT_SEARCH_SERVICE.md) - Neo4j search engine
- [Master Parameter JSON](docs/MASTER_PARAMETER_JSON_ARCHITECTURE.md) - Data models

**Deployment**:
- [Docker Deployment](docs/deployment/docker.md) - Containerized development
- [Linux Deployment](docs/deployment/linux-systemd.md) - Production Linux
- [Database Setup](docs/deployment/database-setup.md) - Neo4j, PostgreSQL, Redis

---

## Directory Structure

```
ESAB-Recommender/
├── src/backend/
│   ├── app/
│   │   ├── api/v1/configurator.py  # S1→SN REST endpoints
│   │   ├── services/
│   │   │   ├── intent/             # Agent 1 - Parameter Extraction (LLM)
│   │   │   ├── neo4j/              # Agent 2 - Product Search (Graph DB)
│   │   │   ├── response/           # Agent 3 - Message Generation
│   │   │   ├── orchestrator/       # State Machine (S1→SN coordinator)
│   │   │   ├── multilingual/       # Translation service
│   │   │   ├── observability/      # LangSmith integration
│   │   │   └── graph/              # LangGraph workflow (optional)
│   │   ├── models/
│   │   │   ├── conversation.py     # ConversationState, MasterParameterJSON, ResponseJSON
│   │   │   └── graph_state.py      # LangGraph state models
│   │   ├── database/
│   │   │   ├── database.py         # Redis + PostgreSQL managers
│   │   │   ├── redis_session_storage.py
│   │   │   └── postgres_archival.py
│   │   └── config/
│   │       ├── component_applicability.json
│   │       ├── master_parameter_schema.json
│   │       └── product_names.json
│   ├── .env
│   ├── requirements.txt
│   └── main.py
├── deployment/                     # Production deployment scripts
│   ├── deploy.sh
│   ├── esab-recommender.service
│   └── README.md
├── docs/                           # Architecture documents
│   ├── CORRECTED_STATE_FLOW_ARCHITECTURE.md
│   ├── MASTER_PARAMETER_JSON_ARCHITECTURE.md
│   ├── LLM_ENTITY_EXTRACTION_ARCHITECTURE.md
│   └── redis_session_lifecycle.md
├── CLAUDE.md                       # Guide for Claude Code instances
└── README.md
```

---

## Installation

```bash
# 1. Navigate to backend directory
cd src/backend

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
# Create .env file at: src/backend/.env
# Copy from template: deployment/env/.env.example
# Required variables:
# - OPENAI_API_KEY
# - NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
# - REDIS_URL or REDIS_HOST/REDIS_PORT
# - ENABLE_REDIS_CACHING (default: true)
# - ENABLE_REDIS_SESSIONS (default: true)
# - CACHE_TTL (overrides session TTL when set)
# - POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
# - LANGSMITH_API_KEY (optional)
# For detailed configuration, see: deployment/env/README.md

# 5. Run on port 8000
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## API Endpoints

### New S1→SN Configurator

```
POST /api/v1/configurator/message
Content-Type: application/json

{
  "session_id": "optional-session-id",
  "user_id": "operator-42",
  "participants": ["operator-42", "field-tech-5"],
  "metadata": {"site": "detroit", "machineId": "M-8831"},
  "message": "I need a 500A MIG welder",
  "reset": false
}

Response:
{
  "session_id": "uuid",
  "message": "Great! I found the Aristo 500ix...",
  "current_state": "feeder_selection",
  "master_parameters": {...},
  "response_json": {...},
  "participants": ["operator-42", "field-tech-5"],
  "owner_user_id": "operator-42",
  "last_updated": "2025-02-08T12:34:56.789Z"
}
```

---

## Testing

### Quick Testing

```bash
# Start the server (from src/backend directory)
cd src/backend
source venv/bin/activate  # Windows: venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# In another terminal, test the API
# Health check
curl http://localhost:8000/health

# Test configurator
curl -X POST http://localhost:8000/api/v1/configurator/message \
  -H "Content-Type: application/json" \
  -d '{"message": "I need a 500A MIG welder", "language": "en"}'

# Or use Swagger UI
# Navigate to: http://localhost:8000/docs

# View HTML test interfaces
# Open in browser:
http://localhost:8000/static/index.html
http://localhost:8000/static/test_configurator.html
http://localhost:8000/static/test_extraction.html
```

### Run Test Scripts

```bash
cd src/backend
python test_explicit_selection.py
```

---

## Key Features

### 1. Mandatory PowerSource
- S1 cannot be skipped
- System keeps prompting until user provides details

### 2. Component Applicability
- Automatic NA assignment for incompatible components
- Dynamic state skipping (e.g., Renegade ES300 → skip S2, S3, S4)

### 3. Compatibility Validation
- Every search validates COMPATIBLE_WITH relationships
- Per-component compatibility rules (see docs)

### 4. Master Parameter JSON
- Tracks user requirements across all states
- LLM fills parameters via structured prompts
- Latest value wins (user can change mind)

### 5. Response JSON
- Selected products (cart)
- Used for final package generation
- Minimum requirement: PowerSource selected

### 6. Multilingual Support
- Supports 7 languages: English, Spanish, French, German, Portuguese, Italian, Swedish
- LLM-based translation with context awareness
- Automatic language detection

### 7. Observability
- LangSmith integration for real-time tracing
- Session archival for analytics
- Health monitoring endpoints

---

## Architecture Documents

See `/docs` for detailed architecture:

- `CORRECTED_STATE_FLOW_ARCHITECTURE.md` - Complete S1→SN flow
- `MASTER_PARAMETER_JSON_ARCHITECTURE.md` - Parameter tracking
- `LLM_ENTITY_EXTRACTION_ARCHITECTURE.md` - Prompt-based extraction
- `PHASE1_ARCHITECTURE.md` - Implementation components
- `SYSTEM_ALIGNMENT_ANALYSIS.md` - Spec alignment

---

## Safety & Isolation

### Complete Isolation from V1

✅ **File System**: Separate `/Recommender_v2` directory
✅ **Runtime**: Production port (8000)
✅ **Database**: Separate connection pool
✅ **Dependencies**: Own virtual environment
✅ **No Shared Code**: All services copied and simplified

### Service Management

The application runs as systemd services on Linux production servers:
- Backend service runs on port 8000
- Session data stored in Redis (hot) and PostgreSQL (archival)
- Neo4j provides product database with compatibility relationships
- LangSmith provides optional observability and tracing
- HTML test interfaces accessible at `/static/` endpoints

---

## Development Status

- [x] Architecture design completed
- [x] Directory structure created
- [x] Configuration files implemented
- [x] Master Parameter JSON models (dynamic schema-based)
- [x] LLM Entity Extractor (parameter_extractor.py)
- [x] State Machine orchestrator (state_orchestrator.py)
- [x] API endpoints (configurator.py)
- [x] Database layer (Redis + PostgreSQL + Neo4j)
- [x] Multi-agent orchestration (3-agent pipeline)
- [x] Multilingual support (7 languages)
- [x] Session management (hot storage + archival)
- [x] LangSmith observability integration
- [x] Production deployment scripts
- [x] CLAUDE.md documentation for AI assistants

---

## Deployment

### Production Deployment (Linux)

```bash
# Automated deployment
cd deployment
chmod +x deploy.sh
sudo ./deploy.sh install

# Manage services
sudo systemctl start esab-recommender.target   # Start both backend and frontend
sudo systemctl stop esab-recommender.target    # Stop both
sudo systemctl restart esab-recommender.target # Restart both
sudo systemctl status esab-recommender.target  # Check status

# View logs
sudo journalctl -u esab-recommender.service -f
```

For detailed deployment instructions, see [deployment/README.md](deployment/README.md).

---

**Created**: 2025-10-24
**Author**: Claude + Bharath
**Purpose**: Safe S1→SN implementation without affecting V1

