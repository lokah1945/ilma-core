#!/usr/bin/env python3
"""ILMA Extreme Scale QA Script v1.0"""
import argparse, json, os, sys

class ExtremeScaleQA:
    VERSION = "1.0"
    def __init__(self, project_dir):
        self.project_dir = project_dir

    def qa_longform(self):
        issues = []
        manifest = os.path.join(self.project_dir, "manifest.json")
        graph = os.path.join(self.project_dir, "chapter_graph.json")
        report = os.path.join(self.project_dir, "report.md")

        # Structure
        if not os.path.exists(manifest): issues.append({"category": "structure", "severity": "critical", "issue": "manifest.json missing"})
        if not os.path.exists(graph): issues.append({"category": "structure", "severity": "critical", "issue": "chapter_graph.json missing"})

        # Completeness
        if os.path.exists(graph):
            g = json.load(open(graph))
            pending = [c for c in g["chapters"] if c["status"] == "pending"]
            if pending: issues.append({"category": "completeness", "severity": "high", "issue": f"{len(pending)} chapters pending"})
        if os.path.exists(report):
            words = len(open(report).read().split())
            if words < 100: issues.append({"category": "completeness", "severity": "medium", "issue": f"Report too short: {words} words"})

        score = max(0, 10 - len(issues) * 0.5)
        return {"category": "longform", "issues": issues, "score": score, "passed": len([i for i in issues if i["severity"] in ("critical","high")]) == 0}

    def qa_codebase(self):
        issues = []
        manifest = os.path.join(self.project_dir, "architecture_manifest.json")
        graph = os.path.join(self.project_dir, "dependency_graph.json")

        if not os.path.exists(manifest): issues.append({"category": "structure", "severity": "critical", "issue": "architecture_manifest.json missing"})
        if not os.path.exists(graph): issues.append({"category": "structure", "severity": "critical", "issue": "dependency_graph.json missing"})

        if os.path.exists(graph):
            g = json.load(open(graph))
            if not g.get("is_acyclic", False): issues.append({"category": "architecture", "severity": "critical", "issue": "Dependency graph has cycles"})
            if g.get("total_nodes", 0) < 10: issues.append({"category": "completeness", "severity": "medium", "issue": f"Only {g['total_nodes']} files generated"})

        score = max(0, 10 - len(issues) * 0.5)
        return {"category": "codebase", "issues": issues, "score": score, "passed": len([i for i in issues if i["severity"] in ("critical","high")]) == 0}

    def qa_research(self):
        issues = []
        manifest = os.path.join(self.project_dir, "research_manifest.json")
        paper = os.path.join(self.project_dir, "paper.md")

        if not os.path.exists(manifest): issues.append({"category": "structure", "severity": "critical", "issue": "research_manifest.json missing"})
        if not os.path.exists(paper): issues.append({"category": "structure", "severity": "critical", "issue": "paper.md missing"})

        if os.path.exists(manifest):
            m = json.load(open(manifest))
            if len(m.get("sources", [])) < 3: issues.append({"category": "evidence", "severity": "high", "issue": f"Only {len(m.get('sources',[]))} sources (need 3+)"})
            if not m.get("methodology"): issues.append({"category": "methodology", "severity": "high", "issue": "No methodology section"})
            if not m.get("limitations"): issues.append({"category": "methodology", "severity": "medium", "issue": "No limitations section"})

        score = max(0, 10 - len(issues) * 0.5)
        return {"category": "research", "issues": issues, "score": score, "passed": len([i for i in issues if i["severity"] in ("critical","high")]) == 0}

    def run_all(self):
        results = {}
        name = os.path.basename(self.project_dir)

        if "longform" in name:
            results["longform"] = self.qa_longform()
        elif "codebase" in name or "massive" in name:
            results["codebase"] = self.qa_codebase()
        elif "paper" in name or "research" in name:
            results["research"] = self.qa_research()

        total_issues = sum(len(r["issues"]) for r in results.values())
        avg_score = sum(r["score"] for r in results.values()) / max(1, len(results))
        all_passed = all(r["passed"] for r in results.values())

        print(f"QA Results for {name}:")
        for cat, r in results.items():
            status = "PASS" if r["passed"] else "FAIL"
            print(f"  [{status}] {cat}: score={r['score']:.1f}/10, issues={len(r['issues'])}")
            for iss in r["issues"][:5]:
                print(f"    - [{iss['severity']}] {iss['issue']}")

        print(f"\nOverall: score={avg_score:.1f}/10, all_passed={all_passed}")
        return {"results": results, "total_issues": total_issues, "avg_score": avg_score, "all_passed": all_passed}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project-dir", required=True)
    args = p.parse_args()
    qa = ExtremeScaleQA(args.project_dir)
    result = qa.run_all()
    sys.exit(0 if result["all_passed"] else 1)

if __name__ == "__main__": main()
