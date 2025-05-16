"""
Unit tests for the program_database module.
"""

import os
import pytest
from alphaevolve.core.program_database import ProgramDatabase, Program

class TestProgramDatabase:
    """Tests for the ProgramDatabase class."""
    
    def test_add_program(self, temp_dir):
        """Test adding a program to the database."""
        db = ProgramDatabase(
            results_dir=temp_dir,
            population_size=5,
            metrics=["accuracy", "performance"]
        )
        
        code = "def test(): return 42"
        scores = {"accuracy": 0.9, "performance": 0.8}
        
        program_id = db.add_program(program=code, scores=scores)
        
        # Check in-memory storage
        assert program_id in db.programs
        assert db.programs[program_id].code == code
        assert db.programs[program_id].scores == scores
        
        # Check disk storage
        json_path = os.path.join(temp_dir, "programs", f"{program_id}.json")
        assert os.path.exists(json_path)
        
        code_path = os.path.join(temp_dir, "programs", f"{program_id}.py")
        assert os.path.exists(code_path)
        
        # Verify file content
        with open(code_path, 'r') as f:
            assert f.read() == code
    
    def test_get_best_program(self, temp_dir):
        """Test getting the best program according to a metric."""
        db = ProgramDatabase(
            results_dir=temp_dir,
            population_size=5,
            metrics=["accuracy", "performance"]
        )
        
        # Add multiple programs
        db.add_program(
            program="def v1(): return 1",
            scores={"accuracy": 0.5, "performance": 0.7}
        )
        
        db.add_program(
            program="def v2(): return 2",
            scores={"accuracy": 0.8, "performance": 0.6}
        )
        
        db.add_program(
            program="def v3(): return 3",
            scores={"accuracy": 0.7, "performance": 0.9}
        )
        
        # Get best by primary metric (accuracy)
        best = db.get_best_program()
        assert best.code == "def v2(): return 2"
        assert best.scores["accuracy"] == 0.8
        
        # Get best by secondary metric
        best_performance = db.get_best_program(metric="performance")
        assert best_performance.code == "def v3(): return 3"
        assert best_performance.scores["performance"] == 0.9
    
    def test_sample_programs(self, temp_dir):
        """Test sampling programs from the database."""
        db = ProgramDatabase(
            results_dir=temp_dir,
            population_size=5,
            metrics=["accuracy"]
        )
        
        # Add multiple programs
        for i in range(5):
            db.add_program(
                program=f"def v{i}(): return {i}",
                scores={"accuracy": 0.5 + i * 0.1}
            )
        
        # Sample parent and inspirations
        parent, inspirations = db.sample_programs()
        
        # Check that we got a valid parent
        assert parent is not None
        assert parent.code.startswith("def v")
        
        # Check inspirations
        assert isinstance(inspirations, list)
        assert all(insp.code.startswith("def v") for insp in inspirations)
        assert all(insp.id != parent.id for insp in inspirations)
    
    def test_update_population(self, temp_dir):
        """Test updating the population when it exceeds the limit."""
        db = ProgramDatabase(
            results_dir=temp_dir,
            population_size=3,  # Small population size for testing
            archive_mode="best",
            metrics=["accuracy"]
        )
        
        # Add more programs than the population size
        for i in range(5):
            db.add_program(
                program=f"def v{i}(): return {i}",
                scores={"accuracy": 0.5 + i * 0.1}
            )
        
        # Should only keep the 3 best programs
        assert len(db.programs) == 3
        
        # The best ones should be kept
        accuracy_values = [p.scores["accuracy"] for p in db.programs.values()]
        assert min(accuracy_values) >= 0.7  # 0.7, 0.8, 0.9
    
    def test_get_pareto_front(self, temp_dir):
        """Test getting the Pareto front of programs."""
        db = ProgramDatabase(
            results_dir=temp_dir,
            population_size=5,
            archive_mode="pareto",
            metrics=["accuracy", "performance"]
        )
        
        # Add various programs with different trade-offs
        db.add_program(
            program="def v1(): return 1",
            scores={"accuracy": 0.9, "performance": 0.5}  # High accuracy, low performance
        )
        
        db.add_program(
            program="def v2(): return 2",
            scores={"accuracy": 0.5, "performance": 0.9}  # Low accuracy, high performance
        )
        
        db.add_program(
            program="def v3(): return 3",
            scores={"accuracy": 0.7, "performance": 0.7}  # Balanced
        )
        
        db.add_program(
            program="def v4(): return 4",
            scores={"accuracy": 0.4, "performance": 0.4}  # Dominated by all others
        )
        
        # Get Pareto front
        pareto_front = db._get_pareto_front()
        
        # v1, v2, v3 should be in the Pareto front, v4 should not
        assert len(pareto_front) == 3
        
        # Convert to set for easier comparison
        program_ids = set(db.programs.keys())
        pareto_front_set = set(pareto_front)
        
        # Find the ID of v4 (the dominated program)
        v4_id = None
        for pid, program in db.programs.items():
            if program.code == "def v4(): return 4":
                v4_id = pid
                break
        
        assert v4_id is not None
        assert v4_id not in pareto_front_set 