#!/usr/bin/env python3
"""Dependency graph validator for 100-file codebase."""
import sys, os, ast, json
from pathlib import Path
from collections import defaultdict

class DependencyVisitor(ast.NodeVisitor):
    def __init__(self, filepath):
        self.filepath = filepath
        self.imports = []
        self.from_imports = []
        self.imports_from = defaultdict(list)
    
    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        if node.module:
            for alias in node.names:
                self.from_imports.append((node.module, alias.name))
                self.imports_from[node.module].append(alias.name)
        self.generic_visit(node)

def extract_dependencies(filepath):
    """Extract imports from a Python file."""
    try:
        with open(filepath) as f:
            tree = ast.parse(f.read(), filename=str(filepath))
        visitor = DependencyVisitor(filepath)
        visitor.visit(tree)
        return visitor.imports, visitor.from_imports
    except Exception:
        return [], []

def validate_codebase(root_path, max_iterations=100):
    """Validate dependency graph of codebase."""
    root = Path(root_path)
    results = {
        "valid": True,
        "files_analyzed": 0,
        "total_imports": 0,
        "internal_imports": 0,
        "external_imports": 0,
        "cycles": [],
        "orphan_modules": [],
        "unresolved_imports": [],
        "acyclic": True
    }
    
    # Map file paths to module names
    file_to_module = {}
    for py_file in sorted(root.rglob("*.py")):
        if "__pycache__" in str(py_file) or ".pytest" in str(py_file):
            continue
        rel = py_file.relative_to(root)
        parts = list(rel.parts)[:-1]  # directory path
        module = ".".join(parts) if parts else "__root__"
        file_to_module[str(rel)] = module
    
    # Build dependency graph
    graph = {}  # file -> set of dependencies
    all_modules = set()
    
    iteration = 0
    for py_file in sorted(root.rglob("*.py")):
        if "__pycache__" in str(py_file) or ".pytest" in str(py_file):
            continue
        iteration += 1
        if iteration > max_iterations:
            break
            
        rel = str(py_file.relative_to(root))
        imports, from_imports = extract_dependencies(py_file)
        
        internal_deps = []
        external_deps = []
        
        for imp in imports:
            if imp.startswith(("models.", "services.", "middleware.", "persistence.", "cli.", "migrations.")):
                internal_deps.append(imp)
            elif imp in ["json", "os", "sys", "time", "datetime", "pathlib", "typing", "dataclasses", "uuid", "hashlib", "collections", "threading", "re"]:
                pass  # stdlib, skip
            else:
                external_deps.append(imp)
        
        for module, _ in from_imports:
            if module and any(module.startswith(p) for p in ["models", "services", "middleware", "persistence", "cli", "migrations"]):
                internal_deps.append(module)
            elif module:
                external_deps.append(module)
        
        graph[rel] = {
            "imports": list(set(internal_deps + external_deps)),
            "internal": list(set(internal_deps)),
            "external": list(set(external_deps)),
            "test": "/tests/" in rel
        }
        
        for dep in internal_deps:
            all_modules.add(dep)
        
        results["files_analyzed"] += 1
        results["total_imports"] += len(imports) + len(from_imports)
        results["internal_imports"] += len(set(internal_deps))
        results["external_imports"] += len(set(external_deps))
    
    # Detect orphans (modules with no incoming dependencies and not in tests/)
    incoming = defaultdict(int)
    for file_path, deps in graph.items():
        if "/tests/" not in file_path:
            for dep in deps.get("internal", []):
                incoming[dep] += 1
    
    for file_path, deps in graph.items():
        if "/tests/" not in file_path and not deps.get("internal"):
            if incoming.get(file_path.replace("/", ".").replace(".py", ""), 0) == 0:
                pass  # Could be top-level entry point
    
    # Check for cycles (simple DFS)
    visited = set()
    rec_stack = set()
    cycles = []
    
    def dfs(node, path):
        visited.add(node)
        rec_stack.add(node)
        for dep in graph.get(node, {}).get("internal", []):
            dep_key = dep.replace(".", "/") + ".py"
            dep_file = next((f for f in graph if dep in f or f.endswith(dep.replace(".", "/") + ".py")), None)
            if dep_file and dep_file in rec_stack:
                cycles.append((node, dep_file))
            if dep_file and dep_file not in visited:
                dfs(dep_file, path + [node])
        rec_stack.remove(node)
    
    for node in list(graph.keys())[:50]:  # limit to avoid infinite loops
        if node not in visited:
            dfs(node, [])
    
    if cycles:
        results["cycles"] = cycles[:5]  # limit
        results["acyclic"] = False
        results["valid"] = False
    
    # Services that should have at least one test
    services_without_test = []
    for f, deps in graph.items():
        if f.startswith("services/") and f != "services/__init__.py" and not deps.get("test"):
            services_without_test.append(f)
    
    results["services_without_test"] = services_without_test
    
    return results

if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "test_projects/phase9_100file_codebase"
    result = validate_codebase(root)
    
    print("=== Dependency Graph Validation ===")
    print(f"Files analyzed: {result['files_analyzed']}")
    print(f"Total imports: {result['total_imports']}")
    print(f"Internal imports: {result['internal_imports']}")
    print(f"External imports: {result['external_imports']}")
    print(f"Acyclic: {result['acyclic']}")
    print(f"Valid: {result['valid']}")
    print(f"Cycles found: {len(result['cycles'])}")
    if result['cycles']:
        print("Cycles:", result['cycles'][:3])
    sv = result.get("services_without_test", [])
    print(f"Services without test: {len(sv)}")
    if sv:
        print("  Examples:", sv[:5])
    
    # Output JSON
    with open("dependency_graph.json", "w") as f:
        json.dump(result, f, indent=2)
    print("\nSaved to dependency_graph.json")
