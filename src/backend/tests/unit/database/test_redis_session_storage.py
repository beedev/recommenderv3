import pytest

from app.api.v1.configurator import get_or_create_session
from app.models.conversation import ConversationState, get_configurator_state


@pytest.mark.asyncio
async def test_save_and_retrieve_session_with_participants(redis_storage):
    state_enum = get_configurator_state()

    conversation_state = ConversationState(
        session_id="session-1",
        current_state=state_enum.POWER_SOURCE_SELECTION,
        owner_user_id="owner-1",
        participants=["owner-1", "guest-1"],
        metadata={"site": "detroit"},
    )

    await redis_storage.save_session(conversation_state)

    restored = await redis_storage.get_session("session-1")
    assert restored is not None
    assert set(restored.participants) == {"owner-1", "guest-1"}
    assert restored.owner_user_id == "owner-1"
    assert restored.metadata["site"] == "detroit"

    sessions_for_owner = await redis_storage.get_sessions_for_user("owner-1")
    assert "session-1" in sessions_for_owner


@pytest.mark.asyncio
async def test_get_or_create_session_reuses_existing(redis_storage):
    first = await get_or_create_session(user_id="user-1", language="en")
    second = await get_or_create_session(user_id="user-1", language="en")

    assert first.session_id == second.session_id
    assert "user-1" in second.participants


@pytest.mark.asyncio
async def test_get_or_create_session_reset_creates_new(redis_storage):
    initial = await get_or_create_session(user_id="user-reset", language="en")
    reset_session = await get_or_create_session(user_id="user-reset", language="en", reset=True)

    assert initial.session_id != reset_session.session_id
    assert not await redis_storage.session_exists(initial.session_id)
    assert await redis_storage.session_exists(reset_session.session_id)
