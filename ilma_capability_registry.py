"""
ILMA Capability Registry — Category-based capability management
Part of ILMA v3.0 AYDA Integration (9/10 components — capability_registry added 2026-05-08)
"""
from __future__ import annotations
from typing import Optional
from functools import lru_cache
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import logging
import threading
import time
import hashlib

# Path constants for ILMA components
ILMA_PROFILES_DIR = Path("/root/.hermes/profiles")
ILMA_CAPABILITY_REGISTRY_PATH = ILMA_PROFILES_DIR / "ilma" / "ilma_capability_registry.py"

# Configure module logger
_logger = logging.getLogger(__name__)


class CapabilityCategory(Enum):
    COGNITIVE = "cognitive"          # Thinking, reasoning, planning
    EXECUTIVE = "executive"          # Task execution, delegation, workflow
    CREATIVE = "creative"            # Writing, design, generation
    ANALYTICAL = "analytical"         # Research, analysis, data processing
    OPERATIONAL = "operational"      # IT, DevOps, networking, automation
    COMMUNICATION = "communication"  # Messaging, reporting, documentation
    SECURITY = "security"            # Auth, encryption, validation
    INTEGRATION = "integration"       # API, plugins, external systems
    MEMORY = "memory"                 # Storage, retrieval, learning
    META = "meta"                    # Self-improvement, evolution


class CapabilityStatus(Enum):
    VERIFIED = "verified"            # Tested, proven, documented
    PROVISIONAL = "provisional"       # Implemented but not fully tested
    EMERGING = "emerging"             # Partially implemented, in progress
    DEPRECATED = "deprecated"         # Will be removed
    EXTERNAL = "external"             # Delegated to external provider


@dataclass
class CapabilityEntry:
    name: str
    category: CapabilityCategory
    status: CapabilityStatus
    description: str
    primary_tool: str
    fallback_tools: list = field(default_factory=list)
    script_fallback: Optional[str] = None
    api_fallback: Optional[str] = None
    browser_fallback: Optional[str] = None
    service_fallback: Optional[str] = None
    sub_agent_fallback: Optional[str] = None
    evidence_id: Optional[str] = None
    test_results: Optional[dict] = None
    performance_metrics: Optional[dict] = None
    dependencies: list = field(default_factory=list)
    risk_level: str = "low"           # low, medium, high, critical
    owner: str = "ILMA"
    last_verified: float = field(default_factory=time.time)
    verified_by: str = "system"
    tags: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def is_usable(self) -> bool:
        return self.status in (CapabilityStatus.VERIFIED, CapabilityStatus.PROVISIONAL)

    def needs_approval(self) -> bool:
        return self.risk_level in ("high", "critical")


