#!/usr/bin/env python3
"""
ILMA MASTER ORCHESTRATOR v2.1 (Phase 4B)
========================================
Layer 2 Central Command. Wires Analysis -> Routing -> Execution.

Phase 4B (2026-06-03):
  - execute() now uses SubAgentRouter.route_and_execute() instead of
    ProviderKernel.call() directly. This closes CS-01 (the 189s timeout
    bypass where mark_failure was never called).
  - ProviderKernel is kept ONLY as an emergency fallback if SubAgentRouter
    itself fails to import or initialize.
  - allow_paid=False is enforced at the orchestrator level (FREE-ONLY policy).
"""

import json
import logging
import time
import os
import sys

from typing import Any, Dict, Optional
from pathlib import Path

# Import Phase 18 Methodology modules
try:
    from ilma_capability_contracts import classify_intent_to_domain, get_contract
    from ilma_domain_evaluators import run_domain_evaluators
except ImportError:
    pass


# Import our optimized modules
from ilma_model_router import route_task_simple as route_task

# FIX 2026-06-21: SubAgentRouter & ProviderKernel moved to lazy @property in __init__
# — eliminates 0.27s eager import cost on module load.

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ILMA.Orchestrator")

class ILMAOrchestrator:
    def __init__(self):
        # FIX 2026-06-21: lazy init for heavy imports (SubAgentRouter 0.17s, ProviderKernel 0.10s).
        # Halves orchestrator import time from ~0.30s to near-zero for import-only paths.
        self._subagent = None
        self._kernel = None
        self.system_name = "Hermes Agent Profile ILMA"
        # Phase 69-Autonomy: execution log tracks every task routed through
        # the orchestrator. Backs ilma.py --status metrics (routes count).
        self.execution_log: list = []

    @property
    def subagent(self):
        if self._subagent is None:
            from ilma_subagent_router import SubAgentRouter
            self._subagent = SubAgentRouter()
        return self._subagent

    @property
    def kernel(self):
        if self._kernel is None:
            from ilma_provider_kernel import ProviderKernel
            self._kernel = ProviderKernel()
        return self._kernel

    def route_intent(self, task: str) -> Dict[str, Any]:
        """
        Phase 6: Admin Intent Expansion Layer.
        Expands a short admin command into a full execution profile.
        """
        logger.info(f"Expanding intent for: {task}")
        
        # 1. Quick heuristic classification
        task_lower = task.lower()
        intent = "general_execution"
        handler = "direct"
        risk_level = "low"
        
        if any(w in task_lower for w in ["rapikan", "audit", "cek", "fix", "optimalkan", "hardening", "validasi"]):
            intent = "system_maintenance"
            handler = "autonomous_loop"
            risk_level = "medium"
            if "semua" in task_lower:
                risk_level = "high"
        elif any(w in task_lower for w in ["buat", "bikin", "code", "script"]):
            intent = "creation"
            handler = "kanban_workflow"
        elif any(w in task_lower for w in ["hapus", "delete", "remove", "reset"]):
            intent = "destructive"
            handler = "guarded_execution"
            risk_level = "high"
            
        # 2. Phase 18 Domain Classification & Contract
        domain = "GENERAL"
        contract_data = {}
        try:
            domain = classify_intent_to_domain(task)
            contract = get_contract(domain)
            contract_data = {
                "capability_domain": contract.domain,
                "methodology_id": contract.methodology_id,
                "required_validators": contract.required_validators,
                "quality_checklist": contract.quality_checklist
            }
        except Exception as e:
            logger.warning(f"Failed to load capability contract: {e}")

        # 3. Build the Task Profile (Intent Expansion + Contract)
        task_profile = {
            "admin_intent": intent,
            "scope": "system" if intent == "system_maintenance" else "local",
            "risk_level": risk_level,
            "handler": handler,
            "params": {"force_model": None, "expanded_context": True},
            "validation_plan": "critic_review" if risk_level != "low" else "basic"
        }
        task_profile.update(contract_data)
        
        logger.info(f"Intent Profile: {json.dumps(task_profile)}")
        return task_profile

    def execute_with_intent(self, prompt: str, handler: str, params: Any) -> Dict[str, Any]:
        """
        Safe wrapper for execute to match ilma.py's expected signature:
        orch.execute_with_intent(task, result["handler"], result["params"])
        """
        force_model = params.get("force_model") if isinstance(params, dict) else None
        
        if handler == "guarded_execution":
            logger.warning("High risk action detected. Applying safe mode execution.")
            prompt = f"SYSTEM GUARD: This is a high-risk destructive command. Please evaluate carefully.\n\n{prompt}"
        
        if handler == "autonomous_loop":
            try:
                from ilma_autonomous_loop_engine import AutonomousLoopEngine
                engine = AutonomousLoopEngine()
                logger.info("Executing via AutonomousLoopEngine")
                return engine.run_cycle(prompt)
            except Exception as e:
                logger.error(f"AutonomousLoopEngine failed: {e}")
                return {"status": "error", "error": str(e)}
                
        if handler == "kanban_workflow":
            try:
                from ilma_workflow_ecc import run_workflow
                logger.info("Executing via WorkflowECC")
                return run_workflow(prompt)
            except Exception as e:
                logger.error(f"WorkflowECC failed: {e}")
                return {"status": "error", "error": str(e)}
        
        # PHASE 19 DEEP ROUTING TO DOMAIN MODULES
        domain_match = None
        try:
            from ilma_capability_contracts import classify_intent_to_domain
            domain_match = classify_intent_to_domain(prompt)
        except Exception:
            pass
            
        if domain_match == "RESEARCH":
            try:
                logger.info("PHASE 19 WIRING: Routing to ilma_research_engine")
                from ilma_research_engine import research
                res_content = research(prompt, depth="advanced")
                # Wrap response in standard struct
                exec_result = {"status": "success", "response": res_content}
            except Exception as e:
                logger.error(f"Research engine failed: {e}")
                exec_result = self.execute(prompt, task_type=handler, force_model=force_model)

        elif domain_match == "WRITING":
            try:
                logger.info("PHASE 19 WIRING: Routing to ilma_scriptorium")
                from ilma_scriptorium import write
                # we pass prompt as topic.
                res_content = write(prompt)
                exec_result = {"status": "success", "response": res_content.get("final_doc", str(res_content))}
            except Exception as e:
                logger.error(f"Scriptorium failed: {e}")
                exec_result = self.execute(prompt, task_type=handler, force_model=force_model)
        else:
            # fallback to the original execute method for "direct" or "guarded_execution"
            exec_result = self.execute(prompt, task_type=handler, force_model=force_model)
        
        # Phase 18: Post-Execution Domain Validator
        try:
            domain = classify_intent_to_domain(prompt)
            contract = get_contract(domain)
            if contract.domain != "GENERAL" and exec_result.get("status") == "success":
                val_res = run_domain_evaluators(exec_result.get("response", ""), contract)
                exec_result["domain_validation"] = val_res
                if not val_res.get("valid", True):
                    logger.warning(f"Domain validation failed for {domain}: {val_res}")
                    # Q2 (audit 2026-06-20): optionally BLOCK on failure for high-criticality
                    # domains. Flag domain_validation_blocking is OFF by default (canary); when
                    # ON, a failing SECURITY/CODING output is surfaced as needs_revision instead
                    # of being silently returned. Response is preserved for inspection.
                    try:
                        from ilma_feature_flags import get_flags
                        _blocking = get_flags().is_enabled("domain_validation_blocking")
                    except Exception:
                        _blocking = False
                    if _blocking and str(contract.domain).upper() in ("SECURITY", "CODING"):
                        exec_result["status"] = "needs_revision"
                        exec_result["quality_gate"] = "FAILED"
                        exec_result["quality_gate_missing"] = val_res.get("details", val_res)
                        logger.error(f"[domain-gate] BLOCKED {contract.domain}: {val_res.get('details', val_res)}")
        except Exception as e:
            logger.debug(f"Domain validation skipped: {e}")
            
        return exec_result

    def execute(self, prompt: str, task_type: Optional[str] = None, force_model: Optional[str] = None) -> Dict[str, Any]:
        """
        The canonical execution pipeline (Phase 4B).

        Phase 4B changes:
        - Execution goes through SubAgentRouter.route_and_execute() — has
          mark_success/mark_failure, circuit breaker, fallback chain.
        - allow_paid=False enforces FREE-ONLY policy at orchestrator level.
        - ProviderKernel is only used as emergency fallback if SubAgentRouter
          itself fails.
        - Phase 1.1 Block 4: input validation (ilma_input_validator) integrated.
        """
        # Phase 1.1 Block 4: input validation (feature-flag controlled)
        if os.environ.get("ILMA_INPUT_VALIDATION", "true").lower() in ("true", "1", "yes"):
            try:
                from ilma_input_validator import validate_input
                validate_input(prompt)
            except Exception as ve:
                logger.warning(f"[ORCH-EXEC] Input validation failed: {ve}")
                return {
                    "success": False,
                    "error": f"Input validation failed: {ve}",
                    "blocked": True,
                }
        # P4 observability (inline, fully guarded — must never break execution):
        # per-request id for log correlation + a tracing span + Prometheus metrics.
        import uuid as _uuid
        request_id = _uuid.uuid4().hex[:12]
        _span = None
        try:
            from ilma_tracing import get_tracer
            _span = get_tracer().start_span("orchestrator.execute")
        except Exception:
            _span = None
        logger.info(f"[ORCH-EXEC] req={request_id} Processing request: {prompt[:80]}...")
        start_ts = time.time()

        try:
            # 1. Routing hint (informational; SubAgentRouter will re-route)
            try:
                model_id_hint, provider_hint, reason_hint = route_task(prompt, task_type, force_model)
            except Exception as e:
                logger.debug(f"[ORCH-EXEC] route_task hint failed: {e}")
                model_id_hint, provider_hint, reason_hint = ("", "", "")

            # 2. Build task with hint (SubAgentRouter will pick best model)
            task = prompt
            if force_model:
                task = f"[preferred={force_model}] {prompt}"

            # 3. Execution through SubAgentRouter (HEALTH-TRACKED)
            result = self.subagent.route_and_execute(
                message=task,
                task_type_or_desc=task_type or prompt[:100],
                thinking="Auto",
                allow_paid=False,  # FREE-ONLY policy
                stateless=True,
            )

            # 4. Normalize result
            decision = result.get("decision", {})
            if result.get("success") and result.get("content"):
                response = result["content"]
                status = "success"
            else:
                response = ""
                status = "error"

            elapsed_ms = (time.time() - start_ts) * 1000

            # Phase 69-Autonomy: log this execution for the --status metric
            self.execution_log.append({
                "ts": start_ts,
                "prompt_preview": prompt[:80],
                "task_type": task_type,
                "model": result.get("model", model_id_hint),
                "status": status,
                "latency_ms": result.get("latency_ms", elapsed_ms),
                "elapsed_s": round(elapsed_ms / 1000, 3),
            })
            # Cap log at 200 entries — keep memory bounded
            if len(self.execution_log) > 200:
                self.execution_log = self.execution_log[-200:]

            # P4: emit metrics + close span (guarded — never breaks the return)
            _model = result.get("model", model_id_hint) or "unknown"
            _prov = decision.get("provider", provider_hint) or "unknown"
            try:
                from ilma_metrics import record_request, record_error
                record_request(_model, _prov, status)
                if status != "success":
                    record_error(result.get("error_type") or "exec_error", _prov)
            except Exception:
                pass
            try:
                if _span is not None:
                    _span.end()
            except Exception:
                pass

            return {
                "status": status,
                "request_id": request_id,
                "model": result.get("model", model_id_hint),
                "provider": decision.get("provider", provider_hint),
                "reason": decision.get("reasoning", reason_hint),
                "response": response,
                "error": result.get("error", ""),
                "error_type": result.get("error_type", ""),
                "latency_ms": result.get("latency_ms", elapsed_ms),
                "used_fallback": result.get("used_fallback", False),
                "original_model": result.get("original_model", ""),
            }

        except Exception as e:
            # Emergency fallback to ProviderKernel (Phase 4B safety net)
            logger.error(f"[ORCH-EXEC] SubAgentRouter failed: {e}. Falling back to ProviderKernel.")
            try:
                model_id, provider, reason = route_task(prompt, task_type, force_model)
                messages = [{"role": "user", "content": prompt}]
                response = self.kernel.call(provider, model_id, messages)
                return {
                    "status": "success" if "Error:" not in response else "error",
                    "model": model_id,
                    "provider": provider,
                    "reason": reason,
                    "response": response,
                    "error": f"FALLBACK_TO_KERNEL: {str(e)[:200]}",
                    "used_fallback": True,
                }
            except Exception as e2:
                return {
                    "status": "error",
                    "response": "",
                    "error": f"ORCHESTRATOR_FAILURE: SubAgentRouter={e}, Kernel={e2}",
                }

if __name__ == "__main__":
    import sys
    orchestrator = ILMAOrchestrator()
    if len(sys.argv) > 1:
        res = orchestrator.execute(sys.argv[1])
        print(json.dumps(res, indent=2))
    else:
        print("Usage: python3 ilma_orchestrator.py 'Your prompt'")
