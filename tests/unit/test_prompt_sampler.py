"""
Unit tests for the prompt_sampler module.
"""

import os
import pytest
from unittest.mock import MagicMock
from alphaevolve.core.prompt_sampler import PromptSampler
from alphaevolve.core.program_database import Program

class TestPromptSampler:
    """Tests for the PromptSampler class."""
    
    def test_construct_prompt_with_default_template(self):
        """Test constructing a prompt with the default template."""
        # Create a sampler with just the default template
        sampler = PromptSampler()
        
        # Create mock parent program and inspirations
        parent = Program(
            id="parent123",
            code="def test(): return 42",
            scores={"accuracy": 0.8, "performance": 0.7},
            timestamp="2023-01-01T12:00:00"
        )
        
        inspirations = [
            Program(
                id="insp1",
                code="def better(): return 43",
                scores={"accuracy": 0.9, "performance": 0.6},
                timestamp="2023-01-01T12:01:00"
            )
        ]
        
        # Construct a prompt
        prompt = sampler.construct_prompt(parent, inspirations)
        
        # Basic assertions
        assert parent.code in prompt
        assert "accuracy: 0.8" in prompt
        assert "performance: 0.7" in prompt
        assert "INSPIRATION" in prompt
        assert "better(): return 43" in prompt
        assert "accuracy: 0.9" in prompt
        assert "performance: 0.6" in prompt
    
    def test_prompt_with_custom_template(self, temp_dir):
        """Test using a custom prompt template."""
        # Create template directory and files
        templates_dir = os.path.join(temp_dir, "templates")
        os.makedirs(templates_dir)
        
        # Write a custom template
        with open(os.path.join(templates_dir, "custom.txt"), "w") as f:
            f.write("""
CUSTOM TEMPLATE

CODE: {parent_program}
METRICS: {evaluation_criteria}
OTHER EXAMPLES: {inspirations}
""")
        
        # Create sampler with custom templates
        sampler = PromptSampler(prompt_templates_dir=templates_dir)
        
        # Create mock parent program and inspirations
        parent = Program(
            id="parent123",
            code="def test(): return 42",
            scores={"accuracy": 0.8},
            timestamp="2023-01-01T12:00:00"
        )
        
        inspirations = []
        
        # Construct a prompt with specific template
        prompt = sampler.construct_prompt(parent, inspirations, template_name="custom")
        
        # Check custom template was used
        assert "CUSTOM TEMPLATE" in prompt
        assert "CODE: def test(): return 42" in prompt
        assert "METRICS: " in prompt
        assert "accuracy: 0.8" in prompt
    
    def test_loading_context(self, temp_dir):
        """Test loading context files."""
        # Create context directory and files
        context_dir = os.path.join(temp_dir, "context")
        os.makedirs(context_dir)
        
        # Write context files
        with open(os.path.join(context_dir, "01_intro.txt"), "w") as f:
            f.write("This is an introduction.")
        
        with open(os.path.join(context_dir, "02_theory.txt"), "w") as f:
            f.write("This is some theory.")
        
        # Create sampler with context
        sampler = PromptSampler(context_files_dir=context_dir)
        
        # Create mock parent program and inspirations
        parent = Program(
            id="parent123",
            code="def test(): return 42",
            scores={"accuracy": 0.8},
            timestamp="2023-01-01T12:00:00"
        )
        
        inspirations = []
        
        # Construct a prompt
        prompt = sampler.construct_prompt(parent, inspirations)
        
        # Check context was included
        assert "This is an introduction." in prompt
        assert "This is some theory." in prompt
    
    def test_template_performance_tracking(self):
        """Test tracking template performance."""
        sampler = PromptSampler()
        
        # Add performance data for templates
        sampler.templates = {"t1": "Template 1", "t2": "Template 2"}
        sampler.template_performance = {"t1": [], "t2": []}
        
        sampler.update_template_performance("t1", 0.8)
        sampler.update_template_performance("t1", 0.9)
        sampler.update_template_performance("t2", 0.7)
        
        # Get best template
        best = sampler.get_best_performing_template()
        assert best == "t1"  # t1 has average 0.85, t2 has 0.7
    
    def test_update_templates(self, temp_dir):
        """Test updating templates."""
        # Create template directory
        templates_dir = os.path.join(temp_dir, "templates")
        os.makedirs(templates_dir)
        
        # Initial template
        with open(os.path.join(templates_dir, "initial.txt"), "w") as f:
            f.write("Initial template")
        
        sampler = PromptSampler(prompt_templates_dir=templates_dir)
        
        # Add new templates
        new_templates = {
            "new_template": "This is a new template",
            "another_new": "Another new template"
        }
        
        sampler.update_templates(new_templates)
        
        # Check in-memory templates
        assert "new_template" in sampler.templates
        assert "another_new" in sampler.templates
        assert sampler.templates["new_template"] == "This is a new template"
        
        # Check saved templates
        assert os.path.exists(os.path.join(templates_dir, "new_template.txt"))
        assert os.path.exists(os.path.join(templates_dir, "another_new.txt"))
        
        # Check template_performance was updated
        assert "new_template" in sampler.template_performance
        assert "another_new" in sampler.template_performance 