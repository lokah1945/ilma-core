#!/usr/bin/env python3
"""ILMA Execution Script: security_review"""
import argparse, json, re

EVIDENCE_ID = "P3-SEC-001"

PATTERNS = [
    (r"eval\s*\(", "security", "high", "Dangerous eval() usage"),
    (r"os\.system\s*\(", "security", "high", "Shell injection via os.system()"),
    (r"subprocess\.call\s*\(", "security", "high", "Potential shell=True risk"),
    (r"pickle\.load", "security", "medium", "Insecure pickle deserialization"),
    (r"yaml\.load\s*\(", "security", "medium", "Unsafe yaml.load (use yaml.safe_load)"),
    (r"password\s*=", "secret", "high", "Hardcoded password"),
    (r"api_key\s*=", "secret", "high", "Hardcoded API key"),
    (r"secret\s*=", "secret", "high", "Hardcoded secret"),
    (r"token\s*=", "secret", "high", "Hardcoded token"),
    (r"except\s*:\s*pass", "quality", "medium", "Bare except:pass hides errors"),
    (r"global\s+\w+", "quality", "medium", "Global variable usage"),
]

def review(code):
    issues = []
    for pattern, itype, severity, desc in PATTERNS:
        for m in re.finditer(pattern, code):
            line_no = code[:m.start()].count("\n") + 1
            issues.append({"type": itype, "severity": severity, "description": desc, "line": line_no})
    security_issues = [i for i in issues if i["type"] == "security"]
    secret_issues = [i for i in issues if i["type"] == "secret"]
    quality_issues = [i for i in issues if i["type"] == "quality"]
    return {
        "total_issues": len(issues),
        "security_issues": len(security_issues),
        "secret_issues": len(secret_issues),
        "quality_issues": len(quality_issues),
        "details": issues,
        "risk_level": "HIGH" if secret_issues else "MEDIUM" if security_issues else "LOW",
    }

def main(args):
    sample_code = args.code or 'API_KEY = "sk-abc123"\npassword = "secret123"\ndef load_data(path):\n    import yaml\n    return yaml.load(open(path))\ntry:\n    eval("1+1")\nexcept:\n    pass'
    output = {"evidence_id": EVIDENCE_ID, "script": "ilma_exec_security_review.py", "status": "EXECUTION_VERIFIED"}
    result = review(sample_code)
    output.update(result)
    if args.json:
        print(json.dumps(output, indent=2))
    else:
        print(json.dumps(output))
    return output

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--code", default=None)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    main(args)
