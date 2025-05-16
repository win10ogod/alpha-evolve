import logging
import os
import json
import yaml
from typing import Dict, List, Any, Optional, Union
import datetime
import tempfile
import shutil
import re

logger = logging.getLogger(__name__)

def setup_logging(
    log_dir: str,
    log_level: int = logging.INFO,
    console_level: int = logging.INFO,
    filename: Optional[str] = None
) -> logging.Logger:
    """
    Set up logging for the AlphaEvolve system.
    
    Args:
        log_dir: Directory to store log files
        log_level: Logging level for file handler
        console_level: Logging level for console handler
        filename: Optional specific filename for the log file
        
    Returns:
        Configured root logger
    """
    # Create log directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)
    
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all logs
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Set up file handler
    if not filename:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"alphaevolve_{timestamp}.log"
    
    file_handler = logging.FileHandler(
        os.path.join(log_dir, filename),
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Set up console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    return root_logger

def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from YAML or JSON file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Dictionary containing configuration
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            if config_path.endswith('.yaml') or config_path.endswith('.yml'):
                config = yaml.safe_load(f)
            elif config_path.endswith('.json'):
                config = json.load(f)
            else:
                raise ValueError(f"Unsupported config file format: {config_path}")
    except Exception as e:
        logger.error(f"Error loading config file {config_path}: {str(e)}")
        raise
    
    return config

def save_config(config: Dict[str, Any], output_path: str) -> None:
    """
    Save configuration to a file.
    
    Args:
        config: Configuration dictionary
        output_path: Path to save the configuration
    """
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            if output_path.endswith('.yaml') or output_path.endswith('.yml'):
                yaml.dump(config, f, default_flow_style=False)
            elif output_path.endswith('.json'):
                json.dump(config, f, indent=2)
            else:
                raise ValueError(f"Unsupported config file format: {output_path}")
                
        logger.info(f"Configuration saved to {output_path}")
        
    except Exception as e:
        logger.error(f"Error saving config to {output_path}: {str(e)}")
        raise

def create_run_directory(base_dir: str, run_prefix: str = "run") -> str:
    """
    Create a timestamped directory for a new run.
    
    Args:
        base_dir: Base directory for runs
        run_prefix: Prefix for the run directory name
        
    Returns:
        Path to the created run directory
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(base_dir, f"{run_prefix}_{timestamp}")
    
    os.makedirs(run_dir, exist_ok=True)
    logger.info(f"Created run directory: {run_dir}")
    
    return run_dir

def find_newest_run_directory(base_dir: str, run_prefix: str = "run") -> Optional[str]:
    """
    Find the most recent run directory.
    
    Args:
        base_dir: Base directory containing run directories
        run_prefix: Prefix for the run directory names
        
    Returns:
        Path to the newest run directory, or None if none found
    """
    if not os.path.exists(base_dir):
        return None
    
    run_dirs = [
        d for d in os.listdir(base_dir) 
        if os.path.isdir(os.path.join(base_dir, d)) and d.startswith(run_prefix)
    ]
    
    if not run_dirs:
        return None
    
    newest_dir = max(run_dirs, key=lambda d: os.path.getctime(os.path.join(base_dir, d)))
    return os.path.join(base_dir, newest_dir)

def safe_execute_code(code: str, globals_dict: Optional[Dict[str, Any]] = None) -> Any:
    """
    Execute code in a safe environment (using a temporary file).
    
    Args:
        code: Python code to execute
        globals_dict: Optional dictionary of global variables
        
    Returns:
        The result of the last statement in the code
    """
    with tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w', encoding='utf-8') as temp_file:
        temp_file_path = temp_file.name
        temp_file.write(code)
    
    try:
        # Create a restricted globals dictionary if not provided
        if globals_dict is None:
            globals_dict = {'__builtins__': __builtins__}
        
        # Execute the code
        with open(temp_file_path, 'r', encoding='utf-8') as f:
            code_str = f.read()
        
        code_obj = compile(code_str, temp_file_path, 'exec')
        locals_dict = {}
        exec(code_obj, globals_dict, locals_dict)
        
        return locals_dict
        
    finally:
        # Clean up the temporary file
        try:
            os.unlink(temp_file_path)
        except:
            pass

def is_valid_python(code: str) -> bool:
    """
    Check if the given code is valid Python.
    
    Args:
        code: Python code to check
        
    Returns:
        True if the code is valid Python, False otherwise
    """
    try:
        compile(code, '<string>', 'exec')
        return True
    except SyntaxError:
        return False 