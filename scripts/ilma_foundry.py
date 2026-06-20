"""
ILMA v5.0 — THE FOUNDRY (Autonomous CI/CD Pipeline)
Shadow Deployment & Auto-Rollback System

Manages the complete lifecycle of skill mutations from genetic engine:
1. Shadow Deployment — Release to 10% traffic
2. Traffic Monitoring — Watch for anomalies
3. Auto-Rollback — Instant recovery on failure

SUPREME ARCHITECT: ILMA v5.0 — Infinity Production Update
"""

from __future__ import annotations
import asyncio
import json
import os
import sys
import time
import uuid
import hashlib
import re
import traceback
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Foundry")


# ═══════════════════════════════════════════════════════════════════════════════
# DEPLOYMENT STATES & CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

class DeploymentState(Enum):
    """Lifecycle states for a skill deployment."""
    CREATED = "created"              # Mutation generated
    SANDBOX_TESTING = "sandbox"      # Testing in ephemeral sandbox
    APPROVED = "approved"            # Passed RLAIF evaluation
    SHADOW_DEPLOYING = "shadowing"  # Releasing to 10% traffic
    SHADOW_ACTIVE = "shadow_active" # Monitoring 10% traffic
    SHADOW_SUCCESS = "shadow_success" # Shadow passed, promoting
    PROMOTING = "promoting"         # Full rollout
    PROMOTED = "promoted"           # Running 100% traffic
    SHADOW_FAILED = "shadow_failed"  # Shadow detected anomaly
    ROLLING_BACK = "rolling_back"   # Reverting to baseline
    ROLLED_BACK = "rolled_back"     # Back to previous version
    ARCHIVED = "archived"            # Decommissioned


@dataclass
class DeploymentConfig:
    """Configuration for deployment pipeline."""
    shadow_traffic_percent: float = 10.0    # 10% for shadow
    shadow_duration_minutes: int = 30       # Monitor for 30 min
    anomaly_threshold_error_rate: float = 5.0  # 5% error rate triggers
    anomaly_threshold_latency_ms: float = 5000.0  # 5s latency triggers
    auto_rollback_enabled: bool = True
    require_manual_approval: bool = False
    max_shadow_retries: int = 3


@dataclass
class DeploymentVersion:
    """A version of a skill in the deployment pipeline."""
    id: str
    skill_name: str
    version: str                        # e.g., "1.2.3"
    source: str                         # "genetic_mutation" or "manual"
    parent_version: Optional[str]       # Previous version this evolved from
    
    # Files
    baseline_path: Path                # Current production file
    shadow_path: Path                  # New version file
    
    # State
    state: DeploymentState = DeploymentState.CREATED
    
    # Metrics (collected during shadow)
    shadow_start: Optional[str] = None
    shadow_end: Optional[str] = None
    shadow_requests: int = 0
    shadow_errors: int = 0
    shadow_error_rate: float = 0.0
    shadow_avg_latency_ms: float = 0.0
    
    # Baseline metrics (for comparison)
    baseline_error_rate: float = 0.0
    baseline_avg_latency_ms: float = 0.0
    
    # Rollback
    rollback_reason: Optional[str] = None
    rolled_back_at: Optional[str] = None
    
    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    created_by: str = "genetic_engine"  # or "manual"
    fitness_score: float = 0.0          # RLAIF score


@dataclass
class AnomalyEvent:
    """Detected anomaly during shadow deployment."""
    timestamp: str
    version_id: str
    anomaly_type: str       # "error_rate", "latency", "crash", "memory_leak"
    severity: str           # "low", "medium", "high", "critical"
    metric_name: str
    actual_value: float
    threshold_value: float
    description: str


# ═══════════════════════════════════════════════════════════════════════════════
# TRAFFIC SPLITTER — SHADOW ROUTING
# ═══════════════════════════════════════════════════════════════════════════════

