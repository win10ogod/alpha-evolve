# AlphaEvolve

AlphaEvolve is a system that uses Large Language Models (LLMs) within an evolutionary framework to iteratively improve code for solving complex scientific, algorithmic, or engineering problems.

## Overview

AlphaEvolve combines the power of modern LLMs with evolutionary computation to:

1. Automatically evolve and improve code
2. Discover novel and efficient solutions
3. Adapt code to changing requirements and environments

The system maintains a population of programs (solutions) and iteratively improves them through LLM-driven mutations, automated evaluations, and selection.

## Key Features

- **Evolutionary Framework**: Maintains a population of programs that evolve over time
- **LLM Integration**: Uses Language Models to propose intelligent code modifications
- **Flexible Evaluation**: Pluggable evaluation system to assess program fitness
- **Block-based Evolution**: Can focus evolution on specific code blocks marked with special comments
- **Meta-Prompt Evolution**: Optional evolution of prompt templates to improve LLM guidance
- **Persistent Storage**: Supports both file-based and PostgreSQL database backends for program storage

## Architecture

AlphaEvolve consists of several core components:

- **Controller**: The central orchestrator that manages the evolutionary loop.
- **Program Database**: Stores programs, their performance metrics, and maintains population diversity.
- **Prompt Sampler**: Constructs prompts for LLMs based on templates, context, and successful programs.
- **LLM Interface**: Handles communication with Large Language Models (via LiteLLM).
- **Code Patcher**: Applies LLM-generated changes to code, handling different formats and evolve blocks.
- **Evaluation Manager**: Executes and evaluates programs, potentially in parallel.
- **Meta-Prompter**: (Optional) Evolves prompt templates over time to improve LLM performance.

## Getting Started

### Prerequisites

- Python 3.8+
- Access to one or more LLMs (configured via LiteLLM)

### Installation

```bash
git clone https://github.com/yourusername/alphaevolve.git
cd alphaevolve
pip install -e .
```

### Basic Usage

1. **Create a new problem:**

```bash
python -m alphaevolve.cli.alphaevolve new my_problem
```

This creates a new problem directory with template files.

2. **Customize the problem:**

- Modify the source code in `problems/my_problem/src/`
- Update the evaluation function in `problems/my_problem/evaluate.py`
- Add context files to `problems/my_problem/problem_context/`
- Customize prompt templates in `problems/my_problem/prompt_templates/`

3. **Run AlphaEvolve:**

```bash
python -m alphaevolve.cli.alphaevolve run problems/my_problem/config.yaml
```

## Creating a Custom Problem

To create a custom problem for AlphaEvolve:

1. Define the problem by providing initial code.
2. Mark sections of code to evolve using `# EVOLVE-BLOCK-START` and `# EVOLVE-BLOCK-END` comments.
3. Create an evaluation function that returns a dictionary of metrics.
4. Configure the AlphaEvolve run via the config file.

### Example Evaluation Function

```python
def evaluate(program_path: str) -> Dict[str, float]:
    """
    Evaluate a program by testing its performance.
    
    Args:
        program_path: Path to the program file
        
    Returns:
        Dictionary of performance metrics (higher is better)
    """
    try:
        # Load and test the program
        # ...
        
        return {
            "accuracy": 0.95,
            "efficiency": 0.85,
            "overall": 0.90
        }
    except Exception:
        return {"error": 1.0}
```

## Configuration

AlphaEvolve is configured via YAML files. Key parameters include:

- `problem_dir`: Path to the problem directory
- `controller`: Settings for the evolutionary loop
- `llm`: LLM model and generation settings
- `evaluation`: Settings for evaluation
- `program_database`: Population and archiving settings
- `prompt`: Prompt templates and context settings

## Using PostgreSQL Storage

AlphaEvolve supports using PostgreSQL for persistent storage of programs and their evolutionary history. This is particularly useful for:

1. Handling large populations and long-running experiments
2. Preserving evolution history across multiple runs
3. Enabling more complex queries and analysis of the evolutionary process
4. Supporting distributed or multi-machine experiments

### Setup PostgreSQL

1. Install PostgreSQL and create a database:
```bash
# Example for Ubuntu/Debian
sudo apt install postgresql
sudo -u postgres psql -c "CREATE DATABASE alphaevolve;"
sudo -u postgres psql -c "CREATE USER alphaevolve_user WITH PASSWORD 'your_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE alphaevolve TO alphaevolve_user;"
```

2. Add PostgreSQL configuration to your AlphaEvolve config file:
```yaml
program_database:
  db_type: "postgresql"
  population_size: 100
  metrics: ["accuracy", "performance"]
  
  postgresql:
    host: "localhost"
    port: 5432
    dbname: "alphaevolve"
    user: "alphaevolve_user"
    password: "your_password"
  
  min_pool_size: 1
  max_pool_size: 10
```

3. Run AlphaEvolve with this configuration to use PostgreSQL storage.

You can find a full example configuration in `alphaevolve/common_configs/postgresql_example.yaml`.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

I recommend you to read the original article, I am just a poor imitation.

[alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms](https://deepmind.google/discover/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/)

AlphaEvolve is inspired by works at the intersection of LLMs and evolutionary computation, including research on automated programming, genetic programming, and LLM-guided search. 
