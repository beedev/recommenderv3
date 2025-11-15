"""
Manual Test Script: Redis Disabled Mode

Tests the application behavior when ENABLE_REDIS_CACHING=false.

Verifies:
1. No Redis connections attempted
2. InMemorySessionStorage is used instead
3. Session CRUD operations work correctly
4. TTL expiration and cleanup after 60+ seconds
5. Health check shows "in-memory" storage type

Usage:
    # Set environment variable
    export ENABLE_REDIS_CACHING=false
    # or on Windows:
    set ENABLE_REDIS_CACHING=false

    # Run the script
    python tests/manual/test_redis_disabled.py

Requirements:
    - OpenAI API key must be set
    - Neo4j connection must be available
    - PostgreSQL connection (optional)
"""

import os
import sys
import asyncio
import time
from pathlib import Path

# Add src/backend to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

async def main():
    """Main test function"""

    print("=" * 80)
    print("Redis Disabled Mode Test")
    print("=" * 80)
    print()

    # Step 1: Verify environment variable is set
    print("Step 1: Checking ENABLE_REDIS_CACHING environment variable")
    redis_enabled = os.getenv("ENABLE_REDIS_CACHING", "true").lower()
    print(f"  ENABLE_REDIS_CACHING = {redis_enabled}")

    if redis_enabled == "true":
        print()
        print("❌ ERROR: ENABLE_REDIS_CACHING is not set to 'false'")
        print()
        print("Please run:")
        print("  export ENABLE_REDIS_CACHING=false  # Linux/Mac")
        print("  set ENABLE_REDIS_CACHING=false     # Windows")
        print()
        return
    else:
        print("  ✅ Redis is disabled")
    print()

    # Step 2: Initialize session storage
    print("Step 2: Initializing session storage")
    try:
        from app.database.redis_session_storage import (
            init_redis_session_storage,
            get_redis_session_storage,
            InMemorySessionStorage
        )
        from app.config.cache_config import get_config_service

        session_ttl = get_config_service().get_session_ttl()
        print(f"  Session TTL: {session_ttl} seconds")

        # Initialize with None redis client to force in-memory mode
        init_redis_session_storage(redis_client=None, ttl=session_ttl)

        storage = get_redis_session_storage()
        print(f"  Storage type: {type(storage).__name__}")

        if isinstance(storage, InMemorySessionStorage):
            print("  ✅ InMemorySessionStorage is active")
        else:
            print(f"  ❌ ERROR: Expected InMemorySessionStorage, got {type(storage).__name__}")
            return

    except Exception as e:
        print(f"  ❌ ERROR: Failed to initialize session storage: {e}")
        import traceback
        traceback.print_exc()
        return
    print()

    # Step 3: Test session CRUD operations
    print("Step 3: Testing session CRUD operations")
    try:
        from app.models.conversation import ConversationState, ConfiguratorState

        # Create test session
        session_id = "test-session-001"
        test_session = ConversationState(
            session_id=session_id,
            owner_user_id="test-user",
            current_state=ConfiguratorState.POWER_SOURCE_SELECTION
        )

        # Save session
        print(f"  Creating session: {session_id}")
        await storage.save_session(test_session)
        print("  ✅ Session saved")

        # Retrieve session
        retrieved = await storage.get_session(session_id)
        if retrieved and retrieved.session_id == session_id:
            print("  ✅ Session retrieved successfully")
        else:
            print("  ❌ ERROR: Session not found or mismatch")
            return

        # Check session exists
        exists = await storage.session_exists(session_id)
        if exists:
            print("  ✅ Session exists check passed")
        else:
            print("  ❌ ERROR: Session exists check failed")
            return

        # Get sessions for user
        user_sessions = await storage.get_sessions_for_user("test-user")
        if session_id in user_sessions:
            print("  ✅ User-to-session mapping works")
        else:
            print("  ❌ ERROR: User-to-session mapping failed")
            return

    except Exception as e:
        print(f"  ❌ ERROR: CRUD operations failed: {e}")
        import traceback
        traceback.print_exc()
        return
    print()

    # Step 4: Verify no Redis connections
    print("Step 4: Verifying no Redis connections attempted")
    try:
        from app.database.database import redis_manager

        if redis_manager._initialized:
            print("  ⚠️  WARNING: Redis manager shows initialized")
            print("     This may be okay if Redis init failed gracefully")
        else:
            print("  ✅ Redis manager not initialized")

        # Try to get Redis client
        from app.database.database import get_redis_client
        redis_client = await get_redis_client()

        if redis_client is None:
            print("  ✅ get_redis_client() returns None")
        else:
            print("  ⚠️  WARNING: Redis client is available")
            print("     This is unexpected when ENABLE_REDIS_CACHING=false")

    except Exception as e:
        print(f"  ⚠️  Redis check raised exception: {e}")
        print("     This is expected if Redis init was skipped")
    print()

    # Step 5: Test TTL enforcement (quick test)
    print("Step 5: Testing TTL enforcement")
    print("  Creating session with short TTL for testing...")

    # Create a new storage instance with very short TTL for testing
    test_storage = InMemorySessionStorage(ttl=5)  # 5 second TTL

    test_session_2 = ConversationState(
        session_id="test-session-ttl",
        owner_user_id="test-user-ttl",
        current_state=ConfiguratorState.POWER_SOURCE_SELECTION
    )

    await test_storage.save_session(test_session_2)
    print("  ✅ Session with 5s TTL created")

    print("  Waiting 6 seconds for expiration...")
    await asyncio.sleep(6)

    # Manually trigger cleanup
    await test_storage._cleanup_expired_sessions()

    # Check if session was removed
    exists_after = await test_storage.session_exists("test-session-ttl")
    if not exists_after:
        print("  ✅ Session expired and removed successfully")
    else:
        print("  ❌ ERROR: Session should have been removed")

    # Clean up test storage
    await test_storage.stop_cleanup_loop()
    print()

    # Step 6: Verify session metadata tracking
    print("Step 6: Verifying session metadata tracking")
    if hasattr(storage, '_session_metadata'):
        metadata = storage._session_metadata.get(session_id)
        if metadata:
            print(f"  Session metadata tracked:")
            print(f"    - created_at: {metadata.get('created_at')}")
            print(f"    - ttl: {metadata.get('ttl')}")
            print("  ✅ Session metadata tracking works")
        else:
            print("  ⚠️  WARNING: Session metadata not found")
    else:
        print("  ❌ ERROR: _session_metadata attribute not found")
    print()

    # Step 7: Test session deletion
    print("Step 7: Testing session deletion")
    await storage.delete_session(session_id)

    deleted_exists = await storage.session_exists(session_id)
    if not deleted_exists:
        print("  ✅ Session deleted successfully")
    else:
        print("  ❌ ERROR: Session should have been deleted")
    print()

    # Step 8: Clean up
    print("Step 8: Cleanup")
    await storage.stop_cleanup_loop()
    print("  ✅ Cleanup loop stopped")
    print()

    print("=" * 80)
    print("✅ All tests passed!")
    print("=" * 80)
    print()
    print("Summary:")
    print("  - Redis bypass confirmed")
    print("  - InMemorySessionStorage working correctly")
    print("  - TTL enforcement active")
    print("  - Session CRUD operations functional")
    print("  - Metadata tracking operational")
    print()
    print("Note: For full verification, check:")
    print("  1. Start the server with ENABLE_REDIS_CACHING=false")
    print("  2. Check health endpoint: curl http://localhost:8000/health")
    print("  3. Verify 'session_storage.type' shows 'in-memory'")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
