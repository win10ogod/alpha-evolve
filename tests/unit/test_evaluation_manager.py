"""
Unit tests for the evaluation_manager module.
"""

import os
import pytest
import asyncio
from unittest.mock import patch, MagicMock
from alphaevolve.core.evaluation_manager import EvaluationManager

class TestEvaluationManager:
    """Tests for the EvaluationManager class."""
    
    def test_evaluate_function_loading(self, temp_dir):
        """Test loading the evaluate function from a file."""
        # Create a simple evaluate function
        evaluate_path = os.path.join(temp_dir, "evaluate.py")
        with open(evaluate_path, "w") as f:
            f.write("""
def evaluate(program_path):
    return {"score": 0.75}
""")
        
        # Create the evaluation manager
        manager = EvaluationManager(
            evaluate_function_path=evaluate_path,
            working_dir=temp_dir
        )
        
        # Check if the function was loaded correctly
        assert manager.evaluate_function is not None
        assert callable(manager.evaluate_function)
    
    @pytest.mark.asyncio
    async def test_evaluate_in_process(self, temp_dir):
        """Test evaluating a program in the current process."""
        # Create a simple evaluate function
        evaluate_path = os.path.join(temp_dir, "evaluate.py")
        with open(evaluate_path, "w") as f:
            f.write("""
def evaluate(program_path):
    # This is a mock evaluation that just returns fixed scores
    return {"accuracy": 0.9, "performance": 0.8}
""")
        
        # Create the evaluation manager
        manager = EvaluationManager(
            evaluate_function_path=evaluate_path,
            working_dir=temp_dir,
            use_subprocess=False  # Use in-process evaluation
        )
        
        # Create a simple test program
        program_code = "def test(): return 42"
        
        # Evaluate the program
        scores = await manager.evaluate(program_code)
        
        # Check the results
        assert scores["accuracy"] == 0.9
        assert scores["performance"] == 0.8
    
    @pytest.mark.asyncio
    async def test_batch_evaluate(self, temp_dir):
        """Test evaluating multiple programs in parallel."""
        # Create a simple evaluate function
        evaluate_path = os.path.join(temp_dir, "evaluate.py")
        with open(evaluate_path, "w") as f:
            f.write("""
def evaluate(program_path):
    # Return different scores based on the content of the file
    import os
    with open(program_path, 'r') as f:
        content = f.read()
    
    if "v1" in content:
        return {"score": 0.5}
    elif "v2" in content:
        return {"score": 0.7}
    else:
        return {"score": 0.3}
""")
        
        # Create the evaluation manager
        manager = EvaluationManager(
            evaluate_function_path=evaluate_path,
            working_dir=temp_dir,
            max_workers=2  # Use 2 workers for parallel evaluation
        )
        
        # Create multiple test programs
        programs = [
            "def v1(): return 1",
            "def v2(): return 2",
            "def v3(): return 3"
        ]
        
        # Evaluate the programs in batch
        results = await manager.batch_evaluate(programs)
        
        # Check we got results for all programs
        assert len(results) == 3
        
        # Check each program got appropriate scores
        assert any(r.get("score") == 0.5 for r in results)
        assert any(r.get("score") == 0.7 for r in results)
        assert any(r.get("score") == 0.3 for r in results)
    
    @pytest.mark.asyncio
    async def test_cascade_evaluation(self, temp_dir):
        """Test cascading evaluation based on thresholds."""
        # Create a simple evaluate function
        evaluate_path = os.path.join(temp_dir, "evaluate.py")
        with open(evaluate_path, "w") as f:
            f.write("""
def evaluate(program_path):
    # This is a mock evaluation that returns multiple metrics
    return {
        "first_test": 0.6,
        "second_test": 0.8,
        "third_test": 0.4
    }
""")
        
        # Create the evaluation manager with cascade thresholds
        manager = EvaluationManager(
            evaluate_function_path=evaluate_path,
            working_dir=temp_dir,
            cascade_thresholds={
                "first_test": 0.7,  # This will fail
                "second_test": 0.7,  # This would pass
                "third_test": 0.5   # This would fail
            }
        )
        
        # Create a simple test program
        program_code = "def test(): return 42"
        
        # Evaluate with cascade
        scores = await manager.evaluate(program_code, cascade=True)
        
        # Should only get the first failing metric
        assert len(scores) == 1
        assert "first_test" in scores
        assert scores["first_test"] == 0.6
        
        # Evaluate without cascade
        scores = await manager.evaluate(program_code, cascade=False)
        
        # Should get all metrics
        assert len(scores) == 3
        assert scores["first_test"] == 0.6
        assert scores["second_test"] == 0.8
        assert scores["third_test"] == 0.4
    
    @pytest.mark.asyncio
    async def test_evaluation_error_handling(self, temp_dir):
        """Test handling errors during evaluation."""
        # Create an evaluate function that raises an exception
        evaluate_path = os.path.join(temp_dir, "evaluate.py")
        with open(evaluate_path, "w") as f:
            f.write("""
def evaluate(program_path):
    raise ValueError("Simulated evaluation error")
""")
        
        # Create the evaluation manager
        manager = EvaluationManager(
            evaluate_function_path=evaluate_path,
            working_dir=temp_dir
        )
        
        # Create a simple test program
        program_code = "def test(): return 42"
        
        # Evaluate the program
        scores = await manager.evaluate(program_code)
        
        # Should get an error indicator
        assert "error" in scores
        assert scores["error"] == 1.0 