class CapabilityRegistry:
    """
    Central registry for all ILMA capabilities.
    Tracks status, fallbacks, evidence, and performance metrics.
    """

    def __init__(self):
        self._capabilities: dict[str, CapabilityEntry] = {}
        self._lock = threading.RLock()
        self._categories: dict[CapabilityCategory, list[str]] = {c: [] for c in CapabilityCategory}
        self._tags_index: dict[str, set[str]] = {}
        self._status_index: dict[CapabilityStatus, set[str]] = {}
        self._initialized = False
        self.initialize()  # Auto-initialize on construction

    def initialize(self) -> None:
        """Load default capabilities."""
        if self._initialized:
            return
        self._register_defaults()
        self._initialized = True

    def register(self, entry: CapabilityEntry) -> None:
        with self._lock:
            self._capabilities[entry.name] = entry
            self._categories[entry.category].append(entry.name)
            for tag in entry.tags:
                if tag not in self._tags_index:
                    self._tags_index[tag] = set()
                self._tags_index[tag].add(entry.name)
            if entry.status not in self._status_index:
                self._status_index[entry.status] = set()
            self._status_index[entry.status].add(entry.name)

    def get(self, name: str) -> Optional[CapabilityEntry]:
        with self._lock:
            return self._capabilities.get(name)

    def get_by_category(self, category: CapabilityCategory) -> list[CapabilityEntry]:
        with self._lock:
            names = self._categories.get(category, [])
            return [self._capabilities[n] for n in names if n in self._capabilities]

    def get_by_status(self, status: CapabilityStatus) -> list[CapabilityEntry]:
        with self._lock:
            names = self._status_index.get(status, [])
            return [self._capabilities[n] for n in names if n in self._capabilities]

    def get_by_tag(self, tag: str) -> list[CapabilityEntry]:
        with self._lock:
            names = self._tags_index.get(tag, set())
            return [self._capabilities[n] for n in names if n in self._capabilities]

    def get_usable(self) -> list[CapabilityEntry]:
        with self._lock:
            return [e for e in self._capabilities.values() if e.is_usable()]

    def get_all(self) -> list[CapabilityEntry]:
        with self._lock:
            return list(self._capabilities.values())

    def update_status(self, name: str, status: CapabilityStatus, evidence_id: Optional[str] = None) -> bool:
        with self._lock:
            entry = self._capabilities.get(name)
            if not entry:
                return False
            old_status = entry.status
            entry.status = status
            entry.last_verified = time.time()
            if evidence_id:
                entry.evidence_id = evidence_id
            # Update status index
            if old_status in self._status_index:
                self._status_index[old_status].discard(name)
            if status not in self._status_index:
                self._status_index[status] = set()
            self._status_index[status].add(name)
            return True

    def update_evidence(self, name: str, evidence_id: str, test_results: Optional[dict] = None) -> bool:
        with self._lock:
            entry = self._capabilities.get(name)
            if not entry:
                return False
            entry.evidence_id = evidence_id
            if test_results:
                entry.test_results = test_results
            entry.last_verified = time.time()
            return True

    def update_metrics(self, name: str, metrics: dict) -> bool:
        with self._lock:
            entry = self._capabilities.get(name)
            if not entry:
                return False
            entry.performance_metrics = metrics
            return True

    def search(self, query: str) -> list[CapabilityEntry]:
        with self._lock:
            query_lower = query.lower()
            results = []
            for entry in self._capabilities.values():
                if query_lower in entry.name.lower():
                    results.append(entry)
                elif query_lower in entry.description.lower():
                    results.append(entry)
                elif query_lower in [t.lower() for t in entry.tags]:
                    results.append(entry)
            return results

    def needs_approval(self, name: str) -> bool:
        with self._lock:
            entry = self._capabilities.get(name)
            return entry.needs_approval() if entry else False

    def get_fallback(self, name: str) -> Optional[str]:
        with self._lock:
            entry = self._capabilities.get(name)
            if not entry:
                return None
            # Try fallback_tools — look for registered capability by name
            # or by matching its primary_tool against the fallback name.
            # fallback_tools entries are tool names (e.g. "ilma_knowledge_graph")
            # which may map to a capability whose primary_tool = that name.
            for fb in entry.fallback_tools:
                # Direct capability name match first
                fb_entry = self._capabilities.get(fb)
                if fb_entry and fb_entry.is_usable():
                    return fb
                # Fallback: find capability whose primary_tool matches this fallback
                for cap_name, cap_entry in self._capabilities.items():
                    if cap_entry.primary_tool == fb and cap_entry.is_usable():
                        return cap_name
            # Last resort: script_fallback (path to a script module)
            return entry.script_fallback

    def get_category_summary(self) -> dict:
        with self._lock:
            return {
                cat.value: {
                    "total": len(names),
                    "verified": sum(1 for n in names if self._capabilities[n].status == CapabilityStatus.VERIFIED),
                    "provisional": sum(1 for n in names if self._capabilities[n].status == CapabilityStatus.PROVISIONAL),
                    "emerging": sum(1 for n in names if self._capabilities[n].status == CapabilityStatus.EMERGING),
                }
                for cat, names in self._categories.items()
                if names
            }

    def get_status_summary(self) -> dict:
        with self._lock:
            return {s.value: len(names) for s, names in self._status_index.items() if names}

    def generate_fingerprint(self) -> str:
        """Generate a fingerprint of the current registry state."""
        with self._lock:
            data = {
                "capabilities": sorted(self._capabilities.keys()),
                "status": {k: v.status.value for k, v in self._capabilities.items()},
                "timestamp": time.time(),
            }
            return hashlib.sha256(str(data).encode()).hexdigest()[:16]

    def export_manifest(self) -> dict:
        with self._lock:
            return {
                "total_capabilities": len(self._capabilities),
                "categories": len([c for c in self._categories.values() if c]),
                "fingerprint": self.generate_fingerprint(),
                "last_updated": time.time(),
                "entries": [
                    {
                        "name": e.name,
                        "category": e.category.value,
                        "status": e.status.value,
                        "description": e.description,
                        "primary_tool": e.primary_tool,
                        "risk_level": e.risk_level,
                        "evidence_id": e.evidence_id,
                        "is_usable": e.is_usable(),
                    }
                    for e in self._capabilities.values()
                ],
            }

    def _register_defaults(self) -> None:
        """Register default ILMA capabilities."""
        defaults = [
            # COGNITIVE
            CapabilityEntry(
                name="reasoning",
                category=CapabilityCategory.COGNITIVE,
                status=CapabilityStatus.VERIFIED,
                description="Deductive, inductive, abductive, causal, analogical reasoning",
                primary_tool="ilma_reasoning_runtime",
                fallback_tools=["ilma_knowledge_graph", "ilma_confidence_router"],
                evidence_id="reasoning_runtime_verified",
                risk_level="low",
                tags=["reasoning", "thinking", "logic", "analysis"],
            ),
            CapabilityEntry(
                name="planning",
                category=CapabilityCategory.COGNITIVE,
                status=CapabilityStatus.PROVISIONAL,
                description="Multi-step task planning with dependency resolution",
                primary_tool="ilma_knowledge_graph",
                fallback_tools=["ilma_reasoning_runtime"],
                evidence_id="planning_provisional_20260510",
                risk_level="medium",
                tags=["planning", "strategy", "roadmap"],
            ),
            CapabilityEntry(
                name="problem_solving",
                category=CapabilityCategory.COGNITIVE,
                status=CapabilityStatus.VERIFIED,
                description="Problem decomposition, solution mapping, failure recovery",
                primary_tool="ilma_reasoning_runtime",
                fallback_tools=["ilma_learning_engine", "ilma_confidence_router"],
                evidence_id="problem_solve_verified",
                risk_level="low",
                tags=["problem_solving", "debugging", "troubleshooting"],
            ),

            # EXECUTIVE
            CapabilityEntry(
                name="task_execution",
                category=CapabilityCategory.EXECUTIVE,
                status=CapabilityStatus.VERIFIED,
                description="Execute tasks via tools, scripts, API, delegation",
                primary_tool="ilma_execution_graph",
                fallback_tools=["ilma_autonomous_loop_engine"],
                evidence_id="execution_graph_verified",
                risk_level="medium",
                tags=["execution", "tools", "automation"],
            ),
            CapabilityEntry(
                name="delegation",
                category=CapabilityCategory.EXECUTIVE,
                status=CapabilityStatus.VERIFIED,
                description="Delegate to sub-agents with isolated context",
                primary_tool="delegate_task",
                fallback_tools=["ilma_autonomous_loop_engine"],
                evidence_id="delegation_verified",
                risk_level="medium",
                tags=["delegation", "subagent", "parallel"],
            ),
            CapabilityEntry(
                name="workflow_orchestration",
                category=CapabilityCategory.EXECUTIVE,
                status=CapabilityStatus.VERIFIED,
                description="Multi-phase workflow with checkpoints and rollback",
                primary_tool="ilma_workflow_ecc",
                fallback_tools=["ilma_execution_graph"],
                evidence_id="workflow_ecc_verified",
                risk_level="medium",
                tags=["workflow", "orchestration", "pipeline"],
            ),
            CapabilityEntry(
                name="autonomous_loop",
                category=CapabilityCategory.EXECUTIVE,
                status=CapabilityStatus.VERIFIED,
                description="Self-improvement loop: discovery, evaluation, evolution",
                primary_tool="ilma_autonomous_loop_engine",
                fallback_tools=["ilma_learning_engine"],
                evidence_id="autonomous_loop_verified",
                risk_level="medium",
                tags=["autonomy", "self_improve", "evolution"],
            ),

            # CREATIVE
            CapabilityEntry(
                name="writing",
                category=CapabilityCategory.CREATIVE,
                status=CapabilityStatus.VERIFIED,
                description="Blog, articles, documentation, professional writing",
                primary_tool="minimax_m2.7",
                fallback_tools=["qwen3.5", "claude"],
                evidence_id="writing_scripts_20260510_verified",
                risk_level="low",
                tags=["writing", "content", "blog", "documentation"],
            ),
            CapabilityEntry(
                name="longform_writing",
                category=CapabilityCategory.CREATIVE,
                status=CapabilityStatus.PROVISIONAL,
                description="1000+ page long-form content with structure and continuity",
                primary_tool="minimax_m2.7",
                fallback_tools=["qwen3.5"],
                evidence_id="longform_writing_provisional_20260510",
                risk_level="low",
                tags=["longform", "book", "novel", "deep_content"],
            ),
            CapabilityEntry(
                name="creative_generation",
                category=CapabilityCategory.CREATIVE,
                status=CapabilityStatus.PROVISIONAL,
                description="Song lyrics, stories, creative concepts",
                primary_tool="minimax_m2.7",
                fallback_tools=["claude", "dalle"],
                evidence_id="creative_generation_provisional_20260510",
                risk_level="low",
                tags=["creative", "song", "story", "art"],
            ),

            # ANALYTICAL
            CapabilityEntry(
                name="research",
                category=CapabilityCategory.ANALYTICAL,
                status=CapabilityStatus.VERIFIED,
                description="Deep research with sources, citations, evidence",
                primary_tool="web_search",
                fallback_tools=["arxiv", "browser", "memory"],
                evidence_id="research_verified",
                risk_level="low",
                tags=["research", "sources", "citations", "papers"],
            ),
            CapabilityEntry(
                name="data_analysis",
                category=CapabilityCategory.ANALYTICAL,
                status=CapabilityStatus.VERIFIED,
                description="Analyze data, generate insights, statistics",
                primary_tool="execute_code",
                fallback_tools=["jupyter", "python"],
                evidence_id="execute_code_20260510_verified",
                risk_level="low",
                tags=["analysis", "data", "statistics", "insights"],
            ),
            CapabilityEntry(
                name="code_analysis",
                category=CapabilityCategory.ANALYTICAL,
                status=CapabilityStatus.VERIFIED,
                description="Static analysis, code review, quality assessment",
                primary_tool="execute_code",
                fallback_tools=["claude_code", "codex"],
                evidence_id="execute_code_20260510_verified",
                risk_level="low",
                tags=["code_review", "static_analysis", "quality"],
            ),

            # OPERATIONAL
            CapabilityEntry(
                name="coding",
                category=CapabilityCategory.OPERATIONAL,
                status=CapabilityStatus.VERIFIED,
                description="Write, debug, refactor production code",
                primary_tool="execute_code",
                fallback_tools=["claude_code", "codex", "ilma_execution_graph"],
                evidence_id="coding_verified",
                risk_level="medium",
                tags=["coding", "programming", "debugging", "refactor"],
            ),
            CapabilityEntry(
                name="heavy_coding",
                category=CapabilityCategory.OPERATIONAL,
                status=CapabilityStatus.PROVISIONAL,
                description="1000+ file codebase engineering, production-grade",
                primary_tool="delegate_task",
                fallback_tools=["ilma_execution_graph"],
                evidence_id="heavy_coding_provisional_20260510",
                risk_level="high",
                tags=["heavy_coding", "large_codebase", "production"],
            ),
            CapabilityEntry(
                name="networking",
                category=CapabilityCategory.OPERATIONAL,
                status=CapabilityStatus.VERIFIED,
                description="Network configuration, DNS, firewall, diagnostics",
                primary_tool="terminal",
                fallback_tools=["browser", "delegate_task"],
                evidence_id="networking_script_20260510_verified",
                risk_level="high",
                tags=["networking", "dns", "firewall", "tcp"],
            ),
            CapabilityEntry(
                name="devops",
                category=CapabilityCategory.OPERATIONAL,
                status=CapabilityStatus.VERIFIED,
                description="CI/CD, Docker, Kubernetes, automation scripts",
                primary_tool="terminal",
                fallback_tools=["delegate_task", "execute_code"],
                evidence_id="devops_verified",
                risk_level="high",
                tags=["devops", "docker", "kubernetes", "cicd"],
            ),
            CapabilityEntry(
                name="database",
                category=CapabilityCategory.OPERATIONAL,
                status=CapabilityStatus.VERIFIED,
                description="SQL, NoSQL, migrations, queries, optimization",
                primary_tool="execute_code",
                fallback_tools=["terminal", "delegate_task"],
                evidence_id="execute_code_db_20260510_verified",
                risk_level="high",
                tags=["database", "sql", "mongodb", "postgres"],
            ),
            CapabilityEntry(
                name="api_integration",
                category=CapabilityCategory.OPERATIONAL,
                status=CapabilityStatus.VERIFIED,
                description="REST, GraphQL, webhook integration",
                primary_tool="execute_code",
                fallback_tools=["terminal", "browser"],
                evidence_id="execute_code_api_20260510_verified",
                risk_level="medium",
                tags=["api", "rest", "graphql", "integration"],
            ),
            CapabilityEntry(
                name="system_administration",
                category=CapabilityCategory.OPERATIONAL,
                status=CapabilityStatus.VERIFIED,
                description="Server management, monitoring, automation",
                primary_tool="terminal",
                fallback_tools=["delegate_task", "execute_code"],
                evidence_id="sysadmin_verified",
                risk_level="critical",
                tags=["sysadmin", "server", "monitoring", "automation"],
            ),

            # COMMUNICATION
            CapabilityEntry(
                name="messaging",
                category=CapabilityCategory.COMMUNICATION,
                status=CapabilityStatus.VERIFIED,
                description="Send messages via Telegram, Discord, etc.",
                primary_tool="send_message",
                fallback_tools=["terminal"],
                evidence_id="messaging_engine_20260510_verified",
                risk_level="medium",
                tags=["messaging", "telegram", "discord", "notification"],
            ),
            CapabilityEntry(
                name="reporting",
                category=CapabilityCategory.COMMUNICATION,
                status=CapabilityStatus.VERIFIED,
                description="Generate structured reports with evidence",
                primary_tool="minimax_m2.7",
                fallback_tools=["execute_code", "write_file"],
                evidence_id="reporting_verified",
                risk_level="low",
                tags=["reporting", "documentation", "evidence"],
            ),

            # SECURITY
            CapabilityEntry(
                name="security_review",
                category=CapabilityCategory.SECURITY,
                status=CapabilityStatus.VERIFIED,
                description="Security audit, vulnerability assessment",
                primary_tool="execute_code",
                fallback_tools=["terminal", "browser"],
                evidence_id="security_review_verified",
                risk_level="high",
                tags=["security", "audit", "vulnerability"],
            ),
            CapabilityEntry(
                name="authentication",
                category=CapabilityCategory.SECURITY,
                status=CapabilityStatus.VERIFIED,
                description="Auth patterns, token management, OAuth",
                primary_tool="execute_code",
                fallback_tools=["terminal"],
                evidence_id="auth_patterns_20260510_verified",
                risk_level="high",
                tags=["auth", "oauth", "jwt", "tokens"],
            ),

            # INTEGRATION
            CapabilityEntry(
                name="browser_automation",
                category=CapabilityCategory.INTEGRATION,
                status=CapabilityStatus.VERIFIED,
                description="Browser navigation, clicking, typing, snapshots",
                primary_tool="browser_navigate",
                fallback_tools=["web_search", "vision_analyze"],
                evidence_id="browser_automation_verified",
                risk_level="medium",
                tags=["browser", "automation", "scraping", "interaction"],
            ),
            CapabilityEntry(
                name="web_fetch",
                category=CapabilityCategory.INTEGRATION,
                status=CapabilityStatus.VERIFIED,
                description="Fetch and parse any URL — extract title, content, images, links (100% free, no API key)",
                primary_tool="ilma_free_webfetch",
                fallback_tools=["browser", "web_search"],
                evidence_id="web_fetch_20260522_verified",
                risk_level="low",
                tags=["web", "fetch", "parsing", "extraction", "free"],
            ),
            CapabilityEntry(
                name="web_search",
                category=CapabilityCategory.INTEGRATION,
                status=CapabilityStatus.VERIFIED,
                description="Web search via Mojeek — title, URL, snippet for any query (100% free, no API key)",
                primary_tool="ilma_web_search",
                fallback_tools=["browser", "arxiv"],
                evidence_id="web_search_20260522_verified",
                risk_level="low",
                tags=["web", "search", "mojeek", "free"],
            ),
            CapabilityEntry(
                name="external_api",
                category=CapabilityCategory.INTEGRATION,
                status=CapabilityStatus.VERIFIED,
                description="Call external APIs with rate limiting and retries",
                primary_tool="execute_code",
                fallback_tools=["terminal", "browser"],
                evidence_id="external_api_client_20260510_verified",
                risk_level="medium",
                tags=["api", "external", "integration"],
            ),
            CapabilityEntry(
                name="multimodel_routing",
                category=CapabilityCategory.INTEGRATION,
                status=CapabilityStatus.VERIFIED,
                description="Route requests to optimal AI model providers",
                primary_tool="ilma_provider_kernel",
                fallback_tools=["minimax_m2.7"],
                evidence_id="provider_kernel_verified",
                risk_level="medium",
                tags=["routing", "models", "providers", "llm"],
            ),

            # MEMORY
            CapabilityEntry(
                name="long_term_memory",
                category=CapabilityCategory.MEMORY,
                status=CapabilityStatus.VERIFIED,
                description="Persistent memory across sessions",
                primary_tool="memory",
                fallback_tools=["session_search", "note_taking"],
                evidence_id="memory_verified",
                risk_level="low",
                tags=["memory", "persistence", "storage"],
            ),
            CapabilityEntry(
                name="short_term_memory",
                category=CapabilityCategory.MEMORY,
                status=CapabilityStatus.VERIFIED,
                description="Session context, todo tracking, state",
                primary_tool="todo",
                fallback_tools=["execute_code", "write_file"],
                evidence_id="short_term_memory_verified",
                risk_level="low",
                tags=["session", "context", "state"],
            ),
            CapabilityEntry(
                name="knowledge_base",
                category=CapabilityCategory.MEMORY,
                status=CapabilityStatus.VERIFIED,
                description="Structured knowledge with relationships",
                primary_tool="ilma_knowledge_graph",
                fallback_tools=["memory", "session_search"],
                evidence_id="knowledge_graph_verified",
                risk_level="low",
                tags=["knowledge", "graph", "relationships"],
            ),
            CapabilityEntry(
                name="learning_from_experience",
                category=CapabilityCategory.MEMORY,
                status=CapabilityStatus.VERIFIED,
                description="Save learned patterns as reusable skills",
                primary_tool="skill_manage",
                fallback_tools=["memory", "write_file"],
                evidence_id="skill_verified",
                risk_level="low",
                tags=["learning", "skills", "experience"],
            ),

            # META
            CapabilityEntry(
                name="self_improvement",
                category=CapabilityCategory.META,
                status=CapabilityStatus.VERIFIED,
                description="Auto-evolution, optimization, self-audit",
                primary_tool="ilma_autonomous_loop_engine",
                fallback_tools=["ilma_learning_engine", "memory"],
                evidence_id="self_improve_verified",
                risk_level="medium",
                tags=["evolution", "optimization", "self_audit"],
            ),
            CapabilityEntry(
                name="confidence_routing",
                category=CapabilityCategory.META,
                status=CapabilityStatus.VERIFIED,
                description="Route based on confidence level and criticality",
                primary_tool="ilma_confidence_router",
                fallback_tools=["ilma_knowledge_graph"],
                evidence_id="confidence_router_verified",
                risk_level="low",
                tags=["confidence", "routing", "criticality"],
            ),
            CapabilityEntry(
                name="evidence_validation",
                category=CapabilityCategory.META,
                status=CapabilityStatus.VERIFIED,
                description="Validate claims with evidence, detect hallucinations",
                primary_tool="ilma_grounding_loop",
                fallback_tools=["web_search", "memory"],
                evidence_id="grounding_loop_verified",
                risk_level="low",
                tags=["grounding", "evidence", "hallucination", "validation"],
            ),
            CapabilityEntry(
                name="capability_discovery",
                category=CapabilityCategory.META,
                status=CapabilityStatus.PROVISIONAL,
                description="Discover and register new capabilities at runtime",
                primary_tool="ilma_capability_registry",
                fallback_tools=["memory", "skill_view"],
                evidence_id="capability_discovery_provisional_20260510",
                risk_level="low",
                tags=["discovery", "registry", "capability"],
            ),
        ]

        for entry in defaults:
            self.register(entry)


