"""
Redis Session Storage Service with multi-user mapping.

Provides session caching with:
- Hash-based session payload storage
- User→session indexing
- Active-session sorted set for lifecycle management
- TTL refresh and concurrency safeguards
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Union

from redis.asyncio import Redis
from redis.exceptions import WatchError

from ..models.conversation import ConversationState, SESSION_SCHEMA_VERSION

logger = logging.getLogger(__name__)

# Validation regex for user IDs and customer IDs
# Allow alphanumeric, hyphens, underscores (safe for Redis keys)
# Max length 100 characters to prevent DoS
_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")
_SESSION_ID_PATTERN = re.compile(r"^[a-fA-F0-9-]{8,50}$")  # UUID-like format
_MAX_PARTICIPANTS = 50  # Prevent memory exhaustion from unlimited participants


def _validate_identifier(identifier: str, field_name: str = "identifier") -> str:
    """
    Validate and sanitize user/customer identifiers for Redis key construction.

    Args:
        identifier: The identifier to validate
        field_name: Name of the field for error messages

    Returns:
        The validated identifier

    Raises:
        ValueError: If identifier is invalid or unsafe
    """
    if not identifier:
        raise ValueError(f"{field_name} cannot be empty")

    if not isinstance(identifier, str):
        raise ValueError(f"{field_name} must be a string, got {type(identifier).__name__}")

    # Check for dangerous characters that could cause injection
    if not _ID_PATTERN.match(identifier):
        raise ValueError(
            f"{field_name} contains invalid characters. "
            f"Only alphanumeric, hyphens, and underscores allowed (max 100 chars)"
        )

    return identifier


def _validate_session_id(session_id: str) -> str:
    """
    Validate session ID format.

    Args:
        session_id: The session ID to validate

    Returns:
        The validated session ID

    Raises:
        ValueError: If session ID is invalid
    """
    if not session_id:
        raise ValueError("session_id cannot be empty")

    if not isinstance(session_id, str):
        raise ValueError(f"session_id must be a string, got {type(session_id).__name__}")

    # Allow UUID-like formats (with or without hyphens)
    if not _SESSION_ID_PATTERN.match(session_id):
        raise ValueError(
            "session_id must be a valid UUID-like format (alphanumeric and hyphens, 8-50 chars)"
        )

    return session_id


def _utc_now() -> datetime:
    """Return timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    """Return ISO formatted UTC string."""
    return _utc_now().isoformat()


