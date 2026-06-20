#!/usr/bin/env python3
"""
ilma_git_guard.py — pre-commit/push secret guard for the autonomy loop (C2, 2026-06-20)
=======================================================================================
The autonomy loop does `git add -A` + commit + `git push origin master` as root every
cycle. That is a credential-leak vector: any secret that lands in the tree gets pushed.
This guard scans the STAGED diff (added lines only) for secret patterns; the caller
aborts the commit/push if anything is found.

API:
  scan_staged(repo) -> list[(kind, sample)]   # secrets in the staged diff
  safe_to_commit(repo) -> (bool, list)        # (ok, findings)
Env escape hatch: ILMA_AUTONOMY_NO_PUSH=1 → callers skip push entirely.
"""
import os, re, subprocess

SECRET_PATTERNS = [
    (re.compile(r"nvapi-[A-Za-z0-9_\-]{24,}"), "nvidia_key"),
    (re.compile(r"sk-or-v1-[A-Za-z0-9]{24,}"), "openrouter_key"),
    (re.compile(r"sk-proj-[A-Za-z0-9_\-]{20,}"), "openai_proj_key"),
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "anthropic_key"),
    (re.compile(r"sk-[A-Za-z0-9]{32,}"), "generic_sk_key"),
    (re.compile(r"gsk_[A-Za-z0-9]{30,}"), "groq_key"),
    (re.compile(r"csk-[A-Za-z0-9]{30,}"), "cerebras_key"),
    (re.compile(r"AIza[A-Za-z0-9_\-]{30,}"), "google_key"),
    (re.compile(r"tgp_v1_[A-Za-z0-9_\-]{20,}"), "together_key"),
    (re.compile(r"xai-[A-Za-z0-9]{60,}"), "xai_key"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private_key"),
    # JWT / OAuth tokens (the auth.json leak class, 2026-06-20): header.payload.sig
    (re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"), "jwt_token"),
    (re.compile(r"\brt_[A-Za-z0-9]{20,}"), "refresh_token"),
    (re.compile(r"(?i)\b(access[_-]?token|refresh[_-]?token|agent[_-]?key|bearer)\b\s*[:=]\s*[\"']?[A-Za-z0-9._\-]{16,}"),
     "oauth_token_assignment"),
    (re.compile(r"(?i)(password|passwd|secret|api[_-]?key|auth[_-]?token)\s*[:=]\s*[\"'][^\"'\s]{12,}[\"']"),
     "generic_secret_assignment"),
]

# Fail-closed filename denylist: these files must NEVER be committed regardless of
# their content (defense-in-depth in case a value pattern is missed). Matched against
# the staged path basename and full path.
DENYLIST_PATTERNS = [
    re.compile(r"(^|/)auth\.json$"),
    re.compile(r"(^|/)auth\.lock$"),
    re.compile(r"(^|/)\.env(\.|$)"),
    re.compile(r"(?i)credential"),
    re.compile(r"(?i)(^|/)[^/]*secret[^/]*$"),
    re.compile(r"(?i)(^|/)[^/]*token[^/]*\.json$"),
    re.compile(r"(?i)(^|/)id_(rsa|ed25519|ecdsa)(\.pub)?$"),
]


def _dynamic_secret_values() -> set:
    """Load the ACTUAL secret values (e.g. the mongo password) from env/.env so we can
    detect them WITHOUT hardcoding any literal in this source file."""
    vals = set()
    for k in ("ILMA_MONGO_PASS",):
        v = os.environ.get(k)
        if not v:
            try:
                for line in open("/root/.hermes/.env"):
                    if line.startswith(k + "="):
                        v = line.split("=", 1)[1].strip()
                        break
            except Exception:
                pass
        if v and len(v) >= 6:
            vals.add(v)
    return vals


_DYNAMIC_SECRETS = _dynamic_secret_values()


def _scan_staged_filenames(repo: str) -> list:
    """Fail-closed: flag any staged path matching the secret-file denylist."""
    try:
        # --diff-filter=ACMR: only Added/Copied/Modified/Renamed (NOT Deleted), so
        # committing the REMOVAL of a denylisted file is still allowed.
        names = subprocess.run(["git", "-C", repo, "diff", "--cached",
                                "--name-only", "--diff-filter=ACMR"],
                               capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return []
    found = []
    for path in names.splitlines():
        path = path.strip()
        if not path:
            continue
        for pat in DENYLIST_PATTERNS:
            if pat.search(path):
                found.append(("denylisted_file", path))
                break
    return found


def scan_staged(repo: str) -> list:
    """Secrets found in newly-ADDED staged lines + denylisted staged filenames.
    Returns [(kind, masked_sample), ...]."""
    found = _scan_staged_filenames(repo)
    try:
        diff = subprocess.run(["git", "-C", repo, "diff", "--cached", "--unified=0"],
                              capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return found
    for line in diff.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for pat, kind in SECRET_PATTERNS:
            m = pat.search(line)
            if m:
                tok = m.group(0)
                found.append((kind, (tok[:8] + "…") if len(tok) > 10 else "***"))
        # dynamic: the real configured secret values (mongo password, etc.)
        for sv in _DYNAMIC_SECRETS:
            if sv in line:
                found.append(("configured_secret", "***"))
    return found


def safe_to_commit(repo: str):
    findings = scan_staged(repo)
    return (len(findings) == 0, findings)


def push_allowed() -> bool:
    return os.environ.get("ILMA_AUTONOMY_NO_PUSH", "") not in ("1", "true", "yes")


if __name__ == "__main__":
    import sys
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    ok, f = safe_to_commit(repo)
    print("SAFE" if ok else f"BLOCKED: {f}")
    sys.exit(0 if ok else 1)
