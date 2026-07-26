#!/usr/bin/env python3
"""ILMA Dashboard Backend — FastAPI application entry point."""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.database import engine, create_db_and_tables
from app.routers import (
    providers_router,
    models_router,
    usage_router,
    benchmarks_router,
    specializations_router,
    routing_router,
    workflows_router,
    evidence_router,
    capabilities_router,
    health_router,
    overview_router,
    refresh_router,
    tasks_router,
)

def create_app() -> FastAPI:
    settings = Settings()
    
    app = FastAPI(
        title="ILMA Web Observability Dashboard",
        description="Real-time ILMA system monitoring: providers, models, benchmarks, routing, workflows",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # CORS — localhost only by default
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Create DB tables on startup
    @app.on_event("startup")
    def on_startup():
        create_db_and_tables()
    
    # Register routers
    app.include_router(health_router, prefix="/api", tags=["health"])
    app.include_router(overview_router, prefix="/api", tags=["overview"])
    app.include_router(providers_router, prefix="/api", tags=["providers"])
    app.include_router(models_router, prefix="/api", tags=["models"])
    app.include_router(usage_router, prefix="/api", tags=["usage"])
    app.include_router(benchmarks_router, prefix="/api", tags=["benchmarks"])
    app.include_router(specializations_router, prefix="/api", tags=["specializations"])
    app.include_router(routing_router, prefix="/api", tags=["routing"])
    app.include_router(workflows_router, prefix="/api", tags=["workflows"])
    app.include_router(evidence_router, prefix="/api", tags=["evidence"])
    app.include_router(capabilities_router, prefix="/api", tags=["capabilities"])
    app.include_router(refresh_router, prefix="/api", tags=["refresh"])
    app.include_router(tasks_router, prefix="/api", tags=["tasks"])
    
    @app.get("/")
    def root():
        return {
            "service": "ILMA Web Observability Dashboard",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/api/health",
        }
    
    return app


app = create_app()