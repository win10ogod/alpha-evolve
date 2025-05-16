#!/usr/bin/env python3
"""
Command-line interface for AlphaEvolve.
"""

import argparse
import asyncio
import os
import sys
import logging
import yaml
import json
from pathlib import Path
from typing import Dict, List, Optional, Any

# Ensure the alphaevolve package is in the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from alphaevolve.core.utils import setup_logging, create_run_directory
from alphaevolve.main import run_alphaevolve

logger = logging.getLogger(__name__)

def create_new_problem(problem_dir: str, problem_name: str) -> None:
    """
    Create a new problem directory with template files.
    
    Args:
        problem_dir: Base directory for all problems
        problem_name: Name of the new problem
    """
    problem_path = os.path.join(problem_dir, problem_name)
    
    if os.path.exists(problem_path):
        raise ValueError(f"Problem directory already exists: {problem_path}")
    
    # Create directory structure
    os.makedirs(problem_path, exist_ok=True)
    os.makedirs(os.path.join(problem_path, 'src'), exist_ok=True)
    os.makedirs(os.path.join(problem_path, 'prompt_templates'), exist_ok=True)
    os.makedirs(os.path.join(problem_path, 'problem_context'), exist_ok=True)
    os.makedirs(os.path.join(problem_path, 'results'), exist_ok=True)
    
    # Create template files
    
    # 1. Sample source file with evolve block
    with open(os.path.join(problem_path, 'src', 'example.py'), 'w', encoding='utf-8') as f:
        f.write("""# Example program to be evolved

def factorial(n):
    # EVOLVE-BLOCK-START factorial
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result
    # EVOLVE-BLOCK-END

def fibonacci(n):
    # EVOLVE-BLOCK-START fibonacci
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
    # EVOLVE-BLOCK-END

if __name__ == "__main__":
    print(f"Factorial of 5: {factorial(5)}")
    print(f"Fibonacci of 10: {fibonacci(10)}")
""")

    # 2. Sample evaluation script
    with open(os.path.join(problem_path, 'evaluate.py'), 'w', encoding='utf-8') as f:
        f.write('''# Evaluation script for the example problem
import time
import importlib.util
import sys
from typing import Dict, Any

def evaluate(program_path: str) -> Dict[str, float]:
    """
    Evaluate a program by loading it and testing its functions.
    
    Args:
        program_path: Path to the program file
        
    Returns:
        Dictionary of performance metrics
    """
    try:
        # Load the program as a module
        spec = importlib.util.spec_from_file_location("program_module", program_path)
        if spec is None or spec.loader is None:
            return {"error": 1.0}
            
        program = importlib.util.module_from_spec(spec)
        sys.modules["program_module"] = program
        spec.loader.exec_module(program)
        
        # Check if the required functions exist
        if not hasattr(program, "factorial") or not hasattr(program, "fibonacci"):
            return {"error": 1.0, "missing_functions": 1.0}
        
        # Test factorial function
        factorial_test_cases = [(0, 1), (1, 1), (5, 120), (10, 3628800)]
        factorial_correct = 0
        
        for n, expected in factorial_test_cases:
            try:
                result = program.factorial(n)
                if result == expected:
                    factorial_correct += 1
            except:
                pass
        
        factorial_accuracy = factorial_correct / len(factorial_test_cases)
        
        # Test fibonacci function
        fibonacci_test_cases = [(0, 0), (1, 1), (5, 5), (10, 55)]
        fibonacci_correct = 0
        
        for n, expected in fibonacci_test_cases:
            try:
                result = program.fibonacci(n)
                if result == expected:
                    fibonacci_correct += 1
            except:
                pass
                
        fibonacci_accuracy = fibonacci_correct / len(fibonacci_test_cases)
        
        # Measure performance (lower is better)
        start_time = time.time()
        try:
            program.factorial(20)
            program.fibonacci(30)
        except:
            pass
        elapsed_time = time.time() - start_time
        
        # Convert to a score (higher is better)
        performance_score = 1.0 / (1.0 + elapsed_time)
        
        # Calculate overall score
        overall_score = (factorial_accuracy + fibonacci_accuracy + performance_score) / 3.0
        
        return {
            "factorial_accuracy": factorial_accuracy,
            "fibonacci_accuracy": fibonacci_accuracy,
            "performance": performance_score,
            "overall": overall_score
        }
        
    except Exception as e:
        print(f"Error evaluating program: {str(e)}")
        return {"error": 1.0, "exception": 1.0}

# Test the evaluate function if run directly
if __name__ == "__main__":
    if len(sys.argv) > 1:
        program_path = sys.argv[1]
        metrics = evaluate(program_path)
        print(metrics)
    else:
        print("Usage: python evaluate.py <program_path>")
''')

    # 3. Sample prompt template
    with open(os.path.join(problem_path, 'prompt_templates', 'improve_code.txt'), 'w', encoding='utf-8') as f:
        f.write("""You are an expert programmer tasked with improving algorithmic code.

CONTEXT:
{context}

PROGRAM TO IMPROVE:
```python
{parent_program}
```

EVALUATION CRITERIA:
{evaluation_criteria}

INSPIRATION FROM OTHER SOLUTIONS:
{inspirations}

YOUR TASK:
Analyze the current implementation and improve it for better performance, correctness, and readability.
Focus on improving the algorithm's efficiency and/or numerical stability.

If you want to modify a specific part, use the following format:
<<<<<<< SEARCH
... code to be replaced ...
=======
... replacement code ...
>>>>>>> REPLACE

If you want to replace the entire program, provide the complete code.

YOUR IMPROVED CODE:
""")

    # 4. Sample context file
    with open(os.path.join(problem_path, 'problem_context', 'algorithms_info.txt'), 'w', encoding='utf-8') as f:
        f.write("""Factorial Function:
The factorial of a non-negative integer n is the product of all positive integers less than or equal to n.
It is denoted by n! and calculated as: n! = n × (n-1) × (n-2) × ... × 2 × 1
For n = 0, the factorial is defined as 0! = 1.

Fibonacci Sequence:
The Fibonacci sequence is a series of numbers where each number is the sum of the two preceding ones, starting from 0 and 1.
F(0) = 0, F(1) = 1, F(n) = F(n-1) + F(n-2) for n > 1

Both functions can be optimized in various ways:
- Recursive implementations with memoization
- Iterative implementations
- Mathematical formulas (e.g., Binet's formula for Fibonacci)
- Tail-recursive implementations

For larger inputs, consider:
- Overflow protection
- Stack usage for recursive implementations
- Time complexity optimizations
""")

    # 5. Config file
    config = {
        "problem_dir": problem_path,
        "controller": {
            "max_iterations": 20,
            "target_score": {"overall": 0.95}
        },
        "program_database": {
            "population_size": 10,
            "archive_mode": "best",
            "metrics": ["overall", "factorial_accuracy", "fibonacci_accuracy", "performance"]
        },
        "llm": {
            "model": "lm_studio/llama-3-8b-instruct",
            "temperature": 0.7,
            "max_tokens": 2048,
            "fallback_models": []
        },
        "evaluation": {
            "max_workers": 2,
            "timeout": 30,
            "use_subprocess": True
        },
        "prompt": {
            "evolve_templates": False,
            "max_context_length": 8000
        }
    }
    
    with open(os.path.join(problem_path, 'config.yaml'), 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False)
    
    print(f"Created new problem directory: {problem_path}")
    print(f"To run AlphaEvolve on this problem, use: alphaevolve run {os.path.join(problem_path, 'config.yaml')}")

def main():
    """Main entry point for the AlphaEvolve CLI."""
    parser = argparse.ArgumentParser(description="AlphaEvolve CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Run AlphaEvolve")
    run_parser.add_argument("config", help="Path to configuration file")
    run_parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    # New problem command
    new_parser = subparsers.add_parser("new", help="Create a new problem")
    new_parser.add_argument("name", help="Name of the new problem")
    new_parser.add_argument("--dir", "-d", default="problems", help="Base directory for problems")
    
    args = parser.parse_args()
    
    if args.command == "run":
        # Set up basic logging
        logging.basicConfig(
            level=logging.DEBUG if args.verbose else logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s"
        )
        
        # Run AlphaEvolve
        try:
            asyncio.run(run_alphaevolve(args.config))
        except Exception as e:
            logger.error(f"Error running AlphaEvolve: {str(e)}", exc_info=args.verbose)
            sys.exit(1)
            
    elif args.command == "new":
        try:
            create_new_problem(args.dir, args.name)
        except Exception as e:
            print(f"Error creating new problem: {str(e)}")
            sys.exit(1)
            
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main() 