"""
Unit tests for the postgresql_program_database module.
"""

import os
import pytest
import json
import datetime
from unittest.mock import patch, MagicMock, call

from alphaevolve.core.postgresql_program_database import PostgreSQLProgramDatabase
from alphaevolve.core.program_database import Program

@pytest.fixture
def mock_pool():
    """Mock connection pool for PostgreSQL."""
    pool = MagicMock()
    conn = MagicMock()
    cursor = MagicMock()
    
    # Mock connection and cursor behavior
    pool.getconn.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cursor
    
    return pool, conn, cursor

@pytest.fixture
def postgres_db(temp_dir, mock_pool):
    """Create a PostgreSQLProgramDatabase with mocks."""
    pool, _, _ = mock_pool
    
    # Patch the connection pool creation
    with patch('alphaevolve.core.postgresql_program_database.SimpleConnectionPool', return_value=pool):
        # Create the database
        db = PostgreSQLProgramDatabase(
            results_dir=temp_dir,
            db_config={
                'host': 'localhost',
                'port': 5432,
                'dbname': 'alphaevolve_test',
                'user': 'test_user',
                'password': 'test_password'
            },
            population_size=5,
            metrics=["accuracy", "performance"]
        )
        yield db
        
        # Close the database connection
        db.close()

class TestPostgreSQLProgramDatabase:
    """Tests for the PostgreSQLProgramDatabase class."""
    
    def test_initialization(self, mock_pool, temp_dir):
        """Test database initialization."""
        pool, conn, cursor = mock_pool
        
        # Patch the connection pool creation
        with patch('alphaevolve.core.postgresql_program_database.SimpleConnectionPool', return_value=pool):
            # Create the database
            db = PostgreSQLProgramDatabase(
                results_dir=temp_dir,
                db_config={
                    'host': 'localhost',
                    'port': 5432,
                    'dbname': 'alphaevolve_test',
                    'user': 'test_user',
                    'password': 'test_password'
                },
                population_size=10,
                metrics=["accuracy", "performance"]
            )
            
            # Verify database initialization
            pool.getconn.assert_called_once()
            conn.cursor.assert_called()
            cursor.execute.assert_called()
            conn.commit.assert_called_once()
            pool.putconn.assert_called_once_with(conn)
            
            # Close the connection
            db.close()
    
    def test_load_existing_programs(self, postgres_db, mock_pool):
        """Test loading existing programs from the database."""
        _, conn, cursor = mock_pool
        
        # Mock cursor.fetchall return value
        mock_timestamp = datetime.datetime.now()
        cursor.fetchall.return_value = [
            {
                'id': 'prog1',
                'code': 'def test1(): return 42',
                'scores': {'accuracy': 0.9, 'performance': 0.7},
                'parent_id': None,
                'timestamp': mock_timestamp,
                'metadata': {'version': 1}
            },
            {
                'id': 'prog2', 
                'code': 'def test2(): return 43',
                'scores': {'accuracy': 0.8, 'performance': 0.8},
                'parent_id': 'prog1',
                'timestamp': mock_timestamp,
                'metadata': None
            }
        ]
        
        # Call the method
        postgres_db._load_existing_programs()
        
        # Verify the cursor was called with SELECT
        cursor.execute.assert_called_with("SELECT * FROM programs")
        
        # Verify programs were loaded into memory
        assert len(postgres_db.programs) == 2
        assert 'prog1' in postgres_db.programs
        assert 'prog2' in postgres_db.programs
        assert postgres_db.programs['prog1'].code == 'def test1(): return 42'
        assert postgres_db.programs['prog2'].parent_id == 'prog1'
    
    def test_save_program(self, postgres_db, mock_pool):
        """Test saving a program to the database."""
        _, conn, cursor = mock_pool
        
        # Create a program
        program = Program(
            id="test_id",
            code="def test(): return 42",
            scores={"accuracy": 0.9, "performance": 0.7},
            parent_id=None,
            timestamp=datetime.datetime.now().isoformat(),
            metadata={"version": 1}
        )
        
        # Save the program
        postgres_db._save_program(program)
        
        # Verify the cursor was called with INSERT
        cursor.execute.assert_called()
        conn.commit.assert_called_once()
        
        # Verify file was also created
        code_file = os.path.join(postgres_db.results_dir, "programs", f"{program.id}.py")
        assert os.path.exists(code_file)
        with open(code_file, 'r') as f:
            assert f.read() == program.code
    
    def test_update_population(self, postgres_db, mock_pool):
        """Test updating the population based on scores."""
        _, conn, cursor = mock_pool
        
        # Add multiple programs
        for i in range(10):  # Exceeds population_size of 5
            postgres_db.programs[f"prog{i}"] = Program(
                id=f"prog{i}",
                code=f"def test{i}(): return {i}",
                scores={"accuracy": 0.5 + i * 0.05, "performance": 0.5},
                timestamp=datetime.datetime.now().isoformat()
            )
        
        # Update population
        postgres_db._update_population()
        
        # Verify database was updated
        cursor.execute.assert_called()
        conn.commit.assert_called()
        
        # Should keep only the 5 best programs (based on accuracy)
        assert len(postgres_db.programs) == 5
        
        # The best ones should be kept
        for i in range(5, 10):
            assert f"prog{i}" in postgres_db.programs
    
    def test_get_program_ancestors(self, postgres_db, mock_pool):
        """Test retrieving program ancestors."""
        _, conn, cursor = mock_pool
        
        # Create a chain of programs in memory
        postgres_db.programs["prog3"] = Program(
            id="prog3",
            code="def test3(): return 3",
            scores={"accuracy": 0.9},
            parent_id="prog2",
            timestamp=datetime.datetime.now().isoformat()
        )
        
        postgres_db.programs["prog2"] = Program(
            id="prog2", 
            code="def test2(): return 2",
            scores={"accuracy": 0.8},
            parent_id="prog1",
            timestamp=datetime.datetime.now().isoformat()
        )
        
        # prog1 is not in memory, will be fetched from DB
        mock_timestamp = datetime.datetime.now()
        cursor.fetchall.return_value = [
            {
                'id': 'prog1',
                'code': 'def test1(): return 1',
                'scores': {'accuracy': 0.7},
                'parent_id': None,
                'timestamp': mock_timestamp,
                'metadata': {}
            }
        ]
        
        # Get ancestors of prog3
        ancestors = postgres_db.get_program_ancestors("prog3")
        
        # Should fetch prog1 from database
        cursor.execute.assert_called()
        
        # Should return both ancestors
        assert len(ancestors) == 2
        assert ancestors[0].id == "prog2"
        assert ancestors[1].id == "prog1"
    
    def test_close(self, postgres_db, mock_pool):
        """Test closing the database connection."""
        pool, _, _ = mock_pool
        
        # Close the database
        postgres_db.close()
        
        # Verify the pool was closed
        pool.closeall.assert_called_once() 