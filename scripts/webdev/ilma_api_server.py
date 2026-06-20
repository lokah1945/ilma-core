#!/usr/bin/env python3
"""
ILMA API Server
==============
REST API server template.
"""

from flask import Flask, jsonify, request
import subprocess

app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "ilma-api"})

@app.route("/execute", methods=["POST"])
def execute():
    cmd = request.json.get("command")
    if not cmd:
        return jsonify({"error": "No command provided"}), 400
    # SECURITY: shell=False + allowlist of safe commands (Phase 15B)
    # Block shell metacharacters to prevent command injection
    allowed = ["curl", "wget", "git", "docker", "python3", "ls", "cat", "head", "tail", "grep"]
    import shlex
    parts = shlex.split(cmd)
    if not parts or parts[0] not in allowed:
        return jsonify({"error": f"Command not in allowlist. Allowed: {allowed}"}), 403
    result = subprocess.run(parts, shell=False, capture_output=True, text=True, timeout=30)
    return jsonify({
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode
    })

@app.route("/skills")
def skills():
    from pathlib import Path
    skills_dir = Path("/root/.hermes/profiles/ilma/skills")
    return jsonify({"skills": [s.name for s in skills_dir.iterdir() if s.is_dir()]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)