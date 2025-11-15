import json

from app.models.conversation import ConversationState, get_configurator_state
from app.database import redis_session_storage
import pytest


def test_conversation_state_serializes_enum_value_roundtrip():
    state_enum = get_configurator_state()
    conversation_state = ConversationState(
        session_id="test-session",
        current_state=state_enum.FEEDER_SELECTION,
    )

    payload = conversation_state.model_dump(mode="json")

    assert payload["current_state"] == state_enum.FEEDER_SELECTION.value
    serialized = json.dumps(payload, default=str)
    assert "ConfiguratorState." not in serialized

    restored = ConversationState(**json.loads(serialized))
    assert restored.current_state == state_enum.FEEDER_SELECTION

    legacy_restored = ConversationState(
        session_id="legacy",
        current_state="ConfiguratorState.POWER_SOURCE_SELECTION",
    )
    assert legacy_restored.current_state == state_enum.POWER_SOURCE_SELECTION


@pytest.mark.asyncio
async def test_in_memory_session_storage_when_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_REDIS_CACHING", "false")
    original_redis = redis_session_storage._redis_session_storage
    original_memory = redis_session_storage._in_memory_session_storage
    original_warning = redis_session_storage._fallback_warning_logged

    try:
        redis_session_storage._redis_session_storage = None
        redis_session_storage._in_memory_session_storage = None
        redis_session_storage._fallback_warning_logged = False

        storage = redis_session_storage.get_redis_session_storage()
        assert isinstance(storage, redis_session_storage.InMemorySessionStorage)

        state_enum = get_configurator_state()
        conversation_state = ConversationState(
            session_id="fallback",
            current_state=state_enum.FEEDER_SELECTION,
        )

        await storage.save_session(conversation_state)
        restored = await storage.get_session("fallback")
        assert restored is conversation_state
    finally:
        redis_session_storage._redis_session_storage = original_redis
        redis_session_storage._in_memory_session_storage = original_memory
        redis_session_storage._fallback_warning_logged = original_warning
        monkeypatch.delenv("ENABLE_REDIS_CACHING", raising=False)
