#!/usr/bin/env python3
"""Seed ILMA data into dashboard SQLite DB."""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../dashboard/backend"))

from app.database import create_db_and_tables, engine
from app.services.ingestion_service import IngestionService
from sqlmodel import Session


def main():
    print("=" * 60)
    print("ILMA Dashboard — Database Seeder")
    print("=" * 60)
    
    # Create tables
    print("\n[1] Creating DB tables...")
    create_db_and_tables()
    print("✅ Tables created")
    
    # Ingest all sources
    print("\n[2] Ingesting ILMA data sources...")
    service = IngestionService()
    results = service.ingest_all()
    
    for key, count in results.items():
        if isinstance(count, bool):
            print(f"  {key}: {'✅' if count else '❌'}")
        else:
            print(f"  {key}: {count} records")
    
    # Print summary
    print("\n[3] Verifying ingestion...")
    with Session(engine) as s:
        from app.models import Provider, ModelRecord, BenchmarkRecord, CapabilityRecord, EvidenceRecord, SubagentRoute, WorkflowDefinition
        
        counts = {
            "providers": s.query(Provider).count(),
            "models": s.query(ModelRecord).count(),
            "benchmarks": s.query(BenchmarkRecord).count(),
            "capabilities": s.query(CapabilityRecord).count(),
            "evidence": s.query(EvidenceRecord).count(),
            "subagent_routes": s.query(SubagentRoute).count(),
            "workflows": s.query(WorkflowDefinition).count(),
        }
        
        print("\n📊 Final Counts:")
        for name, count in counts.items():
            print(f"  {name}: {count}")
    
    print("\n✅ Seeding complete!")
    print(f"DB: /root/.hermes/profiles/ilma/data/PROVIDER_INTELLIGENCE_MASTER.json")


if __name__ == "__main__":
    main()