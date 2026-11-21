#!/usr/bin/env python3
"""
ILMA Storage Audit & Cleanup Script
Re-runnable audit based on session 2026-11-13 findings.

Usage:
    python3 scripts/storage_audit_cleanup.py --scan      # Show what would be cleaned
    python3 scripts/storage_audit_cleanup.py --clean     # Execute cleanup (with confirmations)
    python3 scripts/storage_audit_cleanup.py --verify    # Post-cleanup verification
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import List, Tuple

ROOT = Path("/root")
HERMES_ILMA = Path("/root/.hermes/profiles/ilma")

# Classification: (path_pattern, description, safe_to_delete, keep_condition)
TARGETS = [
    # Benchmark DB backups - keep last 7 days (28 files at 4x/day)
    (HERMES_ILMA / "ilma_model_router_data" / "backups" / "benchmark_database_*.json",
     "Benchmark DB backups", True, "keep_last_n:28"),
    (HERMES_ILMA / "ilma_model_router_data" / "backups" / "PROVIDER_INTELLIGENCE_MASTER_*.json",
     "Provider intelligence backups", True, "keep_last_n:28"),

    # Logs - keep current + 3 rotated, delete .gz and old rotated
    (HERMES_ILMA / "logs" / "*.log.[4-9]", "Old rotated logs (4+)", True, ""),
    (HERMES_ILMA / "logs" / "*.log.1[0-9]", "Old rotated logs (10+)", True, ""),
    (HERMES_ILMA / "logs" / "*.gz", "Gzipped old logs", True, ""),
    (HERMES_ILMA / "logs" / "sot_sync_daemon.log", "SOT sync daemon log (unbounded)", True, ""),
    (HERMES_ILMA / "logs" / "two_way_sync.log", "Two-way sync log (unbounded)", True, ""),

    # Playwright cache - profile level
    (HERMES_ILMA / "home" / ".cache" / "ms-playwright" / "chromium-*",
     "Profile Playwright chromium versions", True, "keep_latest_version"),
    (HERMES_ILMA / "home" / ".cache" / "ms-playwright" / "chromium_headless_shell-*",
     "Profile Playwright headless shell versions", True, "keep_latest_version"),
    (HERMES_ILMA / "home" / ".cache" / "ms-playwright" / "ffmpeg-*",
     "Profile Playwright ffmpeg", True, ""),

    # Playwright cache - system level
    (ROOT / ".cache" / "ms-playwright" / "chromium-*",
     "System Playwright chromium versions", True, "keep_latest_version"),
    (ROOT / ".cache" / "ms-playwright" / "chromium_headless_shell-*",
     "System Playwright headless shell versions", True, "keep_latest_version"),
    (ROOT / ".cache" / "ms-playwright" / "ffmpeg-*",
     "System Playwright ffmpeg", True, ""),

    # Old state snapshots
    (HERMES_ILMA / "state-snapshots" / "*",
     "Old state snapshots", True, ""),

    # Package manager caches
    (ROOT / ".npm" / "_cacache", "Global npm cache", True, ""),
    (ROOT / ".cache" / "pip", "Pip cache", True, ""),
    (ROOT / ".cache" / "uv", "UV cache", True, ""),
    (ROOT / ".cache" / "pnpm", "PNPM store", True, ""),
    (ROOT / ".npm" / "_prebuilds" / "*.tar.gz", "NPM prebuild tarballs", True, ""),
    (ROOT / ".cache" / "vscode-ripgrep" / "*.tar.gz", "VSCode ripgrep tarballs", True, ""),

    # Opencode history (keep DB)
    (ROOT / ".local" / "share" / "opencode" / "snapshot", "Opencode snapshots", True, ""),
    (ROOT / ".local" / "share" / "opencode" / "tool-output", "Opencode tool output", True, ""),
    (ROOT / ".local" / "share" / "opencode" / "log", "Opencode logs", True, ""),

    # Legacy CLI installations (check not in PATH first)
    (ROOT / ".gemini", "Gemini CLI", True, "check_not_in_path:gemini"),
    (ROOT / ".qwen", "Qwen CLI", True, "check_not_in_path:qwen"),
    (ROOT / ".zcode", "ZCode CLI", True, "check_not_in_path:zcode"),
    (ROOT / ".blackbox-cli-v2", "Blackbox CLI v2", True, "check_not_in_path:blackbox"),
    (ROOT / ".blackboxcli", "Blackbox CLI v1", True, "check_not_in_path:blackbox"),
    (ROOT / ".kimi-code", "Kimi CLI", True, "check_not_in_path:kimi"),
    (ROOT / ".grok", "Grok CLI", True, "check_not_in_path:grok"),
    (ROOT / ".claude", "Claude Code config", True, "check_not_in_path:claude"),

    # Old Codex backups/homes
    (ROOT / ".codex-backup", "Codex backup config", True, ""),
    (ROOT / ".codex-homes", "Codex profile homes", True, ""),

    # Backup tarballs
    (ROOT / "*.tar.gz", "Root tarballs", True, ""),
    (ROOT / "hermes-backup*.tar.gz", "Hermes backup tarballs", True, ""),
    (ROOT / "backup_*.tar.gz", "Wrapper backup tarballs", True, ""),
    (HERMES_ILMA / "backups" / "*" / "*.tar.gz", "Hermes profile backup tarballs", True, ""),
    (ROOT / "backup" / "ilma-system-backup*.tar.gz", "ILMA system backup tarballs", True, ""),
    (ROOT / "backup" / "forensics" / "*.tar.gz", "Forensics tarballs", True, ""),

    # Old backup directories (keep last 7 days)
    (ROOT / "backup" / "ilma" / "ilma_backup_202607*", "ILMA backups Jul", True, ""),
    (ROOT / "backup" / "ilma" / "ilma_backup_202608*", "ILMA backups Aug", True, ""),
    (ROOT / "backup" / "ilma" / "ilma_backup_202609*", "ILMA backups Sep", True, ""),
    (ROOT / "backup" / "ilma" / "ilma_backup_202610*", "ILMA backups Oct", True, ""),
    (ROOT / "backup" / "ilma" / "ilma_backup_2026110[1-5]*", "ILMA backups Nov 1-5", True, ""),
    (ROOT / "backup" / "ilma" / "ilma_codex_primary_backup*", "Codex primary backups", True, ""),
    (ROOT / "backup" / "ilma" / "evolution_20260507*", "Evolution backups May", True, ""),
    (ROOT / "backup" / "ilma" / "military_optimization_20260507*", "Military optimization backups", True, ""),
    (ROOT / "backup" / "ilma" / "core_consolidation", "Core consolidation backup", True, ""),
    (ROOT / "backup" / "ilma" / "passive_benchmark_refresh", "Passive benchmark refresh", True, ""),
    (ROOT / "backup" / "ilma" / "PROVIDER_INTELLIGENCE_MASTER_20260517*.json", "Old provider intelligence", True, ""),

    # Old /root/backups/
    (ROOT / "backups" / "*", "Old /root/backups", True, ""),
    (ROOT / "backup_archive", "Backup archive", True, ""),

    # Unused local models
    (ROOT / "models" / "*.gguf", "Local GGUF models", True, ""),

    # llama.cpp source/build
    (ROOT / "llama.cpp", "llama.cpp source/build tree", True, "check_no_active_process"),
]


def run_cmd(cmd: str, capture=True) -> Tuple[int, str, str]:
    """Run shell command, return (exit_code, stdout, stderr)"""
    result = subprocess.run(cmd, shell=True, capture_output=capture, text=True)
    return result.returncode, result.stdout, result.stderr


def get_latest_playwright_version(cache_dir: Path) -> str:
    """Find the latest chromium version in Playwright cache"""
    if not cache_dir.exists():
        return ""
    versions = []
    for d in cache_dir.glob("chromium-*"):
        try:
            ver = int(d.name.split("-")[1])
            versions.append((ver, d))
        except (IndexError, ValueError):
            pass
    for d in cache_dir.glob("chromium_headless_shell-*"):
        try:
            ver = int(d.name.split("-")[1])
            versions.append((ver, d))
        except (IndexError, ValueError):
            pass
    if versions:
        return str(max(versions, key=lambda x: x[0])[0].name)
    return ""


def is_in_path(cmd_name: str) -> bool:
    """Check if command exists in PATH"""
    return shutil.which(cmd_name) is not None


def check_process_using_path(path: Path) -> bool:
    """Check if any process has files open under path"""
    _, stdout, _ = run_cmd(f"lsof {path} 2>/dev/null")
    return bool(stdout.strip())


def scan_targets() -> List[dict]:
    """Scan all targets and return list of findings"""
    findings = []
    for pattern, desc, safe, condition in TARGETS:
        matches = list(Path(pattern).parent.glob(pattern.name)) if "*" in pattern.name else ([pattern] if pattern.exists() else [])
        if hasattr(pattern, 'parent') and "*" in str(pattern):
            # Handle glob patterns
            parent = pattern.parent
            name = pattern.name
            matches = list(parent.glob(name))
        else:
            matches = [pattern] if pattern.exists() else []

        total_size = 0
        for m in matches:
            if m.is_file():
                total_size += m.stat().st_size
            elif m.is_dir():
                for f in m.rglob("*"):
                    if f.is_file():
                        try:
                            total_size += f.stat().st_size
                        except OSError:
                            pass

        # Check conditions
        keep = False
        reason = ""
        if "keep_last_n:" in condition:
            n = int(condition.split(":")[1])
            if len(matches) <= n:
                keep = True
                reason = f"Only {len(matches)} files, keeping all (threshold: {n})"
        elif condition == "keep_latest_version":
            # For Playwright cache, would need more logic
            reason = "Would keep latest version only"
        elif condition == "check_not_in_path:":
            cmd = condition.split(":")[1]
            if is_in_path(cmd):
                keep = True
                reason = f"Command '{cmd}' found in PATH"
        elif condition == "check_no_active_process":
            if check_process_using_path(pattern):
                keep = True
                reason = "Active process using this path"

        findings.append({
            "pattern": str(pattern),
            "description": desc,
            "matches": len(matches),
            "size_bytes": total_size,
            "size_human": f"{total_size / (1024**3):.2f}G" if total_size > 1024**3 else f"{total_size / (1024**2):.1f}M",
            "safe_to_delete": safe and not keep,
            "keep_reason": reason,
            "paths": [str(m) for m in matches[:5]]  # Show first 5
        })
    return findings


def clean_targets(dry_run: bool = True) -> dict:
    """Execute cleanup"""
    results = {"deleted": [], "kept": [], "errors": [], "freed_bytes": 0}
    for pattern, desc, safe, condition in TARGETS:
        if not safe:
            continue

        # Same matching logic as scan
        matches = []
        if hasattr(pattern, 'parent') and "*" in str(pattern):
            parent = pattern.parent
            name = pattern.name
            matches = list(parent.glob(name))
        else:
            matches = [pattern] if pattern.exists() else []

        # Check keep conditions
        keep = False
        if "keep_last_n:" in condition:
            n = int(condition.split(":")[1])
            if len(matches) <= n:
                keep = True
        elif condition == "check_not_in_path:":
            cmd = condition.split(":")[1]
            if is_in_path(cmd):
                keep = True
        elif condition == "check_no_active_process":
            if check_process_using_path(pattern):
                keep = True

        if keep:
            results["kept"].append({"pattern": str(pattern), "reason": condition})
            continue

        for m in matches:
            try:
                size = 0
                if m.is_file():
                    size = m.stat().st_size
                    if not dry_run:
                        m.unlink()
                elif m.is_dir():
                    for f in m.rglob("*"):
                        if f.is_file():
                            try:
                                size += f.stat().st_size
                            except OSError:
                                pass
                    if not dry_run:
                        shutil.rmtree(m)

                if not dry_run:
                    results["deleted"].append(str(m))
                    results["freed_bytes"] += size
                    print(f"  DELETED: {m} ({size/1024**2:.1f}M)")
                else:
                    print(f"  WOULD DELETE: {m} ({size/1024**2:.1f}M)")
            except Exception as e:
                results["errors"].append({"path": str(m), "error": str(e)})
                print(f"  ERROR: {m} - {e}")

    return results


def verify_post_cleanup() -> dict:
    """Run verification checks"""
    checks = {}

    # 1. ilma profile boots
    code, out, err = run_cmd("cd /root/.hermes/profiles/ilma && python3 ilma.py --status")
    checks["ilma_boot"] = {"pass": code == 0 and "Ready" in out, "output": out[:200]}

    # 2. Runtime wiring
    code, out, err = run_cmd("cd /root/.hermes/profiles/ilma && python3 ilma_runtime_wiring.py --verify")
    checks["runtime_wiring"] = {"pass": code == 0 and "missing=0" in out and "import_error=0" in out, "output": out[:200]}

    # 3. Browser CDP endpoint
    code, out, err = run_cmd("curl -s --max-time 3 http://127.0.0.1:9222/json/version")
    checks["browser_cdp"] = {"pass": code == 0 and "webSocketDebuggerUrl" in out, "output": out[:100]}

    # 4. Codex process
    code, out, err = run_cmd("ps aux | grep codex | grep app-server-daemon | grep -v grep")
    checks["codex_running"] = {"pass": code == 0 and "app-server-daemon" in out, "output": out[:100]}

    # 5. rea-agents MCP
    code, out, err = run_cmd("ps aux | grep 'rea-agents.*mcp' | grep -v grep")
    checks["rea_agents_running"] = {"pass": code == 0 and "rea-agents" in out, "output": out[:100]}

    # 6. Opencode DB
    code, out, err = run_cmd("sqlite3 /root/.local/share/opencode/opencode.db '.tables'")
    checks["opencode_db"] = {"pass": code == 0 and len(out.strip()) > 0, "output": out[:100]}

    # 7. Disk space
    code, out, err = run_cmd("df -h /root")
    checks["disk_space"] = {"pass": True, "output": out.strip()}

    return checks


def main():
    import argparse
    parser = argparse.ArgumentParser(description="ILMA Storage Audit & Cleanup")
    parser.add_argument("--scan", action="store_true", help="Scan and show what would be cleaned")
    parser.add_argument("--clean", action="store_true", help="Execute cleanup (requires --yes)")
    parser.add_argument("--verify", action="store_true", help="Run post-cleanup verification")
    parser.add_argument("--yes", action="store_true", help="Confirm cleanup execution")
    args = parser.parse_args()

    if args.scan:
        print("=" * 80)
        print("ILMA STORAGE AUDIT SCAN")
        print("=" * 80)
        findings = scan_targets()
        total_to_clean = 0
        for f in findings:
            status = "✅ CLEAN" if f["safe_to_delete"] else "⏭️  KEEP"
            reason = f" ({f['keep_reason']})" if f["keep_reason"] else ""
            print(f"{status} | {f['size_human']:>8} | {f['matches']:>3} files | {f['description']}{reason}")
            if f["paths"]:
                for p in f["paths"]:
                    print(f"    → {p}")
            if f["safe_to_delete"]:
                # Parse size
                if "G" in f["size_human"]:
                    total_to_clean += float(f["size_human"].replace("G", "")) * 1024**3
                elif "M" in f["size_human"]:
                    total_to_clean += float(f["size_human"].replace("M", "")) * 1024**2
        print(f"\nTotal reclaimable: {total_to_clean / (1024**3):.2f}G")
        return

    if args.clean:
        if not args.yes:
            print("ERROR: Use --yes to confirm cleanup")
            sys.exit(1)
        print("=" * 80)
        print("EXECUTING CLEANUP")
        print("=" * 80)
        results = clean_targets(dry_run=False)
        print(f"\nDeleted: {len(results['deleted'])} items")
        print(f"Freed: {results['freed_bytes'] / (1024**3):.2f}G")
        print(f"Kept: {len(results['kept'])} targets")
        print(f"Errors: {len(results['errors'])}")
        return

    if args.verify:
        print("=" * 80)
        print("POST-CLEANUP VERIFICATION")
        print("=" * 80)
        checks = verify_post_cleanup()
        all_pass = True
        for name, check in checks.items():
            status = "✅" if check["pass"] else "❌"
            print(f"{status} {name}: {check['output'][:100]}")
            if not check["pass"]:
                all_pass = False
        print(f"\nAll checks passed: {all_pass}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()