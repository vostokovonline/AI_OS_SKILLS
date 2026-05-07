"""
Hello World Skill for OCCP v1.0 Testing
Simple skill to demonstrate the complete workflow
"""
import datetime
from typing import Dict, Any


def execute(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the hello world skill

    Args:
        input_data: Dictionary containing:
            - action: 'greet' | 'echo' | 'get_timestamp'
            - name: name for greeting (for 'greet' action)
            - message: message to echo (for 'echo' action)

    Returns:
        Result dictionary with status, output, duration_ms
    """
    start_time = datetime.datetime.now()

    action = input_data.get('action', 'greet')

    if action == 'greet':
        name = input_data.get('name', 'World')
        output = f'Hello, {name}! Welcome to OCCP v1.0!'

    elif action == 'echo':
        message = input_data.get('message', 'No message provided')
        output = f'Echo: {message}'

    elif action == 'get_timestamp':
        output = f'Current timestamp: {datetime.datetime.utcnow().isoformat()}'

    else:
        output = f'Unknown action: {action}. Available actions: greet, echo, get_timestamp'

    end_time = datetime.datetime.now()
    duration_ms = int((end_time - start_time).total_seconds() * 1000)

    return {
        'status': 'passed',
        'output': output,
        'duration_ms': duration_ms,
        'timestamp': datetime.datetime.utcnow().isoformat()
    }


if __name__ == '__main__':
    # Test execution
    test_input = {'action': 'greet', 'name': 'OCCP User'}
    result = execute(test_input)
    print(result)
