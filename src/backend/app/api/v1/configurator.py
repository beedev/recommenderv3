"""
Selection-Aware Configurator API Endpoint
FastAPI router for S1→SN welding equipment configuration
Supports product selection from previous responses
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...database.redis_session_storage import get_redis_session_storage
from ...models.conversation import (
    ConversationState,
    ResponseJSON,
    MasterParameterJSON,
    get_configurator_state,
)
from ...services.orchestrator.state_orchestrator import StateByStateOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/configurator", tags=["configurator"])


# Dependency injection placeholder (overridden in main.py)
def get_orchestrator_dep() -> StateByStateOrchestrator:
    """Dependency injection placeholder for orchestrator - overridden in main.py"""
    raise RuntimeError("Orchestrator dependency not initialized")


class MessageRequest(BaseModel):
    """Request model for user message"""

    session_id: Optional[str] = None
    user_id: Optional[str] = None
    customer_id: Optional[str] = None
    participants: Optional[List[str]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    message: str
    reset: bool = False
    language: str = "en"  # ISO 639-1 language code (en, es, fr, de, pt, it, sv)


class SelectProductRequest(BaseModel):
    """Request model for product selection"""

    session_id: Optional[str] = None
    user_id: Optional[str] = None
    participants: Optional[List[str]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    product_gin: str
    product_data: Dict[str, Any]


class MessageResponse(BaseModel):
    """Response model for message endpoint"""

    session_id: str
    message: str
    current_state: str
    master_parameters: Dict
    response_json: Dict
    products: Optional[list] = None
    awaiting_selection: bool = False
    can_finalize: bool = False
    participants: List[str] = Field(default_factory=list)
    owner_user_id: Optional[str] = None
    customer_id: Optional[str] = None
    last_updated: str
    component_statuses: Dict[str, str] = Field(default_factory=dict)
    # Pagination metadata (optional - only present for paginated responses)
    pagination: Optional[Dict[str, Any]] = None


def _now_utc() -> datetime:
    """Return timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _coerce_datetime(value: Any) -> datetime:
    """Convert stored datetime value into timezone-aware datetime."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            # Handle strings with trailing Z
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    return datetime.fromtimestamp(0, tz=timezone.utc)


def _apply_request_context(
    conversation_state: ConversationState,
    *,
    language: Optional[str],
    user_id: Optional[str],
    customer_id: Optional[str],
    participants: Optional[List[str]],
    metadata: Optional[Dict[str, Any]],
) -> bool:
    """
    Merge request context onto conversation state.

    Returns:
        True if the state was mutated and should be resaved.
    """
    updated = False

    if language and conversation_state.language != language:
        conversation_state.language = language
        updated = True

    if customer_id and conversation_state.customer_id != customer_id:
        conversation_state.customer_id = customer_id
        updated = True

    if user_id:
        if not conversation_state.owner_user_id:
            conversation_state.owner_user_id = user_id
            updated = True
        if user_id not in conversation_state.participants:
            conversation_state.participants.append(user_id)
            updated = True

    if participants:
        for participant in participants:
            if participant and participant not in conversation_state.participants:
                conversation_state.participants.append(participant)
                updated = True

    if metadata:
        conversation_state.metadata.update(metadata)
        updated = True

    if updated:
        # Deduplicate while preserving order
        conversation_state.participants = list(dict.fromkeys(conversation_state.participants))
        conversation_state.last_updated = _now_utc()

    return updated


async def _select_latest_session_for_user(
    redis_storage,
    user_id: str,
) -> Optional[ConversationState]:
    """
    Retrieve the most recently updated session for a given user.
    Uses batch retrieval to avoid N+1 query pattern.
    """
    session_ids = await redis_storage.get_sessions_for_user(user_id)
    if not session_ids:
        return None

    # Batch retrieve all sessions for this user (single round-trip)
    sessions_dict = await redis_storage.get_sessions_batch(session_ids)

    latest_session: Optional[ConversationState] = None
    latest_timestamp: Optional[datetime] = None

    for candidate_id, candidate in sessions_dict.items():
        if not candidate:
            continue

        candidate_ts = _coerce_datetime(candidate.last_updated)
        if latest_timestamp is None or candidate_ts > latest_timestamp:
            latest_session = candidate
            latest_timestamp = candidate_ts

    return latest_session


async def get_or_create_session(
    session_id: Optional[str] = None,
    reset: bool = False,
    language: str = "en",
    *,
    user_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    participants: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> ConversationState:
    """Get existing session from Redis or create new one"""

    redis_storage = get_redis_session_storage()

    metadata = metadata or {}
    participants = participants or []

    # Handle reset by clearing state but keeping same session_id (Option C)
    if reset:
        if session_id:
            # Fetch existing session and clear state
            existing_session = await redis_storage.get_session(session_id)
            if existing_session:
                # Clear state but keep session_id
                existing_session.conversation_history = []
                existing_session.response_json = ResponseJSON()
                existing_session.master_parameters = MasterParameterJSON()
                existing_session.current_state = get_configurator_state().POWER_SOURCE_SELECTION
                existing_session.pagination_states = {}
                await redis_storage.save_session(existing_session)
                logger.info("Reset session state (kept session_id): %s", session_id)
                return existing_session

        # If session doesn't exist, create new one (fallback)

    # Attempt to load by explicit session identifier
    if session_id:
        existing_session = await redis_storage.get_session(session_id)
        if existing_session:
            if _apply_request_context(
                existing_session,
                language=language,
                user_id=user_id,
                customer_id=customer_id,
                participants=participants,
                metadata=metadata,
            ):
                await redis_storage.save_session(existing_session)
            logger.info(
                "Retrieved existing session from Redis: %s (language: %s)",
                session_id,
                existing_session.language,
            )
            return existing_session

    # Fallback to most recent session for the user
    if user_id and not reset:
        existing_session = await _select_latest_session_for_user(redis_storage, user_id)
        if existing_session:
            if _apply_request_context(
                existing_session,
                language=language,
                user_id=user_id,
                customer_id=customer_id,
                participants=participants,
                metadata=metadata,
            ):
                await redis_storage.save_session(existing_session)
            logger.info(
                "Reused existing session %s for user %s",
                existing_session.session_id,
                user_id,
            )
            return existing_session

    # Create new session
    new_session_id = session_id or str(uuid.uuid4())
    conversation_state = ConversationState(
        session_id=new_session_id,
        language=language,
        owner_user_id=user_id,
        customer_id=customer_id,
        participants=participants or ([user_id] if user_id else []),
    )
    if metadata:
        conversation_state.metadata.update(metadata)

    await redis_storage.save_session(conversation_state)

    logger.info(
        "Created new session in Redis: %s (language: %s, owner: %s)",
        new_session_id,
        language,
        user_id,
    )
    return conversation_state


async def save_conversation(session_id: str, conversation_state: ConversationState):
    """Save conversation state to storage"""
    redis_storage = get_redis_session_storage()
    await redis_storage.save_session(conversation_state)
    logger.info(f"Saved conversation for session: {session_id}")


async def get_last_shown_products(session_id: str) -> Optional[List[Dict]]:
    """
    Retrieve products shown in previous response

    Args:
        session_id: Session identifier

    Returns:
        List of product dicts or None if not found
    """
    try:
        # Try to get from Redis
        from ...database.database import get_redis_client

        redis_client = await get_redis_client()
        if redis_client is None:
            logger.debug("Redis not available - cannot retrieve last products")
            return None

        products_key = f"last_products:{session_id}"
        products_data = await redis_client.get(products_key)

        if products_data:
            products = json.loads(products_data)
            logger.info(
                f"Retrieved {len(products)} products from previous turn for session {session_id}"
            )
            return products

        return None

    except Exception as e:
        logger.warning(f"Could not load last products: {e}")
        return None


async def store_shown_products(session_id: str, products: List[Dict]):
    """
    Store products shown in this response for next turn
    
    Args:
        session_id: Session identifier
        products: List of product dicts to store
    """
    try:
        from ...database.database import get_redis_client

        redis_client = await get_redis_client()
        if redis_client is None:
            logger.warning("Redis not available - products not stored")
            return

        products_key = f"last_products:{session_id}"
        products_json = json.dumps(products)

        # Store for 1 hour
        await redis_client.set(products_key, products_json, ex=3600)

        logger.info(f"Stored {len(products)} products for session {session_id}")

    except Exception as e:
        logger.warning(f"Could not store products: {e}")


@router.post(
    "/message",
    response_model=MessageResponse,
    summary="Process user message in S1→S7 configurator flow",
    description="""
