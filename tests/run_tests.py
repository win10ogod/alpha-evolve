#!/usr/bin/env python3
"""
Run unit tests for AlphaEvolve.
"""

import os
import sys
import subprocess
import argparse

def run_tests(verbose=False, coverage=False, pattern=None):
    """
    Run pytest with optional parameters.
    
    Args:
        verbose: Run with verbose output
        coverage: Run with coverage reporting
        pattern: Only run tests matching the pattern
    """
    # Ensure pytest and pytest-asyncio are installed
    try:
        import pytest
        import pytest_asyncio
    except ImportError:
        print("Installing test dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pytest", "pytest-asyncio", "pytest-cov"])
    
    # Build command
    cmd = [sys.executable, "-m", "pytest"]
    
    # Add options
    if verbose:
        cmd.append("-v")
        
    if coverage:
        cmd.extend(["--cov=alphaevolve", "--cov-report=term", "--cov-report=html"])
        
    if pattern:
        cmd.append(pattern)
        
    # Run the tests
    result = subprocess.run(cmd)
    return result.returncode

def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Run AlphaEvolve unit tests")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--coverage", action="store_true", help="Run with coverage reporting")
    parser.add_argument("pattern", nargs="?", help="Only run tests matching the pattern")
    
    args = parser.parse_args()
    
    # Run the tests
    return run_tests(verbose=args.verbose, coverage=args.coverage, pattern=args.pattern)

if __name__ == "__main__":
    sys.exit(main()) 