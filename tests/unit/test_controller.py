"""
Unit tests for the controller module.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from alphaevolve.core.controller import Controller
from alphaevolve.core.program_database import Program

class TestController:
    """Tests for the Controller class."""
    
    @pytest.mark.asyncio
    async def test_controller_initialization(self):
        """Test initializing the controller with mocked components."""
        # Create mock components
        program_db = MagicMock()
        prompt_sampler = MagicMock()
        llm_interface = MagicMock()
        code_patcher = MagicMock()
        evaluator = MagicMock()
        meta_prompter = MagicMock()
        
        # Create controller
        controller = Controller(
            program_db=program_db,
            prompt_sampler=prompt_sampler,
            llm_interface=llm_interface,
            code_patcher=code_patcher,
            evaluator=evaluator,
            meta_prompter=meta_prompter,
            max_iterations=10,
            budget={"llm_calls": 100},
            target_score={"accuracy": 0.95}
        )
        
        # Verify initialization
        assert controller.program_db == program_db
        assert controller.prompt_sampler == prompt_sampler
        assert controller.llm_interface == llm_interface
        assert controller.code_patcher == code_patcher
        assert controller.evaluator == evaluator
        assert controller.meta_prompter == meta_prompter
        assert controller.max_iterations == 10
        assert controller.budget["llm_calls"] == 100
        assert controller.target_score["accuracy"] == 0.95
        assert controller.current_iteration == 0
        assert not controller.stopped
    
    @pytest.mark.asyncio
    async def test_controller_run_iteration(self):
        """Test running a single iteration of the controller."""
        # Mock components
        program_db = MagicMock()
        prompt_sampler = MagicMock()
        llm_interface = AsyncMock()
        code_patcher = MagicMock()
        evaluator = AsyncMock()
        
        # Setup mock returns
        parent_program = Program(
            id="parent123",
            code="def test(): return 42",
            scores={"accuracy": 0.8},
            timestamp="2023-01-01T12:00:00"
        )
        inspirations = []
        program_db.sample_programs.return_value = (parent_program, inspirations)
        
        prompt_sampler.construct_prompt.return_value = "Test prompt"
        
        llm_interface.generate.return_value = "Generated code"
        
        code_patcher.apply_changes.return_value = "Modified code"
        
        evaluator.evaluate.return_value = {"accuracy": 0.85}
        
        # Create controller
        controller = Controller(
            program_db=program_db,
            prompt_sampler=prompt_sampler,
            llm_interface=llm_interface,
            code_patcher=code_patcher,
            evaluator=evaluator,
            max_iterations=1
        )
        
        # Run the controller
        result = await controller.run()
        
        # Verify the iteration was executed correctly
        program_db.sample_programs.assert_called_once()
        prompt_sampler.construct_prompt.assert_called_once_with(
            parent_program=parent_program,
            inspirations=inspirations
        )
        llm_interface.generate.assert_called_once_with("Test prompt")
        code_patcher.apply_changes.assert_called_once_with(
            parent_program=parent_program,
            changes="Generated code"
        )
        evaluator.evaluate.assert_called_once_with("Modified code")
        program_db.add_program.assert_called_once_with(
            program="Modified code",
            scores={"accuracy": 0.85},
            parent_id="parent123"
        )
    
    @pytest.mark.asyncio
    async def test_should_stop_max_iterations(self):
        """Test stopping when max iterations is reached."""
        # Create controller with mocked components
        controller = Controller(
            program_db=MagicMock(),
            prompt_sampler=MagicMock(),
            llm_interface=MagicMock(),
            code_patcher=MagicMock(),
            evaluator=MagicMock(),
            max_iterations=5
        )
        
        # Set iteration to max
        controller.current_iteration = 5
        
        # Check should_stop
        assert controller.should_stop()
    
    @pytest.mark.asyncio
    async def test_should_stop_budget_exceeded(self):
        """Test stopping when budget is exceeded."""
        # Create mocks
        llm_interface = MagicMock()
        llm_interface.call_count = 110  # Exceeds budget
        
        # Create controller
        controller = Controller(
            program_db=MagicMock(),
            prompt_sampler=MagicMock(),
            llm_interface=llm_interface,
            code_patcher=MagicMock(),
            evaluator=MagicMock(),
            max_iterations=100,
            budget={"llm_calls": 100}
        )
        
        # Check should_stop
        assert controller.should_stop()
    
    @pytest.mark.asyncio
    async def test_should_stop_target_met(self):
        """Test stopping when target score is met."""
        # Create mocks
        program_db = MagicMock()
        best_program = Program(
            id="best",
            code="def best(): pass",
            scores={"accuracy": 0.96, "performance": 0.8},
            timestamp="2023-01-01T12:00:00"
        )
        program_db.get_best_program.return_value = best_program
        
        # Create controller
        controller = Controller(
            program_db=program_db,
            prompt_sampler=MagicMock(),
            llm_interface=MagicMock(),
            code_patcher=MagicMock(),
            evaluator=MagicMock(),
            max_iterations=100,
            target_score={"accuracy": 0.95}  # Target is met
        )
        
        # Check should_stop
        assert controller.should_stop()
    
    @pytest.mark.asyncio
    async def test_meta_prompter_evolution(self):
        """Test evolving meta-prompts during controller run."""
        # Mock components
        program_db = MagicMock()
        prompt_sampler = MagicMock()
        llm_interface = AsyncMock()
        code_patcher = MagicMock()
        evaluator = AsyncMock()
        meta_prompter = AsyncMock()
        
        # Setup mock returns for a successful run
        parent_program = Program(
            id="parent123",
            code="def test(): return 42",
            scores={"accuracy": 0.8},
            timestamp="2023-01-01T12:00:00"
        )
        program_db.sample_programs.return_value = (parent_program, [])
        prompt_sampler.construct_prompt.return_value = "Test prompt"
        llm_interface.generate.return_value = "Generated code"
        code_patcher.apply_changes.return_value = "Modified code"
        evaluator.evaluate.return_value = {"accuracy": 0.85}
        
        # Mock for meta-prompter evolution
        top_programs = [MagicMock()]
        program_db.get_top_programs.return_value = top_programs
        prompt_sampler.get_templates.return_value = {"template1": "Old template"}
        meta_prompter.evolve_prompts.return_value = {"template1_new": "New template"}
        
        # Create controller
        controller = Controller(
            program_db=program_db,
            prompt_sampler=prompt_sampler,
            llm_interface=llm_interface,
            code_patcher=code_patcher,
            evaluator=evaluator,
            meta_prompter=meta_prompter,
            max_iterations=10  # Run for 10 iterations
        )
        
        # Setup to ensure meta-prompter evolution on 10th iteration
        controller.current_iteration = 9  # Will become 10 during the run
        
        # Run one iteration
        await controller.run()
        
        # Verify meta-prompter was called
        program_db.get_top_programs.assert_called_with(limit=5)
        meta_prompter.evolve_prompts.assert_called_with(
            current_templates={"template1": "Old template"},
            successful_programs=top_programs
        )
        prompt_sampler.update_templates.assert_called_with({"template1_new": "New template"})
    
    @pytest.mark.asyncio
    async def test_error_handling_during_iteration(self):
        """Test handling errors during an iteration."""
        # Mock components
        program_db = MagicMock()
        prompt_sampler = MagicMock()
        llm_interface = AsyncMock()
        code_patcher = MagicMock()
        evaluator = AsyncMock()
        
        # Setup to raise an error during code patching
        parent_program = Program(
            id="parent123",
            code="def test(): return 42",
            scores={"accuracy": 0.8},
            timestamp="2023-01-01T12:00:00"
        )
        program_db.sample_programs.return_value = (parent_program, [])
        prompt_sampler.construct_prompt.return_value = "Test prompt"
        llm_interface.generate.return_value = "Generated code"
        code_patcher.apply_changes.side_effect = ValueError("Invalid code")
        
        # Create controller
        controller = Controller(
            program_db=program_db,
            prompt_sampler=prompt_sampler,
            llm_interface=llm_interface,
            code_patcher=code_patcher,
            evaluator=evaluator,
            max_iterations=1
        )
        
        # Run the controller
        await controller.run()
        
        # Verify the error was handled and the iteration completed
        assert controller.current_iteration == 1
        
        # Verify no program was added due to the error
        program_db.add_program.assert_not_called() 