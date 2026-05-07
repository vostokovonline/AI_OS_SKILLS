#!/usr/bin/env python3
"""
Create sample goal relations for testing
Demonstrates all 4 relation types: causal, dependency, conflict, reinforcement
"""

import requests
import json

API_URL = "http://localhost:8000"

# Get all goals first
def get_goals():
    response = requests.get(f"{API_URL}/goals/list")
    data = response.json()
    return data.get("goals", [])

goals = get_goals()

# Map goal titles to IDs
goal_ids = {g['title']: g['id'] for g in goals}

print("=" * 60)
print("Creating sample goal relations...")
print("=" * 60)
print()

# Define sample relations
relations = [
    # CAUSAL - one goal causes/enables another
    {
        "from": "Создать AI-OS систему",
        "to": "Настроить Dashboard v2",
        "type": "causal",
        "reason": "AI-OS system enables dashboard configuration",
        "strength": 0.9
    },
    {
        "from": "Создать AI-OS систему",
        "to": "Интегрировать Telegram бота",
        "type": "causal",
        "reason": "AI-OS system enables Telegram integration",
        "strength": 0.8
    },

    # DEPENDENCY - one goal depends on another (B must complete before A)
    {
        "from": "Получение устойчивого дохода",
        "to": "Создать AI-OS систему",
        "type": "dependency",
        "reason": "AI-OS system is a means to achieve sustainable income",
        "strength": 1.0
    },
    {
        "from": "Оставить след в истории человечества",
        "to": "Создать AI-OS систему",
        "type": "dependency",
        "reason": "AI-OS could be part of legacy",
        "strength": 0.7
    },

    # CONFLICT - goals compete for resources or are mutually exclusive
    {
        "from": "Помогать близким и родным",
        "to": "Получение устойчивого дохода",
        "type": "conflict",
        "reason": "Time trade-off between family and career",
        "strength": 0.6
    },
    {
        "from": "Помогать близким и родным",
        "to": "Оставить след в истории человечества",
        "type": "conflict",
        "reason": "Both goals compete for time and energy",
        "strength": 0.5
    },

    # REINFORCEMENT - progress on one goal helps another
    {
        "from": "Помогать близким и родным",
        "to": "Оставить след в истории человечества",
        "type": "reinforcement",
        "reason": "Helping family can contribute to legacy",
        "strength": 0.8
    },
    {
        "from": "Настроить Dashboard v2",
        "to": "Оставить след в истории человечества",
        "type": "reinforcement",
        "reason": "Better visualization enables better impact",
        "strength": 0.7
    }
]

created_count = 0
errors = 0

for rel in relations:
    from_id = goal_ids.get(rel["from"])
    to_id = goal_ids.get(rel["to"])

    if not from_id:
        print(f"❌ Goal not found: {rel['from']}")
        errors += 1
        continue
    if not to_id:
        print(f"❌ Goal not found: {rel['to']}")
        errors += 1
        continue

    # Create relation via API
    try:
        response = requests.post(
            f"{API_URL}/relations",
            json={
                "from_goal_id": from_id,
                "to_goal_id": to_id,
                "relation_type": rel["type"],
                "strength": rel["strength"],
                "reason": rel["reason"]
            },
            headers={"Content-Type": "application/json"}
        )

        result = response.json()

        if response.status_code == 200 and result.get("status") == "created":
            type_emoji = {
                "causal": "🔵",
                "dependency": "🟧",
                "conflict": "🔴",
                "reinforcement": "🟢"
            }.get(rel["type"], "•")

            print(f"{type_emoji} {rel['from'][:35]}")
            print(f"   → {rel['to'][:35]}")
            print(f"   Type: {rel['type']}, Strength: {rel['strength']}")
            print(f"   Reason: {rel['reason'][:60]}...")
            print()
            created_count += 1
        else:
            print(f"❌ Failed to create relation: {result}")
            errors += 1

    except Exception as e:
        print(f"❌ Error: {e}")
        errors += 1

print("=" * 60)
print(f"✅ Created {created_count} relations")
if errors > 0:
    print(f"❌ {errors} errors")
print("=" * 60)
