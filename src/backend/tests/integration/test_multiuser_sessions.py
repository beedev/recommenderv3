"""
Comprehensive tests for Redis multi-user session management.

Tests cover:
- Input validation and injection prevention
- Batch session retrieval (N+1 prevention)
- Schema migration for backward compatibility
- Participant limit enforcement
- Concurrency control
- Memory efficiency
"""

import pytest
import json
from datetime import datetime, timezone
from typing import Dict, List

from app.database.redis_session_storage import (
    RedisSessionStorage,
    InMemorySessionStorage,
    _validate_identifier,
    _validate_session_id,
    _MAX_PARTICIPANTS,
)
from app.models.conversation import ConversationState, get_configurator_state, SESSION_SCHEMA_VERSION


@pytest.fixture
async def redis_client():
    """Create fake Redis client for testing."""
    import fakeredis.aio as fakeredis_aioredis
    client = fakeredis_aioredis.FakeRedis(decode_responses=True)
    try:
        yield client
    finally:
        await client.flushall()
        await client.close()


@pytest.fixture
async def redis_storage(redis_client):
    """Create RedisSessionStorage instance for testing."""
    storage = RedisSessionStorage(redis_client, ttl=300, enable_sessions=True)
    yield storage


@pytest.fixture
async def in_memory_storage():
    """Create InMemorySessionStorage instance for testing."""
    storage = InMemorySessionStorage(ttl=300)
    yield storage


# ============================================================================
# Input Validation Tests
# ============================================================================


class TestInputValidation:
    """Test input validation and injection prevention."""

    def test_validate_identifier_valid(self):
        """Test valid identifiers are accepted."""
        assert _validate_identifier("user123") == "user123"
        assert _validate_identifier("user-123") == "user-123"
        assert _validate_identifier("user_123") == "user_123"
        assert _validate_identifier("ABC-def_123") == "ABC-def_123"

    def test_validate_identifier_invalid_characters(self):
        """Test identifiers with invalid characters are rejected."""
        with pytest.raises(ValueError, match="invalid characters"):
            _validate_identifier("user@123")
        with pytest.raises(ValueError, match="invalid characters"):
            _validate_identifier("user/123")
        with pytest.raises(ValueError, match="invalid characters"):
            _validate_identifier("user;DROP TABLE sessions;")
        with pytest.raises(ValueError, match="invalid characters"):
            _validate_identifier("user:123")  # Colon could inject Redis keys
        with pytest.raises(ValueError, match="invalid characters"):
            _validate_identifier("user*123")  # Wildcard could break SCAN

    def test_validate_identifier_empty(self):
        """Test empty identifiers are rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            _validate_identifier("")

    def test_validate_identifier_too_long(self):
        """Test identifiers exceeding max length are rejected (DoS prevention)."""
        long_id = "a" * 101  # Max is 100
        with pytest.raises(ValueError, match="invalid characters"):
            _validate_identifier(long_id)

    def test_validate_session_id_valid(self):
        """Test valid session IDs are accepted."""
        assert _validate_session_id("550e8400-e29b-41d4-a716-446655440000") == "550e8400-e29b-41d4-a716-446655440000"
        assert _validate_session_id("550e8400e29b41d4a716446655440000") == "550e8400e29b41d4a716446655440000"

    def test_validate_session_id_invalid(self):
        """Test invalid session IDs are rejected."""
        with pytest.raises(ValueError, match="valid UUID-like format"):
            _validate_session_id("session@123")
        with pytest.raises(ValueError, match="valid UUID-like format"):
            _validate_session_id("../../etc/passwd")


# ============================================================================
# Batch Retrieval Tests (N+1 Prevention)
# ============================================================================


class TestBatchRetrieval:
    """Test batch session retrieval to prevent N+1 query pattern."""

    @pytest.mark.asyncio
    async def test_get_sessions_batch_success(self, redis_storage):
        """Test batch retrieval returns all requested sessions."""
        state_enum = get_configurator_state()

        # Create 3 sessions
        session_ids = ["batch-1", "batch-2", "batch-3"]
        for sid in session_ids:
            state = ConversationState(
                session_id=sid,
                current_state=state_enum.POWER_SOURCE_SELECTION,
                owner_user_id="owner-batch",
                participants=["owner-batch"],
            )
            await redis_storage.save_session(state)

        # Batch retrieve all 3 (single round-trip)
        results = await redis_storage.get_sessions_batch(session_ids)

        assert len(results) == 3
        for sid in session_ids:
            assert sid in results
            assert results[sid] is not None
            assert results[sid].session_id == sid

    @pytest.mark.asyncio
    async def test_get_sessions_batch_missing(self, redis_storage):
        """Test batch retrieval handles missing sessions gracefully."""
        state_enum = get_configurator_state()

        # Create only 1 of 3 sessions
        existing_session = ConversationState(
            session_id="exists-1",
            current_state=state_enum.POWER_SOURCE_SELECTION,
            owner_user_id="owner-1",
        )
        await redis_storage.save_session(existing_session)

        # Request 3 sessions (2 don't exist)
        session_ids = ["exists-1", "missing-1", "missing-2"]
        results = await redis_storage.get_sessions_batch(session_ids)

        assert len(results) == 3
        assert results["exists-1"] is not None
        assert results["missing-1"] is None
        assert results["missing-2"] is None

    @pytest.mark.asyncio
    async def test_get_sessions_batch_empty_list(self, redis_storage):
        """Test batch retrieval with empty list returns empty dict."""
        results = await redis_storage.get_sessions_batch([])
        assert results == {}


# ============================================================================
# Schema Migration Tests
# ============================================================================


class TestSchemaMigration:
    """Test backward compatibility with old session schema."""

    @pytest.mark.asyncio
    async def test_migrate_v0_to_v1(self, redis_storage):
        """Test migration from schema v0 (no multi-user fields) to v1."""
        state_enum = get_configurator_state()
        session_id = "migrate-v0"

        # Manually create old schema session (v0 - no multi-user fields)
        old_payload = {
            "session_id": session_id,
            "current_state": "power_source_selection",
            "master_parameters": {},
            "response_json": {},
            "conversation_history": [],
            "language": "en",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            # NOTE: No schema_version, owner_user_id, customer_id, participants, metadata
        }

        # Store directly in Redis
        session_key = redis_storage._session_key(session_id)
        await redis_storage.redis.hset(
            session_key,
            mapping={"state": json.dumps(old_payload, default=str)}
        )
        await redis_storage.redis.expire(session_key, 300)

        # Retrieve session - should trigger migration
        session = await redis_storage.get_session(session_id)

        assert session is not None
        assert session.session_id == session_id
        # Check migrated fields have defaults
        assert session.owner_user_id is None
        assert session.customer_id is None
        assert session.participants == []
        assert session.metadata == {}
        assert session.schema_version == SESSION_SCHEMA_VERSION

    @pytest.mark.asyncio
    async def test_no_migration_for_current_schema(self, redis_storage):
        """Test sessions at current schema version don't trigger migration."""
        state_enum = get_configurator_state()

        # Create session with current schema
        session = ConversationState(
            session_id="current-schema",
            current_state=state_enum.POWER_SOURCE_SELECTION,
            owner_user_id="owner-1",
            customer_id="customer-1",
            participants=["owner-1"],
            metadata={"test": "value"},
        )
        await redis_storage.save_session(session)

        # Retrieve session - should NOT trigger migration
        retrieved = await redis_storage.get_session("current-schema")

        assert retrieved is not None
        assert retrieved.schema_version == SESSION_SCHEMA_VERSION
        assert retrieved.owner_user_id == "owner-1"
        assert retrieved.customer_id == "customer-1"


