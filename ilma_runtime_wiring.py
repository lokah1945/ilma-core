#!/usr/bin/env python3
"""
ILMA RUNTIME WIRING CONTRACT v1.2
=================================
Canonical pipeline: BOOT → ANALYZE → ROUTE → RESOLVE → EXECUTE → EVALUATE → VERIFY → LEARN → REPORT

This module defines the canonical runtime wiring between all ILMA modules.
Every module in the pipeline is documented here - NO STANDALONE MODULES.

PIPELINE LAYERS:
  LAYER 0 - BOOT:     ilma.py (boot loader, CLI interface)
  LAYER 1 - ROUTING:  model_router, subagent_router, health_manager, confidence_router
  LAYER 2 - EXEC:     capability_registry, orchestrator, provider_kernel, browser_engine
  LAYER 3 - WORKFLOW: workflow_ecc
  LAYER 4 - VERIFY:   actor_critic_core, judge_system, grounding_loop, evidence_validator, adversarial_qa
  LAYER 5 - REASON:   cognition_kernel, reasoning_runtime, execution_graph
  LAYER 6 - KNOW:     knowledge_graph, knowledge_ingestion, learning_engine
  LAYER 7 - AUTONOMY: autonomous_loop_engine, model_registry
  LAYER 8 - SPECIAL:  super_coding_command_center, partner_wrappers
  LAYER 9 - LEARN:    self_improve_integrator (SELF-IMPROVEMENT CLOSED LOOP)

ARCHITECTURE NOTES:
  - All 30+ wired modules wire into the ILMA pipeline.
  - 8 experimental/standalone modules were archived to fabric_archive/
  - LAYER 9 is the canonical self-improvement layer (v1.2 addition)
  - sys.path is managed at import time to prevent scripts/ shadowing root modules
  - The runtime wiring is verified by ilma.py --status
  - Legacy proxy project removed 2026-06-19.
"""

import logging
import sys
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
from importlib import import_module

# Configure module logger
logger = logging.getLogger(__name__)

# Determine ILMA_ROOT - configurable via environment variable
ILMA_ROOT = Path(os.environ.get("ILMA_ROOT", "/root/.hermes/profiles/ilma"))


