"""Dashboard configuration and settings."""
import os
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Paths
    ILMA_DIR: str = "/root/.hermes/profiles/ilma"
    DB_PATH: str = "/root/.hermes/profiles/ilma/data/ilma_dashboard.db"
    
    # Data sources
    MODEL_SPECIALIZATION_DB: str = "{ILMA_DIR}/model_specialization_database.json"
    CAPABILITY_REGISTRY: str = "{ILMA_DIR}/scripts/ilma_capability_registry.py"
    BENCHMARK_DB: str = "{ILMA_DIR}/ilma_benchmark.db"
    EVIDENCE_LEDGER: str = "{ILMA_DIR}/docs/ILMA_EVIDENCE_LEDGER_2026-05-07.md"
    UNIFIED_ROUTER: str = "{ILMA_DIR}/scripts/ilma_unified_router.py"
    RUNTIME_ROUTER: str = "{ILMA_DIR}/scripts/ilma_runtime_router.py"
    WORKFLOW_ECC: str = "{ILMA_DIR}/scripts/ilma_workflow_ecc.py"
    WORKFLOW_ENGINE: str = "{ILMA_DIR}/scripts/ilma_workflow_engine.py"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    
    # Security
    CORS_ORIGINS: list = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    class Config:
        env_prefix = "ILMA_DASHBOARD_"
        extra = "ignore"
    
    def resolve(self, key: str) -> str:
        return self.__dict__.get(key, "").replace("{ILMA_DIR}", self.ILMA_DIR)


settings = Settings()