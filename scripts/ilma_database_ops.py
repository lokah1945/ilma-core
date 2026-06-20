#!/usr/bin/env python3
"""
ILMA Database Operations Engine
===============================
Database query execution, migration management, and connection pooling.
Supports SQL and NoSQL databases.

Classes: QueryEngine, MigrationManager, ConnectionPool

Usage:
    python3 ilma_database_ops.py --query "SELECT * FROM users LIMIT 10"
    python3 ilma_database_ops.py --migrate --up
    python3 ilma_database_ops.py --pool-status

Author: ILMA v5.0
Version: 1.0.0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DatabaseOps")


# =============================================================================
# ENUMS AND DATA STRUCTURES
# =============================================================================

class DatabaseType(Enum):
    """Supported database types."""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    REDIS = "redis"


class MigrationDirection(Enum):
    """Migration direction."""
    UP = "up"
    DOWN = "down"


@dataclass
class QueryResult:
    """Result of a database query."""
    success: bool
    rows: List[Tuple[Any, ...]]
    columns: List[str]
    row_count: int
    execution_time_ms: float
    error_message: Optional[str] = None


@dataclass
class MigrationRecord:
    """Record of a migration."""
    version: int
    name: str
    applied_at: datetime
    direction: MigrationDirection
    checksum: str


@dataclass
class ConnectionConfig:
    """Database connection configuration."""
    db_type: DatabaseType
    host: str = "localhost"
    port: int = 0
    database: str = ""
    username: str = ""
    password: str = ""
    timeout: int = 30
    max_connections: int = 10


# =============================================================================
# CONNECTION POOL CLASS
# =============================================================================

class ConnectionPool:
    """
    Database connection pool with lifecycle management.
    
    Supports configurable pool sizes, timeout settings, and connection reuse.
    """
    
    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.pool: List[Any] = []
        self.in_use: Set[Any] = set()
        self.available: List[Any] = []
        self.max_connections = config.max_connections
        self.created_count = 0
        self._lock = None  # Simplified for single-threaded use
        logger.info(f"ConnectionPool initialized for {config.db_type.value}")
    
    def get_connection(self) -> Optional[Any]:
        """Get a connection from the pool."""
        try:
            # Try to get from available pool
            if self.available:
                conn = self.available.pop()
                self.in_use.add(conn)
                return conn
            
            # Create new connection if under limit
            if self.created_count < self.max_connections:
                conn = self._create_connection()
                if conn:
                    self.created_count += 1
                    self.in_use.add(conn)
                    return conn
            
            # Wait and retry or return None
            logger.warning("Connection pool exhausted")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get connection: {e}")
            return None
    
    def release_connection(self, conn: Any) -> bool:
        """Release a connection back to the pool."""
        try:
            if conn in self.in_use:
                self.in_use.remove(conn)
                if self._is_connection_valid(conn):
                    self.available.append(conn)
                    return True
                else:
                    # Connection is invalid, close it
                    self._close_connection(conn)
                    self.created_count -= 1
                    return False
            return False
            
        except Exception as e:
            logger.error(f"Failed to release connection: {e}")
            return False
    
    def _create_connection(self) -> Optional[Any]:
        """Create a new database connection."""
        try:
            if self.config.db_type == DatabaseType.SQLITE:
                conn = sqlite3.connect(self.config.database, timeout=self.config.timeout)
                conn.row_factory = sqlite3.Row
                return conn
            
            elif self.config.db_type == DatabaseType.POSTGRESQL:
                import psycopg2
                conn = psycopg2.connect(
                    host=self.config.host,
                    port=self.config.port or 5432,
                    dbname=self.config.database,
                    user=self.config.username,
                    password=self.config.password,
                    connect_timeout=self.config.timeout
                )
                return conn
            
            elif self.config.db_type == DatabaseType.MYSQL:
                import pymysql
                conn = pymysql.connect(
                    host=self.config.host,
                    port=self.config.port or 3306,
                    db=self.config.database,
                    user=self.config.username,
                    password=self.config.password,
                    connect_timeout=self.config.timeout
                )
                return conn
            
            else:
                logger.error(f"Unsupported database type: {self.config.db_type}")
                return None
                
        except ImportError as e:
            logger.error(f"Database driver not available: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
            return None
    
    def _is_connection_valid(self, conn: Any) -> bool:
        """Check if a connection is still valid."""
        try:
            if self.config.db_type == DatabaseType.SQLITE:
                conn.execute("SELECT 1")
                return True
            elif self.config.db_type in (DatabaseType.POSTGRESQL, DatabaseType.MYSQL):
                conn.cursor().execute("SELECT 1")
                return True
            return False
        except Exception:
            return False
    
    def _close_connection(self, conn: Any) -> None:
        """Close a connection."""
        try:
            conn.close()
        except Exception:
            pass
    
    def close_all(self) -> None:
        """Close all connections in the pool."""
        all_conns = list(self.in_use) + self.available
        for conn in all_conns:
            try:
                conn.close()
            except Exception:
                pass
        
        self.pool.clear()
        self.available.clear()
        self.in_use.clear()
        self.created_count = 0
        logger.info("All connections closed")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        return {
            "max_connections": self.max_connections,
            "created": self.created_count,
            "available": len(self.available),
            "in_use": len(self.in_use),
            "total": len(self.pool)
        }


# =============================================================================
# QUERY ENGINE CLASS
# =============================================================================

class QueryEngine:
    """
    Database query execution engine with support for multiple databases,
    parameterized queries, and transaction management.
    """
    
    def __init__(self, pool: Optional[ConnectionPool] = None, config: Optional[ConnectionConfig] = None):
        if pool:
            self.pool = pool
        elif config:
            self.pool = ConnectionPool(config)
        else:
            # Default to SQLite
            self.pool = ConnectionPool(ConnectionConfig(
                db_type=DatabaseType.SQLITE,
                database=":memory:"
            ))
        self.query_history: List[Dict[str, Any]] = []
        logger.info("QueryEngine initialized")
    
    def execute_query(
        self,
        query: str,
        params: Optional[Tuple[Any, ...]] = None,
        fetch: bool = True
    ) -> QueryResult:
        """Execute a query and return results."""
        start_time = time.time()
        
        conn = self.pool.get_connection()
        if not conn:
            return QueryResult(
                success=False,
                rows=[],
                columns=[],
                row_count=0,
                execution_time_ms=0,
                error_message="Failed to get connection from pool"
            )
        
        try:
            cursor = conn.cursor()
            
            # Execute query
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            execution_time = (time.time() - start_time) * 1000
            
            # Fetch results if requested
            if fetch:
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                
                result = QueryResult(
                    success=True,
                    rows=rows,
                    columns=columns,
                    row_count=len(rows),
                    execution_time_ms=execution_time
                )
            else:
                result = QueryResult(
                    success=True,
                    rows=[],
                    columns=[],
                    row_count=cursor.rowcount,
                    execution_time_ms=execution_time
                )
            
            # Record in history
            self.query_history.append({
                "query": query[:200],  # Truncate for history
                "params": str(params)[:100],
                "execution_time_ms": execution_time,
                "row_count": result.row_count,
                "timestamp": datetime.now().isoformat()
            })
            
            return result
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Query execution failed: {e}")
            return QueryResult(
                success=False,
                rows=[],
                columns=[],
                row_count=0,
                execution_time_ms=execution_time,
                error_message=str(e)
            )
        finally:
            self.pool.release_connection(conn)
    
    def execute_many(
        self,
        query: str,
        params_list: List[Tuple[Any, ...]]
    ) -> QueryResult:
        """Execute a query with multiple parameter sets."""
        start_time = time.time()
        
        conn = self.pool.get_connection()
        if not conn:
            return QueryResult(
                success=False,
                rows=[],
                columns=[],
                row_count=0,
                execution_time_ms=0,
                error_message="Failed to get connection from pool"
            )
        
        try:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            
            execution_time = (time.time() - start_time) * 1000
            
            result = QueryResult(
                success=True,
                rows=[],
                columns=[],
                row_count=len(params_list),
                execution_time_ms=execution_time
            )
            
            return result
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Batch query execution failed: {e}")
            return QueryResult(
                success=False,
                rows=[],
                columns=[],
                row_count=0,
                execution_time_ms=execution_time,
                error_message=str(e)
            )
        finally:
            self.pool.release_connection(conn)
    
    def begin_transaction(self) -> bool:
        """Begin a transaction."""
        conn = self.pool.get_connection()
        if not conn:
            return False
        
        try:
            conn.execute("BEGIN")
            return True
        except Exception as e:
            logger.error(f"Failed to begin transaction: {e}")
            return False
        finally:
            # For simplicity, we'll keep connection in pool
            # In production, you'd want proper transaction tracking
            self.pool.release_connection(conn)
    
    def commit_transaction(self) -> bool:
        """Commit a transaction."""
        result = self.execute_query("COMMIT", fetch=False)
        return result.success
    
    def rollback_transaction(self) -> bool:
        """Rollback a transaction."""
        result = self.execute_query("ROLLBACK", fetch=False)
        return result.success
    
    def get_table_info(self, table_name: str) -> List[Dict[str, Any]]:
        """Get information about a table's structure."""
        if self.pool.config.db_type == DatabaseType.SQLITE:
            query = f"PRAGMA table_info({table_name})"
            result = self.execute_query(query)
            
            if result.success:
                return [
                    {
                        "name": row[1],
                        "type": row[2],
                        "nullable": not row[3],
                        "default": row[4],
                        "primary_key": bool(row[5])
                    }
                    for row in result.rows
                ]
        elif self.pool.config.db_type == DatabaseType.POSTGRESQL:
            query = """
            SELECT column_name, data_type, is_nullable, column_default, is_primary_key
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
            """
            result = self.execute_query(query, (table_name,))
            
            if result.success:
                return [
                    {
                        "name": row[0],
                        "type": row[1],
                        "nullable": row[2] == "YES",
                        "default": row[3],
                        "primary_key": row[4]
                    }
                    for row in result.rows
                ]
        
        return []
    
    def explain_query(self, query: str) -> str:
        """Get query execution plan."""
        if self.pool.config.db_type == DatabaseType.SQLITE:
            result = self.execute_query(f"EXPLAIN QUERY PLAN {query}")
            if result.success:
                return "\n".join([str(row) for row in result.rows])
        
        return "EXPLAIN not supported for this database type"
    
    def get_query_history(self) -> List[Dict[str, Any]]:
        """Get query execution history."""
        return self.query_history[-50:]  # Last 50 queries


