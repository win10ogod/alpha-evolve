import asyncio
import logging
from typing import Dict, List, Optional, Any

from alphaevolve.core.program_database import ProgramDatabase
from alphaevolve.core.prompt_sampler import PromptSampler
from alphaevolve.core.llm_interface import LLMInterface
from alphaevolve.core.code_utils import CodePatcher
from alphaevolve.core.evaluation_manager import EvaluationManager
from alphaevolve.core.meta_prompter import MetaPrompter

logger = logging.getLogger(__name__)

class Controller:
    """
    The central orchestrator of the AlphaEvolve pipeline.
    Manages the asynchronous flow between samplers, LLMs, evaluators, and the database.
    """
    
    def __init__(
        self,
        program_db: ProgramDatabase,
        prompt_sampler: PromptSampler,
        llm_interface: LLMInterface,
        code_patcher: CodePatcher,
        evaluator: EvaluationManager,
        meta_prompter: Optional[MetaPrompter] = None,
        max_iterations: int = 100,
        budget: Optional[Dict[str, Any]] = None,
        target_score: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize the Controller.
        
        Args:
            program_db: Database to store and retrieve programs
            prompt_sampler: Component to construct prompts
            llm_interface: Interface to communicate with LLMs
            code_patcher: Component to apply changes to code
            evaluator: Component to evaluate programs
            meta_prompter: Optional component for meta-prompt evolution
            max_iterations: Maximum number of iterations to run
            budget: Optional budget constraints (e.g., {'llm_calls': 1000, 'time_hours': 24})
            target_score: Optional target scores to reach (e.g., {'accuracy': 0.99})
        """
        self.program_db = program_db
        self.prompt_sampler = prompt_sampler
        self.llm_interface = llm_interface
        self.code_patcher = code_patcher
        self.evaluator = evaluator
        self.meta_prompter = meta_prompter
        self.max_iterations = max_iterations
        self.budget = budget or {}
        self.target_score = target_score or {}
        
        self.current_iteration = 0
        self.stopped = False
        
    async def run(self):
        """Run the AlphaEvolve pipeline until stopping criteria are met."""
        logger.info("Starting AlphaEvolve pipeline")
        
        while not self.should_stop():
            self.current_iteration += 1
            logger.info(f"Starting iteration {self.current_iteration}")
            
            # Get parent program(s) and inspirations from database
            parent_program, inspirations = self.program_db.sample_programs()
            
            # Construct prompt
            prompt = self.prompt_sampler.construct_prompt(
                parent_program=parent_program,
                inspirations=inspirations
            )
            
            # Generate code modifications using LLM
            generated_code = await self.llm_interface.generate(prompt)
            
            # Apply changes to create child program
            try:
                child_program = self.code_patcher.apply_changes(
                    parent_program=parent_program,
                    changes=generated_code
                )
                
                # Evaluate the child program
                scores = await self.evaluator.evaluate(child_program)
                
                # Store the results in the program database
                self.program_db.add_program(
                    program=child_program,
                    scores=scores,
                    parent_id=parent_program.id
                )
                
                # Log progress
                logger.info(f"Iteration {self.current_iteration} - Scores: {scores}")
                
                # Optionally evolve meta-prompts
                if self.meta_prompter and self.current_iteration % 10 == 0:  # Every 10 iterations
                    await self.evolve_meta_prompts()
                    
            except Exception as e:
                logger.error(f"Error in iteration {self.current_iteration}: {str(e)}")
                
        logger.info(f"AlphaEvolve pipeline completed after {self.current_iteration} iterations")
        return self.program_db.get_best_programs()
                
    def should_stop(self) -> bool:
        """Check if stopping criteria are met."""
        if self.stopped:
            return True
            
        if self.current_iteration >= self.max_iterations:
            logger.info(f"Reached maximum iterations: {self.max_iterations}")
            return True
            
        # Check budget constraints
        for resource, limit in self.budget.items():
            usage = self.get_resource_usage(resource)
            if usage >= limit:
                logger.info(f"Budget exceeded for {resource}: {usage}/{limit}")
                return True
                
        # Check if target scores are reached
        best_program = self.program_db.get_best_program()
        if best_program:
            for metric, target in self.target_score.items():
                if best_program.scores.get(metric, 0) >= target:
                    logger.info(f"Target score reached for {metric}: {best_program.scores[metric]}")
                    continue
                return False
            return len(self.target_score) > 0  # Return True if all targets met
            
        return False
        
    def get_resource_usage(self, resource: str) -> float:
        """Get current usage for a specific resource."""
        if resource == 'llm_calls':
            return self.llm_interface.call_count
        # Add other resource tracking as needed
        return 0
        
    async def evolve_meta_prompts(self):
        """Evolve meta-prompts if configured."""
        if not self.meta_prompter:
            return
            
        # Get successful programs from database
        successful_programs = self.program_db.get_top_programs(limit=5)
        
        # Use meta-prompter to improve prompt templates
        new_prompt_templates = await self.meta_prompter.evolve_prompts(
            current_templates=self.prompt_sampler.get_templates(),
            successful_programs=successful_programs
        )
        
        # Update the prompt sampler with improved templates
        self.prompt_sampler.update_templates(new_prompt_templates)
        
    def stop(self):
        """Signal the controller to stop at the next iteration."""
        self.stopped = True 