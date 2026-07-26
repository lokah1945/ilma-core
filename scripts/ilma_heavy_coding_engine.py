#!/usr/bin/env python3
"""
ILMA Heavy Coding Engine
========================
Large-scale codebase engineering with 1000+ file generation capabilities.

Classes: MegaFileGenerator, DependencyResolver, ProjectScaleMetrics

Usage:
    python3 ilma_heavy_coding_engine.py --generate-project --name MyProject --scale large
    python3 ilma_heavy_coding_engine.py --resolve-deps --project /path/to/project
    python3 ilma_heavy_coding_engine.py --metrics --project /path/to/project

Author: ILMA v5.0
Version: 1.0.0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("HeavyCodingEngine")


# =============================================================================
# ENUMS AND DATA STRUCTURES
# =============================================================================

class ProjectScale(Enum):
    """Project scale levels."""
    SMALL = "small"           # < 50 files
    MEDIUM = "medium"         # 50-200 files
    LARGE = "large"          # 200-500 files
    ENTERPRISE = "enterprise"  # 500-1000 files
    MEGA = "mega"            # 1000+ files


class ProjectType(Enum):
    """Project type templates."""
    WEB_API = "web_api"
    CLI_TOOL = "cli_tool"
    DATA_PIPELINE = "data_pipeline"
    MICROSERVICES = "microservices"
    MONOLITH = "monolith"
    FULLSTACK = "fullstack"


@dataclass
class FileSpec:
    """File specification for code generation."""
    path: str
    module: str
    file_type: str
    lines: int
    purpose: str
    dependencies: List[str] = field(default_factory=list)
    template: str = "standard"
    content_hash: Optional[str] = None


@dataclass
class ModuleSpec:
    """Module/package specification."""
    name: str
    path: str
    files: List[str]
    submodules: List[str] = field(default_factory=list)
    public_api: List[str] = field(default_factory=list)


@dataclass
class DependencyInfo:
    """Dependency information."""
    module: str
    imports: List[str]
    used_by: List[str] = field(default_factory=list)
    import_count: int = 0


@dataclass
class ProjectMetrics:
    """Project-scale metrics."""
    total_files: int
    total_lines: int
    total_modules: int
    total_dependencies: int
    cyclomatic_complexity_avg: float
    coupling_score: float
    cohesion_score: float
    code_to_test_ratio: float
    documentation_coverage: float


# =============================================================================
# MEGA FILE GENERATOR CLASS
# =============================================================================

class MegaFileGenerator:
    """
    Production-scale code generation engine.
    
    Generates complete projects with 1000+ files, managing dependencies,
    module structure, and code quality standards.
    """
    
    SCALE_FILE_COUNTS = {
        ProjectScale.SMALL: (10, 50),
        ProjectScale.MEDIUM: (50, 200),
        ProjectScale.LARGE: (200, 500),
        ProjectScale.ENTERPRISE: (500, 1000),
        ProjectScale.MEGA: (1000, 5000)
    }
    
    def __init__(self, output_dir: str = "./generated_project"):
        self.output_dir = Path(output_dir)
        self.generated_files: List[str] = []
        self.manifest: Dict[str, Any] = {}
        logger.info(f"MegaFileGenerator initialized for: {output_dir}")
    
    def generate_project(
        self,
        name: str,
        project_type: ProjectType,
        scale: ProjectScale,
        include_tests: bool = True,
        include_docs: bool = True
    ) -> Dict[str, Any]:
        """Generate a complete project structure."""
        logger.info(f"Generating project: {name} (scale: {scale.value})")
        
        start_time = time.time()
        
        # Create project directory structure
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Calculate file count based on scale
        min_files, max_files = self.SCALE_FILE_COUNTS[scale]
        target_files = (min_files + max_files) // 2
        
        # Generate file specifications
        file_specs = self._generate_file_specs(name, project_type, target_files)
        
        # Generate actual files
        self._generate_files(file_specs)
        
        # Generate special files (README, config, etc.)
        self._generate_special_files(name, project_type, file_specs)
        
        # Generate tests if requested
        if include_tests:
            self._generate_tests(file_specs)
        
        # Generate documentation if requested
        if include_docs:
            self._generate_docs(name, file_specs)
        
        # Create project manifest
        manifest = self._create_manifest(name, project_type, scale, file_specs)
        
        duration = time.time() - start_time
        
        logger.info(f"Project generated in {duration:.2f}s: {len(self.generated_files)} files")
        
        return {
            "success": True,
            "project_name": name,
            "total_files": len(self.generated_files),
            "duration_seconds": duration,
            "manifest": manifest
        }
    
    def _generate_file_specs(
        self,
        name: str,
        project_type: ProjectType,
        target_count: int
    ) -> List[FileSpec]:
        """Generate file specifications based on project type and scale."""
        specs = []
        
        # Core application structure
        core_files = [
            FileSpec("app/__init__.py", "app", "init", 5, "Package initialization"),
            FileSpec("app/config.py", "app", "config", 40, "Configuration management"),
            FileSpec("app/main.py", "app", "main", 60, "Application entry point"),
            FileSpec("app/models.py", "app", "model", 100, "Data models"),
            FileSpec("app/schemas.py", "app", "schema", 80, "Data schemas"),
            FileSpec("app/database.py", "app", "database", 70, "Database connection"),
            FileSpec("app/dependencies.py", "app", "dependency", 50, "Dependency injection"),
        ]
        specs.extend(core_files)
        
        # API structure for web projects
        if project_type in (ProjectType.WEB_API, ProjectType.MICROSERVICES, ProjectType.FULLSTACK):
            api_files = [
                FileSpec("app/api/__init__.py", "app.api", "init", 5, "API package init"),
                FileSpec("app/api/routes.py", "app.api", "route", 150, "API routes"),
                FileSpec("app/api/endpoints.py", "app.api", "endpoint", 200, "API endpoints"),
                FileSpec("app/api/middleware.py", "app.api", "middleware", 80, "API middleware"),
                FileSpec("app/api/validators.py", "app.api", "validator", 60, "Request validators"),
            ]
            specs.extend(api_files)
        
        # Services layer
        services = [
            FileSpec("app/services/__init__.py", "app.services", "init", 5, "Services init"),
            FileSpec("app/services/business_logic.py", "app.services", "service", 120, "Business logic"),
            FileSpec("app/services/external_api.py", "app.services", "service", 100, "External API client"),
            FileSpec("app/services/cache.py", "app.services", "cache", 60, "Cache service"),
            FileSpec("app/services/queue.py", "app.services", "queue", 70, "Queue service"),
        ]
        specs.extend(services)
        
        # Utils
        utils = [
            FileSpec("app/utils/__init__.py", "app.utils", "init", 5, "Utils package"),
            FileSpec("app/utils/helpers.py", "app.utils", "util", 80, "Helper functions"),
            FileSpec("app/utils/decorators.py", "app.utils", "decorator", 60, "Common decorators"),
            FileSpec("app/utils/validators.py", "app.utils", "validator", 50, "Validators"),
            FileSpec("app/utils/exceptions.py", "app.utils", "exception", 40, "Custom exceptions"),
        ]
        specs.extend(utils)
        
        # CLI structure
        if project_type in (ProjectType.CLI_TOOL, ProjectType.MONOLITH):
            cli_files = [
                FileSpec("app/cli.py", "app", "cli", 100, "CLI interface"),
                FileSpec("app/commands.py", "app", "command", 120, "CLI commands"),
                FileSpec("app/argparse_config.py", "app", "argparse", 50, "Argparse setup"),
            ]
            specs.extend(cli_files)
        
        # Data pipeline structure
        if project_type == ProjectType.DATA_PIPELINE:
            pipeline_files = [
                FileSpec("app/pipeline/__init__.py", "app.pipeline", "init", 5, "Pipeline init"),
                FileSpec("app/pipeline/extractors.py", "app.pipeline", "extractor", 100, "Data extractors"),
                FileSpec("app/pipeline/transformers.py", "app.pipeline", "transformer", 120, "Data transformers"),
                FileSpec("app/pipeline/loaders.py", "app.pipeline", "loader", 100, "Data loaders"),
                FileSpec("app/pipeline/schedulers.py", "app.pipeline", "scheduler", 60, "Job schedulers"),
            ]
            specs.extend(pipeline_files)
        
        # Add more files to reach target count
        current_count = len(specs)
        remaining = target_files - current_count
        
        # Generate module files
        module_count = max(1, remaining // 10)
        for i in range(module_count):
            module_files = self._generate_module_files(f"module_{i+1}", remaining // module_count)
            specs.extend(module_files)
        
        # Fill remaining with standard files
        while len(specs) < target_count:
            spec = FileSpec(
                path=f"app/components_{len(specs) // 20}/component_{len(specs)}.py",
                module=f"app.components_{len(specs) // 20}",
                file_type="component",
                lines=30 + (len(specs) % 50),
                purpose=f"Component {len(specs)}",
                dependencies=["app.models"]
            )
            specs.append(spec)
        
        return specs[:target_count]
    
    def _generate_module_files(self, module_name: str, count: int) -> List[FileSpec]:
        """Generate files for a module."""
        specs = []
        module_path = f"app/{module_name}"
        
        specs.append(FileSpec(
            f"{module_path}/__init__.py", module_name, "init", 5, "Module init"
        ))
        
        for i in range(min(count - 1, 10)):
            specs.append(FileSpec(
                f"{module_path}/component_{i+1}.py",
                module_name,
                "component",
                40 + (i * 5),
                f"{module_name} component {i+1}",
                dependencies=[f"{module_name}.__init__"]
            ))
        
        return specs
    
    def _generate_files(self, specs: List[FileSpec]) -> None:
        """Generate actual code files from specifications."""
        for spec in specs:
            try:
                content = self._generate_file_content(spec)
                filepath = self.output_dir / spec.path
                filepath.parent.mkdir(parents=True, exist_ok=True)
                
                with open(filepath, "w") as f:
                    f.write(content)
                
                self.generated_files.append(spec.path)
                spec.content_hash = hashlib.md5(content.encode()).hexdigest()
                
            except Exception as e:
                logger.error(f"Failed to generate {spec.path}: {e}")
    
    def _generate_file_content(self, spec: FileSpec) -> str:
        """Generate content for a file based on its spec."""
        if spec.file_type == "init":
            return f'''"""Package: {spec.module}"""
from . import *
'''
        
        elif spec.file_type == "config":
            return f'''"""Configuration for {spec.module}"""
import os
from typing import Optional

class Config:
    """Application configuration"""
    
    # Environment
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    ENV: str = os.getenv("ENV", "production")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    DATABASE_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
    DATABASE_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    
    # API
    API_VERSION: str = "v1"
    API_TITLE: str = "{spec.module} API"
    API_DESCRIPTION: str = "{spec.purpose}"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Cache
    CACHE_TYPE: str = os.getenv("CACHE_TYPE", "redis")
    CACHE_REDIS_URL: str = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379/0")
    CACHE_DEFAULT_TIMEOUT: int = 300
    
    @classmethod
    def from_env(cls) -> "{spec.module}.Config":
        """Create config from environment variables"""
        return cls()
    
    @classmethod
    def validate(cls) -> bool:
        """Validate configuration"""
        required = ["DATABASE_URL", "SECRET_KEY"]
        return all(os.getenv(k) for k in required)


config = Config()
'''
        
        elif spec.file_type == "model":
            return f'''"""Data models for {spec.module}"""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

class ModelStatus(Enum):
    """Status enumeration"""
    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"


@dataclass
class BaseModel:
    """Base model with common fields"""
    id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    status: ModelStatus = ModelStatus.PENDING
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {{k: v.value if isinstance(v, Enum) else v 
                 for k, v in self.__dict__.items()}}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BaseModel:
        """Create from dictionary"""
        return cls(**{{k: v for k, v in data.items() if k in cls.__annotations__}})


@dataclass
class User(BaseModel):
    """User model"""
    username: str = ""
    email: str = ""
    full_name: Optional[str] = None
    is_active: bool = True
    roles: List[str] = field(default_factory=list)


@dataclass
class Project(BaseModel):
    """Project model"""
    name: str = ""
    description: str = ""
    owner_id: int = 0
    visibility: str = "private"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Resource(BaseModel):
    """Generic resource model"""
    name: str = ""
    type: str = ""
    project_id: int = 0
    config: Dict[str, Any] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)


class ModelRegistry:
    """Registry for model classes"""
    _models: Dict[str, type] = {{}}
    
    @classmethod
    def register(cls, name: str, model_class: type) -> None:
        cls._models[name] = model_class
    
    @classmethod
    def get(cls, name: str) -> Optional[type]:
        return cls._models.get(name)
    
    @classmethod
    def list_models(cls) -> List[str]:
        return list(cls._models.keys())


# Register models
ModelRegistry.register("User", User)
ModelRegistry.register("Project", Project)
ModelRegistry.register("Resource", Resource)
'''
        
        else:
            # Generic component
            return f'''"""Module: {spec.module} - {spec.purpose}"""
from __future__ import annotations
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class ComponentState:
    """State for {spec.module}"""
    initialized: bool = False
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class {spec.module.split('.')[-1].title().replace('_', '')}Component:
    """Component for {spec.purpose}"""
    
    def __init__(self):
        self.state = ComponentState()
        self.logger = logging.getLogger(__name__)
        self._initialized = False
    
    def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Initialize the component"""
        try:
            self.logger.info(f"Initializing {{self.__class__.__name__}}")
            # Initialization logic here
            if config:
                self.state.data.update(config)
            self._initialized = True
            self.state.initialized = True
            return True
        except Exception as e:
            self.logger.error(f"Initialization failed: {{e}}")
            return False
    
    def process(self, data: Any) -> Any:
        """Process data"""
        if not self._initialized:
            raise RuntimeError("Component not initialized")
        return data
    
    def cleanup(self) -> None:
        """Cleanup resources"""
        self._initialized = False
        self.state = ComponentState()