Process natural language messages to build a welding equipment configuration.

**Features:**
- Sequential S1→S7 state machine (PowerSource → Feeder → Cooler → Interconnector → Torch → Accessories → Finalize)
- Compound request handling (specify multiple components in one message)
- Auto-selection when exactly 1 product matches
- Multi-language support (en, es, fr, de, pt, it, sv)
- Session resumption across page reloads
- Product selection from previous responses

**Conversation Flow:**
1. New session: Starts at S1 (power_source_selection)
2. Each state shows compatible products based on previous selections
3. User can specify products naturally or select from numbered list
4. System auto-skips states where applicability = "N"
5. Finalize when minimum requirements met (PowerSource selected)

**Compound Request Examples:**
- "Aristo 500ix with RobustFeed U6" (auto-selects both if unique matches)
- "500A MIG welder for aluminum" (searches PowerSource with parameters)
- "I need a cooler" (searches Cooler compatible with selected PowerSource)

**Special Commands:**
- "skip" - Skip optional component
- "done" - Finish current multi-select state (Accessories)
- "finalize" - Complete configuration (if valid)
- "start over" / "reset" - Start new session
    """,
    response_description="Configuration response with AI message, updated state, products (if showing options), and selection status",
    responses={
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "examples": {
                        "sequential_flow": {
                            "summary": "Sequential Flow - Initial PowerSource Query",
                            "description": "Traditional step-by-step flow starting with power source selection",
                            "value": {
                                "session_id": "abc-123-def-456",
                                "message": "I found several 500A MIG welders:\n\n1. **Aristo 500ix** (GIN: 0446200880)\n   - Current: 500A\n   - Process: MIG/GMAW\n   - Description: Premium inverter power source\n\n2. **Warrior 500i** (GIN: 0449100880)\n   - Current: 500A\n   - Process: MIG/GMAW\n   - Description: Industrial power source\n\nWhich power source would you like? (Enter number or product name)",
                                "current_state": "power_source_selection",
                                "master_parameters": {
                                    "power_source": {
                                        "current_output": "500A",
                                        "process": "MIG"
                                    }
                                },
                                "response_json": {},
                                "products": [
                                    {
                                        "gin": "0446200880",
                                        "item_name": "Aristo 500ix",
                                        "category": "PowerSource",
                                        "description_catalogue": "Premium 500A MIG inverter"
                                    },
                                    {
                                        "gin": "0449100880",
                                        "item_name": "Warrior 500i",
                                        "category": "PowerSource",
                                        "description_catalogue": "Industrial 500A MIG power source"
                                    }
                                ],
                                "awaiting_selection": True,
                                "can_finalize": False,
                                "participants": ["user-123"],
                                "owner_user_id": "user-123",
                                "customer_id": None,
                                "last_updated": "2025-11-02T10:30:00Z"
                            }
                        },
                        "compound_auto_select": {
                            "summary": "Compound Request - Auto-Selection",
                            "description": "User specifies multiple components with unique matches - system auto-selects both",
                            "value": {
                                "session_id": "xyz-789-abc-012",
                                "message": "✅ PowerSource: Aristo 500ix (GIN: 0446200880) - Auto-selected\n✅ Feeder: RobustFeed U6 (GIN: 0460520880) - Auto-selected\n\nCurrent Package:\n• PowerSource: Aristo 500ix\n• Feeder: RobustFeed U6\n\nNext: Would you like to add a Cooler? [Y/N/skip]",
                                "current_state": "cooler_selection",
                                "master_parameters": {
                                    "power_source": {
                                        "product_name": "Aristo 500ix"
                                    },
                                    "feeder": {
                                        "product_name": "RobustFeed U6"
                                    }
                                },
                                "response_json": {
                                    "PowerSource": {
                                        "gin": "0446200880",
                                        "name": "Aristo 500ix",
                                        "category": "PowerSource"
                                    },
                                    "Feeder": {
                                        "gin": "0460520880",
                                        "name": "RobustFeed U6",
                                        "category": "Feeder"
                                    }
                                },
                                "products": [],
                                "awaiting_selection": False,
                                "can_finalize": False,
                                "participants": ["user-456"],
                                "owner_user_id": "user-456",
                                "customer_id": "cust-789",
                                "last_updated": "2025-11-02T10:35:00Z"
                            }
                        },
                        "compound_disambiguation": {
                            "summary": "Compound Request - Disambiguation Required",
                            "description": "User specifies multiple components but one has multiple matches - system asks for clarification",
                            "value": {
                                "session_id": "def-456-ghi-789",
                                "message": "✅ PowerSource: Aristo 500ix (GIN: 0446200880) - Auto-selected\n\nFor Feeder, I found multiple RobustFeed models:\n\n1. **RobustFeed U4** (GIN: 0460510880)\n   - Wire Size: 0.8-1.6mm\n   - Cooling: Water-cooled\n\n2. **RobustFeed U6** (GIN: 0460520880)\n   - Wire Size: 0.8-2.4mm\n   - Cooling: Water-cooled\n\n3. **RobustFeed PRO** (GIN: 0460530880)\n   - Wire Size: 0.8-3.2mm\n   - Cooling: Water-cooled\n\nWhich feeder would you like? (Enter number or product name)",
                                "current_state": "feeder_selection",
                                "master_parameters": {
                                    "power_source": {
                                        "product_name": "Aristo 500ix"
                                    },
                                    "feeder": {
                                        "product_name": "RobustFeed"
                                    }
                                },
                                "response_json": {
                                    "PowerSource": {
                                        "gin": "0446200880",
                                        "name": "Aristo 500ix",
                                        "category": "PowerSource"
                                    }
                                },
                                "products": [
                                    {
                                        "gin": "0460510880",
                                        "item_name": "RobustFeed U4",
                                        "category": "Feeder"
                                    },
                                    {
                                        "gin": "0460520880",
                                        "item_name": "RobustFeed U6",
                                        "category": "Feeder"
                                    },
                                    {
                                        "gin": "0460530880",
                                        "item_name": "RobustFeed PRO",
                                        "category": "Feeder"
                                    }
                                ],
                                "awaiting_selection": True,
                                "can_finalize": False,
                                "participants": ["user-789"],
                                "owner_user_id": "user-789",
                                "customer_id": None,
                                "last_updated": "2025-11-02T10:40:00Z"
                            }
                        },
                        "validation_error": {
                            "summary": "Validation Error - PowerSource Required First",
                            "description": "User tries to specify downstream component without PowerSource - system prompts for PowerSource",
                            "value": {
                                "session_id": "ghi-789-jkl-012",
                                "message": "To configure a Feeder, I first need to know which Power Source you want. Please specify a power source first.\n\nExamples:\n- 'I need a 500A MIG welder'\n- 'Aristo 500ix'\n- '500 amp power source for aluminum'",
                                "current_state": "power_source_selection",
                                "master_parameters": {},
                                "response_json": {},
                                "products": [],
                                "awaiting_selection": False,
                                "can_finalize": False,
                                "participants": ["user-012"],
                                "owner_user_id": "user-012",
                                "customer_id": None,
                                "last_updated": "2025-11-02T10:45:00Z"
                            }
                        }
                    }
                }
            }
        },
        400: {
            "description": "Bad Request - Invalid input parameters",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid language code. Supported: en, es, fr, de, pt, it, sv"
                    }
                }
            }
        },
        500: {
            "description": "Internal Server Error - Processing failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Error processing message: Connection to Neo4j failed"
                    }
                }
            }
        }
    }
)
async def process_configurator_message(
    request: MessageRequest, orchestrator: StateByStateOrchestrator = Depends(get_orchestrator_dep)
):
    """
    Process user message in configurator flow with selection awareness

    Flow:
    1. Get/create conversation state
    2. Load products from previous turn (if any)
    3. Process message with orchestrator (includes selection detection)
    4. Store products for next turn (if any)
    5. Save conversation state
    6. Return response
    """
    try:
        # Get or create conversation state
        conversation_state = await get_or_create_session(
            session_id=request.session_id,
            reset=request.reset,
            language=request.language,
            user_id=request.user_id,
            customer_id=request.customer_id,
            participants=request.participants,
            metadata=request.metadata,
        )

        # ===== CRITICAL: Load last shown products =====
        last_shown_products = await get_last_shown_products(conversation_state.session_id) if conversation_state.session_id else None

        # ===== Process message with orchestrator =====
        result = await orchestrator.process_message(
            conversation_state,
            request.message,
            last_shown_products  # ✅ FIX: Pass products to enable selection detection
        )

        # ===== Store products for next turn =====
        if result.get("products") and len(result.get("products", [])) > 0:
            await store_shown_products(conversation_state.session_id, result["products"])

        # Save updated conversation state
        await save_conversation(conversation_state.session_id, conversation_state)

        # Build response
        response = MessageResponse(
            session_id=conversation_state.session_id,
            message=result.get("message", ""),
            current_state=result.get("current_state", conversation_state.current_state.value),
            master_parameters=conversation_state.master_parameters.dict(),
            response_json=orchestrator._serialize_response_json(conversation_state),
            products=result.get("products", []),
            awaiting_selection=result.get("awaiting_selection", False),
            can_finalize=result.get("can_finalize", False),
            participants=conversation_state.participants,
            owner_user_id=conversation_state.owner_user_id,
            customer_id=conversation_state.customer_id,
            last_updated=_coerce_datetime(conversation_state.last_updated).isoformat(),
            component_statuses=conversation_state.response_json.get_all_component_statuses(),
            pagination=result.get("pagination")  # 🆕 Include pagination metadata
        )

        return response

    except Exception as e:
        logger.error(f"Error in configurator endpoint: {e}", exc_info=True)

        # CRITICAL FIX: Return session_id even in error cases to maintain session continuity
        # Without this, frontend loses session_id and creates new session on retry
        error_session_id = None
        try:
            if 'conversation_state' in locals() and conversation_state:
                error_session_id = conversation_state.session_id
            elif request.session_id:
                error_session_id = request.session_id
        except:
            pass

        # Return structured error response with session_id
        return MessageResponse(
            session_id=error_session_id or str(uuid.uuid4()),  # Fallback to new ID
            message=f"I encountered an error: {str(e)}. Please try again or say 'skip' to continue.",
            current_state="power_source_selection",  # Safe default
            master_parameters={},
            response_json={},
            products=[],
            awaiting_selection=False,
            can_finalize=False,
            participants=request.participants or [],
            owner_user_id=request.user_id,
            customer_id=request.customer_id,
            last_updated=datetime.now(timezone.utc).isoformat(),
            component_statuses={},  # Fixed: dict instead of list
            pagination=None
        )


@router.post(
    "/select",
    response_model=MessageResponse,
    summary="Select a product directly by GIN",
    description="""
