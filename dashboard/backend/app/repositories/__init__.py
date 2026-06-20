"""
app/repositories/__init__.py — Data Access Layer
"""
from sqlmodel import Session, select, func
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import json

from app.models import (
    Provider, ModelRecord, BenchmarkRecord, TokenUsageEvent,
    CapabilityRecord, EvidenceRecord, SubagentRoute,
    WorkflowDefinition, WorkflowRun, RefreshJob, SystemHealthSnapshot
)


class ProviderRepository:
    """Data access for providers"""

    def __init__(self, session: Session):
        self.session = session

    def list_all(self) -> List[Provider]:
        return list(self.session.exec(select(Provider)).all())

    def get_by_id(self, provider_id: str) -> Optional[Provider]:
        return self.session.exec(
            select(Provider).where(Provider.provider_id == provider_id)
        ).first()

    def upsert(self, data: Dict[str, Any]) -> Provider:
        existing = self.get_by_id(data.get("provider_id", ""))
        if existing:
            for k, v in data.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
            return existing
        p = Provider(**data)
        self.session.add(p)
        return p

    def count(self) -> int:
        return self.session.exec(select(func.count(Provider.id))).first() or 0


class ModelRepository:
    """Data access for model_ids"""

    def __init__(self, session: Session):
        self.session = session

    def list_all(
        self,
        provider: Optional[str] = None,
        free_paid: Optional[str] = None,
        source_type: Optional[str] = None,
        capability: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ModelRecord]:
        q = select(ModelRecord)
        if provider:
            q = q.where(ModelRecord.provider == provider)
        if free_paid:
            q = q.where(ModelRecord.free_or_paid == free_paid.upper())
        if source_type:
            q = q.where(ModelRecord.source_type == source_type)
        q = q.offset(offset).limit(limit)
        return list(self.session.exec(q).all())

    def get_by_canonical_id(self, canonical_model_id: str) -> Optional[ModelRecord]:
        return self.session.exec(
            select(ModelRecord).where(ModelRecord.canonical_model_id == canonical_model_id)
        ).first()

    def upsert(self, data: Dict[str, Any]) -> ModelRecord:
        existing = self.get_by_canonical_id(data.get("canonical_model_id", ""))
        if existing:
            for k, v in data.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
            return existing
        m = ModelRecord(**data)
        self.session.add(m)
        return m

    def count(self, free_paid: Optional[str] = None) -> int:
        q = select(func.count(ModelRecord.id))
        if free_paid:
            q = q.where(ModelRecord.free_or_paid == free_paid.upper())
        return self.session.exec(q).first() or 0

    def count_by_provider(self, provider: str) -> int:
        return self.session.exec(
            select(func.count(ModelRecord.id)).where(ModelRecord.provider == provider)
        ).first() or 0


class BenchmarkRepository:
    """Data access for benchmark_records"""

    def __init__(self, session: Session):
        self.session = session

    def list_all(
        self,
        capability: Optional[str] = None,
        evidence_level: Optional[str] = None,
        limit: int = 100
    ) -> List[BenchmarkRecord]:
        q = select(BenchmarkRecord)
        if capability:
            q = q.where(BenchmarkRecord.task_category == capability)
        if evidence_level:
            q = q.where(BenchmarkRecord.evidence_level == evidence_level)
        q = q.limit(limit)
        return list(self.session.exec(q).all())

    def list_by_model(self, canonical_model_id: str) -> List[BenchmarkRecord]:
        return list(self.session.exec(
            select(BenchmarkRecord).where(
                BenchmarkRecord.canonical_model_id == canonical_model_id
            )
        ).all())

    def upsert(self, data: Dict[str, Any]) -> BenchmarkRecord:
        existing = self.session.exec(
            select(BenchmarkRecord).where(
                BenchmarkRecord.benchmark_id == data.get("benchmark_id", "")
            )
        ).first()
        if existing:
            for k, v in data.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
            return existing
        b = BenchmarkRecord(**data)
        self.session.add(b)
        return b

    def count(self) -> int:
        return self.session.exec(select(func.count(BenchmarkRecord.id))).first() or 0