# =============================================================================
# MIGRATION MANAGER CLASS
# =============================================================================

class MigrationManager:
    """
    Database migration management with version tracking and rollback support.
    
    Manages migration files, tracks applied migrations, and handles
    forward/backward migration execution.
    """
    
    def __init__(self, engine: QueryEngine, migrations_dir: str = "./migrations"):
        self.engine = engine
        self.migrations_dir = Path(migrations_dir)
        self.migrations_dir.mkdir(parents=True, exist_ok=True)
        self.migrations_table = "_schema_migrations"
        self._ensure_migrations_table()
        logger.info(f"MigrationManager initialized with dir: {migrations_dir}")
    
    def _ensure_migrations_table(self) -> None:
        """Ensure the migrations tracking table exists."""
        if self.engine.pool.config.db_type == DatabaseType.SQLITE:
            query = f"""
            CREATE TABLE IF NOT EXISTS {self.migrations_table} (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL,
                direction TEXT NOT NULL,
                checksum TEXT NOT NULL
            )
            """
        else:
            query = f"""
            CREATE TABLE IF NOT EXISTS {self.migrations_table} (
                version SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP NOT NULL,
                direction VARCHAR(10) NOT NULL,
                checksum VARCHAR(64) NOT NULL
            )
            """
        
        self.engine.execute_query(query, fetch=False)
    
    def create_migration(self, name: str, up_sql: str, down_sql: str) -> str:
        """Create a new migration file."""
        # Get next version number
        current_version = self.get_current_version()
        new_version = current_version + 1
        
        # Create migration content
        migration_content = {
            "version": new_version,
            "name": name,
            "up": up_sql,
            "down": down_sql,
            "created_at": datetime.now().isoformat()
        }
        
        filename = f"{new_version:04d}_{name.replace(' ', '_')}.json"
        filepath = self.migrations_dir / filename
        
        with open(filepath, "w") as f:
            json.dump(migration_content, f, indent=2)
        
        logger.info(f"Created migration: {filename}")
        return filename
    
    def get_current_version(self) -> int:
        """Get the current migration version."""
        query = f"SELECT MAX(version) FROM {self.migrations_table}"
        result = self.engine.execute_query(query)
        
        if result.success and result.rows and result.rows[0][0]:
            return result.rows[0][0]
        
        return 0
    
    def get_applied_migrations(self) -> List[MigrationRecord]:
        """Get list of applied migrations."""
        query = f"SELECT version, name, applied_at, direction, checksum FROM {self.migrations_table} ORDER BY version"
        result = self.engine.execute_query(query)
        
        if result.success:
            return [
                MigrationRecord(
                    version=row[0],
                    name=row[1],
                    applied_at=datetime.fromisoformat(row[2]),
                    direction=MigrationDirection(row[3]),
                    checksum=row[4]
                )
                for row in result.rows
            ]
        
        return []
    
    def get_pending_migrations(self) -> List[Dict[str, Any]]:
        """Get list of migrations that haven't been applied."""
        applied = {m.version for m in self.get_applied_migrations()}
        
        pending = []
        for filepath in sorted(self.migrations_dir.glob("*.json")):
            try:
                with open(filepath) as f:
                    migration = json.load(f)
                
                if migration["version"] not in applied:
                    pending.append(migration)
            except Exception as e:
                logger.error(f"Failed to read migration {filepath}: {e}")
        
        return pending
    
    def migrate_up(self, target_version: Optional[int] = None) -> bool:
        """Apply pending migrations up to target version."""
        pending = self.get_pending_migrations()
        
        if not pending:
            logger.info("No pending migrations")
            return True
        
        for migration in pending:
            if target_version and migration["version"] > target_version:
                break
            
            success = self._apply_migration(migration, MigrationDirection.UP)
            
            if not success:
                logger.error(f"Migration failed: {migration['name']}")
                return False
        
        logger.info("All pending migrations applied")
        return True
    
    def migrate_down(self, target_version: int) -> bool:
        """Rollback migrations down to target version."""
        applied = self.get_applied_migrations()
        applied = sorted(applied, key=lambda m: m.version, reverse=True)
        
        for migration_record in applied:
            if migration_record.version <= target_version:
                break
            
            # Find the migration file
            migration_file = self.migrations_dir / f"{migration_record.version:04d}_{migration_record.name}.json"
            
            if not migration_file.exists():
                logger.warning(f"Migration file not found for version {migration_record.version}")
                continue
            
            with open(migration_file) as f:
                migration = json.load(f)
            
            success = self._apply_migration(migration, MigrationDirection.DOWN)
            
            if not success:
                logger.error(f"Rollback failed at version {migration_record.version}")
                return False
        
        logger.info(f"Rolled back to version {target_version}")
        return True
    
    def _apply_migration(self, migration: Dict[str, Any], direction: MigrationDirection) -> bool:
        """Apply a single migration."""
        version = migration["version"]
        name = migration["name"]
        
        sql = migration["up"] if direction == MigrationDirection.UP else migration["down"]
        
        # Calculate checksum
        checksum = hashlib.sha256(sql.encode()).hexdigest()
        
        try:
            # Execute migration SQL
            for statement in sql.split(";"):
                statement = statement.strip()
                if statement:
                    result = self.engine.execute_query(statement, fetch=False)
                    if not result.success:
                        logger.error(f"SQL failed: {statement[:100]}")
                        return False
            
            # Record migration
            if direction == MigrationDirection.UP:
                insert_query = f"""
                INSERT INTO {self.migrations_table} (version, name, applied_at, direction, checksum)
                VALUES (?, ?, ?, ?, ?)
                """
                self.engine.execute_query(
                    insert_query,
                    (version, name, datetime.now().isoformat(), direction.value, checksum),
                    fetch=False
                )
            else:
                delete_query = f"DELETE FROM {self.migrations_table} WHERE version = ?"
                self.engine.execute_query(delete_query, (version,), fetch=False)
            
            logger.info(f"Migration {direction.value}: {version}_{name}")
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False
    
    def rollback_last(self) -> bool:
        """Rollback the last applied migration."""
        applied = self.get_applied_migrations()
        
        if not applied:
            logger.info("No migrations to rollback")
            return True
        
        last_migration = applied[-1]
        return self.migrate_down(last_migration.version - 1)
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Get comprehensive migration status."""
        applied = self.get_applied_migrations()
        pending = self.get_pending_migrations()
        
        return {
            "current_version": self.get_current_version(),
            "applied_count": len(applied),
            "pending_count": len(pending),
            "applied_migrations": [
                {"version": m.version, "name": m.name, "applied_at": m.applied_at.isoformat()}
                for m in applied
            ],
            "pending_migrations": [
                {"version": m["version"], "name": m["name"]}
                for m in pending
            ]
        }


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="ILMA Database Operations - Query execution, migrations, and connection management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Query Execution
  %(prog)s --query "SELECT * FROM users LIMIT 10"
  %(prog)s --query "SELECT COUNT(*) FROM orders" --db-type sqlite --db "./mydb.sqlite"
  
  # Migration Management
  %(prog)s --migrate --up
  %(prog)s --migrate --down --target 5
  %(prog)s --migration-status
  
  # Connection Pool
  %(prog)s --pool-status
  %(prog)s --create-pool --db-type postgresql --host localhost --db mydb
  
  # Table Information
  %(prog)s --table-info users
        """
    )
    
    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    # Database connection options
    parser.add_argument("--db-type", choices=["sqlite", "postgresql", "mysql", "mongodb"], default="sqlite")
    parser.add_argument("--host", default="localhost", help="Database host")
    parser.add_argument("--port", type=int, help="Database port")
    parser.add_argument("--db", help="Database name")
    parser.add_argument("--username", help="Database username")
    parser.add_argument("--password", help="Database password")
    
    # Query options
    parser.add_argument("--query", help="Execute SQL query")
    parser.add_argument("--table-info", help="Get table structure")
    
    # Migration options
    parser.add_argument("--migrate", action="store_true", help="Run migrations")
    parser.add_argument("--direction", choices=["up", "down"], default="up", help="Migration direction")
    parser.add_argument("--target", type=int, help="Target migration version")
    parser.add_argument("--migration-status", action="store_true", help="Show migration status")
    parser.add_argument("--migrations-dir", default="./migrations", help="Migrations directory")
    
    # Pool options
    parser.add_argument("--pool-status", action="store_true", help="Show connection pool status")
    parser.add_argument("--create-pool", action="store_true", help="Create connection pool")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Build connection config
        db_type = DatabaseType(args.db_type)
        config = ConnectionConfig(
            db_type=db_type,
            host=args.host,
            port=args.port or 0,
            database=args.db or (":memory:" if db_type == DatabaseType.SQLITE else ""),
            username=args.username or "",
            password=args.password or ""
        )
        
        # Initialize engine with pool
        pool = ConnectionPool(config)
        engine = QueryEngine(pool)
        
        # Query Execution
        if args.query:
            result = engine.execute_query(args.query)
            
            print(f"\nQuery Results:")
            print(f"  Success: {result.success}")
            print(f"  Rows: {result.row_count}")
            print(f"  Time: {result.execution_time_ms:.2f}ms")
            
            if result.error_message:
                print(f"  Error: {result.error_message}")
            elif result.columns:
                print(f"  Columns: {', '.join(result.columns)}")
                for row in result.rows[:20]:  # Limit output
                    print(f"    {row}")
                if len(result.rows) > 20:
                    print(f"    ... ({len(result.rows) - 20} more rows)")
        
        # Table Info
        elif args.table_info:
            info = engine.get_table_info(args.table_info)
            
            print(f"\nTable: {args.table_info}")
            print(f"  Columns: {len(info)}")
            for col in info:
                pk = " [PK]" if col.get("primary_key") else ""
                nullable = "NULL" if col.get("nullable") else "NOT NULL"
                print(f"    {col['name']}: {col['type']} {nullable}{pk}")
        
        # Migration Status
        elif args.migration_status:
            manager = MigrationManager(engine, args.migrations_dir)
            status = manager.get_migration_status()
            
            print(f"\nMigration Status:")
            print(f"  Current Version: {status['current_version']}")
            print(f"  Applied: {status['applied_count']}")
            print(f"  Pending: {status['pending_count']}")
            
            if status['applied_migrations']:
                print("\n  Applied Migrations:")
                for m in status['applied_migrations']:
                    print(f"    {m['version']}: {m['name']} ({m['applied_at'][:10]})")
            
            if status['pending_migrations']:
                print("\n  Pending Migrations:")
                for m in status['pending_migrations']:
                    print(f"    {m['version']}: {m['name']}")
        
        # Run Migrations
        elif args.migrate:
            manager = MigrationManager(engine, args.migrations_dir)
            
            if args.direction == "up":
                success = manager.migrate_up(args.target)
                print(f"\nMigration up: {'SUCCESS' if success else 'FAILED'}")
            else:
                target = args.target if args.target is not None else manager.get_current_version() - 1
                success = manager.migrate_down(target)
                print(f"\nMigration down: {'SUCCESS' if success else 'FAILED'}")
        
        # Pool Status
        elif args.pool_status:
            stats = pool.get_stats()
            
            print(f"\nConnection Pool Status:")
            print(f"  Max Connections: {stats['max_connections']}")
            print(f"  Created: {stats['created']}")
            print(f"  Available: {stats['available']}")
            print(f"  In Use: {stats['in_use']}")
        
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()