def create_component() -> {spec.module.split('.')[-1].title().replace('_', '')}Component:
    """Factory function"""
    return {spec.module.split('.')[-1].title().replace('_', '')}Component()
'''
    
    def _generate_special_files(
        self,
        name: str,
        project_type: ProjectType,
        specs: List[FileSpec]
    ) -> None:
        """Generate special files like README, requirements, etc."""
        # README
        readme = f"""# {name}

{project_type.value.replace('_', ' ').title()} Project

## Overview

This project was generated by ILMA Heavy Coding Engine.

## Structure

- `app/` - Main application code
- `tests/` - Test files
- `docs/` - Documentation

## Features

- Modern architecture
- Comprehensive testing
- API documentation
- CI/CD ready

## Setup

```bash
pip install -r requirements.txt
python -m app.main
```

## Files: {len(specs)}
"""
        
        with open(self.output_dir / "README.md", "w") as f:
            f.write(readme)
        
        # Requirements
        requirements = """# Core dependencies
fastapi>=0.100.0
uvicorn>=0.23.0
pydantic>=2.0.0
sqlalchemy>=2.0.0

# Database
psycopg2-binary>=2.9.0
alembic>=1.11.0

# Utilities
python-dotenv>=1.0.0
httpx>=0.24.0
redis>=4.5.0

# Testing
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-asyncio>=0.21.0
"""
        
        with open(self.output_dir / "requirements.txt", "w") as f:
            f.write(requirements)
        
        # Git ignore
        gitignore = """__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.env
.venv
venv/
ENV/
.pytest_cache/
.coverage
htmlcov/
*.log
"""
        
        with open(self.output_dir / ".gitignore", "w") as f:
            f.write(gitignore)
    
    def _generate_tests(self, specs: List[FileSpec]) -> None:
        """Generate test files."""
        tests_dir = self.output_dir / "tests"
        tests_dir.mkdir(exist_ok=True)
        
        # Main conftest
        conftest = '''"""Test configuration"""