class InMemorySessionStorage:
    """
    In-memory fallback for session storage when Redis is unavailable or disabled.

    Mimics Redis-backed behaviour to keep API paths consistent.
    Includes TTL enforcement with background cleanup to prevent memory leaks.
    """

    def __init__(self, ttl: int = 3600):
        self._sessions: Dict[str, ConversationState] = {}
        self._user_sessions: Dict[str, Set[str]] = {}
        self._session_metadata: Dict[str, Dict[str, Any]] = {}  # Track creation time and TTL
        self.ttl = ttl
        self._cleanup_task: Optional[asyncio.Task] = None
        self._shutdown = False

        # Start background cleanup if TTL is enabled
        if self.ttl > 0:
            logger.info(f"Starting in-memory session cleanup task (TTL: {self.ttl}s)")
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    def _session_key(self, session_id: str) -> str:
        """Normalize session key (interface compatibility)."""
        return session_id

    async def save_session(
        self,
        conversation_state: ConversationState,
        *,
        participants: Optional[Iterable[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Store conversation state in memory."""
        session_id = self._session_key(conversation_state.session_id)
        participant_set = set(participants or conversation_state.participants or [])

        if conversation_state.owner_user_id:
            participant_set.add(conversation_state.owner_user_id)

        conversation_state.participants = sorted(participant_set)
        if metadata:
            conversation_state.metadata.update(metadata)

        conversation_state.last_updated = _utc_now()
        conversation_state.schema_version = SESSION_SCHEMA_VERSION

        self._sessions[session_id] = conversation_state

        # Track session creation time for TTL enforcement
        if session_id not in self._session_metadata:
            self._session_metadata[session_id] = {
                "created_at": _utc_now(),
                "ttl": self.ttl
            }
        else:
            # Update last access time
            self._session_metadata[session_id]["last_updated"] = _utc_now()

        for user_id in participant_set:
            self._user_sessions.setdefault(user_id, set()).add(session_id)

        logger.debug("Saved session %s to in-memory storage", conversation_state.session_id)

    async def get_session(self, session_id: str) -> Optional[ConversationState]:
        """Retrieve conversation state from memory."""
        session = self._sessions.get(self._session_key(session_id))
        if session:
            logger.debug("Retrieved session %s from in-memory storage", session_id)
        return session

    async def delete_session(self, session_id: str):
        """Delete session from memory."""
        session_id = self._session_key(session_id)
        conversation_state = self._sessions.pop(session_id, None)
        if conversation_state:
            for user_id in conversation_state.participants:
                sessions = self._user_sessions.get(user_id)
                if not sessions:
                    continue
                sessions.discard(session_id)
                if not sessions:
                    self._user_sessions.pop(user_id, None)
        logger.debug("Deleted session %s from in-memory storage", session_id)

    async def extend_ttl(self, session_id: str, ttl: Optional[int] = None):
        """No-op TTL extension for in-memory storage."""
        logger.debug("TTL extension requested for %s (ignored in-memory)", session_id)

    async def session_exists(self, session_id: str) -> bool:
        """Check if session exists."""
        return self._session_key(session_id) in self._sessions

    async def get_all_session_ids(self) -> List[str]:
        """Return list of session IDs."""
        return sorted(self._sessions.keys())

    async def get_sessions_for_user(self, user_id: str) -> List[str]:
        """Return all session IDs for a user."""
        return sorted(self._user_sessions.get(user_id, set()))

    async def get_sessions_batch(self, session_ids: List[str]) -> Dict[str, Optional[ConversationState]]:
        """Retrieve multiple sessions in one operation (for in-memory parity with Redis)."""
        result = {}
        for session_id in session_ids:
            session_key = self._session_key(session_id)
            result[session_id] = self._sessions.get(session_key)
        return result

    async def link_user_session(self, user_id: str, session_id: str):
        """Associate a user with a session."""
        self._user_sessions.setdefault(user_id, set()).add(self._session_key(session_id))

    async def unlink_user_session(self, user_id: str, session_id: str):
        """Remove association between user and session."""
        sessions = self._user_sessions.get(user_id)
        if not sessions:
            return
        sessions.discard(self._session_key(session_id))
        if not sessions:
            self._user_sessions.pop(user_id, None)

    async def revoke_session(self, session_id: str):
        """Alias for delete_session to mirror Redis behaviour."""
        await self.delete_session(session_id)

    async def touch_session(self, session_id: str):
        """Update session last access time."""
        session_id = self._session_key(session_id)
        if session_id in self._session_metadata:
            self._session_metadata[session_id]["last_updated"] = _utc_now()
        logger.debug("Touch requested for %s (updated last_updated)", session_id)

    async def _cleanup_loop(self):
        """Background task to periodically clean up expired sessions."""
        logger.info("In-memory session cleanup loop started")
        try:
            while not self._shutdown:
                await asyncio.sleep(60)  # Check every 60 seconds
                if self._shutdown:
                    break
                await self._cleanup_expired_sessions()
        except asyncio.CancelledError:
            logger.info("Session cleanup loop cancelled")
        except Exception as e:
            logger.error(f"Error in session cleanup loop: {e}", exc_info=True)

    async def _cleanup_expired_sessions(self):
        """Remove sessions that have exceeded their TTL."""
        now = _utc_now()
        expired_sessions = []

        for session_id, metadata in self._session_metadata.items():
            created_at = metadata.get("created_at")
            if not created_at:
                continue

            # Calculate age in seconds
            age_seconds = (now - created_at).total_seconds()

            if age_seconds > self.ttl:
                expired_sessions.append(session_id)

        if expired_sessions:
            logger.info(f"Cleaning up {len(expired_sessions)} expired sessions")
            for session_id in expired_sessions:
                await self.delete_session(session_id)
                self._session_metadata.pop(session_id, None)
            logger.debug(f"Removed expired sessions: {expired_sessions}")

    async def stop_cleanup_loop(self):
        """Stop the background cleanup task gracefully."""
        self._shutdown = True
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("In-memory session cleanup task stopped")


class RedisSessionStorage:
    """
    Redis-backed session storage service.

    Features:
    - Session caching with configurable TTL
    - Hash-based payload storage for structured metadata
    - Session lifecycle management and user mapping
    """

    def __init__(
        self,
        redis_client: Redis,
        ttl: int = 3600,
        *,
        namespace: str = "configurator:sessions",
        enable_sessions: bool = True,
    ):
        """
        Initialize Redis session storage.

        Args:
            redis_client: Redis async client
            ttl: Time-to-live for sessions in seconds (default: 3600 = 1 hour)
            namespace: Base key namespace
            enable_sessions: Feature flag for full session caching behaviour
        """
        self.redis = redis_client
        self.ttl = ttl
        self.namespace = namespace.rstrip(":")
        self.user_namespace = f"{self.namespace}:user"
        self.active_sessions_key = f"{self.namespace}:active"
        self.enable_sessions = enable_sessions
        self.schema_version = SESSION_SCHEMA_VERSION

    def _session_key(self, session_id: str) -> str:
        """Generate Redis key for session ID."""
        validated_id = _validate_session_id(session_id)
        return f"{self.namespace}:{validated_id}"

    def _user_sessions_key(self, user_id: str) -> str:
        """Generate Redis key for user-session mapping set."""
        validated_id = _validate_identifier(user_id, "user_id")
        return f"{self.user_namespace}:{validated_id}"

    def _migrate_session_schema(self, payload: Dict[str, Any], session_id: str) -> bool:
        """
        Migrate session payload from old schema to current schema.

        Args:
            payload: Session payload dictionary (will be mutated in-place)
            session_id: Session ID for logging

        Returns:
            True if migration was performed, False otherwise
        """
        stored_version = payload.get("schema_version", 0)

        # No migration needed if already at current version
        if stored_version == self.schema_version:
            return False

        logger.info(
            "Migrating session %s from schema v%d to v%d",
            session_id,
            stored_version,
            self.schema_version,
        )

        # Migration from v0 (no schema_version) to v1 (adds multi-user fields)
        if stored_version == 0:
            # Add missing multi-user fields with defaults
            if "owner_user_id" not in payload:
                payload["owner_user_id"] = None
            if "customer_id" not in payload:
                payload["customer_id"] = None
            if "participants" not in payload:
                payload["participants"] = []
            if "metadata" not in payload:
                payload["metadata"] = {}

            # Update schema version
            payload["schema_version"] = 1

        # Add future migrations here as schema evolves
        # if stored_version == 1:
        #     # Migration from v1 to v2
        #     payload["new_field"] = default_value
        #     payload["schema_version"] = 2

        return True

    async def save_session(
        self,
        conversation_state: ConversationState,
        *,
        participants: Optional[Iterable[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Save conversation state to Redis with TTL and user mapping.

        Args:
            conversation_state: Conversation state to save
            participants: Optional explicit participants list
            metadata: Optional metadata patch merged into state metadata
        """
        if not self.enable_sessions:
            logger.debug("Redis session caching disabled – skipping save")
            return

        session_key = self._session_key(conversation_state.session_id)
        now = _utc_now()
        now_iso = now.isoformat()
        now_ts = now.timestamp()

        # Validate and sanitize participants
        participant_set: Set[str] = set()
        for participant in (participants or conversation_state.participants or []):
            if participant:
                try:
                    validated_participant = _validate_identifier(participant, "participant")
                    participant_set.add(validated_participant)

                    # Enforce participant limit to prevent DoS
                    if len(participant_set) > _MAX_PARTICIPANTS:
                        logger.warning(
                            f"Participant limit ({_MAX_PARTICIPANTS}) exceeded for session {conversation_state.session_id}"
                        )
                        break
                except ValueError as e:
                    logger.warning(f"Skipping invalid participant ID: {e}")
                    continue

        # Validate and add owner
        if conversation_state.owner_user_id:
            try:
                # Quick fix: replace spaces in owner_user_id
                conversation_state.owner_user_id = conversation_state.owner_user_id.replace(' ', '-')

                validated_owner = _validate_identifier(conversation_state.owner_user_id, "owner_user_id")
                participant_set.add(validated_owner)
                conversation_state.owner_user_id = validated_owner
            except ValueError as e:
                logger.error(f"Invalid owner_user_id: {e}")
                raise

        # Validate customer_id if present
        if conversation_state.customer_id:
            try:
                conversation_state.customer_id = _validate_identifier(
                    conversation_state.customer_id, "customer_id"
                )
            except ValueError as e:
                logger.warning(f"Invalid customer_id, clearing: {e}")
                conversation_state.customer_id = None

        conversation_state.participants = sorted(participant_set)
        conversation_state.last_updated = now
        conversation_state.schema_version = self.schema_version

        if metadata:
            conversation_state.metadata.update(metadata)

        state_payload = conversation_state.model_dump(mode="json")
        # Ensure enum stored as value string for explicit compatibility
        state_payload["current_state"] = conversation_state.current_state.value
        state_payload["last_updated"] = now_iso
        state_payload["schema_version"] = self.schema_version

        session_hash = {
            "currentState": conversation_state.current_state.value,
            "state": json.dumps(state_payload, default=str),
            "language": conversation_state.language,
            "lastTouched": now_iso,
            "schemaVersion": str(self.schema_version),
            "participants": json.dumps(conversation_state.participants),
            "metadata": json.dumps(conversation_state.metadata or {}),
            "ownerUserId": conversation_state.owner_user_id or "",
            "customerId": conversation_state.customer_id or "",
        }

        while True:
            try:
                async with self.redis.pipeline(transaction=True) as pipe:
                    await pipe.watch(session_key)
                    existing_participants_raw = await pipe.hget(session_key, "participants")
                    existing_participants: Set[str] = set()
                    if existing_participants_raw:
                        try:
                            existing_participants = set(json.loads(existing_participants_raw))
                        except json.JSONDecodeError:
                            existing_participants = set()

                    added_participants = participant_set - existing_participants
                    removed_participants = existing_participants - participant_set

                    pipe.multi()
                    pipe.hset(session_key, mapping=session_hash)
                    pipe.expire(session_key, self.ttl)
                    pipe.zadd(self.active_sessions_key, {conversation_state.session_id: now_ts})
                    pipe.expire(self.active_sessions_key, max(self.ttl, 2 * self.ttl))

                    for user_id in added_participants:
                        if not user_id:
                            continue
                        user_key = self._user_sessions_key(user_id)
                        pipe.sadd(user_key, conversation_state.session_id)
                        pipe.expire(user_key, self.ttl)

                    for user_id in removed_participants:
                        if not user_id:
                            continue
                        pipe.srem(self._user_sessions_key(user_id), conversation_state.session_id)

                    await pipe.execute()
                    # After successful pipe.execute()
                    for _ in range(3):
                        cached = await self.redis.hget(session_key, "state")
                        if not cached:
                            await asyncio.sleep(0.05)
                            continue
 
                        decoded = cached.decode("utf-8") if isinstance(cached, (bytes, bytearray)) else cached
                        if decoded == session_hash["state"]:
                            break
 
                        logger.warning(f"Redis visibility delay for {conversation_state.session_id}, retrying...")
                        await asyncio.sleep(0.05)

                    logger.info("Saved session %s to Redis (TTL: %ss)", conversation_state.session_id, self.ttl)
                    break

            except WatchError:
                logger.debug("Watch conflict while saving session %s, retrying", conversation_state.session_id)
                continue
            except Exception as exc:
                logger.error("Failed to save session %s to Redis: %s", conversation_state.session_id, exc)
                raise

    async def get_session(self, session_id: str) -> Optional[ConversationState]:
        """
        Retrieve conversation state from Redis.

        Args:
            session_id: Session ID to retrieve

        Returns:
            ConversationState or None if not found
        """
        if not self.enable_sessions:
            logger.debug("Redis session caching disabled – get_session short-circuited")
            return None

        session_key = self._session_key(session_id)
        try:
            session_hash = await self.redis.hgetall(session_key)
            if not session_hash:
                logger.debug("Session %s not found in Redis", session_id)
                return None

            state_json = session_hash.get("state")
            if not state_json:
                logger.warning("Session %s missing state payload", session_id)
                return None

            payload: Dict[str, Any] = json.loads(state_json)

            # Schema migration: Add missing fields from new schema version
            migrated = self._migrate_session_schema(payload, session_id)

            session = ConversationState(**payload)

            # If schema was migrated, save the updated session
            if migrated:
                logger.info("Migrated session %s to schema v%d", session_id, self.schema_version)
                await self.save_session(session)
            else:
                # Touch TTL asynchronously for non-migrated sessions
                await self.touch_session(session_id)

            logger.info("Retrieved session %s from Redis", session_id)
            return session

        except Exception as exc:
            logger.error("Failed to retrieve session %s from Redis: %s", session_id, exc)
            return None

    async def get_sessions_batch(self, session_ids: List[str]) -> Dict[str, Optional[ConversationState]]:
        """
        Retrieve multiple sessions in a single batch operation (optimized for N+1 prevention).

        Args:
            session_ids: List of session IDs to retrieve

        Returns:
            Dict mapping session_id to ConversationState (or None if not found)
        """
        if not self.enable_sessions:
            logger.debug("Redis session caching disabled – batch get short-circuited")
            return {sid: None for sid in session_ids}

        if not session_ids:
            return {}

        results: Dict[str, Optional[ConversationState]] = {}

        try:
            # Use pipeline for efficient batch retrieval
            async with self.redis.pipeline(transaction=False) as pipe:
                # Queue all HGETALL commands
                for session_id in session_ids:
                    session_key = self._session_key(session_id)
                    pipe.hgetall(session_key)

                # Execute all commands in single round-trip
                session_hashes = await pipe.execute()

            # Parse results
            for session_id, session_hash in zip(session_ids, session_hashes):
                if not session_hash:
                    results[session_id] = None
                    continue

                state_json = session_hash.get("state")
                if not state_json:
                    logger.warning("Session %s missing state payload", session_id)
                    results[session_id] = None
                    continue

                try:
                    payload: Dict[str, Any] = json.loads(state_json)
                    session = ConversationState(**payload)
                    results[session_id] = session
                except Exception as parse_exc:
                    logger.error("Failed to parse session %s: %s", session_id, parse_exc)
                    results[session_id] = None

            logger.info("Retrieved %d sessions in batch (requested: %d)", len([s for s in results.values() if s]), len(session_ids))
            return results

        except Exception as exc:
            logger.error("Failed to retrieve sessions in batch: %s", exc)
            # Return empty results on error
            return {sid: None for sid in session_ids}

    async def delete_session(self, session_id: str):
        """
        Delete session from Redis.

        Args:
            session_id: Session ID to delete
        """
        if not self.enable_sessions:
            logger.debug("Redis session caching disabled – delete_session ignored")
            return

        session_key = self._session_key(session_id)
        while True:
            try:
                async with self.redis.pipeline(transaction=True) as pipe:
                    await pipe.watch(session_key)
                    participants_raw = await pipe.hget(session_key, "participants")
                    participants: Set[str] = set()
                    if participants_raw:
                        try:
                            participants = set(json.loads(participants_raw))
                        except json.JSONDecodeError:
                            participants = set()

                    pipe.multi()
                    pipe.delete(session_key)
                    pipe.zrem(self.active_sessions_key, session_id)
                    for user_id in participants:
                        if user_id:
                            pipe.srem(self._user_sessions_key(user_id), session_id)
                    await pipe.execute()
                    logger.info("Deleted session %s from Redis", session_id)
                    break
            except WatchError:
                logger.debug("Watch conflict while deleting session %s, retrying", session_id)
                continue
            except Exception as exc:
                logger.error("Failed to delete session %s from Redis: %s", session_id, exc)
                break

    async def extend_ttl(self, session_id: str, ttl: Optional[int] = None):
        """
        Extend TTL for an existing session and refresh activity markers.
        """
        if not self.enable_sessions:
            return

        session_key = self._session_key(session_id)
        new_ttl = ttl or self.ttl
        now = _utc_now()
        try:
            async with self.redis.pipeline(transaction=False) as pipe:
                pipe.expire(session_key, new_ttl)
                pipe.hset(session_key, mapping={"lastTouched": now.isoformat()})
                pipe.zadd(self.active_sessions_key, {session_id: now.timestamp()})
                await pipe.execute()
        except Exception as exc:
            logger.error("Failed to extend TTL for session %s: %s", session_id, exc)

    async def touch_session(self, session_id: str):
        """Refresh TTL and activity timestamp without altering payload."""
        await self.extend_ttl(session_id)

    async def session_exists(self, session_id: str) -> bool:
        """Check if session exists in Redis."""
        if not self.enable_sessions:
            return False

        try:
            exists = await self.redis.exists(self._session_key(session_id))
            return bool(exists)
        except Exception as exc:
            logger.error("Failed to check session existence for %s: %s", session_id, exc)
            return False

    async def get_all_session_ids(self) -> List[str]:
        """Get all active session IDs from Redis."""
        if not self.enable_sessions:
            return []

        try:
            session_ids = await self.redis.zrange(self.active_sessions_key, 0, -1)
            if session_ids:
                return [sid for sid in session_ids if sid]

            # fallback to scanning keys when sorted set empty (initial state)
            # Use SCAN instead of KEYS to avoid blocking Redis
            pattern = f"{self.namespace}:*"
            session_ids = []
            cursor = 0

            while True:
                cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
                for key in keys:
                    # Extract session_id from key
                    session_id = key.replace(f"{self.namespace}:", "")
                    if session_id:
                        session_ids.append(session_id)

                if cursor == 0:
                    break

            return session_ids

        except Exception as exc:
            logger.error("Failed to get all session IDs: %s", exc)
            return []

    async def get_sessions_for_user(self, user_id: str) -> List[str]:
        """Return all active session IDs for a user."""
        if not self.enable_sessions:
            return []

        try:
            session_ids = await self.redis.smembers(self._user_sessions_key(user_id))
            return sorted(session_ids)
        except Exception as exc:
            logger.error("Failed to fetch sessions for user %s: %s", user_id, exc)
            return []

    async def link_user_session(self, user_id: str, session_id: str):
        """Associate a user with a session."""
        if not self.enable_sessions:
            return

        try:
            user_key = self._user_sessions_key(user_id)
            async with self.redis.pipeline(transaction=False) as pipe:
                pipe.sadd(user_key, session_id)
                pipe.expire(user_key, self.ttl)
                await pipe.execute()
        except Exception as exc:
            logger.error("Failed to link user %s to session %s: %s", user_id, session_id, exc)

    async def unlink_user_session(self, user_id: str, session_id: str):
        """Remove association between a user and a session."""
        if not self.enable_sessions:
            return

        try:
            await self.redis.srem(self._user_sessions_key(user_id), session_id)
        except Exception as exc:
            logger.error("Failed to unlink user %s from session %s: %s", user_id, session_id, exc)

    async def revoke_session(self, session_id: str):
        """Alias for delete_session to support administrative revocation."""
        await self.delete_session(session_id)


# Global service instances (will be initialized in main.py)
_redis_session_storage: Optional[RedisSessionStorage] = None
_in_memory_session_storage: Optional[InMemorySessionStorage] = None
_fallback_warning_logged: bool = False


def _redis_disabled() -> bool:
    """Check if Redis caching has been explicitly disabled."""
    caching_disabled = os.getenv("ENABLE_REDIS_CACHING", "true").lower() == "false"
    sessions_disabled = os.getenv("ENABLE_REDIS_SESSIONS", "true").lower() == "false"
    return caching_disabled or sessions_disabled


def _get_in_memory_session_storage(ttl: int = 3600) -> InMemorySessionStorage:
    """Lazily initialize and return the in-memory session storage."""
    global _in_memory_session_storage

    if _in_memory_session_storage is None:
        _in_memory_session_storage = InMemorySessionStorage(ttl=ttl)
        logger.info("Initialized in-memory session storage fallback")

    return _in_memory_session_storage


def get_redis_session_storage() -> Union[RedisSessionStorage, InMemorySessionStorage]:
    """
    Get session storage instance.

    Returns Redis-backed storage when available, otherwise falls back to in-memory storage
    if Redis is disabled or not initialized.
    """
    global _redis_session_storage

    if _redis_session_storage is not None:
        return _redis_session_storage

    if _redis_disabled():
        return _get_in_memory_session_storage()

    global _fallback_warning_logged
    if not _fallback_warning_logged:
        logger.warning(
            "Redis session storage requested before initialization. Falling back to in-memory storage."
        )
        _fallback_warning_logged = True

    return _get_in_memory_session_storage()


def init_redis_session_storage(
    redis_client: Optional[Redis],
    ttl: int = 3600,
    enable_caching: Optional[bool] = None,
    enable_sessions: Optional[bool] = None,
):
    """Initialize global Redis session storage instance."""
    global _redis_session_storage, _fallback_warning_logged

    if enable_caching is None:
        enable_caching = os.getenv("ENABLE_REDIS_CACHING", "true").lower() == "true"

    if enable_sessions is None:
        enable_sessions = os.getenv("ENABLE_REDIS_SESSIONS", "true").lower() == "true"

    if redis_client is None or not enable_caching or not enable_sessions:
        _redis_session_storage = None
        _fallback_warning_logged = False
        _get_in_memory_session_storage(ttl=ttl)
        logger.info("Redis client unavailable or sessions disabled; using in-memory session storage")
        return

    _redis_session_storage = RedisSessionStorage(
        redis_client,
        ttl,
        enable_sessions=enable_sessions,
    )
    _fallback_warning_logged = False
    logger.info("Redis session storage initialized (TTL: %ss)", ttl)
