#!/usr/bin/env python3
"""
ILMA Main Entry Point v2.0
===========================
The SINGLE ENTRY POINT for all ILMA operations.

This module provides ONE IMPORT for everything:

    from ilma_main import ILMA
    ilma = ILMA()
    result = ilma.execute("Build me a secure REST API")

Architecture:
    
    ┌────────────────────────────────────────────────────────────────┐
    │                         ILMA MAIN                              │
    │                   (Single Entry Point)                          │
    ├────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │   from ilma_main import ILMA                                    │
    │   ilma = ILMA()                                                │
    │       │                                                         │
    │       ▼                                                         │
    │   ┌──────────────────────────────────────────────────────┐     │
    │   │              MASTER ORCHESTRATOR                       │     │
    │   │                                                        │     │
    │   │  ┌─────────────────┐  ┌─────────────────┐           │     │
    │   │  │ System Integrator│──│ Vector Connector│           │     │
    │   │  │                 │  │                 │           │     │
    │   │  │ • Registry      │  │ • Alpha         │           │     │
    │   │  │ • Event Bus     │  │ • Bravo        │           │     │
    │   │  │ • Unified API   │  │ • Charlie      │           │     │
    │   │  │ • Telemetry     │  │ • Delta        │           │     │
    │   │  └─────────────────┘  └─────────────────┘           │     │
    │   │                                                        │     │
    │   │  ┌─────────────────┐  ┌─────────────────┐           │     │
    │   │  │ Command Parser  │──│ Mission Queue   │           │     │
    │   │  │                 │  │                 │           │     │
    │   │  │ • Intent Detec │  │ • Priority      │           │     │
    │   │  │ • Entity Extra │  │ • Scheduling    │           │     │
    │   │  └─────────────────┘  └─────────────────┘           │     │
    │   │                                                        │     │
    │   └──────────────────────────────────────────────────────┘     │
    │                              │                                  │
    └────────────────────────────────────────────────────────────────┘

Usage Examples:

    # Basic usage
    from ilma_main import ILMA
    ilma = ILMA()
    
    # Natural language command
    result = ilma.execute("Build me a secure REST API with authentication")
    
    # Structured mission
    result = ilma.execute_mission({
        "type": "development",
        "target": "api",
        "params": {"auth": "jwt"}
    })
    
    # Get system status
    status = ilma.get_status()
    
    # Execute specific vector
    result = ilma.vector("alpha", "analyze_codebase", {"path": "."})

What ILMA Controls:

    ┌────────────────────────────────────────────────────────────────┐
    │                     ILMA CONTROLLED SYSTEMS                    │
    ├────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │  SCRIPTS (339 files)                                            │
    │  ├── cloud/         (Cloud deployments)                        │
    │  ├── database/      (DB operations)                            │
    │  ├── devops/        (CI/CD pipelines)                         │
    │  ├── github/        (GitHub automation)                       │
    │  ├── monitoring/    (System monitoring)                       │
    │  ├── security/      (Security modules)                         │
    │  ├── webdev/        (Web development)                         │
    │  └── ilma_vector_*.py (Operational Vectors)                    │
    │                                                                 │
    │  SKILLS (547 files)                                           │
    │  ├── ilma-*         (250+ ILMA-specific skills)               │
    │  ├── devops-*       (DevOps patterns)                         │
    │  ├── data-*         (Data science)                             │
    │  ├── creative-*     (Creative work)                           │
    │  └── ...           (Many more categories)                      │
    │                                                                 │
    │  FABRIC (Enterprise modules)                                   │
    │  ├── event_bus/     (Event-driven architecture)                │
    │  ├── observability/ (Metrics, tracing, dashboards)            │
    │  ├── resilience/    (Auto-recovery, fault tolerance)           │
    │  ├── queue/         (Priority queues, retry logic)             │
    │  └── workers/       (Local, remote, sandbox workers)          │
    │                                                                 │
    │  MEMORY                                                        │
    │  ├── daily notes   (Session memories)                         │
    │  ├── long-term     (Curated memories)                         │
    │  ├── crypto_vault   (Encrypted storage)                        │
    │  └── pager/        (Context paging)                           │
    │                                                                 │
    └────────────────────────────────────────────────────────────────┘
"""
import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# ILMA MAIN CLASS
# =============================================================================