class ILMARuntimeWiring:
    """
    Canonical runtime wiring for all ILMA modules.
    This class defines the wiring contract - actual imports are done lazily.
    """
    
    # ─── PIPELINE LAYER DEFINITIONS ─────────────────────────────────────────
    LAYER_BOOT = "ilma.py"
    
    LAYER_1_ROUTING = [
        "ilma_model_router",      # Primary router: task→model, benchmark, health
        "ilma_subagent_router",  # Sub-agent routing with SQLite cache
        "ilma_health_manager",   # Rate-limit tracking, provider fallback
        "ilma_confidence_router", # Confidence-based task-model matching
        "ilma_hermes_skills_router", # Hermes skills auto-trigger: 168 Hermes + 788 total skills, 137 patterns, 34 categories, execution engine v2.0
        "ilma_thinking_mapper",  # GPT-5.5 thinking tier router: 8 modes (thinking/off/low/high/highest, reasoning_effort/off/low/medium/high), 6 tiers (instant/fast/deep/max/balanced/rigorous)
    ]
    
    LAYER_2_EXECUTION = [
        "ilma_research_engine",
        "ilma_reference_engine",  # real metadata extraction + credibility scoring
        "ilma_citation_manager",  # multi-style citations (APA/IEEE/MLA/Chicago/Harvard/Vancouver)
        "ilma_chart_generator",   # matplotlib data charts
        "ilma_vane_adapter",   # Perplexica-Vane agentic research (SearXNG + free NVIDIA)  # Perplexica-style research evidence spine
        "ilma_capability_registry",  # 10-category capability, fallback chain
        "ilma_orchestrator",         # Central command: cmd_status/route/execute
        "ilma_provider_kernel",      # Cloud provider: 4 providers, free-tier first
        "scripts/ilma_model_db_manager",  # ⭐ SINGLE SOURCE OF TRUTH — model DB sync, 4-step pipeline (sync_providers → passive_benchmark → enrich)
        "ilma_browser_engine",       # Browser automation: Playwright + DOM control (NO spoofing)
    ]
    
    LAYER_3_WORKFLOW = [
        "ilma_workflow_ecc",     # 8-step ECC pipeline
        "ilma_scriptorium",      # research-grounded writing pipeline (7-stage)
        "ilma_project_registry", # project metadata mapping (external/internal)
    ]
    
    LAYER_4_VERIFICATION = [
        "ilma_actor_critic_core",   # 3-agent debate: Actor→Critic→Judge
        "ilma_judge_system",        # 10-level L1-L10 verification
        "ilma_grounding_loop",      # Anti-hallucination: claim extraction
        "ilma_evidence_validator",  # Evidence format validation
        "ilma_adversarial_qa",      # Adversarial QA generation
    ]
    
    LAYER_5_REASONING = [
        "ilma_cognition_kernel",     # 4 cognitive modes
        "ilma_reasoning_runtime",    # 5 reasoning types
        "ilma_execution_graph",      # Execution memory graph
    ]
    
    LAYER_6_KNOWLEDGE = [
        "ilma_knowledge_graph",       # Graph OS: 7 node types
        "ilma_knowledge_ingestion",   # Document parsing, extraction
        "ilma_learning_engine",       # Autonomous learning: paths, resources
    ]
    
    LAYER_7_AUTONOMY = [
        "ilma_autonomous_loop_engine",  # 9-state improvement loop
        "ilma_model_registry",          # SQLite + JSON, 1284+ models
    ]

    LAYER_8_SPECIALIZED = [
        "ilma_super_coding_command_center",  # Coding orchestrator: Claude/Codex/OpenCode/Gemini + judge integration
        "ilma_partner_wrappers",              # Partner wrappers: Prometheus-2 (Judge) + DeepSeek-R1 (Critic)
        "ilma_orphan_wiring",                # Phase 70-Autonomy: wires the 22 previously-orphan admin/CLI modules
    ]

    LAYER_9_SELF_IMPROVE = [
        "ilma_self_improve_integrator",       # LAYER 9 CANONICAL: closes the loop between audit → optimize → DNA updates
    ]

    # All wired modules
    ALL_WIRED = (
        LAYER_1_ROUTING + LAYER_2_EXECUTION + LAYER_3_WORKFLOW +
        LAYER_4_VERIFICATION + LAYER_5_REASONING + LAYER_6_KNOWLEDGE +
        LAYER_7_AUTONOMY + LAYER_8_SPECIALIZED + LAYER_9_SELF_IMPROVE
    )

    # Module purposes (for documentation)
    PURPOSES: Dict[str, str] = {
        "ilma_model_router": "Primary router: task→model, benchmark scoring, health awareness, capability context",
        "ilma_subagent_router": "Sub-agent model selection with SQLite route cache, health tracking",
        "ilma_health_manager": "Provider/model health: rate-limit tracking, auto-fallback, provider switching",
        "ilma_confidence_router": "Confidence-based routing: task complexity → model confidence match",
        "ilma_hermes_skills_router": "Hermes skills auto-trigger: 168 Hermes + 619 ILMA skills, 137 regex patterns, 35 categories, auto-load on task context match",
        "ilma_thinking_mapper": "Thinking tier router: 6 tiers (instant/fast/deep/max/balanced/rigorous) → 8 validated API modes (thinking=off/low/high/highest, reasoning_effort=off/low/medium/high)",
        "ilma_capability_registry": "Capability registry: 10 categories, fallback chain, approval gates",
        "ilma_orchestrator": "Central command: cmd_status/route/execute/benchmark - ILMACore + ILMAOrchestrator",
        "ilma_provider_kernel": "Cloud provider management: 4 providers, free-tier first, fallback rules",
        "ilma_workflow_ecc": "8-step ECC pipeline: 4W1H→ECC→Security→Rules→Hooks→Workflow→Verify→Report",
        "ilma_actor_critic_core": "3-agent debate: Actor→Critic→Judge for self-improvement and evaluation",
        "ilma_judge_system": "10-level L1-L10 verification: compile→unit→security→performance→semantic",
        "ilma_grounding_loop": "Anti-hallucination: claim extraction, confidence scoring, fact verification",
        "ilma_evidence_validator": "Evidence format validation: ILMA-EVID-YYYYMMDD-... pattern",
        "ilma_adversarial_qa": "Adversarial question generation and evaluation",
        "ilma_cognition_kernel": "Cognitive modes: REACTIVE/DELIBERATIVE/AUTONOMOUS/META processing",
        "ilma_reasoning_runtime": "Reasoning types: DEDUCTIVE/INDUCTIVE/ABDUCTIVE/CAUSAL/ANALOGICAL",
        "ilma_execution_graph": "Execution memory graph: TASK↔FILE↔PROVIDER↔SKILL nodes and edges",
        "ilma_knowledge_graph": "Graph OS: 7 node types (AGENT/CONCEPT/SKILL/etc), 7 edge types",
        "ilma_knowledge_ingestion": "Knowledge ingestion: document parsing, extraction, storage",
        "ilma_learning_engine": "Autonomous learning: LearningPath, ResourceIndex, lesson events",
        "ilma_autonomous_loop_engine": "9-state improvement loop: DISCOVERY→EVOLUTION→CONSOLIDATION",
        "ilma_model_registry": "Model registry: SQLite + JSON, 1284+ models, subagent routes",
        "ilma_browser_engine": "Browser automation: Playwright + DOM control (navigate/click/type/snapshot/vision) — NO spoofing",
        "ilma_super_coding_command_center": "Coding orchestrator: Claude/Codex/OpenCode/Gemini + judge integration",
        "ilma_partner_wrappers": "Partner wrappers: Prometheus-2 (Judge) + DeepSeek-R1 (Critic)",
        "ilma_orphan_wiring": "Phase 70-Autonomy: wires 22 previously-orphan CLI modules (drift/miner/disable/chart/log/etc) into the system via stable Python API + CLI subcommand",
        # LAYER 9 — SELF-IMPROVEMENT (v1.2)
        "ilma_self_improve_integrator": "LAYER 9 CANONICAL: unifies LearningLogger + SelfImprovementEngine + KnowledgeGraph + Evidence → unified closed-loop self-improvement",
    }
    
    # Pipeline flow (v1.2: direct cloud APIs only)
    PIPELINE_FLOW = "BOOT → ANALYZE(4W1H+thinking_tier+skill_detect) → ROUTE(model_router+confidence) → RESOLVE(capability) → EXECUTE(direct_api+browser+thinking_tier|hermes_skill_execution) → EVALUATE(actor_critic+judge) → VERIFY(grounding) → LEARN(self_improve_integrator) → REPORT"

    def __init__(self):
        """
        Initialize the ILMA runtime wiring.

        Sets up version info, component cache, and builds the layer map
        for all 31 wired modules across 9 pipeline layers.
        """
        self.version = "1.1"
        self.wired_at = datetime.now().isoformat()
        self._components: Dict[str, Any] = {}
        self._layer_map: Dict[str, List[str]] = {}
        self._build_layer_map()
    
    def _build_layer_map(self):
        """Build mapping of layer name → module list."""
        self._layer_map = {
            "LAYER_1_ROUTING": self.LAYER_1_ROUTING,
            "LAYER_2_EXECUTION": self.LAYER_2_EXECUTION,
            "LAYER_3_WORKFLOW": self.LAYER_3_WORKFLOW,
            "LAYER_4_VERIFICATION": self.LAYER_4_VERIFICATION,
            "LAYER_5_REASONING": self.LAYER_5_REASONING,
            "LAYER_6_KNOWLEDGE": self.LAYER_6_KNOWLEDGE,
            "LAYER_7_AUTONOMY": self.LAYER_7_AUTONOMY,
            "LAYER_8_SPECIALIZED": self.LAYER_8_SPECIALIZED,
            "LAYER_9_SELF_IMPROVE": self.LAYER_9_SELF_IMPROVE,
        }
    
    def get_layer(self, layer_name: str) -> List[str]:
        """
        Get all module names in a specified layer.
        
        Args:
            layer_name: Name of the layer (e.g., 'LAYER_1_ROUTING')
            
        Returns:
            List of module names in the layer, empty list if layer not found
        """
        return self._layer_map.get(layer_name, [])
    
    def get_all_layers(self) -> Dict[str, List[str]]:
        """
        Get a copy of all layer-to-module mappings.
        
        Returns:
            Dictionary mapping layer names to their module name lists
        """
        return self._layer_map.copy()
    
    def get_module_purpose(self, module_name: str) -> str:
        """
        Get the human-readable purpose description for a module.
        
        Args:
            module_name: Name of the module (e.g., 'ilma_model_router')
            
        Returns:
            Purpose description string, or "Unknown purpose" if not found
        """
        return self.PURPOSES.get(module_name, "Unknown purpose")
    
    def list_wired_modules(self) -> List[str]:
        """
        Get a list of all wired module names.
        
        Returns:
            List of module name strings for all 28 wired modules
        """
        return list(self.ALL_WIRED)
    
    def get_pipeline_flow(self) -> str:
        """
        Get the canonical pipeline flow description.
        
        Returns:
            String describing the pipeline flow from BOOT to REPORT
        """
        return self.PIPELINE_FLOW
    
    def verify_module_exists(self, module_name: str) -> bool:
        """
        Check if a module file exists on disk.
        
        Handles both root modules (ilma_foo.py) and subdirectory modules (scripts/ilma_foo).

        Args:
            module_name: Name of the module (with or without .py extension)
            
        Returns:
            True if the module file exists, False otherwise
        """
        if module_name.endswith('.py'):
            path = ILMA_ROOT / module_name
        elif '/' in module_name:
            # e.g. "scripts/ilma_model_db_manager" → scripts/ilma_model_db_manager.py
            path = ILMA_ROOT / f"{module_name}.py"
        else:
            path = ILMA_ROOT / f"{module_name}.py"
        return path.exists()
    
    def get_missing_modules(self) -> List[str]:
        """
        Get list of wired modules that are missing from disk.
        
        Returns:
            List of module names that don't have corresponding .py files
        """
        missing = []
        for mod in self.ALL_WIRED:
            if not self.verify_module_exists(mod):
                missing.append(mod)
        return missing
    
    def verify_pipeline(self) -> Dict[str, Any]:
        """
        Verify that all wired modules exist on disk.
        
        Returns:
            Dictionary with verification results including:
            - total_wired: count of all wired modules
            - layers: list of layer names
            - pipeline_flow: canonical pipeline description
            - status: 'OK' or 'INCOMPLETE'
            - missing_modules: list of missing module names
        """
        missing = self.get_missing_modules()
        return {
            "total_wired": len(self.ALL_WIRED),
            "layers": list(self._layer_map.keys()),
            "pipeline_flow": self.PIPELINE_FLOW,
            "status": "OK" if not missing else "INCOMPLETE",
            "missing_modules": missing,
        }
    
    def lazy_import(self, module_name: str) -> Any:
        """
        Lazily import a module by name.
        
        Ensures ILMA_ROOT takes precedence over scripts/ by managing sys.path.
        This prevents scripts/ from shadowing root ILMA modules.
        
        Args:
            module_name: Name of the module to import
            
        Returns:
            The imported module object
        """
        # Ensure ILMA_ROOT is at the front
        ilma_root_str = str(ILMA_ROOT)
        if ilma_root_str in sys.path:
            sys.path.remove(ilma_root_str)
        sys.path.insert(0, ilma_root_str)
        
        # Convert subdirectory path to dot notation for import_module
        # e.g. "scripts/ilma_model_db_manager" → "scripts.ilma_model_db_manager"
        if '/' in module_name:
            import_name = module_name.replace('/', '.')
        else:
            import_name = module_name
        
        return import_module(import_name)
    
    def load_component(self, module_name: str) -> Dict[str, Any]:
        """
        Lazily load and return component information for a module.
        
        Loads the module via lazy_import, then collects metadata including
        exports, purpose, and file path. Results are cached.
        
        Args:
            module_name: Name of the module to load
            
        Returns:
            Dictionary containing module metadata:
            - module: module name
            - file: absolute file path
            - exists: True
            - purpose: purpose description
            - exports: list of public attribute names
            - loaded_at: ISO timestamp
        """
        if module_name in self._components:
            return self._components[module_name]

        mod = self.lazy_import(module_name)
        exports = [n for n in dir(mod) if not n.startswith('_')]

        # Resolve actual file path (handle subdirectory modules like "scripts/x")
        if '/' in module_name:
            # e.g. "scripts/ilma_model_db_manager" → scripts/ilma_model_db_manager.py
            file_path = ILMA_ROOT / f"{module_name}.py"
        else:
            file_path = ILMA_ROOT / f"{module_name}.py"

        info = {
            "module": module_name,
            "file": str(file_path),
            "exists": file_path.exists(),
            "purpose": self.PURPOSES.get(module_name, "Unknown"),
            "exports": exports,
            "loaded_at": datetime.now().isoformat(),
        }
        
        self._components[module_name] = info
        return info
    
    def run_pipeline_diagnostic(self) -> Dict[str, Any]:
        """
        Run a diagnostic on all wired modules.
        
        Checks each module for file existence and attempts to import it,
        collecting status information for each. Use this to verify the
        runtime wiring is healthy.
        
        Returns:
            Dictionary containing:
            - total: count of wired modules
            - modules: dict mapping module name to status info
            - summary: counts of ok/missing/import_error
        """
        results = {
            "total": len(self.ALL_WIRED),
            "modules": {},
            "summary": {"ok": 0, "missing": 0, "import_error": 0}
        }
        
        for mod_name in self.ALL_WIRED:
            exists = self.verify_module_exists(mod_name)
            if not exists:
                results["modules"][mod_name] = {"status": "MISSING", "exists": False}
                results["summary"]["missing"] += 1
                continue
            
            try:
                info = self.load_component(mod_name)
                results["modules"][mod_name] = {
                    "status": "OK",
                    "exists": True,
                    "exports_count": len(info["exports"]),
                    "purpose": info["purpose"][:60] + "..." if len(info["purpose"]) > 60 else info["purpose"],
                }
                results["summary"]["ok"] += 1
            except Exception as e:
                results["modules"][mod_name] = {
                    "status": "IMPORT_ERROR",
                    "error": str(e)[:100]
                }
                results["summary"]["import_error"] += 1
        
        return results