class UsageRepository:
    """Data access for token_usage_events"""

    def __init__(self, session: Session):
        self.session = session

    def list_by_model(
        self,
        canonical_model_id: str,
        limit: int = 100
    ) -> List[TokenUsageEvent]:
        return list(self.session.exec(
            select(TokenUsageEvent)
            .where(TokenUsageEvent.canonical_model_id == canonical_model_id)
            .order_by(TokenUsageEvent.timestamp.desc())
            .limit(limit)
        ).all())

    def count_period(self, period: str = "today") -> int:
        now = datetime.utcnow()
        if period == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start = now - timedelta(days=7)
        elif period == "month":
            start = now - timedelta(days=30)
        else:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        return self.session.exec(
            select(func.count(TokenUsageEvent.id))
            .where(TokenUsageEvent.timestamp >= start.isoformat())
        ).first() or 0

    def summary(
        self,
        period: str = "today",
        by: str = "provider"
    ) -> Dict[str, int]:
        now = datetime.utcnow()
        if period == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start = now - timedelta(days=7)
        else:
            start = now - timedelta(days=30)

        q = select(TokenUsageEvent).where(
            TokenUsageEvent.timestamp >= start.isoformat()
        )
        events = list(self.session.exec(q).all())

        result: Dict[str, int] = {}
        for e in events:
            key = ""
            if by == "provider":
                key = e.provider
            elif by == "model":
                key = e.canonical_model_id
            elif by == "subagent":
                key = e.subagent_role
            elif by == "workflow":
                key = e.workflow_id
            elif by == "category":
                key = e.task_category
            result[key] = result.get(key, 0) + e.total_tokens

        return result

    def daily_usage(
        self,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        events = list(self.session.exec(
            select(TokenUsageEvent)
            .where(TokenUsageEvent.timestamp >= start_date)
            .where(TokenUsageEvent.timestamp <= end_date)
        ).all())

        daily: Dict[str, Dict[str, Any]] = {}
        for e in events:
            date = e.timestamp[:10]
            if date not in daily:
                daily[date] = {"date": date, "total_requests": 0, "total_tokens": 0, "total_cost": 0.0}
            daily[date]["total_requests"] += 1
            daily[date]["total_tokens"] += e.total_tokens
            daily[date]["total_cost"] += e.estimated_cost

        return sorted(daily.values(), key=lambda x: x["date"])

    def upsert(self, data: Dict[str, Any]) -> TokenUsageEvent:
        t = TokenUsageEvent(**data)
        self.session.add(t)
        return t


class CapabilityRepository:
    """Data access for capability_registry_records"""

    def __init__(self, session: Session):
        self.session = session

    def list_all(self, status: Optional[str] = None) -> List[CapabilityRecord]:
        q = select(CapabilityRecord)
        if status:
            q = q.where(CapabilityRecord.status == status)
        return list(self.session.exec(q).all())

    def upsert(self, data: Dict[str, Any]) -> CapabilityRecord:
        cap_id = data.get("capability_id", "")
        existing = self.session.exec(
            select(CapabilityRecord)
            .where(CapabilityRecord.capability_id == cap_id)
        ).first()
        if existing:
            for k, v in data.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
            return existing
        c = CapabilityRecord(**data)
        self.session.add(c)
        return c

    def count(self) -> int:
        return self.session.exec(
            select(func.count(CapabilityRecord.id))
        ).first() or 0


class EvidenceRepository:
    """Data access for evidence_records"""

    def __init__(self, session: Session):
        self.session = session

    def list_all(
        self,
        capability: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[EvidenceRecord]:
        q = select(EvidenceRecord)
        if capability:
            q = q.where(EvidenceRecord.capability == capability)
        if status:
            q = q.where(EvidenceRecord.status == status)
        return list(self.session.exec(q).all())

    def upsert(self, data: Dict[str, Any]) -> EvidenceRecord:
        ev_id = data.get("evidence_id", "")
        existing = self.session.exec(
            select(EvidenceRecord)
            .where(EvidenceRecord.evidence_id == ev_id)
        ).first()
        if existing:
            for k, v in data.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
            return existing
        e = EvidenceRecord(**data)
        self.session.add(e)
        return e

    def count(self) -> int:
        return self.session.exec(
            select(func.count(EvidenceRecord.id))
        ).first() or 0


class RoutingRepository:
    """Data access for subagent_model_routes"""

    def __init__(self, session: Session):
        self.session = session

    def list_all(self) -> List[SubagentRoute]:
        return list(self.session.exec(
            select(SubagentRoute)
            .where(SubagentRoute.is_active == True)
            .order_by(SubagentRoute.role, SubagentRoute.route_order)
        ).all())

    def list_by_role(self, role: str) -> List[SubagentRoute]:
        return list(self.session.exec(
            select(SubagentRoute)
            .where(SubagentRoute.role == role)
            .where(SubagentRoute.is_active == True)
            .order_by(SubagentRoute.route_order)
        ).all())

    def upsert(self, data: Dict[str, Any]) -> SubagentRoute:
        role = data.get("role", "")
        order = data.get("route_order", 1)
        existing = self.session.exec(
            select(SubagentRoute)
            .where(SubagentRoute.role == role)
            .where(SubagentRoute.route_order == order)
        ).first()
        if existing:
            for k, v in data.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
            return existing
        r = SubagentRoute(**data)
        self.session.add(r)
        return r

    def count(self) -> int:
        return self.session.exec(
            select(func.count(SubagentRoute.id))
        ).first() or 0


class WorkflowRepository:
    """Data access for workflow_definitions"""

    def __init__(self, session: Session):
        self.session = session

    def list_all(self) -> List[WorkflowDefinition]:
        return list(self.session.exec(select(WorkflowDefinition)).all())

    def upsert(self, data: Dict[str, Any]) -> WorkflowDefinition:
        wf_id = data.get("workflow_id", "")
        existing = self.session.exec(
            select(WorkflowDefinition)
            .where(WorkflowDefinition.workflow_id == wf_id)
        ).first()
        if existing:
            for k, v in data.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
            return existing
        w = WorkflowDefinition(**data)
        self.session.add(w)
        return w


class RefreshJobRepository:
    """Data access for refresh_jobs"""

    def __init__(self, session: Session):
        self.session = session

    def list_all(self) -> List[RefreshJob]:
        return list(self.session.exec(select(RefreshJob)).all())

    def upsert(self, data: Dict[str, Any]) -> RefreshJob:
        job_id = data.get("job_id", "")
        existing = self.session.exec(
            select(RefreshJob).where(RefreshJob.job_id == job_id)
        ).first()
        if existing:
            for k, v in data.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
            return existing
        r = RefreshJob(**data)
        self.session.add(r)
        return r


class HealthSnapshotRepository:
    """Data access for system_health_snapshots"""

    def __init__(self, session: Session):
        self.session = session

    def get_latest(self) -> Optional[SystemHealthSnapshot]:
        return self.session.exec(
            select(SystemHealthSnapshot)
            .order_by(SystemHealthSnapshot.timestamp.desc())
            .limit(1)
        ).first()

    def upsert(self, data: Dict[str, Any]) -> SystemHealthSnapshot:
        ts = data.get("timestamp", datetime.utcnow().isoformat())
        existing = self.session.exec(
            select(SystemHealthSnapshot)
            .where(SystemHealthSnapshot.timestamp == ts)
        ).first()
        if existing:
            for k, v in data.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
            return existing
        h = SystemHealthSnapshot(**data)
        self.session.add(h)
        return h