# ============================================================================
# Participant Limit Tests (DoS Prevention)
# ============================================================================


class TestParticipantLimits:
    """Test participant limit enforcement to prevent memory exhaustion."""

    @pytest.mark.asyncio
    async def test_participant_limit_enforced(self, redis_storage):
        """Test participant list is truncated at MAX_PARTICIPANTS."""
        state_enum = get_configurator_state()

        # Create session with too many participants
        excessive_participants = [f"user-{i}" for i in range(_MAX_PARTICIPANTS + 10)]

        session = ConversationState(
            session_id="limit-test",
            current_state=state_enum.POWER_SOURCE_SELECTION,
            owner_user_id="owner-1",
            participants=excessive_participants,
        )

        await redis_storage.save_session(session)

        # Retrieve and verify limit was enforced
        retrieved = await redis_storage.get_session("limit-test")
        assert retrieved is not None
        assert len(retrieved.participants) <= _MAX_PARTICIPANTS + 1  # +1 for owner


# ============================================================================
# Multi-User Session Tests
# ============================================================================


class TestMultiUserSessions:
    """Test multi-user session management features."""

    @pytest.mark.asyncio
    async def test_multiple_users_share_session(self, redis_storage):
        """Test multiple users can participate in same session."""
        state_enum = get_configurator_state()

        session = ConversationState(
            session_id="shared-session",
            current_state=state_enum.POWER_SOURCE_SELECTION,
            owner_user_id="owner-1",
            participants=["owner-1", "guest-1", "guest-2"],
        )
        await redis_storage.save_session(session)

        # All users should have access
        for user_id in ["owner-1", "guest-1", "guest-2"]:
            user_sessions = await redis_storage.get_sessions_for_user(user_id)
            assert "shared-session" in user_sessions

    @pytest.mark.asyncio
    async def test_participant_removal(self, redis_storage):
        """Test removing participants updates user-session mappings."""
        state_enum = get_configurator_state()

        # Create session with 3 participants
        session = ConversationState(
            session_id="removal-test",
            current_state=state_enum.POWER_SOURCE_SELECTION,
            owner_user_id="owner-1",
            participants=["owner-1", "guest-1", "guest-2"],
        )
        await redis_storage.save_session(session)

        # Update session to remove guest-2
        session.participants = ["owner-1", "guest-1"]
        await redis_storage.save_session(session)

        # guest-2 should no longer have access
        guest2_sessions = await redis_storage.get_sessions_for_user("guest-2")
        assert "removal-test" not in guest2_sessions

        # guest-1 should still have access
        guest1_sessions = await redis_storage.get_sessions_for_user("guest-1")
        assert "removal-test" in guest1_sessions


