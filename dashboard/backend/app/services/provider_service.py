"""Provider data service."""
from sqlmodel import Session, select
from app.models import Provider
from app.database import engine
from typing import List, Optional


class ProviderService:
    @staticmethod
    def get_all() -> List[Provider]:
        with Session(engine) as s:
            return list(s.exec(select(Provider)).all())
    
    @staticmethod
    def get_by_id(provider_id: str) -> Optional[Provider]:
        with Session(engine) as s:
            return s.exec(select(Provider).where(Provider.provider_id == provider_id)).first()
    
    @staticmethod
    def upsert(provider: Provider) -> Provider:
        with Session(engine) as s:
            existing = s.exec(select(Provider).where(Provider.provider_id == provider.provider_id)).first()
            if existing:
                for k, v in provider.__dict__.items():
                    if k != "id":
                        setattr(existing, k, v)
                s.add(existing)
                s.commit()
                s.refresh(existing)
                return existing
            else:
                s.add(provider)
                s.commit()
                s.refresh(provider)
                return provider
    
    @staticmethod
    def upsert_bulk(providers: List[Provider]) -> int:
        count = 0
        with Session(engine) as s:
            for p in providers:
                existing = s.exec(select(Provider).where(Provider.provider_id == p.provider_id)).first()
                if existing:
                    for k, v in p.__dict__.items():
                        if k != "id":
                            setattr(existing, k, v)
                else:
                    s.add(p)
                count += 1
            s.commit()
        return count