import pytest
from app.config import Config

@pytest.fixture
def config():
    """Test configuration"""
    return Config(DEBUG=True)

@pytest.fixture
def sample_data():
    """Sample test data"""
    return {"key": "value", "list": [1, 2, 3]}
'''
        
        with open(tests_dir / "conftest.py", "w") as f:
            f.write(conftest)
        
        # Generate test for each module
        modules = set(spec.module for spec in specs)
        for module in list(modules)[:20]:  # Limit tests
            module_name = module.replace(".", "_")
            test_content = f'''"""Tests for {module}"""
import pytest
from app import {module.split('.')[-1]}

def test_module_import():
    """Test module can be imported"""
    assert {module.split('.')[-1]} is not None

def test_basic_functionality():
    """Test basic functionality"""
    pass
'''
            
            test_file = tests_dir / f"test_{module_name}.py"
            with open(test_file, "w") as f:
                f.write(test_content)
    
    def _generate_docs(self, name: str, specs: List[FileSpec]) -> None:
        """Generate documentation."""
        docs_dir = self.output_dir / "docs"
        docs_dir.mkdir(exist_ok=True)
        
        index_content = f"""# {name} Documentation

## Overview

Auto-generated documentation for {name}.

## Modules

"""
        
        modules = set(spec.module for spec in specs)
        for module in sorted(modules):
            index_content += f"- {module}\n"
        
        with open(docs_dir / "index.md", "w") as f:
            f.write(index_content)
    
    def _create_manifest(
        self,
        name: str,
        project_type: ProjectType,
        scale: ProjectScale,
        specs: List[FileSpec]
    ) -> Dict[str, Any]:
        """Create project manifest."""
        manifest = {
            "project_name": name,
            "type": project_type.value,
            "scale": scale.value,
            "generated_at": datetime.now().isoformat(),
            "total_files": len(specs),
            "total_lines": sum(spec.lines for spec in specs),
            "modules": list(set(spec.module for spec in specs)),
            "files": [
                {
                    "path": spec.path,
                    "module": spec.module,
                    "type": spec.file_type,
                    "lines": spec.lines,
                    "hash": spec.content_hash
                }
                for spec in specs
            ]
        }
        
        manifest_path = self.output_dir / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        
        return manifest


# =============================================================================
# DEPENDENCY RESOLVER CLASS
# =============================================================================

class DependencyResolver:
    """
    Dependency resolution and management for large codebases.
    
    Analyzes import relationships, detects circular dependencies,
    and provides dependency metrics.
    """
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.dependencies: Dict[str, DependencyInfo] = {}
        self._cache: Dict[str, Set[str]] = {}
        logger.info(f"DependencyResolver initialized for: {project_root}")
    
    def scan_project(self) -> Dict[str, DependencyInfo]:
        """Scan project for all dependencies."""
        self.dependencies.clear()
        
        for filepath in self.project_root.rglob("*.py"):
            module_path = self._file_to_module(filepath)
            
            try:
                with open(filepath) as f:
                    content = f.read()
                
                imports = self._extract_imports(content)
                
                dep_info = DependencyInfo(
                    module=module_path,
                    imports=imports,
                    import_count=len(imports)
                )
                
                self.dependencies[module_path] = dep_info
                
            except Exception as e:
                logger.warning(f"Failed to analyze {filepath}: {e}")
        
        # Build reverse dependency map
        self._build_reverse_deps()
        
        return self.dependencies
    
    def _file_to_module(self, filepath: Path) -> str:
        """Convert file path to module path."""
        try:
            relative = filepath.relative_to(self.project_root)
            parts = list(relative.parts)
            if parts[-1] == "__init__.py":
                parts = parts[:-1]
            elif parts[-1].endswith(".py"):
                parts[-1] = parts[-1][:-3]
            return ".".join(parts)
        except ValueError:
            return str(filepath.stem)
    
    def _extract_imports(self, content: str) -> List[str]:
        """Extract all imports from file content."""
        imports = []
        
        for line in content.split("\n"):
            line = line.strip()
            
            if line.startswith("import "):
                module = line.replace("import ", "").split(";")[0].split(" as ")[0].strip()
                imports.append(module)
            
            elif line.startswith("from "):
                match = re.match(r"from\s+([^\s]+)\s+import", line)
                if match:
                    imports.append(match.group(1))
        
        return imports
    
    def _build_reverse_deps(self) -> None:
        """Build reverse dependency map (used_by)."""
        for module, dep_info in self.dependencies.items():
            for imported in dep_info.imports:
                if imported in self.dependencies:
                    self.dependencies[imported].used_by.append(module)
    
    def find_circular_dependencies(self) -> List[List[str]]:
        """Detect circular dependencies in the project."""
        cycles = []
        visited = set()
        
        def dfs(module: str, path: List[str]) -> bool:
            if module in path:
                cycle_start = path.index(module)
                cycle = path[cycle_start:] + [module]
                cycles.append(cycle)
                return True
            
            if module in visited:
                return False
            
            visited.add(module)
            path.append(module)
            
            if module in self.dependencies:
                for imp in self.dependencies[module].imports:
                    if imp in self.dependencies:
                        dfs(imp, path)
            
            path.pop()
            return False
        
        for module in self.dependencies:
            visited.clear()
            dfs(module, [])
        
        return cycles
    
    def get_dependency_tree(self, module: str, depth: int = 3) -> Dict[str, Any]:
        """Get dependency tree for a module."""
        if module in self._cache:
            return self._cache[module]
        
        tree = {
            "module": module,
            "imports": [],
            "used_by": []
        }
        
        if module in self.dependencies:
            dep_info = self.dependencies[module]
            
            if depth > 0:
                for imp in dep_info.imports[:10]:  # Limit to avoid explosion
                    if imp in self.dependencies:
                        tree["imports"].append(
                            self.get_dependency_tree(imp, depth - 1)
                        )
            
            tree["used_by"] = dep_info.used_by[:10]
        
        return tree
    
    def resolve_order(self) -> List[str]:
        """Resolve module loading order (topological sort)."""
        # Build graph
        in_degree = {m: 0 for m in self.dependencies}
        adj_list = {m: [] for m in self.dependencies}
        
        for module, dep_info in self.dependencies.items():
            for imp in dep_info.imports:
                if imp in self.dependencies:
                    adj_list[imp].append(module)
                    in_degree[module] += 1
        
        # Kahn's algorithm
        queue = [m for m, d in in_degree.items() if d == 0]
        order = []
        
        while queue:
            module = queue.pop(0)
            order.append(module)
            
            for neighbor in adj_list[module]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        return order
    
    def get_coupling_metrics(self) -> Dict[str, float]:
        """Calculate coupling metrics."""
        if not self.dependencies:
            return {"afferent_coupling": 0, "efferent_coupling": 0, "instability": 0}
        
        total_ce = 0  # Efferent coupling (outgoing)
        total_ca = 0  # Afferent coupling (incoming)
        
        for module, dep_info in self.dependencies.items():
            # Count internal imports
            internal_imports = sum(1 for imp in dep_info.imports if imp in self.dependencies)
            total_ce += internal_imports
            total_ca += len(dep_info.used_by)
        
        avg_ce = total_ce / len(self.dependencies) if self.dependencies else 0
        avg_ca = total_ca / len(self.dependencies) if self.dependencies else 0
        
        # Instability = CE / (CE + CA)
        instability = avg_ce / (avg_ce + avg_ca) if (avg_ce + avg_ca) > 0 else 0
        
        return {
            "afferent_coupling": avg_ca,
            "efferent_coupling": avg_ce,
            "instability": instability,
            "total_dependencies": len(self.dependencies)
        }


# =============================================================================
# PROJECT SCALE METRICS CLASS
# =============================================================================

class ProjectScaleMetrics:
    """
    Metrics collection and analysis for large-scale projects.
    
    Provides complexity analysis, code quality metrics,
    and project health assessment.
    """
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.metrics_cache: Dict[str, Any] = {}
        logger.info(f"ProjectScaleMetrics initialized for: {project_root}")
    
    def collect_metrics(self) -> ProjectMetrics:
        """Collect comprehensive project metrics."""
        files = list(self.project_root.rglob("*.py"))
        
        total_files = len(files)
        total_lines = 0
        total_modules = len(set(self._get_module(f) for f in files))
        
        complexity_sum = 0
        file_count = 0
        
        for filepath in files:
            try:
                with open(filepath) as f:
                    content = f.read()
                
                total_lines += len(content.split("\n"))
                complexity_sum += self._calculate_complexity(content)
                file_count += 1
            except Exception:
                continue
        
        avg_complexity = complexity_sum / file_count if file_count > 0 else 0
        
        # Calculate cohesion and coupling
        resolver = DependencyResolver(str(self.project_root))
        resolver.scan_project()
        coupling_metrics = resolver.get_coupling_metrics()
        
        metrics = ProjectMetrics(
            total_files=total_files,
            total_lines=total_lines,
            total_modules=total_modules,
            total_dependencies=len(resolver.dependencies),
            cyclomatic_complexity_avg=avg_complexity,
            coupling_score=coupling_metrics["efferent_coupling"],
            cohesion_score=0.5,  # Placeholder - requires deeper analysis
            code_to_test_ratio=self._calculate_code_to_test_ratio(),
            documentation_coverage=self._calculate_doc_coverage(files)
        )
        
        self.metrics_cache = self._metrics_to_dict(metrics)
        return metrics
    
    def _get_module(self, filepath: Path) -> str:
        """Get module name from file path."""
        try:
            relative = filepath.relative_to(self.project_root)
            parts = list(relative.parts)
            if parts[-1] == "__init__.py":
                return ".".join(parts[:-1])
            elif parts[-1].endswith(".py"):
                return ".".join(parts[:-1] + [parts[-1][:-3]])
            return str(parts[0])
        except ValueError:
            return filepath.stem
    
    def _calculate_complexity(self, content: str) -> float:
        """Calculate cyclomatic complexity."""
        complexity = 1
        
        # Count control flow structures
        patterns = [
            r'\bif\b', r'\belse\b', r'\belif\b',
            r'\bfor\b', r'\bwhile\b',
            r'\band\b', r'\bor\b',
            r'\btry\b', r'\bcatch\b', r'\bfinally\b'
        ]
        
        for pattern in patterns:
            complexity += len(re.findall(pattern, content))
        
        return complexity
    
    def _calculate_code_to_test_ratio(self) -> float:
        """Calculate code to test ratio."""
        src_files = list(self.project_root.glob("app/**/*.py"))
        test_files = list(self.project_root.glob("tests/**/*.py"))
        
        src_lines = 0
        test_lines = 0
        
        for f in src_files:
            try:
                src_lines += len(f.read_text().split("\n"))
            except Exception:
                pass
        
        for f in test_files:
            try:
                test_lines += len(f.read_text().split("\n"))
            except Exception:
                pass
        
        if test_lines == 0:
            return 0.0
        
        return src_lines / test_lines
    
    def _calculate_doc_coverage(self, files: List[Path]) -> float:
        """Calculate documentation coverage."""
        documented = 0
        
        for filepath in files:
            try:
                content = filepath.read_text()
                # Check for docstrings
                if '"""' in content or "'''" in content:
                    documented += 1
            except Exception:
                pass
        
        return documented / len(files) if files else 0.0
    
    def _metrics_to_dict(self, metrics: ProjectMetrics) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_files": metrics.total_files,
            "total_lines": metrics.total_lines,
            "total_modules": metrics.total_modules,
            "total_dependencies": metrics.total_dependencies,
            "cyclomatic_complexity_avg": metrics.cyclomatic_complexity_avg,
            "coupling_score": metrics.coupling_score,
            "cohesion_score": metrics.cohesion_score,
            "code_to_test_ratio": metrics.code_to_test_ratio,
            "documentation_coverage": metrics.documentation_coverage
        }
    
    def generate_report(self) -> str:
        """Generate a comprehensive metrics report."""
        metrics = self.collect_metrics()
        
        report = f"""=== Project Scale Metrics ===

Files:
  Total: {metrics.total_files}
  Lines: {metrics.total_lines:,}
  Modules: {metrics.total_modules}

Code Quality:
  Avg Complexity: {metrics.cyclomatic_complexity_avg:.2f}
  Coupling Score: {metrics.coupling_score:.2f}
  Cohesion Score: {metrics.cohesion_score:.2f}

Testing:
  Code/Test Ratio: {metrics.code_to_test_ratio:.2f}

Documentation:
  Coverage: {metrics.documentation_coverage:.1%}
"""
        
        return report
    
    def compare_with_baseline(self, baseline: Dict[str, Any]) -> Dict[str, Any]:
        """Compare current metrics with a baseline."""
        current = self.collect_metrics()
        current_dict = self._metrics_to_dict(current)
        
        comparison = {}
        for key in baseline:
            if key in current_dict:
                diff = current_dict[key] - baseline[key]
                pct = (diff / baseline[key] * 100) if baseline[key] != 0 else 0
                comparison[key] = {
                    "current": current_dict[key],
                    "baseline": baseline[key],
                    "diff": diff,
                    "percent_change": pct
                }
        
        return comparison


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="ILMA Heavy Coding Engine - Large-scale codebase generation and analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate a large project
  %(prog)s --generate-project --name MyProject --scale large --type web_api
  
  # Analyze dependencies
  %(prog)s --resolve-deps --project /path/to/project
  
  # Collect project metrics
  %(prog)s --metrics --project /path/to/project
  
  # Generate dependency report
  %(prog)s --dep-report --project /path/to/project
        """
    )
    
    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    # Generation options
    parser.add_argument("--generate-project", action="store_true", help="Generate a project")
    parser.add_argument("--name", help="Project name")
    parser.add_argument("--scale", choices=["small", "medium", "large", "enterprise", "mega"], 
                       default="large", help="Project scale")
    parser.add_argument("--type", choices=["web_api", "cli_tool", "data_pipeline", "microservices", "fullstack"],
                       default="web_api", help="Project type")
    parser.add_argument("--output-dir", default="./generated_project", help="Output directory")
    
    # Dependency analysis options
    parser.add_argument("--resolve-deps", action="store_true", help="Analyze dependencies")
    parser.add_argument("--find-cycles", action="store_true", help="Find circular dependencies")
    parser.add_argument("--dep-report", action="store_true", help="Generate dependency report")
    parser.add_argument("--project", default=".", help="Project root directory")
    
    # Metrics options
    parser.add_argument("--metrics", action="store_true", help="Collect project metrics")
    parser.add_argument("--report", action="store_true", help="Generate metrics report")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Project Generation
        if args.generate_project:
            if not args.name:
                parser.error("--name is required for project generation")
            
            generator = MegaFileGenerator(output_dir=args.output_dir)
            
            result = generator.generate_project(
                name=args.name,
                project_type=ProjectType(args.type),
                scale=ProjectScale(args.scale),
                include_tests=True,
                include_docs=True
            )
            
            print(f"\n=== Project Generated ===")
            print(f"Name: {result['project_name']}")
            print(f"Files: {result['total_files']}")
            print(f"Duration: {result['duration_seconds']:.2f}s")
            print(f"Output: {args.output_dir}")
        
        # Dependency Resolution
        elif args.resolve_deps:
            resolver = DependencyResolver(args.project)
            deps = resolver.scan_project()
            
            print(f"\n=== Dependency Analysis ===")
            print(f"Modules: {len(deps)}")
            
            cycles = resolver.find_circular_dependencies()
            if cycles:
                print(f"\nCircular Dependencies: {len(cycles)}")
                for cycle in cycles[:5]:
                    print(f"  {' -> '.join(cycle[:6])}")
            else:
                print("No circular dependencies found")
            
            metrics = resolver.get_coupling_metrics()
            print(f"\nCoupling Metrics:")
            print(f"  Afferent: {metrics['afferent_coupling']:.2f}")
            print(f"  Efferent: {metrics['efferent_coupling']:.2f}")
            print(f"  Instability: {metrics['instability']:.3f}")
        
        elif args.find_cycles:
            resolver = DependencyResolver(args.project)
            resolver.scan_project()
            cycles = resolver.find_circular_dependencies()
            
            print(f"\n=== Circular Dependencies ===")
            if cycles:
                print(f"Found {len(cycles)} circular dependencies:")
                for i, cycle in enumerate(cycles[:10]):
                    print(f"  {i+1}. {' -> '.join(cycle[:8])}")
            else:
                print("No circular dependencies found")
        
        elif args.dep_report:
            resolver = DependencyResolver(args.project)
            deps = resolver.scan_project()
            
            print(f"\n=== Dependency Report ===")
            print(f"Total modules: {len(deps)}")
            
            # Top importers
            sorted_deps = sorted(deps.values(), key=lambda x: x.import_count, reverse=True)
            print("\nTop 10 modules by import count:")
            for dep in sorted_deps[:10]:
                print(f"  {dep.module}: {dep.import_count} imports, used by {len(dep.used_by)}")
        
        # Metrics
        elif args.metrics:
            metrics_collector = ProjectScaleMetrics(args.project)
            metrics = metrics_collector.collect_metrics()
            
            print("\n=== Project Metrics ===")
            print(f"Files: {metrics.total_files}")
            print(f"Lines: {metrics.total_lines:,}")
            print(f"Modules: {metrics.total_modules}")
            print(f"Dependencies: {metrics.total_dependencies}")
            print(f"Avg Complexity: {metrics.cyclomatic_complexity_avg:.2f}")
            print(f"Coupling: {metrics.coupling_score:.2f}")
            print(f"Code/Test Ratio: {metrics.code_to_test_ratio:.2f}")
            print(f"Doc Coverage: {metrics.documentation_coverage:.1%}")
        
        elif args.report:
            metrics_collector = ProjectScaleMetrics(args.project)
            report = metrics_collector.generate_report()
            print(report)
        
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()