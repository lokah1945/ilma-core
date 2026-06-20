"""Benchmark data service."""
from sqlmodel import Session, select
from app.models import BenchmarkRecord
from app.database import engine
from typing import List, Optional


class BenchmarkService:
    @staticmethod
    def get_all() -> List[BenchmarkRecord]:
        with Session(engine) as s:
            return list(s.exec(select(BenchmarkRecord)).all())
    
    @staticmethod
    def get_by_model(canonical_model_id: str) -> List[BenchmarkRecord]:
        with Session(engine) as s:
            return list(s.exec(
                select(BenchmarkRecord).where(BenchmarkRecord.canonical_model_id == canonical_model_id)
            ).all())
    
    @staticmethod
    def get_by_capability(capability: str) -> List[BenchmarkRecord]:
        with Session(engine) as s:
            return list(s.exec(
                select(BenchmarkRecord).where(BenchmarkRecord.task_category == capability)
            ).all())
    
    @staticmethod
    def upsert(record: BenchmarkRecord) -> BenchmarkRecord:
        with Session(engine) as s:
            existing = s.exec(select(BenchmarkRecord).where(BenchmarkRecord.benchmark_id == record.benchmark_id)).first()
            if existing:
                for k, v in record.__dict__.items():
                    if k != "id":
                        setattr(existing, k, v)
                s.add(existing)
                s.commit()
                s.refresh(existing)
                return existing
            else:
                s.add(record)
                s.commit()
                s.refresh(record)
                return record
    
    @staticmethod
    def upsert_bulk(records: List[BenchmarkRecord]) -> int:
        count = 0
        with Session(engine) as s:
            for r in records:
                existing = s.exec(select(BenchmarkRecord).where(BenchmarkRecord.benchmark_id == r.benchmark_id)).first()
                if existing:
                    for k, v in r.__dict__.items():
                        if k != "id":
                            setattr(existing, k, v)
                else:
                    s.add(r)
                count += 1
            s.commit()
        return count
    
    @staticmethod
    def count() -> int:
        with Session(engine) as s:
            return len(list(s.exec(select(BenchmarkRecord)).all()))