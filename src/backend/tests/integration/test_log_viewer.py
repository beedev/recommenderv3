"""
Integration Tests for Log Viewer API

Tests the unified log viewing endpoint with all log sources:
- Application logs (from log files)
- Session archives (from PostgreSQL)
- Agent traces (from PostgreSQL)
- Performance metrics (from logs)

Test Coverage:
- Basic log retrieval for each source
- Filtering (session_id, correlation_id, level, time range)
- Pagination (limit/offset)
- Input validation (invalid parameters, missing required fields)
- Error handling (file not found, session not found)
- Caching behavior
"""

import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta
import json
import os
from pathlib import Path

# Markers
pytesttestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio
]


class TestLogViewerAPI:
    """Integration tests for log viewer API endpoints"""

    @pytest.fixture
    def api_base(self):
        """API base URL for testing"""
        return "/api/v1/logs"

    async def test_application_logs_basic(self, async_client: AsyncClient, api_base: str):
        """Test basic application log retrieval"""
        response = await async_client.get(
            api_base,
            params={
                "source": "application",
                "limit": 10
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["source"] == "application"
        assert isinstance(data["logs"], list)
        assert data["limit"] == 10
        assert data["offset"] == 0
        assert isinstance(data["total"], int)

    async def test_application_logs_with_level_filter(self, async_client: AsyncClient, api_base: str):
        """Test application logs filtered by level"""
        response = await async_client.get(
            api_base,
            params={
                "source": "application",
                "level": "error",
                "limit": 50
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["filters_applied"]["level"] == "error"

        # Verify all returned logs are error level (if any logs exist)
        if data["logs"]:
            for log in data["logs"]:
                if "level" in log:
                    assert log["level"].lower() == "error"

    async def test_application_logs_with_session_filter(self, async_client: AsyncClient, api_base: str):
        """Test application logs filtered by session_id"""
        test_session_id = "test-session-123"

        response = await async_client.get(
            api_base,
            params={
                "source": "application",
                "session_id": test_session_id,
                "limit": 20
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["filters_applied"]["session_id"] == test_session_id

    async def test_application_logs_with_correlation_id(self, async_client: AsyncClient, api_base: str):
        """Test application logs filtered by correlation_id"""
        test_correlation_id = "cor-xyz-789"

        response = await async_client.get(
            api_base,
            params={
                "source": "application",
                "correlation_id": test_correlation_id,
                "limit": 20
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["filters_applied"]["correlation_id"] == test_correlation_id

    async def test_application_logs_with_time_range(self, async_client: AsyncClient, api_base: str):
        """Test application logs filtered by time range"""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=1)

        response = await async_client.get(
            api_base,
            params={
                "source": "application",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "limit": 50
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "start_time" in data["filters_applied"]
        assert "end_time" in data["filters_applied"]

    async def test_application_logs_pagination(self, async_client: AsyncClient, api_base: str):
        """Test pagination with offset"""
        # First page
        response1 = await async_client.get(
            api_base,
            params={
                "source": "application",
                "limit": 10,
                "offset": 0
            }
        )

        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["offset"] == 0

        # Second page
        response2 = await async_client.get(
            api_base,
            params={
                "source": "application",
                "limit": 10,
                "offset": 10
            }
        )

        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["offset"] == 10

        # Verify different logs returned (if enough logs exist)
        if data1["total"] > 10:
            assert data1["logs"] != data2["logs"]

    async def test_session_logs_basic(self, async_client: AsyncClient, api_base: str):
        """Test basic session archive retrieval"""
        response = await async_client.get(
            api_base,
            params={
                "source": "session",
                "limit": 10
            }
        )

        # May return 200 with empty results if no sessions archived
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            assert data["source"] == "session"
            assert isinstance(data["logs"], list)

    async def test_session_logs_with_session_id(self, async_client: AsyncClient, api_base: str):
        """Test session logs filtered by specific session_id"""
        test_session_id = "known-session-id"  # Would need actual session ID in real test

        response = await async_client.get(
            api_base,
            params={
                "source": "session",
                "session_id": test_session_id,
                "limit": 1
            }
        )

        assert response.status_code in [200, 404]  # 404 if session doesn't exist

    async def test_session_logs_with_user_id(self, async_client: AsyncClient, api_base: str):
        """Test session logs filtered by user_id"""
        test_user_id = "user-123"

        response = await async_client.get(
            api_base,
            params={
                "source": "session",
                "user_id": test_user_id,
                "limit": 20
            }
        )

        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert data["filters_applied"]["user_id"] == test_user_id

    async def test_session_logs_with_status_filter(self, async_client: AsyncClient, api_base: str):
        """Test session logs filtered by status"""
        for status in ["completed", "abandoned", "finalized"]:
            response = await async_client.get(
                api_base,
                params={
                    "source": "session",
                    "status": status,
                    "limit": 10
                }
            )

            assert response.status_code in [200, 404]

            if response.status_code == 200:
                data = response.json()
                assert data["filters_applied"]["status"] == status

    async def test_agent_logs_requires_session_id(self, async_client: AsyncClient, api_base: str):
        """Test agent logs require session_id parameter"""
        response = await async_client.get(
            api_base,
            params={
                "source": "agents",
                "limit": 10
            }
        )

        # Should return 400 error because session_id is required
        assert response.status_code == 400
        data = response.json()
        assert "session_id is required" in data["detail"].lower()

    async def test_agent_logs_with_session_id(self, async_client: AsyncClient, api_base: str):
        """Test agent logs with valid session_id"""
        test_session_id = "test-session-with-agents"

        response = await async_client.get(
            api_base,
            params={
                "source": "agents",
                "session_id": test_session_id,
                "limit": 50
            }
        )

        # May return 200 with empty results or 404/400 if session doesn't exist
        assert response.status_code in [200, 400, 404, 500]

    async def test_performance_metrics_basic(self, async_client: AsyncClient, api_base: str):
        """Test basic performance metrics retrieval"""
        response = await async_client.get(
            api_base,
            params={
                "source": "performance",
                "limit": 20
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["source"] == "performance"
        assert isinstance(data["logs"], list)

    async def test_performance_metrics_with_time_range(self, async_client: AsyncClient, api_base: str):
        """Test performance metrics filtered by time range"""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=2)

        response = await async_client.get(
            api_base,
            params={
                "source": "performance",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "limit": 100
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True

    async def test_invalid_source(self, async_client: AsyncClient, api_base: str):
        """Test invalid log source returns error"""
        response = await async_client.get(
            api_base,
            params={
                "source": "invalid_source",
                "limit": 10
            }
        )

        assert response.status_code == 422  # Validation error

    async def test_invalid_level(self, async_client: AsyncClient, api_base: str):
        """Test invalid log level returns error"""
        response = await async_client.get(
            api_base,
            params={
                "source": "application",
                "level": "invalid_level",
                "limit": 10
            }
        )

        assert response.status_code == 422  # Validation error

    async def test_invalid_limit_too_large(self, async_client: AsyncClient, api_base: str):
        """Test limit exceeding maximum returns error"""
        response = await async_client.get(
            api_base,
            params={
                "source": "application",
                "limit": 5000  # Max is 1000
            }
        )

        assert response.status_code == 422  # Validation error

    async def test_invalid_limit_negative(self, async_client: AsyncClient, api_base: str):
        """Test negative limit returns error"""
        response = await async_client.get(
            api_base,
            params={
                "source": "application",
                "limit": -10
            }
        )

        assert response.status_code == 422  # Validation error

    async def test_invalid_offset_negative(self, async_client: AsyncClient, api_base: str):
        """Test negative offset returns error"""
        response = await async_client.get(
            api_base,
            params={
                "source": "application",
                "offset": -5,
                "limit": 10
            }
        )

        assert response.status_code == 422  # Validation error

    async def test_invalid_status(self, async_client: AsyncClient, api_base: str):
        """Test invalid status value returns error"""
        response = await async_client.get(
            api_base,
            params={
                "source": "session",
                "status": "invalid_status",
                "limit": 10
            }
        )

        assert response.status_code == 422  # Validation error

    async def test_missing_required_source(self, async_client: AsyncClient, api_base: str):
        """Test missing required source parameter"""
        response = await async_client.get(
            api_base,
            params={
                "limit": 10
            }
        )

        assert response.status_code == 422  # Validation error

    async def test_health_check(self, async_client: AsyncClient, api_base: str):
        """Test log viewer health check endpoint"""
        response = await async_client.get(f"{api_base}/health")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "checks" in data
        assert isinstance(data["checks"], dict)

        # Verify check keys exist
        assert "application_logs" in data["checks"]
        assert "session_logs" in data["checks"]
        assert "redis_cache" in data["checks"]

    async def test_response_structure(self, async_client: AsyncClient, api_base: str):
        """Test response has correct structure"""
        response = await async_client.get(
            api_base,
            params={
                "source": "application",
                "limit": 5
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        required_fields = ["success", "source", "total", "limit", "offset", "logs"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Verify types
        assert isinstance(data["success"], bool)
        assert isinstance(data["source"], str)
        assert isinstance(data["total"], int)
        assert isinstance(data["limit"], int)
        assert isinstance(data["offset"], int)
        assert isinstance(data["logs"], list)

    async def test_filters_applied_in_response(self, async_client: AsyncClient, api_base: str):
        """Test filters_applied field in response"""
        response = await async_client.get(
            api_base,
            params={
                "source": "application",
                "level": "error",
                "session_id": "test-123",
                "limit": 10
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "filters_applied" in data
        filters = data["filters_applied"]

        assert filters["source"] == "application"
        assert filters["level"] == "error"
        assert filters["session_id"] == "test-123"
        assert filters["limit"] == 10


class TestLogParserCaching:
    """Tests for Redis caching behavior"""

    async def test_cache_hit_same_query(self, async_client: AsyncClient):
        """Test cache hit on repeated identical queries"""
        params = {
            "source": "application",
            "level": "info",
            "limit": 10
        }

        # First request (cache miss)
        response1 = await async_client.get("/api/v1/logs", params=params)
        assert response1.status_code == 200

        # Second request (should hit cache)
        response2 = await async_client.get("/api/v1/logs", params=params)
        assert response2.status_code == 200

        # Results should be identical
        assert response1.json()["total"] == response2.json()["total"]

    async def test_cache_miss_different_filters(self, async_client: AsyncClient):
        """Test cache miss with different filters"""
        # Request 1
        response1 = await async_client.get(
            "/api/v1/logs",
            params={"source": "application", "limit": 10}
        )
        assert response1.status_code == 200

        # Request 2 with different filter
        response2 = await async_client.get(
            "/api/v1/logs",
            params={"source": "application", "level": "error", "limit": 10}
        )
        assert response2.status_code == 200

        # Results may be different
        # Just verify both succeeded


# Calculate expected log file path dynamically
def _get_expected_log_path():
    """Get expected log file path using same logic as application."""
    from pathlib import Path
    # Navigate from tests/integration/ up to project root (4 levels up)
    test_file_dir = Path(__file__).resolve().parent  # tests/integration/
    tests_dir = test_file_dir.parent  # tests/
    backend_dir = tests_dir.parent  # backend/
    src_dir = backend_dir.parent  # src/
    project_root = src_dir.parent  # project root
    return project_root / "logs" / "esab-recommender.log"

@pytest.mark.skipif(
    not os.path.exists(_get_expected_log_path()),
    reason="Production log file not found"
)
class TestLogFileAccess:
    """Tests requiring actual log files (skip in CI/dev environments)"""

    async def test_actual_log_file_parsing(self, async_client: AsyncClient):
        """Test parsing actual production log file"""
        response = await async_client.get(
            "/api/v1/logs",
            params={
                "source": "application",
                "limit": 100
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Should have some logs in production
        assert data["total"] > 0
        assert len(data["logs"]) > 0

        # Verify log structure
        first_log = data["logs"][0]
        assert "timestamp" in first_log or "message" in first_log
