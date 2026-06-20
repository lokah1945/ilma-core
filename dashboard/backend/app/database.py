"""SQLModel database engine and table creation."""
import os
from sqlmodel import SQLModel, create_engine, Session
from pathlib import Path


def get_db_path() -> str:
    db_path = os.getenv("ILMA_DASHBOARD_DB", "/root/.hermes/profiles/ilma/data/ilma_dashboard.db")
    # Ensure directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return db_path


engine = create_engine(f"sqlite:///{get_db_path()}", echo=False, connect_args={"check_same_thread": False})


def create_db_and_tables():
    """Import all models then create tables."""
    from app.models import (
        Provider, ModelRecord, BenchmarkRecord, TokenUsageEvent,
        CapabilityRecord, EvidenceRecord, SubagentRoute, WorkflowDefinition,
        WorkflowRun, RefreshJob, SystemHealthSnapshot,
    )
    SQLModel.metadata.create_all(engine)


def get_session():
    """Context manager for DB sessions."""
    with Session(engine) as session:
        yield session