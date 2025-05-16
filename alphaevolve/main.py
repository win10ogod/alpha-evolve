#!/usr/bin/env python3
"""
AlphaEvolve: Automated Evolution of Code Using Large Language Models

Main entry point for the AlphaEvolve system.
"""

import argparse
import asyncio
import logging
import os
import sys
import importlib
from typing import Dict, List, Optional, Any

from alphaevolve.core.utils import setup_logging, load_config, create_run_directory, save_config
from alphaevolve.core.controller import Controller
from alphaevolve.core.program_database import ProgramDatabase
from alphaevolve.core.prompt_sampler import PromptSampler
from alphaevolve.core.llm_interface import LLMInterface
from alphaevolve.core.code_utils import CodePatcher, find_evolve_blocks
from alphaevolve.core.evaluation_manager import EvaluationManager

# Import MetaPrompter conditionally due to current issues
try:
    from alphaevolve.core.meta_prompter import MetaPrompter
    has_meta_prompter = True
except ImportError:
    has_meta_prompter = False

logger = logging.getLogger(__name__)

async def init_components(config: Dict[str, Any], run_dir: str) -> Controller:
    """
    Initialize all AlphaEvolve components based on configuration.
    
    Args:
        config: Configuration dictionary
        run_dir: Directory for this run
        
    Returns:
        Initialized Controller object
    """
    # Create program database
    db_config = config.get('program_database', {})
    db_type = db_config.get('db_type', 'file')
    
    if db_type == 'postgresql':
        # Use PostgreSQL database if configured
        from alphaevolve.core.postgresql_program_database import PostgreSQLProgramDatabase
        program_db = PostgreSQLProgramDatabase(
            results_dir=os.path.join(run_dir, 'programs'),
            db_config=db_config.get('postgresql', {}),
            population_size=db_config.get('population_size', 100),
            archive_mode=db_config.get('archive_mode', 'pareto'),
            metrics=db_config.get('metrics', ['fitness']),
            min_pool_size=db_config.get('min_pool_size', 1),
            max_pool_size=db_config.get('max_pool_size', 10)
        )
    else:
        # Use file-based database by default
        program_db = ProgramDatabase(
            results_dir=os.path.join(run_dir, 'programs'),
            population_size=db_config.get('population_size', 100),
            archive_mode=db_config.get('archive_mode', 'pareto'),
            metrics=db_config.get('metrics', ['fitness'])
        )
    
    # Create LLM interface
    llm_config = config.get('llm', {})
    llm_interface = LLMInterface(
        model=llm_config.get('model', 'lm_studio/llama-3-8b-instruct'),
        api_key=llm_config.get('api_key'),
        api_base=llm_config.get('api_base'),
        temperature=llm_config.get('temperature', 0.8),
        max_tokens=llm_config.get('max_tokens', 1024),
        timeout=llm_config.get('timeout', 60),
        retry_attempts=llm_config.get('retry_attempts', 3),
        retry_delay=llm_config.get('retry_delay', 5),
        fallback_models=llm_config.get('fallback_models', [])
    )
    
    # Create prompt sampler
    prompt_config = config.get('prompt', {})
    prompt_sampler = PromptSampler(
        prompt_templates_dir=os.path.join(config.get('problem_dir', ''), 'prompt_templates'),
        default_template=prompt_config.get('default_template'),
        context_files_dir=os.path.join(config.get('problem_dir', ''), 'problem_context'),
        max_context_length=prompt_config.get('max_context_length', 8000),
        evolve_templates=prompt_config.get('evolve_templates', False)
    )
    
    # Create code patcher
    code_patcher = CodePatcher()
    
    # Create evaluation manager
    eval_config = config.get('evaluation', {})
    evaluation_manager = EvaluationManager(
        evaluate_function_path=os.path.join(config.get('problem_dir', ''), 'evaluate.py'),
        working_dir=config.get('problem_dir', ''),
        max_workers=eval_config.get('max_workers', 4),
        timeout=eval_config.get('timeout', 60),
        cascade_thresholds=eval_config.get('cascade_thresholds'),
        use_subprocess=eval_config.get('use_subprocess', True)
    )
    
    # Create meta prompter if available and enabled
    meta_prompter = None
    if has_meta_prompter and prompt_config.get('evolve_templates', False):
        meta_config = prompt_config.get('meta_prompter', {})
        meta_prompter = MetaPrompter(
            llm_interface=llm_interface,
            max_prompts_per_round=meta_config.get('max_prompts_per_round', 2),
            min_programs_required=meta_config.get('min_programs_required', 5)
        )
    
    # Create controller
    controller_config = config.get('controller', {})
    controller = Controller(
        program_db=program_db,
        prompt_sampler=prompt_sampler,
        llm_interface=llm_interface,
        code_patcher=code_patcher,
        evaluator=evaluation_manager,
        meta_prompter=meta_prompter,
        max_iterations=controller_config.get('max_iterations', 100),
        budget=controller_config.get('budget'),
        target_score=controller_config.get('target_score')
    )
    
    return controller

