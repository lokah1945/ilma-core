#!/usr/bin/env python3
"""
ILMA Capability Contracts & Methodology
Defines the required workflow, tools, and validators for specific domains.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import json

@dataclass
class DomainContract:
    domain: str
    description: str
    methodology_id: str
    required_validators: List[str]
    required_tools: List[str]
    risk_level: str
    fallback_behavior: str
    quality_checklist: List[str]

# Global Registry
METHODOLOGY_REGISTRY = {
    "RESEARCH": DomainContract(
        domain="RESEARCH",
        description="Information gathering and synthesis",
        methodology_id="meth_research_01",
        required_validators=["ResearchValidator"],
        required_tools=["tavily", "browser"],
        risk_level="low",
        fallback_behavior="offline_synthesis_with_placeholders",
        quality_checklist=["evidence_table", "contradiction_check", "freshness_check"]
    ),
    "WRITING": DomainContract(
        domain="WRITING",
        description="Longform content generation",
        methodology_id="meth_writing_01",
        required_validators=["WritingValidator"],
        required_tools=["scriptorium"],
        risk_level="low",
        fallback_behavior="standard_llm_generation",
        quality_checklist=["purpose_audience", "structure", "fact_opinion_separation"]
    ),
    "CODING": DomainContract(
        domain="CODING",
        description="Software development and debugging",
        methodology_id="meth_coding_01",
        required_validators=["CodingValidator", "QualityGate"],
        required_tools=["python_repl", "linter"],
        risk_level="medium",
        fallback_behavior="dry_run_only",
        quality_checklist=["diff_generation", "rollback_plan", "interface_preservation"]
    ),
    "UIUX": DomainContract(
        domain="UIUX",
        description="User interface and experience design",
        methodology_id="meth_uiux_01",
        required_validators=["UIUXValidator"],
        required_tools=[],
        risk_level="low",
        fallback_behavior="standard_llm_generation",
        quality_checklist=["accessibility", "responsive_states", "user_flow"]
    ),
    "SECURITY": DomainContract(
        domain="SECURITY",
        description="Defensive security auditing",
        methodology_id="meth_sec_01",
        required_validators=["SecurityValidator"],
        required_tools=["nmap", "pentest_toolkit"],
        risk_level="high",
        fallback_behavior="refusal",
        quality_checklist=["authorization_scope", "remediation_plan", "no_secret_leakage"]
    ),
    "DATA": DomainContract(
        domain="DATA",
        description="Data and statistical analysis",
        methodology_id="meth_data_01",
        required_validators=["DataAnalysisValidator"],
        required_tools=["python_repl"],
        risk_level="medium",
        fallback_behavior="schema_only_analysis",
        quality_checklist=["outlier_check", "calculation_verification", "insight_separation"]
    ),
    "SYSTEM_DESIGN": DomainContract(
        domain="SYSTEM_DESIGN",
        description="Architecture and infrastructure design",
        methodology_id="meth_sys_01",
        required_validators=["ProductBusinessValidator"],
        required_tools=[],
        risk_level="low",
        fallback_behavior="standard_llm_generation",
        quality_checklist=["spof_identification", "observability", "data_flow"]
    ),
    "GENERAL": DomainContract(
        domain="GENERAL",
        description="Standard task execution",
        methodology_id="meth_gen_01",
        required_validators=[],
        required_tools=[],
        risk_level="low",
        fallback_behavior="direct_execution",
        quality_checklist=[]
    )
}

def classify_intent_to_domain(intent_str: str) -> str:
    """Heuristic domain classifier."""
    i = intent_str.lower()
    
    # Precedence: Security-specific terms win over generic maintenance terms
    if any(w in i for w in [
        "audit security", "audit konfigurasi lokal", "cek config security",
        "cek permission", "scan secret", "threat model", "hardening auth",
        "review dependency risk", "cek exposure", "pentest", "vulnerability"
    ]):
        return "SECURITY"
        
    if any(w in i for w in ["riset", "research", "cari info", "cari data"]):
        return "RESEARCH"
    if any(w in i for w in ["tulis", "artikel", "laporan", "proposal", "sop", "buku"]):
        return "WRITING"
    if any(w in i for w in ["kode", "code", "bug", "debug", "script", "refactor", "patch"]):
        return "CODING"
    if any(w in i for w in ["ui", "ux", "dashboard", "tampilan", "landing page", "responsive"]):
        return "UIUX"
    if any(w in i for w in ["data", "csv", "kpi", "analisa data", "dataset", "analysis"]):
        return "DATA"
    if any(w in i for w in ["arsitektur", "system design", "scaling", "infrastruktur", "architecture"]):
        return "SYSTEM_DESIGN"
    
    return "GENERAL"

def get_contract(domain: str) -> DomainContract:
    return METHODOLOGY_REGISTRY.get(domain, METHODOLOGY_REGISTRY["GENERAL"])
