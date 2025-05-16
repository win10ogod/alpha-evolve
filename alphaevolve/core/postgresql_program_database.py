import logging
import uuid
from typing import Dict, List, Tuple, Optional, Any
import json
import datetime
import os
import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool

from alphaevolve.core.program_database import Program, ProgramDatabase

logger = logging.getLogger(__name__)

class PostgreSQLProgramDatabase(ProgramDatabase):
    """
    PostgreSQL-backed implementation of the ProgramDatabase.
    Stores programs in a PostgreSQL database instead of files.
    """
    
    def __init__(
        self,
        results_dir: str,
        db_config: Dict[str, Any],
        population_size: int = 100,
        archive_mode: str = "pareto",  # Options: "pareto", "best", "diverse"
        metrics: List[str] = None,
        min_pool_size: int = 1,
        max_pool_size: int = 10,
    ):
        """
        Initialize the PostgreSQL Program Database.
        
        Args:
            results_dir: Directory to store any file-related data
            db_config: PostgreSQL connection parameters dict
                      (host, port, dbname, user, password)
            population_size: Max number of programs to keep in active population
            archive_mode: Strategy for maintaining the program archive
            metrics: List of metrics to optimize for (e.g., ["accuracy", "speed"])
            min_pool_size: Minimum size of the connection pool
            max_pool_size: Maximum size of the connection pool
        """
        # Initialize basic properties
        self.results_dir = results_dir
        self.population_size = population_size
        self.archive_mode = archive_mode
        self.metrics = metrics or ["fitness"]
        
        # Ensure results directory exists
        os.makedirs(self.results_dir, exist_ok=True)
        os.makedirs(os.path.join(self.results_dir, "programs"), exist_ok=True)
        
        # In-memory program storage
        self.programs: Dict[str, Program] = {}
        
        # Setup database connection pool
        self.db_config = db_config
        self.pool = SimpleConnectionPool(
            min_pool_size, 
            max_pool_size,
            **db_config
        )
        
        # Initialize database
        self._initialize_database()
        
        # Load programs from database
        self._load_existing_programs()
        
    def _initialize_database(self):
        """Create necessary tables if they don't exist."""
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cursor:
                # Create programs table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS programs (
                        id VARCHAR(36) PRIMARY KEY,
                        code TEXT NOT NULL,
                        scores JSONB NOT NULL,
                        parent_id VARCHAR(36),
                        timestamp TIMESTAMP NOT NULL,
                        metadata JSONB
                    )
                """)
                
                # Create index on timestamp for faster sorting
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS programs_timestamp_idx ON programs (timestamp)
                """)
                
                # Create index on parent_id for ancestry queries
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS programs_parent_id_idx ON programs (parent_id)
                """)
                
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Error initializing database: {str(e)}")
            raise
        finally:
            self.pool.putconn(conn)
    
    def _load_existing_programs(self):
        """Load existing programs from the database."""
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT * FROM programs")
                rows = cursor.fetchall()
                
                for row in rows:
                    program = Program(
                        id=row['id'],
                        code=row['code'],
                        scores=row['scores'],
                        parent_id=row['parent_id'],
                        timestamp=row['timestamp'].isoformat(),
                        metadata=row['metadata'] or {}
                    )
                    self.programs[program.id] = program
                    
            logger.info(f"Loaded {len(self.programs)} existing programs from PostgreSQL")
        except Exception as e:
            logger.error(f"Error loading programs from database: {str(e)}")
        finally:
            self.pool.putconn(conn)
    
    def _save_program(self, program: Program):
        """Save a program to the PostgreSQL database."""
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cursor:
                # Insert program record
                cursor.execute("""
                    INSERT INTO programs (id, code, scores, parent_id, timestamp, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    program.id,
                    program.code,
                    json.dumps(program.scores),
                    program.parent_id,
                    datetime.datetime.fromisoformat(program.timestamp),
                    json.dumps(program.metadata) if program.metadata else None
                ))
                
                # Also save to file for easy inspection (optional)
                code_filename = os.path.join(self.results_dir, "programs", f"{program.id}.py")
                with open(code_filename, "w") as f:
                    f.write(program.code)
                    
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Error saving program to database: {str(e)}")
            # Fall back to file-based storage
            super()._save_program(program)
        finally:
            self.pool.putconn(conn)
    
    def _update_population(self):
        """Update the population based on the selected archive strategy."""
        if len(self.programs) <= self.population_size:
            return
            
        # Get programs to keep using parent class implementation
        if self.archive_mode == "pareto":
            to_keep = self._get_pareto_front()
        elif self.archive_mode == "best":
            primary_metric = self.metrics[0]
            sorted_programs = sorted(
                self.programs.values(),
                key=lambda p: p.scores.get(primary_metric, float("-inf")),
                reverse=True
            )
            to_keep = [p.id for p in sorted_programs[:self.population_size]]
        else:  # "diverse"
            to_keep = self._get_diverse_population()
            
        # Remove programs not in the kept set from both memory and database
        programs_to_remove = set(self.programs.keys()) - set(to_keep)
        if not programs_to_remove:
            return
            
        # Remove from memory
        for program_id in programs_to_remove:
            del self.programs[program_id]
        
        # Mark as inactive in database, but keep the records
        # This is a soft delete that preserves history
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cursor:
                placeholders = ", ".join(["%s"] * len(programs_to_remove))
                cursor.execute(f"""
                    UPDATE programs
                    SET metadata = metadata || '{"active": false}'::jsonb
                    WHERE id IN ({placeholders})
                """, tuple(programs_to_remove))
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating population in database: {str(e)}")
        finally:
            self.pool.putconn(conn)
    
    def get_program_ancestors(self, program_id: str, max_depth: int = 10) -> List[Program]:
        """
        Get the ancestry chain of a program up to a maximum depth.
        
        Args:
            program_id: ID of the program to get ancestors for
            max_depth: Maximum number of generations to trace back
            
        Returns:
            List of ancestor programs, ordered from parent to earliest ancestor
        """
        ancestors = []
        current_id = program_id
        depth = 0
        
        # First try to find ancestors in memory
        while current_id and depth < max_depth:
            program = self.programs.get(current_id)
            if not program:
                break
                
            current_id = program.parent_id
            if current_id:
                parent = self.programs.get(current_id)
                if parent:
                    ancestors.append(parent)
                    depth += 1
        
        # If we didn't find all ancestors in memory, query the database
        if depth < max_depth and current_id:
            conn = self.pool.getconn()
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    # Recursive query to get ancestors
                    cursor.execute("""
                        WITH RECURSIVE ancestry AS (
                            SELECT * FROM programs WHERE id = %s
                            UNION ALL
                            SELECT p.* FROM programs p
                            JOIN ancestry a ON p.id = a.parent_id
                            WHERE p.id IS NOT NULL
                        )
                        SELECT * FROM ancestry
                        WHERE id != %s
                        LIMIT %s
                    """, (program_id, program_id, max_depth))
                    
                    rows = cursor.fetchall()
                    for row in rows:
                        # Skip if already in the list
                        if any(a.id == row['id'] for a in ancestors):
                            continue
                            
                        program = Program(
                            id=row['id'],
                            code=row['code'],
                            scores=row['scores'],
                            parent_id=row['parent_id'],
                            timestamp=row['timestamp'].isoformat(),
                            metadata=row['metadata'] or {}
                        )
                        ancestors.append(program)
            except Exception as e:
                logger.error(f"Error retrieving program ancestry: {str(e)}")
            finally:
                self.pool.putconn(conn)
                
        return ancestors
    
    def close(self):
        """Close database connection pool."""
        if hasattr(self, 'pool') and self.pool:
            self.pool.closeall()
            logger.info("Closed PostgreSQL connection pool") 