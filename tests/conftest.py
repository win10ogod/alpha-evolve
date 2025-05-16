"""
Pytest configuration file for AlphaEvolve tests.
"""

import os
import sys
import pytest
import tempfile
import shutil
from typing import Generator, Dict, Any

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """Create a temporary directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def sample_program() -> str:
    """Return a sample program for testing."""
    return """
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
"""

@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """Return a sample configuration for testing."""
    return {
        "problem_dir": "/tmp/test_problem",
        "controller": {
            "max_iterations": 5,
            "target_score": {"overall": 0.95}
        },
        "program_database": {
            "population_size": 5,
            "archive_mode": "best",
            "metrics": ["overall", "performance"]
        },
        "llm": {
            "model": "lm_studio/llama-3-8b-instruct",
            "temperature": 0.7,
            "max_tokens": 1024
        },
        "evaluation": {
            "max_workers": 2,
            "timeout": 10,
            "use_subprocess": True
        },
        "prompt": {
            "evolve_templates": False
        }
    } 