"""
Calculator Skill - Advanced mathematical operations
"""
import json
from typing import Dict, Any, Union

def execute(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute calculator operation
    
    Args:
        input_data: {
            "action": "add|subtract|multiply|divide|power",
            "a": first_number,
            "b": second_number
        }
    
    Returns:
        Result with status, output, duration_ms
    """
    import time
    from datetime import datetime
    
    start_time = time.time()
    
    action = input_data.get('action', 'add')
    a = input_data.get('a', 0)
    b = input_data.get('b', 0)
    
    try:
        # Validate inputs
        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            raise ValueError("Both 'a' and 'b' must be numbers")
        
        # Perform operation
        if action == 'add':
            result = a + b
            output = f"{a} + {b} = {result}"
            
        elif action == 'subtract':
            result = a - b
            output = f"{a} - {b} = {result}"
            
        elif action == 'multiply':
            result = a * b
            output = f"{a} × {b} = {result}"
            
        elif action == 'divide':
            if b == 0:
                raise ValueError("Division by zero")
            result = a / b
            output = f"{a} ÷ {b} = {result:.4f}"
            
        elif action == 'power':
            # Handle edge cases
            if a == 0 and b < 0:
                raise ValueError("Zero cannot be raised to a negative power")
            result = a ** b
            output = f"{a}^{b} = {result:.6f}" if abs(result) < 0.001 or abs(result) > 10000 else f"{a}^{b} = {result}"
            
        else:
            raise ValueError(f"Unknown action: {action}")
        
        status = "passed"
        
    except Exception as e:
        result = None
        output = f"Error: {str(e)}"
        status = "failed"
    
    end_time = time.time()
    duration_ms = int((end_time - start_time) * 1000)
    
    return {
        'status': status,
        'output': output,
        'result': result,
        'duration_ms': duration_ms,
        'timestamp': datetime.utcnow().isoformat()
    }


if __name__ == '__main__':
    # Test all operations
    tests = [
        {'action': 'add', 'a': 10, 'b': 5},
        {'action': 'subtract', 'a': 10, 'b': 3},
        {'action': 'multiply', 'a': 7, 'b': 6},
        {'action': 'divide', 'a': 20, 'b': 4},
        {'action': 'power', 'a': 2, 'b': 10}
    ]
    
    print("Testing calculator operations:")
    for test in tests:
        result = execute(test)
        print(f"  {result['status'].upper()}: {result['output']}")
