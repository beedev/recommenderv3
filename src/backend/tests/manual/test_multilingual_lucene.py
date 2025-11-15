#!/usr/bin/env python3
"""
Test multilingual Lucene fix implementation
Tests Spanish, French, German, and English queries
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_query(message, language, description):
    """Test a single query"""
    print(f"\n{'='*80}")
    print(f"TEST: {description}")
    print(f"{'='*80}")
    print(f"Language: {language}")
    print(f"Message: {message}")
    print()

    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/configurator/message",
            json={
                "message": message,
                "language": language
            },
            timeout=60
        )

        if response.status_code == 200:
            data = response.json()

            print(f"✅ Status: {response.status_code} OK")
            print(f"📊 State: {data.get('current_state')}")
            print(f"🔍 Products Found: {len(data.get('products', []))}")

            if data.get('products'):
                print(f"\nTop 3 Products:")
                for i, product in enumerate(data['products'][:3], 1):
                    print(f"  {i}. {product.get('name')} (GIN: {product.get('gin')})")
            else:
                print(f"\n❌ NO PRODUCTS FOUND")
                print(f"Message: {data.get('message')}")

            return len(data.get('products', [])) > 0
        else:
            print(f"❌ Status: {response.status_code}")
            print(f"Error: {response.text}")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    print("="*80)
    print("MULTILINGUAL LUCENE FIX - TEST SUITE")
    print("="*80)

    # Check server health
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server is healthy")
        else:
            print(f"⚠️  Server health check returned {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Server is not running: {e}")
        print(f"Please start the server first: uvicorn app.main:app --reload")
        return

    # Test queries
    tests = [
        ("Necesito un soldador MIG de 500A", "es", "Spanish: Need MIG welder 500A"),
        ("J'ai besoin d'un soudeur MIG de 500A", "fr", "French: Need MIG welder 500A"),
        ("Ich brauche einen MIG-Schweißer mit 500A", "de", "German: Need MIG welder 500A"),
        ("I need a MIG welder of 500A", "en", "English: Need MIG welder 500A"),
    ]

    results = []
    for message, language, description in tests:
        success = test_query(message, language, description)
        results.append((description, success))

    # Summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for description, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {description}")

    print(f"\n{'='*80}")
    print(f"RESULTS: {passed}/{total} tests passed")
    print(f"{'='*80}")

    if passed == total:
        print("🎉 All tests passed! Multilingual Lucene fix is working correctly.")
    else:
        print("⚠️  Some tests failed. Check logs for details.")

if __name__ == "__main__":
    main()