# Global registry instance
_registry = None
_registry_lock = threading.Lock()


def get_registry() -> CapabilityRegistry:
    """Get the global capability registry singleton."""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = CapabilityRegistry()
                _registry.initialize()
    return _registry


@lru_cache(maxsize=128)
def get_capability(name: str) -> Optional[CapabilityEntry]:
    """Quick access to a single capability."""
    return get_registry().get(name)


@lru_cache(maxsize=128)
def is_capable(name: str) -> bool:
    """Check if a capability is currently usable."""
    entry = get_registry().get(name)
    return entry.is_usable() if entry else False


def needs_approval(name: str) -> bool:
    """Check if a capability needs owner approval."""
    return get_registry().needs_approval(name)


def get_fallback(name: str) -> Optional[str]:
    """Get the best available fallback for a capability."""
    return get_registry().get_fallback(name)


def route_capability(name: str) -> tuple[bool, Optional[str]]:
    """
    Route to a capability with fallback awareness.
    Returns (success, tool_or_fallback).
    """
    registry = get_registry()
    entry = registry.get(name)
    if not entry:
        return False, None
    if not entry.is_usable():
        fallback = registry.get_fallback(name)
        return False, fallback
    return True, entry.primary_tool


def list_by_category(category: CapabilityCategory) -> list[CapabilityEntry]:
    """List all capabilities in a given category.

    Args:
        category: The CapabilityCategory to filter by.

    Returns:
        List of CapabilityEntry objects belonging to the category.
    """
    return get_registry().get_by_category(category)


def list_usable() -> list[CapabilityEntry]:
    """List all capabilities that are currently usable.

    Usable capabilities are those with status VERIFIED or PROVISIONAL.

    Returns:
        List of CapabilityEntry objects that are usable.
    """
    return get_registry().get_usable()


def list_all() -> list[CapabilityEntry]:
    """List all registered capabilities regardless of status.

    Returns:
        List of all CapabilityEntry objects in the registry.
    """
    return get_registry().get_all()


def update_capability_status(name: str, status: CapabilityStatus, evidence_id: Optional[str] = None) -> bool:
    """Update the status of a capability.

    Args:
        name: The name of the capability to update.
        status: The new CapabilityStatus to set.
        evidence_id: Optional evidence ID for the status change.

    Returns:
        True if the capability was found and updated, False otherwise.
    """
    return get_registry().update_status(name, status, evidence_id)

# Backward-compatibility aliases
list_capabilities = list_all

def get_status() -> dict:
    """Return status summary of the capability registry."""
    return get_registry().get_status_summary()