Direct product selection endpoint - alternative to natural language selection.

Use this endpoint when you have the exact product GIN (Global Item Number) and want to skip natural language processing.

**Use Cases:**
- UI with "Add to Cart" buttons showing product GINs
- Programmatic configuration building
- Selection from previous search results
- Mobile apps with product catalogs

**How It Works:**
1. Validates session exists (or finds user's latest session)
2. Selects product directly through orchestrator
3. Updates ResponseJSON with selected product
4. Advances state machine to next applicable state
5. Returns updated configuration state

**Requirements:**
- Valid session_id OR user_id must be provided
- product_gin must be valid Neo4j product identifier
- product_data should include product details (name, category, etc.)
    """,
    response_description="Configuration response with confirmation message, updated state, and next steps",
    responses={
        200: {
            "description": "Product selected successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "power_source_selection": {
                            "summary": "PowerSource Selection",
                            "description": "User selects Aristo 500ix as power source",
                            "value": {
                                "session_id": "abc-123-def-456",
                                "message": "✅ Selected: Aristo 500ix (PowerSource)\n\nApplicable components for Aristo 500ix:\n• Feeder: Yes\n• Cooler: Yes\n• Interconnector: Yes\n• Torch: Yes\n• Accessories: Yes\n\nNext: Let's configure your Feeder. What type of feeder do you need?",
                                "current_state": "feeder_selection",
                                "master_parameters": {
                                    "power_source": {
                                        "product_name": "Aristo 500ix"
                                    }
                                },
                                "response_json": {
                                    "PowerSource": {
                                        "gin": "0446200880",
                                        "name": "Aristo 500ix",
                                        "category": "PowerSource"
                                    },
                                    "applicability": {
                                        "Feeder": "Y",
                                        "Cooler": "Y",
                                        "Interconnector": "Y",
                                        "Torch": "Y",
                                        "Accessories": "Y"
                                    }
                                },
                                "products": [],
                                "awaiting_selection": False,
                                "can_finalize": True,
                                "participants": ["user-123"],
                                "owner_user_id": "user-123",
                                "customer_id": None,
                                "last_updated": "2025-11-02T11:00:00Z"
                            }
                        },
                        "feeder_selection": {
                            "summary": "Feeder Selection",
                            "description": "User selects RobustFeed U6 as feeder",
                            "value": {
                                "session_id": "xyz-789-abc-012",
                                "message": "✅ Selected: RobustFeed U6 (Feeder)\n\nCurrent Package:\n• PowerSource: Aristo 500ix\n• Feeder: RobustFeed U6\n\nNext: Would you like to add a Cooler? [Y/N/skip]",
                                "current_state": "cooler_selection",
                                "master_parameters": {
                                    "power_source": {
                                        "product_name": "Aristo 500ix"
                                    },
                                    "feeder": {
                                        "product_name": "RobustFeed U6"
                                    }
                                },
                                "response_json": {
                                    "PowerSource": {
                                        "gin": "0446200880",
                                        "name": "Aristo 500ix",
                                        "category": "PowerSource"
                                    },
                                    "Feeder": {
                                        "gin": "0460520880",
                                        "name": "RobustFeed U6",
                                        "category": "Feeder"
                                    }
                                },
                                "products": [],
                                "awaiting_selection": False,
                                "can_finalize": True,
                                "participants": ["user-456"],
                                "owner_user_id": "user-456",
                                "customer_id": "cust-789",
                                "last_updated": "2025-11-02T11:05:00Z"
                            }
                        }
                    }
                }
            }
        },
        404: {
            "description": "Session not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Session not found"
                    }
                }
            }
        },
        500: {
            "description": "Internal Server Error - Selection failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Error selecting product: Invalid product_gin format"
                    }
                }
            }
        }
    }
)
async def select_product(
    request: SelectProductRequest, orchestrator: StateByStateOrchestrator = Depends(get_orchestrator_dep)
):
    """
    Direct product selection endpoint (alternative to natural language)

    Request body:
        {
            "session_id": "...",
            "user_id": "...",
            "product_gin": "...",
            "product_data": {...}
        }
    """
    try:
        redis_storage = get_redis_session_storage()

        # Resolve session by ID or user context
        conversation_state = None
        resolved_session_id = request.session_id

        if resolved_session_id:
            conversation_state = await redis_storage.get_session(resolved_session_id)

        if not conversation_state and request.user_id:
            conversation_state = await _select_latest_session_for_user(redis_storage, request.user_id)
            if conversation_state:
                resolved_session_id = conversation_state.session_id

        if not conversation_state:
            raise HTTPException(status_code=404, detail="Session not found")

        # Ensure context reflects caller metadata before processing
        if _apply_request_context(
            conversation_state,
            language=None,
            user_id=request.user_id,
            customer_id=None,
            participants=request.participants,
            metadata=request.metadata,
        ):
            await redis_storage.save_session(conversation_state)

        # Select product through orchestrator
        result = await orchestrator.select_product(
            conversation_state,
            request.product_gin,
            request.product_data
        )

        # ===== Store products for next turn (same as /message endpoint) =====
        # This prevents stale products from being re-displayed after state transitions
        if result.get("products") and len(result.get("products", [])) > 0:
            await store_shown_products(resolved_session_id, result["products"])

        # ✅ Add assistant's selection response to conversation history (Phase 8.3 fix)
        conversation_state.add_message(
            "assistant",
            result.get("message", ""),
            products=result.get("products", [])
        )

        # Save updated state
        await save_conversation(resolved_session_id, conversation_state)

        # 🎯 DEBUG: Log products from orchestrator result
        products_from_result = result.get("products", [])
        logger.info(f"🎯 NUGGET DEBUG: Select endpoint received {len(products_from_result)} products from orchestrator")

        # Build response
        response = MessageResponse(
            session_id=conversation_state.session_id,
            message=result.get("message", ""),
            current_state=result.get("current_state", conversation_state.current_state.value),
            master_parameters=conversation_state.master_parameters.dict(),
            response_json=orchestrator._serialize_response_json(conversation_state),
            products=products_from_result,  # ✅ FIX: Use products from orchestrator result
            awaiting_selection=result.get("awaiting_selection", False),  # ✅ FIX: Also get awaiting_selection from result
            can_finalize=conversation_state.can_finalize(),
            participants=conversation_state.participants,
            owner_user_id=conversation_state.owner_user_id,
            customer_id=conversation_state.customer_id,
            last_updated=_coerce_datetime(conversation_state.last_updated).isoformat(),
            component_statuses=conversation_state.response_json.get_all_component_statuses(),
            pagination=result.get("pagination")  # 🆕 Include pagination metadata
        )

        return response

    except Exception as e:
        logger.error(f"Error in select endpoint: {e}", exc_info=True)

        # CRITICAL FIX: Return session_id even in error cases to maintain session continuity
        error_session_id = None
        try:
            if 'conversation_state' in locals() and conversation_state:
                error_session_id = conversation_state.session_id
            elif 'resolved_session_id' in locals() and resolved_session_id:
                error_session_id = resolved_session_id
            elif request.session_id:
                error_session_id = request.session_id
        except:
            pass

        # Return structured error response with session_id
        return MessageResponse(
            session_id=error_session_id or str(uuid.uuid4()),  # Fallback to new ID
            message=f"I encountered an error selecting product: {str(e)}. Please try again.",
            current_state="power_source_selection",  # Safe default
            master_parameters={},
            response_json={},
            products=[],
            awaiting_selection=False,
            can_finalize=False,
            participants=request.participants or [],
            owner_user_id=request.user_id,
            customer_id=None,
            last_updated=datetime.now(timezone.utc).isoformat(),
            component_statuses=[],
            pagination=None
        )


@router.get(
    "/state/{session_id}",
    summary="Retrieve current configuration state",
    description="""
Retrieve the complete configuration state for a session.

**Use Cases:**
- Restore UI state after page reload
- Display configuration progress indicator
- Show current cart/package contents
- Debugging and troubleshooting
- Analytics and reporting

**Response Includes:**
- Current state in S1→S7 flow
- Master parameters (user requirements extracted from conversation)
- Response JSON (selected products/cart)
- Full conversation history
- Finalization status
- Session metadata (participants, owner, timestamps)

**State Values:**
- `power_source_selection` - S1: Selecting power source (mandatory)
- `feeder_selection` - S2: Selecting wire feeder (conditional)
- `cooler_selection` - S3: Selecting cooling system (conditional)
- `interconnector_selection` - S4: Selecting interconnector cable (conditional)
- `torch_selection` - S5: Selecting welding torch (conditional)
- `accessories_selection` - S6: Selecting accessories (multi-select, optional)
- `finalize` - S7: Configuration complete

**Session Lifecycle:**
- Sessions stored in Redis with 1-hour TTL
- TTL refreshed on each message/selection
- Sessions can be archived to PostgreSQL for long-term storage
    """,
    response_description="Complete configuration state with cart, parameters, history, and metadata",
    responses={
        200: {
            "description": "Configuration state retrieved successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "in_progress_configuration": {
                            "summary": "In-Progress Configuration",
                            "description": "Configuration with PowerSource and Feeder selected, at Cooler selection state",
                            "value": {
                                "session_id": "abc-123-def-456",
                                "current_state": "cooler_selection",
                                "master_parameters": {
                                    "power_source": {
                                        "product_name": "Aristo 500ix",
                                        "current_output": "500A",
                                        "process": "MIG"
                                    },
                                    "feeder": {
                                        "product_name": "RobustFeed U6",
                                        "cooling_type": "water-cooled"
                                    }
                                },
                                "response_json": {
                                    "PowerSource": {
                                        "gin": "0446200880",
                                        "name": "Aristo 500ix",
                                        "category": "PowerSource"
                                    },
                                    "Feeder": {
                                        "gin": "0460520880",
                                        "name": "RobustFeed U6",
                                        "category": "Feeder"
                                    },
                                    "applicability": {
                                        "Feeder": "Y",
                                        "Cooler": "Y",
                                        "Interconnector": "Y",
                                        "Torch": "Y",
                                        "Accessories": "Y"
                                    }
                                },
                                "conversation_history": [
                                    {
                                        "role": "user",
                                        "content": "I need a 500A MIG welder",
                                        "timestamp": "2025-11-02T10:00:00Z"
                                    },
                                    {
                                        "role": "assistant",
                                        "content": "I found several 500A MIG welders...",
                                        "timestamp": "2025-11-02T10:00:05Z"
                                    },
                                    {
                                        "role": "user",
                                        "content": "Aristo 500ix",
                                        "timestamp": "2025-11-02T10:00:30Z"
                                    },
                                    {
                                        "role": "assistant",
                                        "content": "✅ Selected: Aristo 500ix...",
                                        "timestamp": "2025-11-02T10:00:35Z"
                                    }
                                ],
                                "can_finalize": True,
                                "participants": ["user-123"],
                                "owner_user_id": "user-123",
                                "customer_id": None,
                                "last_updated": "2025-11-02T10:05:00Z"
                            }
                        },
                        "finalized_configuration": {
                            "summary": "Finalized Configuration",
                            "description": "Complete configuration ready for order/export",
                            "value": {
                                "session_id": "xyz-789-abc-012",
                                "current_state": "finalize",
                                "master_parameters": {
                                    "power_source": {
                                        "product_name": "Aristo 500ix"
                                    },
                                    "feeder": {
                                        "product_name": "RobustFeed U6"
                                    },
                                    "cooler": {
                                        "product_name": "Cool 50"
                                    }
                                },
                                "response_json": {
                                    "PowerSource": {
                                        "gin": "0446200880",
                                        "name": "Aristo 500ix",
                                        "category": "PowerSource"
                                    },
                                    "Feeder": {
                                        "gin": "0460520880",
                                        "name": "RobustFeed U6",
                                        "category": "Feeder"
                                    },
                                    "Cooler": {
                                        "gin": "0470100880",
                                        "name": "Cool 50",
                                        "category": "Cooler"
                                    }
                                },
                                "conversation_history": [],
                                "can_finalize": True,
                                "participants": ["user-456", "user-789"],
                                "owner_user_id": "user-456",
                                "customer_id": "cust-123",
                                "last_updated": "2025-11-02T10:30:00Z"
                            }
                        }
                    }
                }
            }
        },
        404: {
            "description": "Session not found - may have expired or been deleted",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Session not found"
                    }
                }
            }
        },
        500: {
            "description": "Internal Server Error - Failed to retrieve state",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Error getting state: Redis connection failed"
                    }
                }
            }
        }
    }
)
async def get_configuration_state(
    session_id: str,
    orchestrator: StateByStateOrchestrator = Depends(get_orchestrator_dep)
):
    """Get current configuration state"""
    try:
        redis_storage = get_redis_session_storage()
        conversation_state = await redis_storage.get_session(session_id)

        if conversation_state is None:
            raise HTTPException(status_code=404, detail="Session not found")

        return {
            "session_id": session_id,
            "current_state": conversation_state.current_state.value,
            "master_parameters": conversation_state.master_parameters.dict(),
            "response_json": orchestrator._serialize_response_json(conversation_state),
            "conversation_history": conversation_state.conversation_history,
            "can_finalize": conversation_state.can_finalize(),
            "participants": conversation_state.participants,
            "owner_user_id": conversation_state.owner_user_id,
            "customer_id": conversation_state.customer_id,
            "last_updated": _coerce_datetime(conversation_state.last_updated).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting state: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/session/{session_id}",
    summary="Delete/reset configuration session",
    description="""
Delete a configuration session and all associated data.

**Use Cases:**
- User clicks "Start Over" button
- Session cleanup after order completion
- Clearing test/demo sessions
- Manual session management
- Debugging and troubleshooting

**What Gets Deleted:**
- Session data from Redis (ConversationState)
- Stored products from previous turn (`last_products:{session_id}`)
- User-to-session associations in Redis sets

**Important Notes:**
- This does NOT delete archived sessions from PostgreSQL
- User can create a new session immediately after deletion
- Session TTL automatically expires sessions after 1 hour of inactivity
- Cannot recover deleted sessions

**Alternatives to Deletion:**
- Let sessions expire naturally (1-hour TTL)
- Use `reset=true` in POST /message to start fresh session
- Archive to PostgreSQL before deleting (use archive endpoint)
    """,
    response_description="Confirmation of session deletion",
    responses={
        200: {
            "description": "Session deleted successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "successful_deletion": {
                            "summary": "Successful Deletion",
                            "description": "Session and associated data deleted successfully",
                            "value": {
                                "message": "Session reset successfully",
                                "session_id": "abc-123-def-456"
                            }
                        }
                    }
                }
            }
        },
        500: {
            "description": "Internal Server Error - Deletion failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Error resetting session: Redis connection timeout"
                    }
                }
            }
        }
    }
)
async def reset_configuration(session_id: str):
    """Reset/delete configuration session"""
    try:
        from ...database.database import get_redis_client

        redis_storage = get_redis_session_storage()
        redis_client = await get_redis_client()

        # Delete session from storage
        await redis_storage.delete_session(session_id)

        # Delete stored products if Redis available
        if redis_client:
            await redis_client.delete(f"last_products:{session_id}")

        logger.info(f"Deleted session: {session_id}")

        return {"message": "Session reset successfully", "session_id": session_id}

    except Exception as e:
        logger.error(f"Error resetting session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
