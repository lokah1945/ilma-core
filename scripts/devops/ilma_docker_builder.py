#!/usr/bin/env python3
"""
ILMA Docker Builder
=================
Docker image build and push automation.
"""

import sys
import subprocess
from pathlib import Path

def build_image(name, tag="latest", dockerfile="Dockerfile", context="."):
    """Build Docker image."""
    import shlex
    cmd = f"docker build -t {name}:{tag} -f {dockerfile} {context}"
    print(f"Building: {cmd}")
    cmd_list = ["docker", "build", "-t", f"{name}:{tag}", "-f", dockerfile, context]
    subprocess.run(cmd_list, capture_output=True, text=True)
    print(f"✅ Built: {name}:{tag}")

def push_image(name, tag="latest"):
    """Push to registry."""
    cmd = f"docker push {name}:{tag}"
    print(f"Pushing: {cmd}")
    cmd_list = ["docker", "push", f"{name}:{tag}"]
    subprocess.run(cmd_list, capture_output=True, text=True)
    print(f"✅ Pushed: {name}:{tag}")

def list_images():
    """List ILMA images."""
    subprocess.run(["docker", "images"], capture_output=True, text=True)

def main():
    if len(sys.argv) < 2:
        print("Usage: ilma_docker_builder.py <action> [args]")
        return
    
    action = sys.argv[1]
    
    if action == "build":
        name = sys.argv[2] if len(sys.argv) > 2 else "ilma/app"
        tag = sys.argv[3] if len(sys.argv) > 3 else "latest"
        build_image(name, tag)
    elif action == "push":
        name = sys.argv[2] if len(sys.argv) > 2 else "ilma/app"
        tag = sys.argv[3] if len(sys.argv) > 3 else "latest"
        push_image(name, tag)
    elif action == "list":
        list_images()

if __name__ == "__main__":
    main()