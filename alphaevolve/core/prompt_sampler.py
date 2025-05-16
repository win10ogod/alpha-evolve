import logging
import os
import random
from typing import Dict, List, Optional, Any, Union
import json
import re

from alphaevolve.core.program_database import Program

logger = logging.getLogger(__name__)

class PromptSampler:
    """
    Constructs prompts for the LLM based on templates and program context.
    Can use pre-defined templates or evolve them over time.
    """
    
    def __init__(
        self,
        prompt_templates_dir: Optional[str] = None,
        default_template: Optional[str] = None,
        context_files_dir: Optional[str] = None,
        max_context_length: int = 8000,
        evolve_templates: bool = False,
    ):
        """
        Initialize the Prompt Sampler.
        
        Args:
            prompt_templates_dir: Directory containing prompt template files
            default_template: Default template string if no templates found
            context_files_dir: Directory containing problem context files
            max_context_length: Maximum length for context in the prompt
            evolve_templates: Whether to evolve templates over time
        """
        self.prompt_templates_dir = prompt_templates_dir
        self.context_files_dir = context_files_dir
        self.max_context_length = max_context_length
        self.evolve_templates = evolve_templates
        
        # Set default template if none provided
        self.default_template = default_template or """
You are an expert software engineer tasked with improving the following code.

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
1. Analyze the current implementation
2. Identify inefficiencies or areas for improvement
3. Generate an improved version of the code or a specific part that needs modification

If you want to modify a specific part, use the following format:
<<<<<<< SEARCH
... code to be replaced ...
=======
... replacement code ...
>>>>>>> REPLACE

If you want to replace the entire program, provide the complete code.

YOUR IMPROVED CODE:
"""
        
        # Load templates from directory if available
        self.templates = {}
        if prompt_templates_dir and os.path.exists(prompt_templates_dir):
            self._load_templates()
        elif default_template:
            self.templates["default"] = self.default_template
        
        # Load problem context files if available
        self.context = ""
        if context_files_dir and os.path.exists(context_files_dir):
            self._load_context()
            
        # Track which templates perform well
        self.template_performance: Dict[str, List[float]] = {
            name: [] for name in self.templates.keys()
        }
    
    def _load_templates(self):
        """Load prompt templates from template directory."""
        for filename in os.listdir(self.prompt_templates_dir):
            if filename.endswith(".txt") or filename.endswith(".md"):
                template_name = os.path.splitext(filename)[0]
                filepath = os.path.join(self.prompt_templates_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        self.templates[template_name] = f.read()
                    logger.info(f"Loaded prompt template: {template_name}")
                except Exception as e:
                    logger.error(f"Error loading template {filepath}: {str(e)}")
    
    def _load_context(self):
        """Load problem context from context files directory."""
        context_parts = []
        
        for filename in sorted(os.listdir(self.context_files_dir)):
            filepath = os.path.join(self.context_files_dir, filename)
            if os.path.isfile(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Add filename as a header for the context
                        context_parts.append(f"--- {filename} ---\n{content}\n")
                except Exception as e:
                    logger.error(f"Error loading context file {filepath}: {str(e)}")
        
        # Combine and truncate if too long
        self.context = "\n".join(context_parts)
        if len(self.context) > self.max_context_length:
            self.context = self.context[:self.max_context_length] + "...[truncated]"
    
    def construct_prompt(
        self, 
        parent_program: Program, 
        inspirations: List[Program],
        template_name: Optional[str] = None
    ) -> str:
        """
        Construct a prompt using the specified template and program context.
        
        Args:
            parent_program: Parent program to be improved
            inspirations: List of programs to use as inspiration
            template_name: Name of the template to use (randomly chosen if None)
            
        Returns:
            Constructed prompt string
        """
        # Select a template (random if not specified)
        if not template_name:
            template_name = random.choice(list(self.templates.keys()))
        
        template = self.templates.get(template_name, self.default_template)
        
        # Format inspirations
        inspiration_text = ""
        if inspirations:
            inspiration_parts = []
            for idx, insp in enumerate(inspirations):
                scores_text = ", ".join([f"{k}: {v}" for k, v in insp.scores.items()])
                inspiration_parts.append(f"INSPIRATION {idx+1} (Scores: {scores_text}):\n```python\n{insp.code}\n```\n")
            inspiration_text = "\n".join(inspiration_parts)
        
        # Format evaluation criteria based on metrics
        if hasattr(parent_program, 'scores') and parent_program.scores:
            metrics = list(parent_program.scores.keys())
            eval_criteria = (
                f"Your code will be evaluated on the following metrics: {', '.join(metrics)}.\n"
                f"Current scores: {', '.join([f'{k}: {v}' for k, v in parent_program.scores.items()])}\n"
                f"Higher values are better for all metrics."
            )
        else:
            eval_criteria = "Your code will be evaluated for correctness and efficiency."
        
        # Fill template
        prompt = template.format(
            parent_program=parent_program.code,
            context=self.context,
            evaluation_criteria=eval_criteria,
            inspirations=inspiration_text,
            timestamp=parent_program.timestamp,
            program_id=parent_program.id
        )
        
        return prompt
    
    def update_template_performance(self, template_name: str, score: float):
        """
        Update performance statistics for a template.
        
        Args:
            template_name: Name of the template
            score: Performance score achieved with this template
        """
        if template_name in self.template_performance:
            self.template_performance[template_name].append(score)
    
    def get_templates(self) -> Dict[str, str]:
        """Get all available prompt templates."""
        return self.templates
    
    def update_templates(self, new_templates: Dict[str, str]):
        """
        Update the available prompt templates.
        
        Args:
            new_templates: Dictionary of template name to template text
        """
        self.templates.update(new_templates)
        
        # Initialize performance tracking for new templates
        for name in new_templates:
            if name not in self.template_performance:
                self.template_performance[name] = []
        
        # Save new templates to disk if directory is configured
        if self.prompt_templates_dir:
            for name, template in new_templates.items():
                try:
                    filepath = os.path.join(self.prompt_templates_dir, f"{name}.txt")
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(template)
                    logger.info(f"Saved new template: {name}")
                except Exception as e:
                    logger.error(f"Error saving template {name}: {str(e)}")
    
    def get_best_performing_template(self) -> Optional[str]:
        """Get the name of the best performing template based on average score."""
        if not self.template_performance:
            return None
            
        # Calculate average scores
        avg_scores = {}
        for name, scores in self.template_performance.items():
            if scores:  # Only consider templates with performance data
                avg_scores[name] = sum(scores) / len(scores)
        
        if not avg_scores:
            return None
            
        # Return the template with highest average score
        return max(avg_scores.items(), key=lambda x: x[1])[0] 