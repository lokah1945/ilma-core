#!/usr/bin/env python3
"""
ILMA Kubernetes Deploy
====================
Kubernetes deployment automation.
"""

import subprocess

def k8s_cmd(cmd):
    import shlex
    cmd_list = ["kubectl"] + shlex.split(cmd) if isinstance(cmd, str) else ["kubectl"] + list(cmd)
    return subprocess.run(cmd_list, capture_output=True, text=True)

def get_pods():
    return k8s_cmd("get pods")

def get_services():
    return k8s_cmd("get svc")

def get_deployments():
    return k8s_cmd("get deployments")

def scale(deployment, replicas):
    return k8s_cmd(f"scale deployment {deployment} --replicas={replicas}")

def rollout_restart(deployment):
    return k8s_cmd(f"rollout restart deployment/{deployment}")

def apply_yaml(file):
    return k8s_cmd(f"apply -f {file}")

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--pods", action="store_true")
    p.add_argument("--svc", action="store_true")
    p.add_argument("--deploy", action="store_true")
    p.add_argument("--scale")
    p.add_argument("--restart")
    p.add_argument("--apply")
    args = p.parse_args()
    if args.pods: print(get_pods().stdout)
    elif args.svc: print(get_services().stdout)
    elif args.deploy: print(get_deployments().stdout)
    elif args.scale:
        d, r = args.scale.split(":")
        print(scale(d, r).stdout)

if __name__ == "__main__": main()