"""
Test Health Endpoints - Phase 5
Verify configuration monitoring and health check endpoints
"""

import sys
import os
import asyncio

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.config.config_monitor import init_config_monitor, get_config_monitor
from app.services.config.config_validator import get_validator


async def test_health_endpoints():
    """Test configuration monitoring and health checks"""

    print("=" * 70)
    print("Testing Health Endpoints & Config Monitor (Phase 5)")
    print("=" * 70)
    print()

    # Initialize validator first
    print("[1/7] Initializing config validator...")
    try:
        validator = get_validator()
        print("[OK] Config validator initialized")
    except Exception as e:
        print(f"[ERROR] Failed to initialize validator: {e}")
        return False

    # Initialize monitor
    print("\n[2/7] Initializing config monitor...")
    try:
        monitor = init_config_monitor()
        print("[OK] Config monitor initialized")
    except Exception as e:
        print(f"[ERROR] Failed to initialize monitor: {e}")
        return False

    # Test individual config validation
    print("\n[3/7] Testing individual config validation...")
    test_configs = [
        "component_types",
        "state_prompts",
        "powersource_state_specifications"
        # Note: master_parameter_schema doesn't have a schema file - it's validated dynamically
    ]

    all_passed = True
    for config_name in test_configs:
        try:
            health = monitor.validate_config(config_name)
            status_icon = "[OK]" if health.status.value == "healthy" else "[WARNING]"
            print(f"{status_icon} {config_name}: {health.status.value}")

            if health.validation_errors:
                print(f"     Errors: {health.validation_errors}")
                all_passed = False

            if health.validation_warnings:
                print(f"     Warnings: {health.validation_warnings}")

        except Exception as e:
            print(f"[ERROR] {config_name}: {e}")
            all_passed = False

    # Test system-wide health
    print("\n[4/7] Testing system-wide health check...")
    try:
        system_health = monitor.validate_all_configs()
        print(f"[OK] System status: {system_health.status.value}")
        print(f"     Total configs: {system_health.total_configs}")
        print(f"     Healthy: {system_health.healthy_configs}")
        print(f"     Warnings: {system_health.warning_configs}")
        print(f"     Errors: {system_health.error_configs}")

        if system_health.error_configs > 0:
            all_passed = False

    except Exception as e:
        print(f"[ERROR] System health check failed: {e}")
        all_passed = False

    # Test consistency validation
    print("\n[5/7] Testing state consistency validation...")
    try:
        consistency_health = monitor.validate_state_consistency()
        status_icon = "[OK]" if consistency_health.status.value == "healthy" else "[WARNING]"
        print(f"{status_icon} Consistency check: {consistency_health.status.value}")

        if consistency_health.validation_errors:
            print(f"     Errors: {consistency_health.validation_errors}")
            all_passed = False

        if consistency_health.validation_warnings:
            print(f"     Warnings: {consistency_health.validation_warnings}")

    except Exception as e:
        print(f"[ERROR] Consistency check failed: {e}")
        all_passed = False

    # Test applicability validation
    print("\n[6/7] Testing applicability validation...")
    try:
        applicability_health = monitor.validate_applicability_config()
        status_icon = "[OK]" if applicability_health.status.value == "healthy" else "[WARNING]"
        print(f"{status_icon} Applicability check: {applicability_health.status.value}")

        if applicability_health.validation_errors:
            print(f"     Errors: {applicability_health.validation_errors}")
            all_passed = False

        if applicability_health.validation_warnings:
            print(f"     Warnings: {applicability_health.validation_warnings}")

    except Exception as e:
        print(f"[ERROR] Applicability check failed: {e}")
        all_passed = False

    # Test comprehensive health
    print("\n[7/7] Testing comprehensive health check...")
    try:
        comprehensive_health = monitor.get_comprehensive_health()
        print(f"[OK] Comprehensive status: {comprehensive_health.status.value}")
        print(f"     Total checks: {comprehensive_health.total_configs}")
        print(f"     Healthy: {comprehensive_health.healthy_configs}")
        print(f"     Warnings: {comprehensive_health.warning_configs}")
        print(f"     Errors: {comprehensive_health.error_configs}")

        # List all checks
        print("\n     Detailed results:")
        for config_name, health in comprehensive_health.configs.items():
            status_icon = {
                "healthy": "[OK]",
                "warning": "[WARNING]",
                "error": "[ERROR]"
            }.get(health.status.value, "[?]")
            print(f"       {status_icon} {config_name}: {health.status.value}")

        if comprehensive_health.error_configs > 0:
            all_passed = False

    except Exception as e:
        print(f"[ERROR] Comprehensive health check failed: {e}")
        all_passed = False

    # Test cache operations
    print("\n[8/7] Testing cache operations...")
    try:
        # Get cached health
        cached = monitor.get_cached_health("component_types")
        if cached:
            print("[OK] Cache retrieval works")
        else:
            print("[WARNING] No cached health found")

        # Clear cache
        monitor.clear_cache()
        print("[OK] Cache cleared successfully")

        # Verify cache is empty
        cached_after_clear = monitor.get_cached_health("component_types")
        if cached_after_clear is None:
            print("[OK] Cache is empty after clear")
        else:
            print("[WARNING] Cache still has data after clear")

    except Exception as e:
        print(f"[ERROR] Cache operations failed: {e}")
        all_passed = False

    # Summary
    print()
    print("=" * 70)
    if all_passed:
        print("[SUCCESS] Health endpoints & config monitor tests passed!")
        print()
        print("Summary:")
        print("- Config monitor initialized")
        print("- Individual config validation working")
        print("- System-wide health checks working")
        print("- Consistency validation working")
        print("- Applicability validation working")
        print("- Comprehensive health checks working")
        print("- Cache operations working")
        print()
        print("Available API endpoints:")
        print("  GET  /api/v1/health/config")
        print("  GET  /api/v1/health/config/{config_name}")
        print("  GET  /api/v1/health/config/validation/full")
        print("  GET  /api/v1/health/config/consistency")
        print("  GET  /api/v1/health/config/applicability")
        print("  POST /api/v1/health/config/cache/clear")
        return True
    else:
        print("[FAILED] Some tests failed")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_health_endpoints())
    sys.exit(0 if success else 1)