class TrafficSplitter:
    """
    Routes traffic between baseline and shadow versions.
    Uses consistent hashing for sticky sessions.
    """
    
    def __init__(self, shadow_percent: float = 10.0):
        self.shadow_percent = shadow_percent
        self.baseline_percent = 100.0 - shadow_percent
        
        # Consistent hashing ring for sticky sessions
        self._hash_ring: Dict[int, str] = {}  # hash → "baseline" or "shadow"
        self._rebuild_ring()
    
    def _rebuild_ring(self):
        """Rebuild consistent hash ring."""
        self._hash_ring.clear()
        
        # 360 degrees on the ring
        # First N% goes to shadow, rest to baseline
        shadow_boundary = int(360 * self.shadow_percent / 100)
        
        for i in range(shadow_boundary):
            self._hash_ring[i] = "shadow"
        
        for i in range(shadow_boundary, 360):
            self._hash_ring[i] = "baseline"
    
    def set_shadow_percent(self, percent: float):
        """Update shadow traffic percentage."""
        self.shadow_percent = percent
        self._rebuild_ring()
        logger.info(f"[SPLITTER] Shadow traffic set to {percent}%")
    
    def get_route(self, request_id: str) -> str:
        """
        Get route for a request.
        Uses consistent hashing based on request_id for sticky sessions.
        """
        # Hash request_id to 0-359
        hash_val = int(hashlib.md5(request_id.encode()).hexdigest(), 16) % 360
        
        return self._hash_ring.get(hash_val, "baseline")
    
    def should_route_to_shadow(self, request_id: str) -> bool:
        """Check if request should go to shadow (new version)."""
        return self.get_route(request_id) == "shadow"
    
    def get_shadow_stats(self) -> Dict[str, float]:
        """Get current traffic split statistics."""
        return {
            "shadow_percent": self.shadow_percent,
            "baseline_percent": self.baseline_percent
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW MONITOR — ANOMALY DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

class ShadowMonitor:
    """
    Monitors shadow deployment for anomalies.
    Compares shadow metrics against baseline.
    """
    
    def __init__(self, config: DeploymentConfig):
        self.config = config
        self.anomaly_history: deque = deque(maxlen=100)
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
        self._running = False
    
    async def start_monitoring(self, version: DeploymentVersion):
        """Start monitoring a shadow deployment."""
        self._running = True
        task = asyncio.create_task(self._monitor_loop(version))
        self._monitoring_tasks[version.id] = task
        logger.info(f"[MONITOR] Started monitoring {version.id}")
    
    async def stop_monitoring(self, version_id: str):
        """Stop monitoring a version."""
        if version_id in self._monitoring_tasks:
            self._monitoring_tasks[version_id].cancel()
            del self._monitoring_tasks[version_id]
        logger.info(f"[MONITOR] Stopped monitoring {version_id}")
    
    async def _monitor_loop(self, version: DeploymentVersion):
        """
        Monitor shadow deployment metrics.
        Checks every 30 seconds for anomalies.
        """
        check_interval = 30  # seconds
        
        while self._running and version.state == DeploymentState.SHADOW_ACTIVE:
            try:
                # Collect current metrics
                await self._collect_metrics(version)
                
                # Check for anomalies
                anomalies = await self._check_anomalies(version)
                
                if anomalies:
                    for anomaly in anomalies:
                        self.anomaly_history.append(anomaly)
                        logger.warning(f"[MONITOR] Anomaly detected: {anomaly.anomaly_type} "
                                     f"({anomaly.metric_name}={anomaly.actual_value} vs threshold={anomaly.threshold_value})")
                    
                    # Auto-rollback if threshold exceeded
                    if len(anomalies) >= 3 or any(a.severity == "critical" for a in anomalies):
                        logger.error(f"[MONITOR] Critical anomalies detected, triggering rollback")
                        version.state = DeploymentState.SHADOW_FAILED
                        return
                
                # Check duration
                if version.shadow_start:
                    elapsed = (datetime.now() - datetime.fromisoformat(version.shadow_start)).total_seconds() / 60
                    if elapsed >= self.config.shadow_duration_minutes:
                        logger.info(f"[MONITOR] Shadow period completed successfully")
                        version.state = DeploymentState.SHADOW_SUCCESS
                        return
                
                await asyncio.sleep(check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[MONITOR] Error in monitor loop: {e}")
                await asyncio.sleep(check_interval)
    
    async def _collect_metrics(self, version: DeploymentVersion):
        """Collect current metrics for version."""
        # In production: pull actual metrics from gateway
        # For now: simulate metrics
        import random
        
        # Simulate shadow metrics
        version.shadow_requests += random.randint(10, 50)
        new_errors = random.randint(0, 3)
        version.shadow_errors += new_errors
        
        if version.shadow_requests > 0:
            version.shadow_error_rate = version.shadow_errors / version.shadow_requests * 100
        
        # Simulate latency (baseline: 200ms, shadow: varies)
        version.shadow_avg_latency_ms = random.uniform(150, 300)
        
        # Baseline metrics (historical)
        version.baseline_error_rate = 1.5  # 1.5% historical
        version.baseline_avg_latency_ms = 200.0  # 200ms historical
    
    async def _check_anomalies(self, version: DeploymentVersion) -> List[AnomalyEvent]:
        """Check for anomalies against thresholds."""
        anomalies = []
        
        # Error rate check
        if version.shadow_error_rate > self.config.anomaly_threshold_error_rate:
            anomaly = AnomalyEvent(
                timestamp=datetime.now().isoformat(),
                version_id=version.id,
                anomaly_type="error_rate",
                severity="high" if version.shadow_error_rate > 10 else "medium",
                metric_name="error_rate_percent",
                actual_value=version.shadow_error_rate,
                threshold_value=self.config.anomaly_threshold_error_rate,
                description=f"Error rate {version.shadow_error_rate:.2f}% exceeds threshold"
            )
            anomalies.append(anomaly)
        
        # Latency check
        if version.shadow_avg_latency_ms > self.config.anomaly_threshold_latency_ms:
            anomaly = AnomalyEvent(
                timestamp=datetime.now().isoformat(),
                version_id=version.id,
                anomaly_type="latency",
                severity="medium",
                metric_name="avg_latency_ms",
                actual_value=version.shadow_avg_latency_ms,
                threshold_value=self.config.anomaly_threshold_latency_ms,
                description=f"Latency {version.shadow_avg_latency_ms:.0f}ms exceeds threshold"
            )
            anomalies.append(anomaly)
        
        # Error rate degradation vs baseline
        if version.shadow_error_rate > version.baseline_error_rate * 3:
            anomaly = AnomalyEvent(
                timestamp=datetime.now().isoformat(),
                version_id=version.id,
                anomaly_type="error_rate_degradation",
                severity="high",
                metric_name="error_rate_vs_baseline",
                actual_value=version.shadow_error_rate,
                threshold_value=version.baseline_error_rate * 3,
                description=f"Error rate {version.shadow_error_rate:.2f}% is 3x baseline"
            )
            anomalies.append(anomaly)
        
        return anomalies


# ═══════════════════════════════════════════════════════════════════════════════
# SKILL REGISTRY — VERSION MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

class SkillRegistry:
    """
    Manages skill versions and file paths.
    Handles baseline/shadow swapping.
    """
    
    def __init__(self, skills_base: Path):
        self.skills_base = Path(skills_base)
        self.versions: Dict[str, List[DeploymentVersion]] = defaultdict(list)
        self.active_versions: Dict[str, DeploymentVersion] = {}
        self._lock = asyncio.Lock()
    
    async def register_mutation(
        self,
        skill_name: str,
        new_code: str,
        fitness_score: float,
        parent_version: Optional[str] = None
    ) -> DeploymentVersion:
        """
        Register a new mutation from genetic engine.
        Creates a new deployment version.
        """
        async with self._lock:
            # Get next version number
            existing = self.versions.get(skill_name, [])
            if existing:
                latest = max(existing, key=lambda v: v.version)
                version_parts = latest.version.split(".")
                version_parts[-1] = str(int(version_parts[-1]) + 1)
                new_version_str = ".".join(version_parts)
            else:
                new_version_str = "1.0.0"
            
            # Create version ID
            version_id = f"{skill_name}_{new_version_str}_{uuid.uuid4().hex[:8]}"
            
            # Paths
            skill_dir = self.skills_base / skill_name
            baseline_path = skill_dir / f"{skill_name}.py"
            shadow_path = skill_dir / f"{skill_name}_shadow_{new_version_str.replace('.', '_')}.py"
            
            # Write shadow file
            shadow_path.parent.mkdir(parents=True, exist_ok=True)
            shadow_path.write_text(new_code)
            
            version = DeploymentVersion(
                id=version_id,
                skill_name=skill_name,
                version=new_version_str,
                source="genetic_mutation",
                parent_version=parent_version,
                baseline_path=baseline_path,
                shadow_path=shadow_path,
                state=DeploymentState.CREATED,
                fitness_score=fitness_score,
                created_by="genetic_engine"
            )
            
            self.versions[skill_name].append(version)
            logger.info(f"[REGISTRY] Registered mutation {version_id} (v{new_version_str}, "
                       f"fitness: {fitness_score:.1f})")
            
            return version
    
    async def get_active_version(self, skill_name: str) -> Optional[DeploymentVersion]:
        """Get the currently active (production) version."""
        return self.active_versions.get(skill_name)
    
    async def get_version_history(self, skill_name: str) -> List[DeploymentVersion]:
        """Get all versions of a skill."""
        return sorted(
            self.versions.get(skill_name, []),
            key=lambda v: v.created_at,
            reverse=True
        )
    
    async def swap_to_shadow(self, version: DeploymentVersion):
        """
        Swap baseline to shadow — for promotion.
        Creates backup of baseline, then replaces with shadow.
        """
        async with self._lock:
            # Backup current baseline
            if version.baseline_path.exists():
                backup_path = version.baseline_path.with_suffix('.bak')
                shutil.copy2(version.baseline_path, backup_path)
                logger.info(f"[REGISTRY] Backed up baseline to {backup_path}")
            
            # Swap
            shutil.copy2(version.shadow_path, version.baseline_path)
            logger.info(f"[REGISTRY] Promoted {version.skill_name} to v{version.version}")
            
            # Update state
            version.state = DeploymentState.PROMOTED
            self.active_versions[version.skill_name] = version
            
            # Archive old versions
            await self._archive_old_versions(version)
    
    async def rollback_to_baseline(self, version: DeploymentVersion, reason: str):
        """
        Rollback to baseline — revert shadow changes.
        """
        async with self._lock:
            # Find the baseline version to restore
            all_versions = self.versions.get(version.skill_name, [])
            baseline_version = None
            
            for v in all_versions:
                if v.state == DeploymentState.PROMOTED:
                    baseline_version = v
                    break
            
            if baseline_version and baseline_version.baseline_path.exists():
                # Restore baseline
                shutil.copy2(baseline_version.baseline_path, version.baseline_path)
            
            # Update version state
            version.state = DeploymentState.ROLLED_BACK
            version.rollback_reason = reason
            version.rolled_back_at = datetime.now().isoformat()
            
            # Delete shadow file
            if version.shadow_path.exists():
                version.shadow_path.unlink()
            
            logger.info(f"[REGISTRY] Rolled back {version.skill_name} to baseline "
                       f"(reason: {reason})")
    
    async def _archive_old_versions(self, promoted_version: DeploymentVersion):
        """Archive old promoted versions after promotion."""
        all_versions = self.versions.get(promoted_version.skill_name, [])
        
        for v in all_versions:
            if v.id != promoted_version.id and v.state == DeploymentState.PROMOTED:
                v.state = DeploymentState.ARCHIVED
                logger.info(f"[REGISTRY] Archived {v.id}")


# ═══════════════════════════════════════════════════════════════════════════════
# THE FOUNDRY — MAIN CI/CD ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

class TheFoundry:
    """
    Main CI/CD orchestrator for autonomous skill deployments.
    
    Pipeline:
    1. Mutation received from genetic_engine
    2. Sandbox testing (already done by genetic engine)
    3. Shadow deployment (10% traffic)
    4. Monitor for anomalies
    5a. If success → Promote to 100%
    5b. If failure → Auto-rollback to baseline
    
    Features:
    - Zero-downtime deployments
    - Automatic rollback on anomalies
    - Traffic splitting without sub-agent awareness
    - Version history and rollback capability
    """
    
    def __init__(
        self,
        skills_base: str = "/root/.hermes/profiles/ilma/skills",
        config: DeploymentConfig = None
    ):
        self.config = config or DeploymentConfig()
        
        self.registry = SkillRegistry(Path(skills_base))
        self.monitor = ShadowMonitor(self.config)
        self.splitter = TrafficSplitter(self.config.shadow_traffic_percent)
        
        # Deployment pipeline state
        self.pending_deployments: Dict[str, DeploymentVersion] = {}
        self.active_deployments: Dict[str, DeploymentVersion] = {}
        self.deployment_history: deque = deque(maxlen=100)
        
        self._running = False
        self._lock = asyncio.Lock()
        
        logger.info(f"[FOUNDRY] Initialized (shadow: {self.config.shadow_traffic_percent}%, "
                   f"duration: {self.config.shadow_duration_minutes}min, "
                   f"auto-rollback: {self.config.auto_rollback_enabled})")
    
    async def deploy_mutation(
        self,
        skill_name: str,
        new_code: str,
        fitness_score: float,
        parent_version: Optional[str] = None
    ) -> DeploymentVersion:
        """
        Main entry point: Deploy a mutation from genetic engine.
        
        Steps:
        1. Register version
        2. Start shadow deployment
        3. Monitor for anomalies
        4. Auto-promote or rollback
        """
        logger.info(f"[FOUNDRY] Deploying mutation for {skill_name} "
                   f"(fitness: {fitness_score:.1f})")
        
        # Step 1: Register
        version = await self.registry.register_mutation(
            skill_name=skill_name,
            new_code=new_code,
            fitness_score=fitness_score,
            parent_version=parent_version
        )
        
        # Step 2: Start sandbox testing (skip if already tested by genetic engine)
        version.state = DeploymentState.SANDBOX_TESTING
        await asyncio.sleep(1)  # Simulate additional sandbox check
        version.state = DeploymentState.APPROVED
        
        # Step 3: Queue for shadow deployment
        self.pending_deployments[version.id] = version
        
        # Step 4: Start deployment pipeline
        asyncio.create_task(self._deployment_pipeline(version))
        
        return version
    
    async def _deployment_pipeline(self, version: DeploymentVersion):
        """
        Complete deployment pipeline for a version.
        """
        try:
            # SHADOW_DEPLOYING
            version.state = DeploymentState.SHADOW_DEPLOYING
            logger.info(f"[FOUNDRY] Starting shadow deployment: {version.id}")
            
            # Update splitter to include this version
            self.active_deployments[version.id] = version
            
            # SHADOW_ACTIVE
            version.state = DeploymentState.SHADOW_ACTIVE
            version.shadow_start = datetime.now().isoformat()
            
            # Start monitoring
            await self.monitor.start_monitoring(version)
            
            # Wait for monitoring to complete (or anomaly detected)
            while version.state == DeploymentState.SHADOW_ACTIVE:
                await asyncio.sleep(10)
                
                # Check if monitoring detected failure
                if version.state == DeploymentState.SHADOW_FAILED:
                    await self._handle_shadow_failure(version)
                    return
                
                # Check if shadow period completed
                if version.shadow_end:
                    break
            
            # SHADOW_SUCCESS
            if version.state == DeploymentState.SHADOW_SUCCESS:
                await self._promote_version(version)
            else:
                logger.warning(f"[FOUNDRY] Unexpected state: {version.state}")
                
        except Exception as e:
            logger.error(f"[FOUNDRY] Pipeline error for {version.id}: {e}")
            version.state = DeploymentState.SHADOW_FAILED
            await self._handle_shadow_failure(version)
    
    async def _handle_shadow_failure(self, version: DeploymentVersion):
        """Handle shadow deployment failure."""
        logger.warning(f"[FOUNDRY] Shadow failed for {version.id}")
        
        if self.config.auto_rollback_enabled:
            await self._rollback_version(version, "Anomaly detected during shadow")
        else:
            version.state = DeploymentState.SHADOW_FAILED
            self.deployment_history.append(version)
    
    async def _promote_version(self, version: DeploymentVersion):
        """Promote shadow to full production."""
        logger.info(f"[FOUNDRY] Promoting {version.id} to production")
        
        version.state = DeploymentState.PROMOTING
        
        try:
            # Swap files
            await self.registry.swap_to_shadow(version)
            
            version.state = DeploymentState.PROMOTED
            self.deployment_history.append(version)
            
            # Remove from active
            if version.id in self.active_deployments:
                del self.active_deployments[version.id]
            
            logger.info(f"[FOUNDRY] ✅ Promoted {version.skill_name} v{version.version} "
                       f"to production")
            
        except Exception as e:
            logger.error(f"[FOUNDRY] Promotion failed: {e}")
            await self._rollback_version(version, f"Promotion failed: {e}")
    
    async def _rollback_version(self, version: DeploymentVersion, reason: str):
        """Rollback to baseline."""
        logger.warning(f"[FOUNDRY] Rolling back {version.id}: {reason}")
        
        version.state = DeploymentState.ROLLING_BACK
        
        try:
            await self.registry.rollback_to_baseline(version, reason)
            
            version.state = DeploymentState.ROLLED_BACK
            self.deployment_history.append(version)
            
            # Remove from active
            if version.id in self.active_deployments:
                del self.active_deployments[version.id]
            
            # Stop monitoring
            await self.monitor.stop_monitoring(version.id)
            
            logger.info(f"[FOUNDRY] ✅ Rolled back {version.skill_name} to baseline")
            
        except Exception as e:
            logger.error(f"[FOUNDRY] Rollback failed: {e}")
            version.state = DeploymentState.SHADOW_FAILED
    
    async def manual_rollback(self, skill_name: str, reason: str = "Manual trigger") -> bool:
        """
        Manually rollback a skill to its previous version.
        """
        active = await self.registry.get_active_version(skill_name)
        
        if not active:
            logger.warning(f"[FOUNDRY] No active deployment for {skill_name}")
            return False
        
        # Find previous version
        history = await self.registry.get_version_history(skill_name)
        previous = None
        
        for v in history:
            if v.state == DeploymentState.PROMOTED and v.id != active.id:
                previous = v
                break
        
        if not previous:
            logger.warning(f"[FOUNDRY] No previous version to rollback to for {skill_name}")
            return False
        
        await self._rollback_version(previous, reason)
        return True
    
    async def get_deployment_status(self, version_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a deployment."""
        version = self.active_deployments.get(version_id)
        if not version:
            for v in self.pending_deployments.values():
                if v.id == version_id:
                    version = v
                    break
        
        if not version:
            return None
        
        return {
            "id": version.id,
            "skill_name": version.skill_name,
            "version": version.version,
            "state": version.state.value,
            "fitness_score": version.fitness_score,
            "shadow_metrics": {
                "requests": version.shadow_requests,
                "errors": version.shadow_errors,
                "error_rate": version.shadow_error_rate,
                "avg_latency_ms": version.shadow_avg_latency_ms
            },
            "baseline_metrics": {
                "error_rate": version.baseline_error_rate,
                "avg_latency_ms": version.baseline_avg_latency_ms
            },
            "shadow_start": version.shadow_start,
            "created_at": version.created_at
        }
    
    def get_active_deployments(self) -> List[Dict[str, Any]]:
        """Get all active deployments."""
        return [
            {
                "id": v.id,
                "skill_name": v.skill_name,
                "version": v.version,
                "state": v.state.value,
                "shadow_requests": v.shadow_requests
            }
            for v in self.active_deployments.values()
        ]
    
    def get_traffic_split(self) -> Dict[str, float]:
        """Get current traffic split configuration."""
        return self.splitter.get_shadow_stats()


# ═══════════════════════════════════════════════════════════════════════════════
# GATEWAY INTEGRATION — REQUEST INTERCEPTION
# ═══════════════════════════════════════════════════════════════════════════════

class FoundryGateway:
    """
    Integrates Foundry with the L5 Orchestrator gateway.
    Intercepts skill execution requests and routes to shadow/baseline.
    """
    
    def __init__(self, foundry: TheFoundry):
        self.foundry = foundry
        self.splitter = foundry.splitter
    
    def route_request(self, skill_name: str, request_id: str) -> str:
        """
        Route a skill execution request.
        Returns: "baseline" or "shadow"
        
        This is called by L5 Orchestrator before executing a skill.
        """
        # Check if skill has active shadow
        active_shadows = [
            v for v in self.foundry.active_deployments.values()
            if v.skill_name == skill_name and v.state == DeploymentState.SHADOW_ACTIVE
        ]
        
        if not active_shadows:
            return "baseline"  # No shadow, use baseline
        
        # Route based on traffic split
        return self.splitter.get_route(request_id)
    
    async def execute_skill(
        self,
        skill_name: str,
        request_id: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute skill with automatic shadow routing.
        """
        route = self.route_request(skill_name, request_id)
        
        version = None
        for v in self.foundry.active_deployments.values():
            if v.skill_name == skill_name and v.state == DeploymentState.SHADOW_ACTIVE:
                version = v
                break
        
        if not version:
            # Use baseline
            return await self._execute_baseline(skill_name, params)
        
        if route == "shadow":
            # Execute shadow version
            return await self._execute_shadow(version, params)
        else:
            # Execute baseline version
            return await self._execute_baseline(skill_name, params)
    
    async def _execute_baseline(self, skill_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute baseline skill version."""
        # In production: import and execute baseline skill
        return {
            "route": "baseline",
            "skill_name": skill_name,
            "status": "success",
            "version": "baseline"
        }
    
    async def _execute_shadow(self, version: DeploymentVersion, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute shadow (new) skill version."""
        # In production: import and execute shadow skill
        # Track metrics
        version.shadow_requests += 1
        
        try:
            result = {
                "route": "shadow",
                "skill_name": version.skill_name,
                "version": version.version,
                "status": "success"
            }
            return result
        except Exception as e:
            version.shadow_errors += 1
            raise


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN — DEMO
# ═══════════════════════════════════════════════════════════════════════════════

async def main():
    """Demo: The Foundry CI/CD Pipeline."""
    print("=" * 70)
    print("ILMA v5.0 — THE FOUNDRY (Autonomous CI/CD) DEMO")
    print("=" * 70)
    
    # Initialize Foundry
    foundry = TheFoundry()
    gateway = FoundryGateway(foundry)
    
    print("\n[FOUNDRY INITIALIZED]")
    print(f"  Shadow traffic: {foundry.config.shadow_traffic_percent}%")
    print(f"  Shadow duration: {foundry.config.shadow_duration_minutes}min")
    print(f"  Auto-rollback: {foundry.config.auto_rollback_enabled}")
    
    # Simulate genetic mutation receiving
    print("\n[SIMULATING GENETIC MUTATION]")
    
    sample_code = '''
def improved_skill(param):
    """Improved version from genetic mutation."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Executing improved version")
    
    try:
        result = process_data(param)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"success": False, "error": str(e)}

def process_data(param):
    # Improved logic
    return param * 2
'''
    
    # Deploy mutation
    version = await foundry.deploy_mutation(
        skill_name="test_skill",
        new_code=sample_code,
        fitness_score=85.5,
        parent_version="1.0.0"
    )
    
    print(f"\n[DEPLOYMENT CREATED]")
    print(f"  Version ID: {version.id}")
    print(f"  Version: v{version.version}")
    print(f"  State: {version.state.value}")
    print(f"  Fitness Score: {version.fitness_score}")
    
    # Simulate traffic routing
    print("\n[TRAFFIC ROUTING TEST]")
    for i in range(5):
        req_id = f"req_{uuid.uuid4().hex[:8]}"
        route = gateway.route_request("test_skill", req_id)
        print(f"  Request {req_id[-8:]}: → {route}")
    
    # Simulate shadow monitoring
    print("\n[SHADOW MONITORING]")
    
    for round_num in range(3):
        await asyncio.sleep(2)
        
        status = await foundry.get_deployment_status(version.id)
        if status:
            print(f"  Round {round_num + 1}:")
            print(f"    State: {status['state']}")
            print(f"    Shadow requests: {status['shadow_metrics']['requests']}")
            print(f"    Shadow error rate: {status['shadow_metrics']['error_rate']:.2f}%")
            print(f"    Latency: {status['shadow_metrics']['avg_latency_ms']:.0f}ms")
    
    # Final status
    print("\n[FINAL STATUS]")
    active = foundry.get_active_deployments()
    print(f"  Active deployments: {len(active)}")
    
    for dep in active:
        print(f"  - {dep['skill_name']} v{dep['version']}: {dep['state']}")
    
    print("\n" + "=" * 70)
    print("FOUNDRY DEMO COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
