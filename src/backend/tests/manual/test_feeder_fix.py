#!/usr/bin/env python3
"""Test the fix for Feeder Lucene scores"""

import requests

# Read session ID from file
with open('/tmp/test_session_id.txt', 'r') as f:
    session_id = f.read().strip()

print(f"Session ID: {session_id}")
print()

# Send explicit Feeder message
response = requests.post(
    "http://localhost:8000/api/v1/configurator/message",
    json={
        "session_id": session_id,
        "message": "I want a water-cooled feeder",
        "language": "en"
    }
)

data = response.json()

print(f"State: {data['current_state']}")
print(f"Products: {len(data.get('products', []))}")
print()
print("Feeder Products (checking for Lucene scores - THE FIX!):")
for i, p in enumerate(data.get('products', [])[:5], 1):
    name = p.get('name', '')
    has_score = 'Score:' in name
    status = '✅' if has_score else '❌'
    print(f"  {i}. {status} {name}")

print()
if any('Score:' in p.get('name', '') for p in data.get('products', [])):
    print("🎉 SUCCESS! Lucene scores are appearing for explicit Feeder messages!")
else:
    print("⚠️  FAILED! Scores still not appearing.")