class ILMA:
    """
    The ONE AND ONLY main class for ILMA.
    
    Use this as the entry point for all ILMA operations.
    
    Example:
        from ilma_main import ILMA
        ilma = ILMA()
        result = ilma.execute("Build me a REST API")
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._orchestrator = None
        self._components_loaded = False
        
        logger.info("=" * 60)
        logger.info("ILMA v2.0 - INITIALIZING")
        logger.info("=" * 60)
    
    def _ensure_components(self):
        """Ensure all components are loaded."""
        if self._components_loaded:
            return
        
        logger.info("Loading ILMA components...")
        
        # Import and initialize orchestrator
        try:
            from ilma_master_orchestrator import MasterOrchestrator
            self._orchestrator = MasterOrchestrator()
            logger.info("✓ Master Orchestrator loaded")
        except ImportError as e:
            logger.warning(f"Master Orchestrator not available: {e}")
            self._orchestrator = None
        
        self._components_loaded = True
        logger.info("ILMA components loaded")
    
    # =========================================================================
    # CORE EXECUTION
    # =========================================================================
    
    def execute(self, command: str, wait: bool = True) -> Dict[str, Any]:
        """
        Execute a natural language command.
        
        Args:
            command: Natural language command
            wait: Wait for completion
            
        Returns:
            Result dictionary
        """
        self._ensure_components()
        
        if self._orchestrator:
            return self._orchestrator.execute(command, wait)
        else:
            return {
                "success": False,
                "error": "Orchestrator not available"
            }
    
    def execute_mission(self, mission_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a structured mission.
        
        Args:
            mission_spec: Mission specification
            
        Returns:
            Result dictionary
        """
        self._ensure_components()
        
        if self._orchestrator:
            return self._orchestrator.execute_mission(mission_spec)
        else:
            return {
                "success": False,
                "error": "Orchestrator not available"
            }
    
    # =========================================================================
    # VECTOR OPERATIONS
    # =========================================================================
    
    def vector(
        self,
        vector_name: str,
        mission: str,
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Execute a specific vector operation.
        
        Args:
            vector_name: alpha, bravo, charlie, delta
            mission: Mission name
            params: Mission parameters
            
        Returns:
            Result dictionary
        """
        self._ensure_components()
        
        if self._orchestrator and self._orchestrator.vector_connector:
            return self._orchestrator.vector_connector.execute_vector(
                vector_name, mission, params or {}
            )
        
        return {
            "success": False,
            "error": "Vector Connector not available"
        }
    
    # =========================================================================
    # SYSTEM STATUS
    # =========================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """Get system status."""
        self._ensure_components()
        
        if self._orchestrator:
            return self._orchestrator.get_system_status()
        
        return {
            "status": "partial",
            "orchestrator": "unavailable"
        }
    
    def get_components(self) -> Dict[str, int]:
        """Get component counts."""
        base_path = Path.home() / ".hermes" / "profiles" / "ilma"
        
        counts = {
            "scripts": 0,
            "skills": 0,
            "fabric_modules": 0,
            "vectors": 0
        }
        
        # Count scripts
        scripts_path = base_path / "scripts"
        if scripts_path.exists():
            counts["scripts"] = len(list(scripts_path.rglob("*.py")))
        
        # Count skills
        skills_path = base_path / "skills"
        if skills_path.exists():
            counts["skills"] = len(list(skills_path.rglob("SKILL.md")))
        
        # Count fabric
        fabric_path = base_path / "fabric"
        if fabric_path.exists():
            counts["fabric_modules"] = len(list(fabric_path.rglob("*.py")))
        
        # Count vectors
        counts["vectors"] = len(list(scripts_path.glob("ilma_vector_*.py")))
        
        return counts
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def analyze_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Analyze code."""
        return self.execute(f"Analyze this {language} code: {code[:100]}...")
    
    def generate_content(
        self,
        topic: str,
        content_type: str = "article"
    ) -> Dict[str, Any]:
        """Generate content."""
        return self.execute(f"Write a {content_type} about {topic}")
    
    def deploy(self, app_path: str, target: str = "production") -> Dict[str, Any]:
        """Deploy application."""
        return self.execute(f"Deploy {app_path} to {target}")
    
    def monitor(self, target: str = "system") -> Dict[str, Any]:
        """Monitor target."""
        return self.execute(f"Monitor {target}")
    
    def secure(self, target: str = "system") -> Dict[str, Any]:
        """Secure target."""
        return self.execute(f"Secure {target}")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_ilma() -> ILMA:
    """
    Get ILMA instance.
    
    Example:
        from ilma_main import get_ilma
        ilma = get_ilma()
    """
    return ILMA()


def execute(command: str) -> Dict[str, Any]:
    """
    Execute command directly.
    
    Example:
        from ilma_main import execute
        result = execute("Build me an API")
    """
    return ILMA().execute(command)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    ilma = ILMA()
    
    print("=" * 70)
    print("ILMA v2.0 - The Unified Intelligence System")
    print("=" * 70)
    
    # Print component counts
    counts = ilma.get_components()
    
    print("\n📊 SYSTEM COMPONENTS:")
    print(f"  Scripts: {counts['scripts']}")
    print(f"  Skills: {counts['skills']}")
    print(f"  Fabric Modules: {counts['fabric_modules']}")
    print(f"  Vectors: {counts['vectors']}")
    print(f"  TOTAL: {sum(counts.values())}")
    
    print("\n" + "=" * 70)
    print("SYSTEM READY")
    print("=" * 70)
    
    # If command provided, execute it
    if len(sys.argv) > 1:
        command = " ".join(sys.argv[1:])
        print(f"\n📨 Executing: {command}")
        result = ilma.execute(command)
        print(f"\n📬 Result:")
        print(json.dumps(result, indent=2))