# ─── CANONICAL PIPELINE EXECUTION ────────────────────────────────────────────

def run_canonical_pipeline(message: str, prefer_free: bool = True) -> Dict[str, Any]:
    """
    Run the canonical ILMA pipeline (v1.2 - LAYER_9 SELF-IMPROVEMENT integrated).

    Pipeline: ANALYZE(4W1H + Hermes skill detect) → ROUTE(model_router)
            → RESOLVE(capability_registry) → EXECUTE(direct_api|browser|hermes_skill_execution)
            → EVALUATE(actor_critic) → VERIFY(judge) → GROUND(grounding_loop)
            → LEARN(self_improve_integrator) → REPORT
    """
    wiring = ILMARuntimeWiring()
    
    # Step 1: ANALYZE - 4W1H analysis + thinking tier detection
    workflow_mod = wiring.lazy_import("ilma_workflow_ecc")
    analysis = workflow_mod.analyze_4w1h(message)

    # Step 1.5: Thinking tier from 4W1H (auto-detected from task keywords)
    thinking_tier = analysis.get("thinking_tier", "fast")
    thinking_params = workflow_mod.get_thinking_params(thinking_tier)

    # Step 1.75: Hermes Skills Router - detect skills for task (v2.0 execution engine)
    router = None
    try:
        skills_mod = wiring.lazy_import("ilma_hermes_skills_router")
        router = skills_mod.get_skills_router()
        task_context = {
            "task_type": analysis.get("what", "general").lower(),
            "domain": analysis.get("what", "general").lower(),
            "complexity": analysis.get("how", "general").lower(),
        }
        skill_matches = router.route(message, context=task_context)
        skill_suggestions = router.suggest_skills_for_task(message, top_n=3)
        analysis["skill_matches"] = [
            {"name": m.skill_name, "category": m.category, "confidence": m.confidence, "source": m.source}
            for m in skill_matches[:5]
        ]
        analysis["skill_suggestions"] = skill_suggestions
        top_skill = skill_matches[0] if skill_matches else None
    except Exception:
        skill_matches = []
        skill_suggestions = []
        top_skill = None
    
    # Step 2: DETECT TASK TYPE - convert raw message to task type
    router_mod = wiring.lazy_import("ilma_model_router")
    task_type = router_mod.detect_task_type(message)
    
    # Step 3: ROUTE - Model routing (pass task_type, NOT raw message)
    route_result = router_mod.route_task(task_type, max_fallbacks=5)
    
    # Step 4: RESOLVE - Capability resolution
    cap_mod = wiring.lazy_import("ilma_capability_registry")
    task_type = route_result.get('task_type', 'general')
    capability = cap_mod.get_capability(task_type) if task_type else None
    
    # Step 5: EXECUTE - If high-confidence Hermes skill detected (>= 0.85), mark for execution
    skill_execution_info = None
    if top_skill and top_skill.confidence >= 0.85 and top_skill.source == "hermes" and router:
        skill_path = router.get_skill_path(top_skill.skill_name)
        if skill_path and "optional-skills" in skill_path:
            skill_execution_info = {
                "name": top_skill.skill_name,
                "confidence": top_skill.confidence,
                "category": top_skill.category,
                "path": skill_path,
                "method": "hermes_skill_execution",
            }
    
    return {
        "pipeline": "Canon8",
        "version": "3.0",
        "hermes_skills_integrated": True,
        "thinking_tier": {
            "tier": thinking_tier,
            "params": thinking_params,
            "source": "analyze_4w1h.auto_detect",
        },
        "steps": [
            {"step": "ANALYZE", "handler": "ilma_workflow_ecc.analyze_4w1h", "result": analysis},
            {"step": "THINKING_TIER", "handler": "ilma_workflow_ecc.detect_thinking_tier + get_thinking_params", "result": {"tier": thinking_tier, "params": thinking_params}},
            {"step": "SKILL_DETECT", "handler": "ilma_hermes_skills_router.route + suggest_skills_for_task", "result": {"matches": len(skill_matches), "top_skill": top_skill.skill_name if top_skill else None}},
            {"step": "ROUTE", "handler": "ilma_model_router.route_task", "result": route_result},
            {"step": "RESOLVE", "handler": "ilma_capability_registry.get_capability", "result": capability},
            {"step": "EXECUTE", "handler": "hermes_skill_execution", "result": skill_execution_info},
        ],
        "task_type": task_type,
        "route_result": route_result,
        "top_skill": top_skill.skill_name if top_skill else None,
        "skill_execution": skill_execution_info,
        "skills_detected": len(skill_matches),
        "suggestions": skill_suggestions[:3],
        "timestamp": datetime.now().isoformat(),
    }


