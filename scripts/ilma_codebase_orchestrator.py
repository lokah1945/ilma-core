#!/usr/bin/env python3
"""ILMA Codebase Orchestrator v1.0"""
import argparse, json, os, sys, re, uuid
from datetime import datetime

class CodebaseOrchestrator:
    VERSION = "1.0"

    def __init__(self, project_dir):
        self.project_dir = project_dir
        self.manifest_path = os.path.join(project_dir, "architecture_manifest.json")
        self.graph_path = os.path.join(project_dir, "dependency_graph.json")
        self.plan_path = os.path.join(project_dir, "file_generation_plan.json")
        self.contracts_path = os.path.join(project_dir, "interface_contracts.md")
        self.test_matrix_path = os.path.join(project_dir, "test_matrix.md")
        self.security_path = os.path.join(project_dir, "SECURITY.md")
        self.rollback_path = os.path.join(project_dir, "ROLLBACK.md")
        self.readme_path = os.path.join(project_dir, "README.md")
        self.files_dir = os.path.join(project_dir, "generated_files")
        self.tests_dir = os.path.join(project_dir, "tests")
        os.makedirs(self.files_dir, exist_ok=True)
        os.makedirs(self.tests_dir, exist_ok=True)

    def init_project(self, name, project_type="cli-tool"):
        project_id = f"CODEBASE_{uuid.uuid4().hex[:8].upper()}"
        stack = {"cli-tool": ["python", "sqlite", "argparse"], "web-api": ["python", "fastapi", "sqlalchemy"], "data-pipeline": ["python", "pandas", "sqlalchemy"]}.get(project_type, ["python"])
        manifest = {"project_id": project_id, "name": name, "type": project_type, "stack": stack, "created_at": datetime.now().isoformat(), "status": "initialized", "total_files_target": 100, "benchmark_files": 20}
        with open(self.manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        plan = self._build_file_plan(name, project_type, stack)
        with open(self.plan_path, "w") as f:
            json.dump(plan, f, indent=2)
        graph = self._build_dependency_graph(plan["files"])
        with open(self.graph_path, "w") as f:
            json.dump(graph, f, indent=2)
        with open(self.contracts_path, "w") as f:
            f.write(self._generate_contracts(plan["files"]))
        with open(self.test_matrix_path, "w") as f:
            f.write(self._generate_test_matrix(plan["files"]))
        with open(self.security_path, "w") as f:
            f.write(self._generate_security_checklist())
        with open(self.rollback_path, "w") as f:
            f.write(self._generate_rollback_plan())
        with open(self.readme_path, "w") as f:
            f.write(self._generate_readme(name, project_type, stack, plan["files"]))
        print(f"Project initialized: {project_id}")
        print(f"  Type: {project_type}")
        print(f"  Files planned: {len(plan['files'])}")
        return project_id

    def _build_file_plan(self, name, ptype, stack):
        files = []
        files.append({"id": "f01", "path": "app/__init__.py", "module": "app", "type": "init", "lines": 5, "purpose": "Package init"})
        files.append({"id": "f02", "path": "app/config.py", "module": "app", "type": "config", "lines": 25, "purpose": "Configuration management", "deps": ["f01"]})
        files.append({"id": "f03", "path": "app/models.py", "module": "app", "type": "model", "lines": 50, "purpose": "Data models", "deps": ["f01", "f02"]})
        files.append({"id": "f04", "path": "app/database.py", "module": "app", "type": "db", "lines": 40, "purpose": "Database connection", "deps": ["f01", "f02", "f03"]})
        files.append({"id": "f05", "path": "app/validation.py", "module": "app", "type": "validation", "lines": 35, "purpose": "Input validation", "deps": ["f01", "f02", "f03"]})
        files.append({"id": "f06", "path": "app/services.py", "module": "app", "type": "service", "lines": 60, "purpose": "Business logic", "deps": ["f03", "f04", "f05"]})
        files.append({"id": "f07", "path": "app/api.py", "module": "app", "type": "api", "lines": 50, "purpose": "API endpoints", "deps": ["f01", "f03", "f06"]})
        files.append({"id": "f08", "path": "app/cli.py", "module": "app", "type": "cli", "lines": 45, "purpose": "CLI interface", "deps": ["f01", "f02", "f06"]})
        files.append({"id": "f09", "path": "app/logging_config.py", "module": "app", "type": "config", "lines": 20, "purpose": "Logging setup", "deps": ["f01", "f02"]})
        files.append({"id": "f10", "path": "app/errors.py", "module": "app", "type": "error", "lines": 30, "purpose": "Custom exceptions", "deps": ["f01"]})
        files.append({"id": "f11", "path": "app/utils/__init__.py", "module": "app.utils", "type": "init", "lines": 3, "purpose": "Utils package"})
        files.append({"id": "f12", "path": "app/utils/helpers.py", "module": "app.utils", "type": "util", "lines": 30, "purpose": "Helper functions", "deps": ["f01"]})
        files.append({"id": "f13", "path": "app/utils/decorators.py", "module": "app.utils", "type": "util", "lines": 25, "purpose": "Decorators", "deps": ["f01", "f12"]})
        files.append({"id": "f14", "path": "tests/__init__.py", "module": "tests", "type": "init", "lines": 3, "purpose": "Test package"})
        files.append({"id": "f15", "path": "tests/test_validation.py", "module": "tests", "type": "test", "lines": 40, "purpose": "Validation tests", "deps": ["f05"]})
        files.append({"id": "f16", "path": "tests/test_services.py", "module": "tests", "type": "test", "lines": 50, "purpose": "Service tests", "deps": ["f06"]})
        files.append({"id": "f17", "path": "tests/test_cli.py", "module": "tests", "type": "test", "lines": 35, "purpose": "CLI tests", "deps": ["f08"]})
        files.append({"id": "f18", "path": "requirements.txt", "module": "root", "type": "config", "lines": 10, "purpose": "Dependencies"})
        files.append({"id": "f19", "path": "setup.py", "module": "root", "type": "config", "lines": 15, "purpose": "Package setup"})
        files.append({"id": "f20", "path": ".gitignore", "module": "root", "type": "config", "lines": 10, "purpose": "Git ignore"})
        return {"files": files, "total": len(files)}

    def _build_dependency_graph(self, files):
        nodes, edges = [], []
        for f in files:
            nodes.append({"id": f["id"], "path": f["path"], "module": f["module"]})
            for dep in f.get("deps", []):
                edges.append({"from": dep, "to": f["id"]})
        cycles = self._detect_cycles({n["id"]: [] for n in nodes}, edges)
        return {"nodes": nodes, "edges": edges, "total_nodes": len(nodes), "total_edges": len(edges), "cycles": cycles, "is_acyclic": len(cycles) == 0}

    def _detect_cycles(self, graph, edges):
        for e in edges:
            graph[e["from"]].append(e["to"])
        visited, rec, cycles = set(), set(), []
        def dfs(node, path):
            visited.add(node); rec.add(node)
            for n in graph.get(node, []):
                if n not in visited:
                    if dfs(n, path+[node]): return True
                elif n in rec: cycles.append(path+[node,n])
            rec.remove(node)
        for node in graph:
            if node not in visited: dfs(node, [])
        return cycles

    def _generate_contracts(self, files):
        lines = ["# Interface Contracts\n\n"]
        for f in files:
            if f["type"] in ("api", "service", "db"):
                lines.append(f"## {f['path']}\n**Purpose:** {f['purpose']}\n**Module:** {f['module']}\n**Dependencies:** {', '.join(f.get('deps',[])) or 'none'}\n\n")
        return "".join(lines)

    def _generate_test_matrix(self, files):
        lines = ["| File | Test File | Coverage | Priority |\n", "|------|-----------|---------|----------|\n"]
        for f in files:
            if f["type"] == "test":
                dep = f.get("deps",["N/A"])[0]
                lines.append(f"| {dep} | {f['path']} | 80% | high |\n")
            elif f["type"] in ("model","service","validation"):
                lines.append(f"| {f['path']} | tests/test_{os.path.basename(f['path'])} | 80% | medium |\n")
        return "".join(lines)

    def _generate_security_checklist(self):
        return """# Security Checklist

- [ ] No hardcoded credentials
- [ ] All user input sanitized
- [ ] SQL injection prevention (parameterized queries)
- [ ] Command injection prevention
- [ ] File path traversal prevention
- [ ] Rate limiting on public endpoints
- [ ] Secrets in environment variables only
- [ ] HTTPS required for external calls
- [ ] Dependency audit: pip-audit
- [ ] No eval/exec with user input
"""

    def _generate_rollback_plan(self):
        return """# Rollback Plan

## Scenario 1: Feature breaks tests
1. git checkout HEAD~1
2. pytest tests/ -v
3. If PASS, rollback success

## Scenario 2: DB migration failure
1. Stop application
2. Restore backup: cp data/app.db.backup data/app.db
3. Re-run migration with --dry-run

## Scenario 3: Dependency conflict
1. Pin package: pip install package==version
2. Test: pytest tests/ -v
"""

    def _generate_readme(self, name, ptype, stack, files):
        return f"""# {name}

**Type:** {ptype}
**Stack:** {', '.join(stack)}
**Files:** {len(files)}

## Quick Start

```bash
pip install -r requirements.txt
python -m app.cli --help
pytest tests/ -v
```

## Architecture

- app/ - Application code
- tests/ - Test suite

## Testing

```bash
pytest tests/ -v --cov=app
```
"""

    def generate_file(self, file_id):
        with open(self.plan_path) as f: plan = json.load(f)
        fdata = next((x for x in plan["files"] if x["id"] == file_id), None)
        if not fdata:
            print(f"File {file_id} not found"); return False
        for dep in fdata.get("deps", []):
            dep_file = next((x for x in plan["files"] if x["id"] == dep), None)
            if dep_file and not os.path.exists(os.path.join(self.project_dir, dep_file["path"])):
                print(f"Dependency {dep} not generated for {file_id}"); return False
        content = self._generate_file_content(fdata)
        out_path = os.path.join(self.project_dir, fdata["path"])
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w") as f: f.write(content)
        print(f"Generated: {fdata['path']}")
        return True

    def _generate_file_content(self, fdata):
        if fdata["type"] == "init": return f'"""Package: {fdata["module"]}"""\n'
        elif fdata["type"] == "config":
            return '''"""Configuration."""
import os
class Config:
    DEBUG = os.getenv("DEBUG","false").lower()=="true"
    DATABASE_URL = os.getenv("DATABASE_URL","sqlite:///app.db")
    LOG_LEVEL = os.getenv("LOG_LEVEL","INFO")
    SECRET_KEY = os.getenv("SECRET_KEY","")
'''
        elif fdata["type"] == "model":
            return '''"""Data models."""
from dataclasses import dataclass
from datetime import datetime
@dataclass
class BaseModel:
    id: int | None = None
    created_at: datetime | None = None
@dataclass
class Task(BaseModel):
    title: str = ""
    description: str = ""
    priority: int = 3
    status: str = "pending"
'''
        elif fdata["type"] == "validation":
            return '''"""Input validation."""
import re
def validate_priority(value): return 1 <= value <= 5
def validate_status(value): return value in ("pending","in_progress","done")
def validate_title(value):
    if not value or len(value.strip())==0: return False,"empty"
    if len(value)>200: return False,"too long"
    return True,""
def sanitize_input(value): return re.sub(r"[<>'\"]","",value)
'''
        elif fdata["type"] == "service":
            return '''"""Business logic."""
from app.models import Task
from app.validation import validate_title,validate_priority
class TaskService:
    def __init__(self,db): self.db=db
    def create_task(self,title,priority=3):
        valid,msg=validate_title(title)
        if not valid: return None,msg
        if not validate_priority(priority): return None,"Invalid priority"
        return Task(title=title,priority=priority),""
'''
        elif fdata["type"] == "cli":
            return f'''"""CLI interface."""
import argparse
def main():
    parser=argparse.ArgumentParser(description="{fdata["module"]} CLI")
    parser.add_argument("--config",help="Config file path")
    args=parser.parse_args()
    print("CLI running...")
if __name__=="__main__": main()
'''
        elif fdata["type"] == "api":
            return f'''"""API endpoints for {fdata["module"]}."""
# Placeholder API module
'''
        elif fdata["type"] == "db":
            return '''"""Database connection."""
class Database:
    def __init__(self, url): self.url=url
    def connect(self): pass
'''
        elif fdata["type"] == "error":
            return '''"""Custom exceptions."""
class AppError(Exception): pass
class ValidationError(AppError): pass
class DatabaseError(AppError): pass
'''
        elif fdata["type"] == "util":
            return f'''"""Utilities for {fdata["module"]}."""
'''
        return f'# {fdata["path"]}\\n# Auto-generated\\n'

    def generate_all(self):
        with open(self.plan_path) as f: plan = json.load(f)
        generated = set()
        for _ in range(len(plan["files"])+1):
            made = False
            for f in plan["files"]:
                if f["id"] in generated: continue
                if all(d in generated for d in f.get("deps",[])):
                    self.generate_file(f["id"]); generated.add(f["id"]); made = True
            if not made: break
        print(f"Generated {len(generated)}/{len(plan['files'])} files")

    def run_tests(self):
        import subprocess
        result = subprocess.run(["python3","-m","pytest",self.tests_dir,"-v","--tb=short"], capture_output=True, text=True, cwd=self.project_dir, env={**__import__("os").environ,"PYTHONPATH":self.project_dir})
        print(result.stdout)
        return result.returncode == 0

    def show_graph(self):
        with open(self.graph_path) as f: g = json.load(f)
        print(f"Dependency Graph:")
        print(f"  Nodes: {g['total_nodes']}")
        print(f"  Edges: {g['total_edges']}")
        print(f"  Acyclic: {'YES' if g['is_acyclic'] else 'NO'}")
        if g["cycles"]: print(f"  Cycles: {len(g['cycles'])}")

    def status(self):
        with open(self.plan_path) as f: plan = json.load(f)
        with open(self.manifest_path) as f: m = json.load(f)
        gen = sum(1 for f in plan["files"] if os.path.exists(os.path.join(self.project_dir, f["path"])))
        print(f"Project: {m['name']} ({m['project_id']})")
        print(f"Files: {gen}/{len(plan['files'])} generated")

def main():
    p = argparse.ArgumentParser(description="ILMA Codebase Orchestrator")
    p.add_argument("--project-dir", default="./test_projects/phase5_massive_codebase_blueprint")
    p.add_argument("--init", help="Init project")
    p.add_argument("--type", default="cli-tool")
    p.add_argument("--generate", help="Generate file by ID")
    p.add_argument("--generate-all", action="store_true")
    p.add_argument("--status", action="store_true")
    p.add_argument("--test", action="store_true")
    p.add_argument("--graph", action="store_true")
    args = p.parse_args()
    o = CodebaseOrchestrator(args.project_dir)
    if args.init: o.init_project(args.init, args.type)
    elif args.generate: o.generate_file(args.generate)
    elif args.generate_all: o.generate_all()
    elif args.status: o.status()
    elif args.test: sys.exit(0 if o.run_tests() else 1)
    elif args.graph: o.show_graph()
    else: p.print_help()

if __name__ == "__main__": main()
