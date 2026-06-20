"""Usage data service."""
from sqlmodel import Session, select, func
from app.models import TokenUsageEvent, TokenUsageDaily
from app.database import engine
from typing import List, Optional
from datetime import datetime, timedelta


class UsageService:
    @staticmethod
    def get_events(limit: int = 100) -> List[TokenUsageEvent]:
        with Session(engine) as s:
            return list(s.exec(select(TokenUsageEvent).limit(limit)).all())
    
    @staticmethod
    def get_summary(period: str = "today") -> dict:
        now = datetime.now()
        if period == "today":
            start = now.replace(hour=0, minute=0, second=0)
        elif period == "week":
            start = now - timedelta(days=7)
        else:  # month
            start = now - timedelta(days=30)
        
        start_str = start.isoformat()
        
        with Session(engine) as s:
            events = list(s.exec(select(TokenUsageEvent).where(TokenUsageEvent.timestamp >= start_str)).all())
        
        total_tokens = sum(e.total_tokens for e in events)
        total_cost = sum(e.estimated_cost for e in events)
        success = sum(1 for e in events if e.request_status == "SUCCESS")
        
        return {
            "period": period,
            "total_events": len(events),
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 6),
            "success_count": success,
            "fail_count": len(events) - success,
        }
    
    @staticmethod
    def get_by_provider(provider: str, period: str = "month") -> List[TokenUsageEvent]:
        now = datetime.now()
        days = {"today": 0, "week": 7, "month": 30}.get(period, 30)
        start_str = (now - timedelta(days=days)).isoformat()
        
        with Session(engine) as s:
            return list(s.exec(
                select(TokenUsageEvent)
                .where(TokenUsageEvent.timestamp >= start_str)
                .where(TokenUsageEvent.provider == provider)
            ).all())
    
    @staticmethod
    def record_event(event: TokenUsageEvent) -> TokenUsageEvent:
        with Session(engine) as s:
            s.add(event)
            s.commit()
            s.refresh(event)
            return event