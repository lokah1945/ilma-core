"""Model data service."""
from sqlmodel import Session, select
from app.models import ModelRecord
from app.database import engine
from typing import List, Optional


class ModelService:
    @staticmethod
    def get_all() -> List[ModelRecord]:
        with Session(engine) as s:
            return list(s.exec(select(ModelRecord)).all())
    
    @staticmethod
    def get_by_id(canonical_id: str) -> Optional[ModelRecord]:
        with Session(engine) as s:
            return s.exec(select(ModelRecord).where(ModelRecord.canonical_model_id == canonical_id)).first()
    
    @staticmethod
    def get_by_provider(provider: str) -> List[ModelRecord]:
        with Session(engine) as s:
            return list(s.exec(select(ModelRecord).where(ModelRecord.provider == provider)).all())
    
    @staticmethod
    def get_by_capability(capability: str) -> List[ModelRecord]:
        with Session(engine) as s:
            # Models with benchmark coverage mentioning this capability
            return list(s.exec(
                select(ModelRecord).where(ModelRecord.benchmark_coverage.contains(capability))
            ).all())
    
    @staticmethod
    def upsert(model: ModelRecord) -> ModelRecord:
        with Session(engine) as s:
            existing = s.exec(select(ModelRecord).where(ModelRecord.canonical_model_id == model.canonical_model_id)).first()
            if existing:
                for k, v in model.__dict__.items():
                    if k != "id":
                        setattr(existing, k, v)
                s.add(existing)
                s.commit()
                s.refresh(existing)
                return existing
            else:
                s.add(model)
                s.commit()
                s.refresh(model)
                return model
    
    @staticmethod
    def upsert_bulk(models: List[ModelRecord]) -> int:
        count = 0
        with Session(engine) as s:
            for m in models:
                existing = s.exec(select(ModelRecord).where(ModelRecord.canonical_model_id == m.canonical_model_id)).first()
                if existing:
                    for k, v in m.__dict__.items():
                        if k != "id":
                            setattr(existing, k, v)
                else:
                    s.add(m)
                count += 1
            s.commit()
        return count
    
    @staticmethod
    def count() -> int:
        with Session(engine) as s:
            return len(list(s.exec(select(ModelRecord)).all()))