async def run_alphaevolve(config_path: str) -> None:
    """
    Run the AlphaEvolve system with the specified configuration.
    
    Args:
        config_path: Path to the configuration file
    """
    # Load configuration
    config = load_config(config_path)
    
    # Create run directory
    problem_name = os.path.basename(config.get('problem_dir', 'unknown_problem'))
    run_dir = create_run_directory(
        base_dir=os.path.join(config.get('problem_dir', ''), 'results'),
        run_prefix=f"{problem_name}_run"
    )
    
    # Set up logging
    setup_logging(
        log_dir=run_dir,
        log_level=logging.DEBUG,
        console_level=logging.INFO
    )
    
    # Save a copy of the configuration
    save_config(config, os.path.join(run_dir, 'config.yaml'))
    
    logger.info(f"Starting AlphaEvolve run in {run_dir}")
    
    try:
        # Initialize components
        controller = await init_components(config, run_dir)
        
        # Set up initial program(s) if not already in database
        if not controller.program_db.programs:
            await setup_initial_programs(controller, config)
        
        # Run the controller
        best_programs = await controller.run()
        
        # Log results
        logger.info(f"AlphaEvolve run completed successfully")
        for i, program in enumerate(best_programs[:3]):
            metrics_str = ", ".join([f"{k}: {v}" for k, v in program.scores.items()])
            logger.info(f"Top program {i+1}: {metrics_str}")
            
            # Save the best program to a special location for easy access
            with open(os.path.join(run_dir, f"best_program_{i+1}.py"), 'w', encoding='utf-8') as f:
                f.write(program.code)
        
    except Exception as e:
        logger.error(f"Error during AlphaEvolve run: {str(e)}", exc_info=True)
        raise

async def setup_initial_programs(controller: Controller, config: Dict[str, Any]) -> None:
    """
    Set up initial programs in the database.
    
    Args:
        controller: Controller instance
        config: Configuration dictionary
    """
    problem_dir = config.get('problem_dir', '')
    src_dir = os.path.join(problem_dir, 'src')
    
    if not os.path.exists(src_dir):
        logger.error(f"Source directory not found: {src_dir}")
        raise FileNotFoundError(f"Source directory not found: {src_dir}")
    
    # Find files with evolve blocks
    logger.info(f"Scanning for EVOLVE-BLOCK markers in {src_dir}")
    evolve_blocks = find_evolve_blocks(src_dir)
    
    if not evolve_blocks:
        logger.warning(f"No EVOLVE-BLOCK markers found in {src_dir}")
        
        # If no evolve blocks, use all Python files in the src directory
        for root, _, files in os.walk(src_dir):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        code = f.read()
                    
                    # Add the program to the database (evaluate first)
                    await add_program_to_db(controller, code, f"Initial program from {file}")
    else:
        # Process each file with evolve blocks
        for file_path, block_names in evolve_blocks.items():
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # Add the program to the database (evaluate first)
            await add_program_to_db(controller, code, f"Initial program from {file_path}")

async def add_program_to_db(controller: Controller, code: str, description: str) -> None:
    """
    Evaluate a program and add it to the database.
    
    Args:
        controller: Controller instance
        code: Program code
        description: Description of the program
    """
    logger.info(f"Evaluating {description}")
    
    try:
        # Evaluate the program
        scores = await controller.evaluator.evaluate(code)
        
        # Add to database
        controller.program_db.add_program(
            program=code,
            scores=scores,
            metadata={"description": description}
        )
        
        logger.info(f"Added {description} to database with scores: {scores}")
        
    except Exception as e:
        logger.error(f"Error adding {description} to database: {str(e)}")

def main():
    """Main entry point for the AlphaEvolve system."""
    parser = argparse.ArgumentParser(description="AlphaEvolve: Automated Evolution of Code Using Large Language Models")
    parser.add_argument('config', help='Path to the configuration file')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Run AlphaEvolve with the specified configuration
    asyncio.run(run_alphaevolve(args.config))

if __name__ == "__main__":
    main() 