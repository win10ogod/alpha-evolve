"""
Unit tests for the code_utils module.
"""

import os
import pytest
from alphaevolve.core.code_utils import EvolveBlockParser, CodePatcher, find_evolve_blocks

class TestEvolveBlockParser:
    """Tests for the EvolveBlockParser class."""
    
    def test_extract_blocks(self, sample_program):
        """Test extracting blocks from code."""
        parser = EvolveBlockParser()
        blocks = parser.extract_blocks(sample_program)
        
        assert len(blocks) == 2
        assert "factorial" in blocks
        assert "fibonacci" in blocks
        
        # Check block content
        _, _, factorial_content = blocks["factorial"]
        assert "result = 1" in factorial_content
        assert "for i in range" in factorial_content
        
        _, _, fibonacci_content = blocks["fibonacci"]
        assert "if n <= 1:" in fibonacci_content
        assert "a, b = b, a + b" in fibonacci_content
    
    def test_replace_block(self, sample_program):
        """Test replacing a block in code."""
        parser = EvolveBlockParser()
        
        new_factorial = """
    # More efficient factorial implementation
    if n <= 1:
        return 1
    return n * factorial(n-1)
"""
        
        modified_code = parser.replace_block(sample_program, "factorial", new_factorial)
        
        assert "# More efficient factorial implementation" in modified_code
        assert "if n <= 1:" in modified_code
        assert "return n * factorial(n-1)" in modified_code
        assert "result = 1" not in modified_code
        
        # Check that other blocks are preserved
        assert "a, b = 0, 1" in modified_code
        assert "a, b = b, a + b" in modified_code
    
    def test_nonexistent_block(self, sample_program):
        """Test replacing a non-existent block."""
        parser = EvolveBlockParser()
        
        # Should return the original code unchanged
        modified_code = parser.replace_block(sample_program, "nonexistent", "new code")
        assert modified_code == sample_program

class TestCodePatcher:
    """Tests for the CodePatcher class."""
    
    def test_apply_diff_changes(self):
        """Test applying diff changes to code."""
        original_code = """
def example():
    x = 1
    y = 2
    return x + y
"""
        
        diff_text = """
<<<<<<< SEARCH
    x = 1
    y = 2
=======
    x = 10
    y = 20
>>>>>>> REPLACE
"""
        
        patcher = CodePatcher()
        patched_code = patcher._apply_diff(original_code, diff_text)
        
        assert "x = 10" in patched_code
        assert "y = 20" in patched_code
        assert "x = 1" not in patched_code
        assert "y = 2" not in patched_code
    
    def test_apply_changes_with_diff(self):
        """Test the apply_changes method with diff-style changes."""
        original_code = "def func():\n    return 1"
        
        changes = """
I'll improve this function:

<<<<<<< SEARCH
def func():
    return 1
=======
def func():
    # Added docstring and better implementation
    '''Returns a calculated value.'''
    return 1 + 0
>>>>>>> REPLACE
"""
        
        patcher = CodePatcher()
        result = patcher.apply_changes(original_code, changes)
        
        assert "# Added docstring" in result
        assert "'''Returns a calculated value.'''" in result
        assert "return 1 + 0" in result
    
    def test_apply_changes_with_code_block(self):
        """Test the apply_changes method with code block style changes."""
        original_code = "def func():\n    return 1"
        
        changes = """
Here's the improved code:

```python
def func():
    # Improved implementation
    return 1 + 0
```
"""
        
        patcher = CodePatcher()
        result = patcher.apply_changes(original_code, changes)
        
        assert "# Improved implementation" in result
        assert "return 1 + 0" in result

def test_find_evolve_blocks(temp_dir, sample_program):
    """Test finding evolve blocks in a directory."""
    # Create a file with evolve blocks
    py_file = os.path.join(temp_dir, "test.py")
    with open(py_file, "w") as f:
        f.write(sample_program)
    
    # Create a file without evolve blocks
    other_file = os.path.join(temp_dir, "no_blocks.py")
    with open(other_file, "w") as f:
        f.write("def regular_function():\n    return 42\n")
    
    # Find evolve blocks
    blocks = find_evolve_blocks(temp_dir)
    
    assert len(blocks) == 1
    assert py_file in blocks
    assert other_file not in blocks
    assert len(blocks[py_file]) == 2
    assert "factorial" in blocks[py_file]
    assert "fibonacci" in blocks[py_file] 