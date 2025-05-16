import logging
import os
import time
import asyncio
import tempfile
import subprocess
import importlib.util
import sys
import json
from typing import Dict, List, Optional, Any, Callable, Union
import concurrent.futures

logger = logging.getLogger(__name__)

class EvaluationManager:
    """
    Manages the evaluation of programs.
    Can run evaluations in parallel and implement cascading evaluation strategies.
    """
    
    def __init__(
        self,
        evaluate_function_path: str,
        working_dir: str,
        max_workers: int = 4,
        timeout: int = 60,
        cascade_thresholds: Optional[Dict[str, float]] = None,
        use_subprocess: bool = False,
    ):
        """
        Initialize the Evaluation Manager.
        
        Args:
            evaluate_function_path: Path to the python file containing the evaluate function
            working_dir: Directory to run evaluations in
            max_workers: Maximum number of parallel evaluations
            timeout: Timeout for evaluations in seconds
            cascade_thresholds: Dict of {metric: threshold} for cascading evaluation
            use_subprocess: Whether to run evaluations in a subprocess (safer but slower)
        """
        self.evaluate_function_path = os.path.abspath(evaluate_function_path)
        self.working_dir = working_dir
        self.max_workers = max_workers
        self.timeout = timeout
        self.cascade_thresholds = cascade_thresholds or {}
        self.use_subprocess = use_subprocess
        
        # Create a thread pool for parallel evaluations
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        
        # Load the evaluate function
        self.evaluate_function = self._load_evaluate_function()
    
    def _load_evaluate_function(self) -> Callable:
        """
        Load the user-provided evaluate function from file.
        
        Returns:
            The loaded evaluate function
        """
        logger.info(f"Loading evaluate function from {self.evaluate_function_path}")
        
        try:
            # Load the module containing the evaluate function
            spec = importlib.util.spec_from_file_location("evaluate_module", self.evaluate_function_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not load module from {self.evaluate_function_path}")
                
            module = importlib.util.module_from_spec(spec)
            sys.modules["evaluate_module"] = module
            spec.loader.exec_module(module)
            
            # Get the evaluate function
            if not hasattr(module, "evaluate"):
                raise AttributeError(f"Module does not have an 'evaluate' function")
            
            return module.evaluate
            
        except Exception as e:
            logger.error(f"Error loading evaluate function: {str(e)}")
            raise
    
    async def evaluate(self, program: str, cascade: bool = True) -> Dict[str, float]:
        """
        Evaluate a program using the loaded evaluate function.
        
        Args:
            program: Source code of the program to evaluate
            cascade: Whether to use cascading evaluation
            
        Returns:
            Dictionary of evaluation metrics
        """
        # Write program to a temporary file
        with tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w', encoding='utf-8') as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(program)
        
        try:
            if self.use_subprocess:
                # Run evaluation in a subprocess
                metrics = await self._evaluate_in_subprocess(temp_file_path)
            else:
                # Run evaluation in the current process
                metrics = await self._evaluate_in_process(temp_file_path, program)
            
            # Apply cascading evaluation if enabled
            if cascade and self.cascade_thresholds and metrics:
                return self._apply_cascade(metrics)
            
            return metrics
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"Error removing temporary file {temp_file_path}: {str(e)}")
    
    async def _evaluate_in_process(self, program_path: str, program_code: str) -> Dict[str, float]:
        """
        Run evaluation in the current process.
        
        Args:
            program_path: Path to the program file
            program_code: Source code of the program
            
        Returns:
            Dictionary of evaluation metrics
        """
        loop = asyncio.get_event_loop()
        
        try:
            # Run the evaluate function in a thread pool
            metrics = await loop.run_in_executor(
                self.executor,
                lambda: self._run_evaluate_with_timeout(program_path)
            )
            
            return metrics
            
        except asyncio.TimeoutError:
            logger.warning(f"Evaluation timed out after {self.timeout} seconds")
            return {"timeout": 1.0}
            
        except Exception as e:
            logger.error(f"Error during evaluation: {str(e)}")
            return {"error": 1.0}
    
    def _run_evaluate_with_timeout(self, program_path: str) -> Dict[str, float]:
        """
        Run the evaluate function with a timeout.
        
        Args:
            program_path: Path to the program file
            
        Returns:
            Dictionary of evaluation metrics
        """
        # Save current directory
        original_dir = os.getcwd()
        
        try:
            # Change to the working directory
            os.chdir(self.working_dir)
            
            # Call the evaluate function
            start_time = time.time()
            metrics = self.evaluate_function(program_path)
            elapsed_time = time.time() - start_time
            
            logger.info(f"Evaluation completed in {elapsed_time:.2f} seconds: {metrics}")
            
            if not isinstance(metrics, dict):
                logger.warning(f"Evaluate function returned non-dict value: {metrics}")
                return {"error": 1.0}
            
            return metrics
            
        finally:
            # Restore original directory
            os.chdir(original_dir)
    
    async def _evaluate_in_subprocess(self, program_path: str) -> Dict[str, float]:
        """
        Run evaluation in a separate subprocess for isolation.
        
        Args:
            program_path: Path to the program file
            
        Returns:
            Dictionary of evaluation metrics
        """
        # Create a simple Python script to run the evaluation
        eval_script = f"""
import sys
import json
import os
sys.path.append(os.path.dirname("{self.evaluate_function_path}"))
from evaluate_module import evaluate

try:
    metrics = evaluate("{program_path}")
    print(json.dumps(metrics))
except Exception as e:
    print(json.dumps({{"error": 1.0, "error_message": str(e)}}))
"""
        
        # Write the script to a temporary file
        with tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w', encoding='utf-8') as eval_file:
            eval_script_path = eval_file.name
            eval_file.write(eval_script)
        
        try:
            # Run the script in a subprocess
            proc = await asyncio.create_subprocess_exec(
                sys.executable, eval_script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_dir
            )
            
            # Set a timeout
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
                
                if proc.returncode != 0:
                    logger.error(f"Evaluation subprocess failed: {stderr.decode()}")
                    return {"error": 1.0, "returncode": proc.returncode}
                
                # Parse the output as JSON
                try:
                    metrics = json.loads(stdout.decode().strip())
                    return metrics
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse evaluation output: {stdout.decode()}")
                    return {"error": 1.0, "parse_error": 1.0}
                    
            except asyncio.TimeoutError:
                logger.warning(f"Evaluation subprocess timed out after {self.timeout} seconds")
                try:
                    proc.kill()
                except:
                    pass
                return {"timeout": 1.0}
                
        finally:
            # Clean up temporary script file
            try:
                os.unlink(eval_script_path)
            except:
                pass
    
    def _apply_cascade(self, metrics: Dict[str, float]) -> Dict[str, float]:
        """
        Apply cascading evaluation.
        If a metric doesn't meet its threshold, return only that metric.
        
        Args:
            metrics: Dictionary of evaluation metrics
            
        Returns:
            Filtered metrics dictionary based on cascade thresholds
        """
        for metric, threshold in self.cascade_thresholds.items():
            if metric in metrics and metrics[metric] < threshold:
                logger.info(f"Cascade threshold not met for {metric}: {metrics[metric]} < {threshold}")
                return {metric: metrics[metric]}
        
        return metrics
    
    async def batch_evaluate(self, programs: List[str], max_concurrent: Optional[int] = None) -> List[Dict[str, float]]:
        """
        Evaluate multiple programs in parallel.
        
        Args:
            programs: List of program source codes
            max_concurrent: Maximum number of concurrent evaluations (defaults to self.max_workers)
            
        Returns:
            List of evaluation metrics dictionaries
        """
        max_concurrent = max_concurrent or self.max_workers
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def _evaluate_with_semaphore(program):
            async with semaphore:
                return await self.evaluate(program)
        
        tasks = [_evaluate_with_semaphore(program) for program in programs]
        return await asyncio.gather(*tasks)
    
    def cleanup(self):
        """Clean up resources used by the evaluation manager."""
        self.executor.shutdown(wait=True) 