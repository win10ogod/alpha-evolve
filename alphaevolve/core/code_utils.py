import logging
import re
from typing import List, Dict, Optional, Tuple, Set
import ast
import os
import difflib

logger = logging.getLogger(__name__)

class EvolveBlockParser:
    """
    Parser for EVOLVE-BLOCK markers in code.
    Identifies blocks of code marked for evolution.
    """
    
    def __init__(self, start_marker: str = "# EVOLVE-BLOCK-START", end_marker: str = "# EVOLVE-BLOCK-END"):
        """
        Initialize the parser.
        
        Args:
            start_marker: String that marks the start of an evolvable block
            end_marker: String that marks the end of an evolvable block
        """
        self.start_marker = start_marker
        self.end_marker = end_marker
    
    def extract_blocks(self, code: str) -> Dict[str, Tuple[int, int, str]]:
        """
        Extract marked blocks from code.
        
        Args:
            code: Source code string
            
        Returns:
            Dictionary mapping block IDs to (start_line, end_line, block_content)
        """
        lines = code.splitlines()
        blocks = {}
        block_id = 0
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            if self.start_marker in line:
                # Extract optional block name if present
                block_name_match = re.search(r'# EVOLVE-BLOCK-START(?:\s+(.+))?', line)
                block_name = block_name_match.group(1) if block_name_match and block_name_match.group(1) else f"block_{block_id}"
                
                start_line = i
                block_content = []
                
                # Find matching end marker
                j = i + 1
                while j < len(lines) and self.end_marker not in lines[j]:
                    block_content.append(lines[j])
                    j += 1
                
                if j < len(lines):  # End marker found
                    end_line = j
                    blocks[block_name] = (start_line, end_line, "\n".join(block_content))
                    block_id += 1
                    i = j  # Skip to after the end marker
                else:
                    logger.warning(f"End marker not found for block starting at line {start_line}")
                    break
            
            i += 1
        
        return blocks
    
    def replace_block(self, code: str, block_name: str, new_content: str) -> str:
        """
        Replace a marked block with new content.
        
        Args:
            code: Original source code
            block_name: Name of the block to replace
            new_content: New content for the block
            
        Returns:
            Updated code with the block replaced
        """
        blocks = self.extract_blocks(code)
        
        if block_name not in blocks:
            logger.warning(f"Block '{block_name}' not found in code")
            return code
        
        start_line, end_line, _ = blocks[block_name]
        lines = code.splitlines()
        
        # Preserve the markers
        start_marker_line = lines[start_line]
        end_marker_line = lines[end_line]
        
        # Replace the block content
        new_lines = (
            lines[:start_line + 1] +  # Lines before block + start marker
            new_content.splitlines() +  # New block content
            [end_marker_line] +  # End marker
            lines[end_line + 1:]  # Lines after block
        )
        
        return "\n".join(new_lines)


class CodePatcher:
    """
    Applies changes to code, handling diffs in various formats.
    """
    
    def __init__(self, evolve_block_parser: Optional[EvolveBlockParser] = None):
        """
        Initialize the code patcher.
        
        Args:
            evolve_block_parser: Parser for EVOLVE-BLOCK markers (if None, a default one is created)
        """
        self.evolve_block_parser = evolve_block_parser or EvolveBlockParser()
    
    def apply_changes(self, parent_program, changes: str) -> str:
        """
        Apply changes to a parent program.
        
        Args:
            parent_program: Program object or string containing the original code
            changes: Changes to apply, either as a diff or complete replacement
            
        Returns:
            Updated program code
        """
        # Get code string from parent program
        if hasattr(parent_program, 'code'):
            original_code = parent_program.code
        else:
            original_code = str(parent_program)
        
        # Check if changes contain diff markers
        if "<<<<<<< SEARCH" in changes and ">>>>>>> REPLACE" in changes:
            return self._apply_diff(original_code, changes)
        elif "# EVOLVE-BLOCK-START" in original_code:
            # Check if the changes are meant for a specific evolve block
            for block_name, (_, _, block_content) in self.evolve_block_parser.extract_blocks(original_code).items():
                if block_content in changes:
                    # This might be a replacement for a specific block
                    # Extract just the new code (assuming format like "Here's the improved code: ```python\n{CODE}\n```")
                    code_pattern = r'```(?:python)?\n(.*?)\n```'
                    code_match = re.search(code_pattern, changes, re.DOTALL)
                    
                    if code_match:
                        new_block_content = code_match.group(1)
                        return self.evolve_block_parser.replace_block(original_code, block_name, new_block_content)
            
            # If we got here, no specific block match was found, or the LLM didn't format correctly
            # Try to find any code blocks and use as complete replacement
            code_pattern = r'```(?:python)?\n(.*?)\n```'
            code_match = re.search(code_pattern, changes, re.DOTALL)
            
            if code_match:
                return code_match.group(1)
        else:
            # Extract code from the changes if it's wrapped in code blocks
            code_pattern = r'```(?:python)?\n(.*?)\n```'
            code_match = re.search(code_pattern, changes, re.DOTALL)
            
            if code_match:
                return code_match.group(1).strip()
        
        # If we can't parse the changes, return the original
        logger.warning("Could not parse changes format, returning original code")
        return original_code
    
    def _apply_diff(self, original_code: str, diff_text: str) -> str:
        """
        Apply a diff to the original code.
        
        Args:
            original_code: Original source code
            diff_text: Text containing diffs in the format:
                       <<<<<<< SEARCH
                       ... code to be replaced ...
                       =======
                       ... replacement code ...
                       >>>>>>> REPLACE
            
        Returns:
            Updated code with diffs applied
        """
        # Find all diff sections
        diff_pattern = r'<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE'
        diff_matches = re.finditer(diff_pattern, diff_text, re.DOTALL)
        
        # Apply diffs one by one
        result = original_code
        for match in diff_matches:
            search_text = match.group(1)
            replace_text = match.group(2)
            
            # Replace search_text with replace_text
            result = result.replace(search_text, replace_text)
        
        return result
    
    def validate_syntax(self, code: str) -> bool:
        """
        Validate that the code has valid Python syntax.
        
        Args:
            code: Python code to validate
            
        Returns:
            True if syntax is valid, False otherwise
        """
        try:
            ast.parse(code)
            return True
        except SyntaxError as e:
            logger.warning(f"Syntax error in code: {str(e)}")
            return False


def find_evolve_blocks(directory: str, extensions: Set[str] = {'.py', '.js', '.java', '.cpp', '.c'}):
    """
    Find files containing EVOLVE-BLOCK markers in a directory.
    
    Args:
        directory: Directory to search in
        extensions: File extensions to consider
        
    Returns:
        Dictionary mapping file paths to lists of evolve block names
    """
    parser = EvolveBlockParser()
    evolve_blocks = {}
    
    for root, _, files in os.walk(directory):
        for file in files:
            if os.path.splitext(file)[1] in extensions:
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        blocks = parser.extract_blocks(content)
                        if blocks:
                            evolve_blocks[file_path] = list(blocks.keys())
                except Exception as e:
                    logger.error(f"Error reading file {file_path}: {str(e)}")
    
    return evolve_blocks 