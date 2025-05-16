import logging
import uuid
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import json
import os
import datetime

logger = logging.getLogger(__name__)

@dataclass
class Program:
    """Represents a program in the database."""
    
    id: str
    code: str
    scores: Dict[str, float]
    parent_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

class ProgramDatabase:
    """
    Manages storage and sampling of programs in the AlphaEvolve system.
    Implements strategies to maintain population diversity and select candidates.
    """
    
    def __init__(
        self,
        results_dir: str,
        population_size: int = 100,
        archive_mode: str = "pareto",  # Options: "pareto", "best", "diverse"
        metrics: List[str] = None,
    ):
        """
        Initialize the Program Database.
        
        Args:
            results_dir: Directory to store program data
            population_size: Max number of programs to keep in active population
            archive_mode: Strategy for maintaining the program archive
            metrics: List of metrics to optimize for (e.g., ["accuracy", "speed"])
        """
        self.results_dir = results_dir
        self.population_size = population_size
        self.archive_mode = archive_mode
        self.metrics = metrics or ["fitness"]
        
        # Ensure results directory exists
        os.makedirs(self.results_dir, exist_ok=True)
        os.makedirs(os.path.join(self.results_dir, "programs"), exist_ok=True)
        
        # In-memory program storage
        self.programs: Dict[str, Program] = {}
        
        # Load any existing programs from the results directory
        self._load_existing_programs()
        
    def _load_existing_programs(self):
        """Load existing programs from the results directory."""
        programs_dir = os.path.join(self.results_dir, "programs")
        if not os.path.exists(programs_dir):
            return
            
        for filename in os.listdir(programs_dir):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(programs_dir, filename), "r") as f:
                        data = json.load(f)
                        program = Program(
                            id=data["id"],
                            code=data["code"],
                            scores=data["scores"],
                            parent_id=data.get("parent_id"),
                            timestamp=data["timestamp"],
                            metadata=data.get("metadata", {})
                        )
                        self.programs[program.id] = program
                except Exception as e:
                    logger.error(f"Error loading program {filename}: {str(e)}")
        
        logger.info(f"Loaded {len(self.programs)} existing programs")
        
    def add_program(self, program: str, scores: Dict[str, float], parent_id: Optional[str] = None, 
                    metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a new program to the database.
        
        Args:
            program: Source code of the program
            scores: Performance metrics
            parent_id: ID of the parent program (if any)
            metadata: Additional metadata about the program
        
        Returns:
            ID of the new program
        """
        program_id = str(uuid.uuid4())
        
        # Create Program object
        new_program = Program(
            id=program_id,
            code=program,
            scores=scores,
            parent_id=parent_id,
            metadata=metadata or {}
        )
        
        # Add to in-memory storage
        self.programs[program_id] = new_program
        
        # Persist to disk
        self._save_program(new_program)
        
        # Update population if needed
        self._update_population()
        
        return program_id
        
    def _save_program(self, program: Program):
        """Save a program to disk."""
        program_data = {
            "id": program.id,
            "code": program.code,
            "scores": program.scores,
            "parent_id": program.parent_id,
            "timestamp": program.timestamp,
            "metadata": program.metadata
        }
        
        filename = os.path.join(self.results_dir, "programs", f"{program.id}.json")
        with open(filename, "w") as f:
            json.dump(program_data, f, indent=2)
            
        # Save the code as a separate file for easy inspection
        code_filename = os.path.join(self.results_dir, "programs", f"{program.id}.py")
        with open(code_filename, "w") as f:
            f.write(program.code)
        
    def _update_population(self):
        """Update the population based on the selected archive strategy."""
        if len(self.programs) <= self.population_size:
            return
            
        # Sort programs based on archive mode
        if self.archive_mode == "pareto":
            # Keep Pareto front programs (non-dominated solutions)
            to_keep = self._get_pareto_front()
        elif self.archive_mode == "best":
            # Keep best programs based on primary metric
            primary_metric = self.metrics[0]
            sorted_programs = sorted(
                self.programs.values(),
                key=lambda p: p.scores.get(primary_metric, float("-inf")),
                reverse=True
            )
            to_keep = [p.id for p in sorted_programs[:self.population_size]]
        else:  # "diverse"
            # Keep diverse set of programs (simple implementation)
            to_keep = self._get_diverse_population()
            
        # Remove programs not in the kept set
        programs_to_remove = set(self.programs.keys()) - set(to_keep)
        for program_id in programs_to_remove:
            # Note: We're not deleting files from disk for history tracking
            del self.programs[program_id]
            
    def _get_pareto_front(self) -> List[str]:
        """Get the Pareto front of programs (those not dominated by others)."""
        pareto_front = []
        program_list = list(self.programs.values())
        
        for p1 in program_list:
            dominated = False
            for p2 in program_list:
                if p1.id == p2.id:
                    continue
                    
                # Check if p2 dominates p1
                p2_dominates = True
                for metric in self.metrics:
                    p1_score = p1.scores.get(metric, float("-inf"))
                    p2_score = p2.scores.get(metric, float("-inf"))
                    
                    # For maximization metrics
                    if p2_score < p1_score:
                        p2_dominates = False
                        break
                        
                if p2_dominates:
                    dominated = True
                    break
                    
            if not dominated:
                pareto_front.append(p1.id)
                
        # If Pareto front is smaller than population size, add other programs
        if len(pareto_front) < self.population_size:
            # Add remaining programs sorted by primary metric
            primary_metric = self.metrics[0]
            remaining = [
                p.id for p in sorted(
                    [p for p in program_list if p.id not in pareto_front],
                    key=lambda p: p.scores.get(primary_metric, float("-inf")),
                    reverse=True
                )
            ]
            pareto_front.extend(remaining[:self.population_size - len(pareto_front)])
            
        return pareto_front[:self.population_size]
        
    def _get_diverse_population(self) -> List[str]:
        """Get a diverse set of programs by simple clustering."""
        # Simple implementation: keep a mix of best and newest programs
        
        # Sort by primary metric (best performers)
        primary_metric = self.metrics[0]
        best_programs = sorted(
            self.programs.values(),
            key=lambda p: p.scores.get(primary_metric, float("-inf")),
            reverse=True
        )
        
        # Sort by timestamp (newest)
        newest_programs = sorted(
            self.programs.values(),
            key=lambda p: p.timestamp,
            reverse=True
        )
        
        # Combine best and newest, removing duplicates
        diverse_ids = []
        seen = set()
        
        # Take half from best
        best_half = int(self.population_size * 0.5)
        for p in best_programs:
            if p.id not in seen and len(diverse_ids) < best_half:
                diverse_ids.append(p.id)
                seen.add(p.id)
        
        # Take rest from newest
        for p in newest_programs:
            if p.id not in seen and len(diverse_ids) < self.population_size:
                diverse_ids.append(p.id)
                seen.add(p.id)
                
        return diverse_ids
        
    def sample_programs(self) -> Tuple[Program, List[Program]]:
        """
        Sample a parent program and inspirations from the database.
        
        Returns:
            Tuple containing:
                - Parent program to modify
                - List of inspiration programs
        """
        if not self.programs:
            raise ValueError("No programs in database to sample from")
            
        # Sample parent program with preference for higher scores
        primary_metric = self.metrics[0]
        sorted_programs = sorted(
            self.programs.values(),
            key=lambda p: p.scores.get(primary_metric, float("-inf")),
            reverse=True
        )
        
        # Simple selection: 70% chance to pick from top third, 30% chance to pick randomly
        if len(sorted_programs) >= 3 and (uuid.uuid4().int % 10) < 7:
            top_third = sorted_programs[:max(1, len(sorted_programs) // 3)]
            parent = top_third[uuid.uuid4().int % len(top_third)]
        else:
            parent = sorted_programs[uuid.uuid4().int % len(sorted_programs)]
            
        # Sample inspiration programs (non-parent)
        inspirations = []
        inspiration_candidates = [p for p in sorted_programs if p.id != parent.id]
        
        if inspiration_candidates:
            # Take up to 3 top-performing non-parent programs as inspiration
            inspirations = inspiration_candidates[:min(3, len(inspiration_candidates))]
            
        return parent, inspirations
        
    def get_best_program(self, metric: Optional[str] = None) -> Optional[Program]:
        """Get the best program according to the specified or primary metric."""
        if not self.programs:
            return None
            
        metric = metric or self.metrics[0]
        return max(
            self.programs.values(),
            key=lambda p: p.scores.get(metric, float("-inf"))
        )
        
    def get_best_programs(self, limit: int = 5) -> List[Program]:
        """Get the top N best programs according to the primary metric."""
        if not self.programs:
            return []
            
        primary_metric = self.metrics[0]
        return sorted(
            self.programs.values(),
            key=lambda p: p.scores.get(primary_metric, float("-inf")),
            reverse=True
        )[:limit]
        
    def get_top_programs(self, metric: Optional[str] = None, limit: int = 5) -> List[Program]:
        """Get the top N programs according to the specified or primary metric."""
        if not self.programs:
            return []
            
        metric = metric or self.metrics[0]
        return sorted(
            self.programs.values(),
            key=lambda p: p.scores.get(metric, float("-inf")),
            reverse=True
        )[:limit]
        
    def get_program(self, program_id: str) -> Optional[Program]:
        """Get a specific program by ID."""
        return self.programs.get(program_id)
        
    def get_all_programs(self) -> List[Program]:
        """Get all programs in the database."""
        return list(self.programs.values()) 