def get_wiring_report() -> Dict[str, Any]:
    """
    Get a comprehensive report of the ILMA runtime wiring status.
    
    Runs both verify_pipeline() and run_pipeline_diagnostic() to provide
    a complete picture of the wiring health including missing modules,
    import errors, and archived modules.
    
    Returns:
        Dictionary containing:
        - version: wiring version
        - wired_at: ISO timestamp when wiring was created
        - total_wired: count of wired modules
        - layers: layer name to count mapping
        - pipeline_flow: canonical pipeline description
        - verification: pipeline verification results
        - diagnostic: detailed diagnostic results
        - archived: list of archived experimental modules
    """
    wiring = ILMARuntimeWiring()
    verification = wiring.verify_pipeline()
    diagnostic = wiring.run_pipeline_diagnostic()
    
    return {
        "version": wiring.version,
        "wired_at": wiring.wired_at,
        "total_wired": len(wiring.ALL_WIRED),
        "layers": {k: len(v) for k, v in wiring._layer_map.items()},
        "pipeline_flow": wiring.PIPELINE_FLOW,
        "verification": verification,
        "diagnostic": diagnostic,
        "archived": [
            "ilma_reflexion_loop.py - experimental",
            "ilma_mae_triplet.py - experimental",
            "ilma_rcr_pattern.py - experimental",
            "ilma_complete_system.py - redundant",
            "ilma_autogen_executor.py - demo only",
            "ilma_metrics_monitoring.py - HIGH_RISK_DEFERRED",
            "fix_benchmark_normalization.py - one-time fix",
            "_phase13e_classifier.py - one-time classifier",
        ]
    }


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import json
    
    # Configure basic logging for CLI output
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    wiring = ILMARuntimeWiring()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--verify':
            report = get_wiring_report()
            print(json.dumps(report, indent=2, default=str))
        elif sys.argv[1] == '--pipeline':
            msg = sys.argv[2] if len(sys.argv) > 2 else "fix this bug"
            result = run_canonical_pipeline(msg)
            print(json.dumps(result, indent=2, default=str))
        elif sys.argv[1] == '--model-db-sync':
            # Run model DB sync (SINGLE SOURCE OF TRUTH)
            sys.path.insert(0, str(ILMA_ROOT / "scripts"))
            from ilma_model_db_manager import ModelDatabaseManager
            mgr = ModelDatabaseManager(dry_run="--dry-run" in sys.argv,
                                       git_push="--git-push" in sys.argv)
            mgr.full_sync()
        elif sys.argv[1] == '--diagnostic':
            diag = wiring.run_pipeline_diagnostic()
            print(json.dumps(diag, indent=2, default=str))
        elif sys.argv[1] == '--list':
            for mod in wiring.list_wired_modules():
                logger.info("  %s", mod)
        else:
            logger.info(f"ILMA Runtime Wiring v{wiring.version}")
            logger.info(f"Wired modules: {len(wiring.ALL_WIRED)}")
            logger.info(f"Pipeline: {wiring.PIPELINE_FLOW}")
            v = wiring.verify_pipeline()
            logger.info(f"Status: {v['status']}")
            if v['missing_modules']:
                logger.warning(f"Missing: {v['missing_modules']}")
    else:
        logger.info(f"ILMA Runtime Wiring v{wiring.version}")
        logger.info(f"Wired modules: {len(wiring.ALL_WIRED)}")
        logger.info(f"Layers: {', '.join(wiring._layer_map.keys())}")
        logger.info(f"Pipeline: {wiring.PIPELINE_FLOW}")
        v = wiring.verify_pipeline()
        logger.info(f"Status: {v['status']}")
        if v['missing_modules']:
            logger.warning(f"Missing: {v['missing_modules']}")