#!/usr/bin/env python3
"""
Create old goals from system history
"""

import requests
import json

API_URL = "http://localhost:8000"

OLD_GOALS = [
    {
        "title": "Оставить след в истории человечества",
        "description": "Создать что-то значимое, что останется после меня и принесет пользу будущим поколениям",
        "goal_type": "achievable",
        "auto_execute": False
    },
    {
        "title": "Помогать близким и родным",
        "description": "Оказывать поддержку и помощь семье, друзьям и близким людям",
        "goal_type": "achievable",
        "auto_execute": False
    },
    {
        "title": "Получение устойчивого дохода",
        "description": "Создать источник стабильного пассивного дохода для финансовой свободы",
        "goal_type": "achievable",
        "auto_execute": False
    }
]

def create_goal(goal_data):
    """Create a single goal"""
    response = requests.post(
        f"{API_URL}/goals/create",
        json=goal_data,
        headers={"Content-Type": "application/json"}
    )
    return response.json()

if __name__ == "__main__":
    print("Creating old goals from system history...")
    print()

    created_goals = []
    for goal in OLD_GOALS:
        print(f"Creating: {goal['title']}")
        result = create_goal(goal)
        print(f"  Result: {result.get('status', 'error')}")
        if 'goal_id' in result:
            created_goals.append({
                'title': goal['title'],
                'id': result['goal_id']
            })
        print()

    print(f"✅ Created {len(created_goals)} goals:")
    for g in created_goals:
        print(f"  • {g['title']}")
        print(f"    ID: {g['id']}")
        print()