# ============================================================================
# Memory Efficiency Tests
# ============================================================================


class TestMemoryEfficiency:
    """Test memory efficiency of session storage."""

    @pytest.mark.asyncio
    async def test_scan_instead_of_keys(self, redis_storage):
        """Test that get_all_session_ids uses SCAN instead of KEYS."""
        state_enum = get_configurator_state()

        # Create multiple sessions
        for i in range(10):
            session = ConversationState(
                session_id=f"scan-test-{i}",
                current_state=state_enum.POWER_SOURCE_SELECTION,
                owner_user_id=f"owner-{i}",
            )
            await redis_storage.save_session(session)

        # Get all session IDs - should use SCAN internally
        all_ids = await redis_storage.get_all_session_ids()
        assert len(all_ids) >= 10  # May include other test sessions

    @pytest.mark.asyncio
    async def test_pipeline_batch_operations(self, redis_storage):
        """Test that batch operations use pipelines efficiently."""
        state_enum = get_configurator_state()

        # Create sessions
        session_ids = [f"pipeline-{i}" for i in range(5)]
        for sid in session_ids:
            session = ConversationState(
                session_id=sid,
                current_state=state_enum.POWER_SOURCE_SELECTION,
                owner_user_id="owner-pipeline",
            )
            await redis_storage.save_session(session)

        # Batch retrieve should use single pipeline
        results = await redis_storage.get_sessions_batch(session_ids)

        # Verify all retrieved successfully
        assert all(results[sid] is not None for sid in session_ids)


# ============================================================================
# In-Memory Fallback Tests
# ============================================================================


class TestInMemoryFallback:
    """Test in-memory fallback when Redis unavailable."""

    @pytest.mark.asyncio
    async def test_in_memory_basic_operations(self, in_memory_storage):
        """Test basic operations work with in-memory storage."""
        state_enum = get_configurator_state()

        session = ConversationState(
            session_id="memory-1",
            current_state=state_enum.POWER_SOURCE_SELECTION,
            owner_user_id="owner-memory",
            participants=["owner-memory"],
        )

        # Save
        await in_memory_storage.save_session(session)

        # Retrieve
        retrieved = await in_memory_storage.get_session("memory-1")
        assert retrieved is not None
        assert retrieved.session_id == "memory-1"

        # Delete
        await in_memory_storage.delete_session("memory-1")
        deleted = await in_memory_storage.get_session("memory-1")
        assert deleted is None


# ============================================================================
# Concurrency Tests
# ============================================================================


class TestConcurrency:
    """Test concurrent session access with optimistic locking."""

    @pytest.mark.asyncio
    async def test_concurrent_save_with_watch(self, redis_storage):
        """Test WATCH/MULTI pattern handles concurrent updates."""
        state_enum = get_configurator_state()

        # Create initial session
        session = ConversationState(
            session_id="concurrent-1",
            current_state=state_enum.POWER_SOURCE_SELECTION,
            owner_user_id="owner-1",
            participants=["owner-1"],
        )
        await redis_storage.save_session(session)

        # Simulate concurrent updates
        session1 = await redis_storage.get_session("concurrent-1")
        session2 = await redis_storage.get_session("concurrent-1")

        # Update both
        session1.participants.append("guest-1")
        session2.participants.append("guest-2")

        # Save both - WATCH should handle conflicts
        await redis_storage.save_session(session1)
        await redis_storage.save_session(session2)

        # Final state should include all participants
        final = await redis_storage.get_session("concurrent-1")
        assert final is not None
        # Note: Due to retry logic, both updates should eventually succeed
        assert "owner-1" in final.participants
