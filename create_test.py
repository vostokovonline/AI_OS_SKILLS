#!/usr/bin/env python3
import requests
import json

# Create 5 fresh test goals
for i in range(5):
    resp = requests.post("http://localhost:8000/goals/create", json={
        "title": f"Fresh file test {i}",
        "description": "Create a simple text file",
        "goal_type": "achievable",
        "is_atomic": True
    }, timeout=10)
    data = resp.json()
    print(f"Created: {data.get('goal_id', 'error')}")

print("All created")