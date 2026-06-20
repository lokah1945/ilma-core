#!/usr/bin/env python3
"""
ilma_model_registry.py — ILMA Unified Model Registry v1.0
==========================================================
Single source of truth for ALL models across ALL providers.
Reads from: SQLite dashboard DB + benchmark JSON.

Provider types:
- NATIVE: Direct API calls (no API key needed for free tier)

History:
- BRIDGE source type was removed 2026-06-19 along with the legacy proxy
  project. The dataclass field ``source_type`` is preserved (always "NATIVE"
  now) so consumers can keep relying on the attribute.

Usage:
    registry = ModelRegistry()
    model = registry.get_model("nvidia/DeepSeek-R1")
    free_models = registry.get_free_models(provider="nvidia")
    top_models = registry.get_top_models(task="coding", limit=10)
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ===================
# Paths
# ===================

ILMA_PROFILE = Path("/root/.hermes/profiles/ilma")
DASHBOARD_DB = ILMA_PROFILE / "data/ilma_dashboard.db"
BENCHMARK_DB = ILMA_PROFILE / "ilma_model_router_data/benchmark_database.json"
PROVIDER_INTEL = ILMA_PROFILE / "ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json"


# ===================
# Data Classes
# ===================

@dataclass
class ModelInfo:
    """Complete model information."""
    canonical_id: str          # e.g. "nvidia/DeepSeek-R1"
    provider: str              # e.g. "nvidia"
    provider_model_id: str     # e.g. "DeepSeek-R1"
    display_name: str
    source_type: str           # "NATIVE" (legacy BRIDGE removed 2026-06-19)
    
    # Capabilities
    free_or_paid: str          # "FREE" or "PAID"
    context_window: int
    max_output: int
    modality: str              # "text", "vision", "multimodal"
    supports_tools: bool
    supports_json: bool
    supports_vision: bool
    supports_long_context: bool
    
    # Quality metrics
    quality_score: float
    coding_score: float
    reasoning_score: float
    tool_use_score: float
    
    # Routing
    specialization: str       # "coding", "reasoning", "general", "vision"
    
    # Status
    availability: str          # "ACTIVE", "DEGRADED", "UNAVAILABLE"
    allowed_by_policy: bool
    last_verified: Optional[str]
    benchmark_coverage: str
    caveat: str
    
    # Benchmark data (from benchmark_database.json)
    benchmark_overall: Optional[float] = None
    benchmark_coding: Optional[float] = None
    benchmark_reasoning: Optional[float] = None
    
    @property
    def is_free(self) -> bool:
        return self.free_or_paid == "FREE"
    
    @property
    def is_active(self) -> bool:
        return self.availability == "ACTIVE" and self.allowed_by_policy
    
    @property
    def quality_effective(self) -> float:
        """Best available quality score (benchmark > db), clamped to [0, 1]."""
        score = self.benchmark_overall if self.benchmark_overall is not None else self.quality_score
        if score is None:
            return 0.0
        # Clamp invalid values (e.g., benchmark data with 11.7)
        return max(0.0, min(1.0, float(score)))
    
    @property
    def coding_effective(self) -> float:
        if self.benchmark_coding is not None:
            return self.benchmark_coding
        return self.coding_score or 0.0
    
    @property
    def reasoning_effective(self) -> float:
        if self.benchmark_reasoning is not None:
            return self.benchmark_reasoning
        return self.reasoning_score or 0.0


@dataclass
class ProviderInfo:
    """Provider-level information."""
    provider_id: str
    display_name: str
    source_type: str           # "NATIVE" (legacy BRIDGE removed 2026-06-19)
    trust_level: int           # 1-10
    health_score: int          # 0-100
    last_verified: Optional[str]
    stale_status: str
    notes: str
    
    # Access
    api_key_present: bool
    api_key_source: str
    
    @property
    def is_native(self) -> bool:
        return self.source_type == "NATIVE"

    @property
    def is_trusted(self) -> bool:
        return self.trust_level >= 7


# ===================
# Model Registry
# ===================

class ModelRegistry:
    """
    Unified model registry reading from SQLite + benchmark JSON.
    
    Single source of truth for all 1284+ models across 16 providers.
    """
    
    def __init__(
        self,
        db_path: str = str(DASHBOARD_DB),
        benchmark_path: str = str(BENCHMARK_DB),
        provider_intel_path: str = str(PROVIDER_INTEL),
    ):
        self.db_path = db_path
        self.benchmark_path = benchmark_path
        self.provider_intel_path = provider_intel_path
        
        # Caches
        self._models: Dict[str, ModelInfo] = {}
        self._providers: Dict[str, ProviderInfo] = {}
        self._free_models: Dict[str, List[ModelInfo]] = {}  # provider → [ModelInfo]
        self._all_free_models: List[ModelInfo] = []
        self._benchmark_scores: Dict[str, Dict] = {}
        self._subagent_routes: Dict[Tuple[str, str], List[Dict]] = {}  # (role, task) → [route]
        
        self._cache_time: float = 0
        self._cache_ttl: float = 300.0  # 5 minutes
        
        # Load everything
        self._load()
    
    def _load(self):
        """Load all data sources."""
        self._load_providers()
        self._load_benchmark()
        self._load_models()
        self._load_subagent_routes()
        self._cache_time = time.time()
    
    def reload_if_stale(self):
        """Reload if cache is stale."""
        if time.time() - self._cache_time > self._cache_ttl:
            self._load()
    
    def _load_providers(self):
        """Load provider info from SQLite."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT provider_id, display_name, source_type, trust_level,
                   health_score, last_verified, stale_status, notes,
                   api_key_present, api_key_source
            FROM providers
        """)
        for row in cur.fetchall():
            pid = row[0]
            self._providers[pid] = ProviderInfo(
                provider_id=pid,
                display_name=row[1],
                source_type=row[2],
                trust_level=row[3],
                health_score=row[4],
                last_verified=row[5],
                stale_status=row[6],
                notes=row[7] or "",
                api_key_present=bool(row[8]),
                api_key_source=row[9] or "",
            )
        conn.close()
    
    def _load_benchmark(self):
        """Load benchmark scores from JSON."""
        if not Path(self.benchmark_path).exists():
            return
        try:
            with open(self.benchmark_path) as f:
                data = json.load(f)
            self._benchmark_scores = data.get("model_scores", {})
        except Exception:
            self._benchmark_scores = {}
    
    def _load_models(self):
        """Load models from SQLite."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                canonical_model_id, provider, provider_model_id, display_name,
                free_or_paid, availability_status, allowed_by_policy,
                context_window, max_output_tokens, modality,
                supports_tools, supports_json, supports_vision, supports_long_context,
                quality_score, coding_score, reasoning_score, tool_use_score,
                specialization, last_verified, benchmark_coverage, caveat
            FROM model_ids
            WHERE allowed_by_policy = 1
        """)
        for row in cur.fetchall():
            canonical_id = row[0]
            provider = row[1]
            
            # Get benchmark data
            benchmark = self._benchmark_scores.get(canonical_id, {})
            bm_overall = benchmark.get("overall")
            bm_coding = benchmark.get("coding_weighted")
            bm_reasoning = benchmark.get("reasoning_weighted")
            
            model = ModelInfo(
                canonical_id=canonical_id,
                provider=provider,
                provider_model_id=row[2],
                display_name=row[3] or canonical_id,
                source_type=self._providers.get(provider, ProviderInfo(
                provider_id=provider,
                display_name=provider,
                source_type="NATIVE",
                trust_level=5,
                health_score=50,
                last_verified=None,
                stale_status="",
                notes="",
                api_key_present=False,
                api_key_source="",
            )).source_type,
                free_or_paid=row[4],
                context_window=row[7] or 0,
                max_output=row[8] or 0,
                modality=row[9] or "text",
                supports_tools=bool(row[10]),
                supports_json=bool(row[11]),
                supports_vision=bool(row[12]),
                supports_long_context=bool(row[13]),
                quality_score=row[14] or 0.0,
                coding_score=row[15] or 0.0,
                reasoning_score=row[16] or 0.0,
                tool_use_score=row[17] or 0.0,
                specialization=row[18] or "general",
                availability=row[5],
                allowed_by_policy=bool(row[6]),
                last_verified=row[19],
                benchmark_coverage=row[20] or "",
                caveat=row[21] or "",
                benchmark_overall=bm_overall,
                benchmark_coding=bm_coding,
                benchmark_reasoning=bm_reasoning,
            )
            
            self._models[canonical_id] = model
            
            # Index free models
            if model.is_free and model.is_active:
                if provider not in self._free_models:
                    self._free_models[provider] = []
                self._free_models[provider].append(model)
                self._all_free_models.append(model)
        
        conn.close()
        
        # Sort all free models by quality
        self._all_free_models.sort(key=lambda m: m.quality_effective, reverse=True)
    
    def _load_subagent_routes(self):
        """Load sub-agent routing table from SQLite."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT role, task_category, route_order, provider,
                   canonical_model_id, free_or_paid, is_active
            FROM subagent_model_routes
            WHERE is_active = 1
            ORDER BY role, task_category, route_order
        """)
        for row in cur.fetchall():
            role, task_cat = row[0], row[1]
            key = (role, task_cat)
            if key not in self._subagent_routes:
                self._subagent_routes[key] = []
            self._subagent_routes[key].append({
                "order": row[2],
                "provider": row[3],
                "model": row[4],
                "free": row[5],
            })
        conn.close()
    
    # ===================
    # Accessors
    # ===================
    
    def get_model(self, canonical_id: str) -> Optional[ModelInfo]:
        """Get model by canonical ID."""
        self.reload_if_stale()
        return self._models.get(canonical_id)
    
    def get_provider(self, provider_id: str) -> Optional[ProviderInfo]:
        """Get provider info."""
        self.reload_if_stale()
        return self._providers.get(provider_id)
    
    def get_all_providers(self) -> List[ProviderInfo]:
        """Get all providers."""
        self.reload_if_stale()
        return list(self._providers.values())
    
    def get_native_providers(self) -> List[ProviderInfo]:
        """Get all NATIVE providers."""
        return [p for p in self.get_all_providers() if p.is_native]

    def get_all_models(self) -> List[ModelInfo]:
        """Get all models."""
        self.reload_if_stale()
        return list(self._models.values())
    
    def get_models_by_provider(self, provider: str) -> List[ModelInfo]:
        """Get all models for a provider."""
        self.reload_if_stale()
        return [m for m in self._models.values() if m.provider == provider]
    
    def get_free_models(
        self,
        provider: Optional[str] = None,
        min_quality: float = 0.0,
        specialization: Optional[str] = None,
    ) -> List[ModelInfo]:
        """Get free models, optionally filtered.

        Direct cloud APIs only — legacy proxy filter removed.
        """
        self.reload_if_stale()
        models = self._all_free_models if provider is None else self._free_models.get(provider, [])
        
        result = []
        for m in models:
            if m.quality_effective >= min_quality:
                if specialization is None or m.specialization == specialization:
                    result.append(m)
        
        return result
    
    def get_top_models(
        self,
        task: str = "general",
        limit: int = 10,
        min_quality: float = 0.0,
    ) -> List[ModelInfo]:
        """Get top models for a task type, sorted by effective quality."""
        self.reload_if_stale()
        
        # Map task to specialization
        spec_map = {
            "coding": "coding",
            "heavy_coding": "coding",
            "reasoning": "reasoning",
            "reasoning_xhigh": "reasoning",
            "general": "general",
            "vision": "vision",
            "research": "research",
        }
        specialization = spec_map.get(task)
        
        # Get candidate models (direct cloud APIs only)
        models = self.get_free_models(min_quality=min_quality)
        
        if specialization:
            spec_models = [m for m in models if m.specialization == specialization]
            if spec_models:
                models = spec_models
        
        return models[:limit]
    
    def get_subagent_routes(self, role: str, task_category: str) -> List[Dict]:
        """Get routing table for a sub-agent role+task."""
        self.reload_if_stale()
        return self._subagent_routes.get((role, task_category), [])
    
    def get_subagent_route_models(
        self,
        role: str,
        task_category: str,
        only_free: bool = True,
    ) -> List[Tuple[int, ModelInfo]]:
        """Get models for a sub-agent in priority order.
        
        Returns: [(priority, ModelInfo), ...]
        """
        routes = self.get_subagent_routes(role, task_category)
        result = []
        for route in routes:
            if only_free and route["free"] != "FREE":
                continue
            model = self.get_model(route["model"])
            if model and model.is_active:
                result.append((route["order"], model))
        return result
    
    # ===================
    # Stats
    # ===================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        self.reload_if_stale()
        return {
            "total_models": len(self._models),
            "total_free_models": len(self._all_free_models),
            "providers": {
                "total": len(self._providers),
                "native": len(self.get_native_providers()),
            },
            "free_by_provider": {
                p: len(models) for p, models in self._free_models.items()
            },
            "subagent_roles": len(self._subagent_routes),
            "benchmark_scores_loaded": len(self._benchmark_scores),
        }


# ===================
# Singleton
# ===================

_registry: Optional[ModelRegistry] = None

def get_registry() -> ModelRegistry:
    """Get singleton registry instance."""
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry


# ===================
# Main (Test)
# ===================

if __name__ == "__main__":
    print("=== ILMA Model Registry Test ===\n")
    
    reg = get_registry()
    stats = reg.get_stats()
    
    print("Registry Stats:")
    print(f"  Total models: {stats['total_models']}")
    print(f"  Total free models: {stats['total_free_models']}")
    print(f"  Providers: {stats['providers']['total']} (NATIVE: {stats['providers']['native']})")
    print(f"  Benchmark scores: {stats['benchmark_scores_loaded']}")
    print(f"  Sub-agent roles: {stats['subagent_roles']}")
    
    print("\nFree models by provider:")
    for p, count in sorted(stats['free_by_provider'].items(), key=lambda x: -x[1]):
        print(f"  {p}: {count}")
    
    print("\nTop 10 free models (by quality):")
    for m in reg.get_top_models(limit=10):
        print(f"  [{m.provider:8}] {m.canonical_id:50} q={m.quality_effective:.2f} spec={m.specialization}")
    
    print("\nSub-agent routes sample:")
    for role, task in [("coding_subagent", "coding"), ("reasoning_subagent", "reasoning")]:
        routes = reg.get_subagent_routes(role, task)
        print(f"  {role}/{task}:")
        for r in routes[:3]:
            print(f"    p{r['order']} [{r['provider']}] {r['model']}")
    
    print("\n✅ Registry test complete")