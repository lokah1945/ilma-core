#!/usr/bin/env python3
"""
ILMA Project Registry v1.0  (2026-06-01)
========================================
Global, comprehensive metadata mapping so ILMA always knows WHAT projects exist,
their status, type, scope, and where their files live. This is a first-class part
of ILMA's self-model — a tidy structure for handling every project.

Storage layout (mandated):
  /root/project/external/<project_slug>/     # user-facing / delivered work
  /root/project/internal/<project_slug>/     # ILMA's own internal projects
Each project dir contains:
  project.json   (per-project metadata)
  research/      manifest, sources, evidence
  drafts/        section/chapter drafts
  figures/       generated images/charts
  exports/       pdf, docx, html, latex
  logs/

Global map:
  /root/project/registry.json   (index of ALL projects + active pointers)

CLI:
  python3 ilma_project_registry.py list
  python3 ilma_project_registry.py create --name "X" --type paper --scope external
  python3 ilma_project_registry.py show <slug>
  python3 ilma_project_registry.py set-status <slug> <status>
  python3 ilma_project_registry.py set-active <slug>
  python3 ilma_project_registry.py scan          # reconcile registry with disk
"""
from __future__ import annotations
import json, os, sys, re, time, argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path("/root/project")
EXTERNAL = PROJECT_ROOT / "external"
INTERNAL = PROJECT_ROOT / "internal"
REGISTRY = PROJECT_ROOT / "registry.json"

SUBDIRS = ["research", "drafts", "figures", "exports", "logs"]
VALID_TYPES = ["paper", "book", "novel", "blog", "report", "documentation", "thesis", "article", "other"]
VALID_STATUS = ["planned", "researching", "drafting", "reviewing", "exporting", "complete", "archived", "paused"]
VALID_SCOPE = ["external", "internal"]


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:60] or "project"


def _ensure_dirs():
    EXTERNAL.mkdir(parents=True, exist_ok=True)
    INTERNAL.mkdir(parents=True, exist_ok=True)


def _load_registry() -> Dict[str, Any]:
    if REGISTRY.exists():
        try:
            return json.loads(REGISTRY.read_text())
        except Exception:
            pass
    return {"_meta": {"version": "1.0", "created_at": _now()},
            "active_project": None, "projects": {}}


def _save_registry(reg: Dict[str, Any]):
    reg["_meta"]["updated_at"] = _now()
    tmp = REGISTRY.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(reg, indent=2, ensure_ascii=False))
    tmp.replace(REGISTRY)


def project_dir(slug: str, scope: str) -> Path:
    base = EXTERNAL if scope == "external" else INTERNAL
    return base / slug


def create_project(name: str, ptype: str = "other", scope: str = "external",
                   topic: str = "", doc_type: str = None, language: str = "id",
                   citation_style: str = "auto", depth: str = "deep",
                   description: str = "") -> Dict[str, Any]:
    _ensure_dirs()
    if ptype not in VALID_TYPES:
        ptype = "other"
    if scope not in VALID_SCOPE:
        scope = "external"
    slug = slugify(name)
    pdir = project_dir(slug, scope)
    # avoid collision
    if pdir.exists():
        slug = f"{slug}-{int(time.time()) % 100000}"
        pdir = project_dir(slug, scope)
    pdir.mkdir(parents=True, exist_ok=True)
    for sd in SUBDIRS:
        (pdir / sd).mkdir(exist_ok=True)

    meta = {
        "slug": slug, "name": name, "type": ptype, "scope": scope,
        "topic": topic or name, "doc_type": doc_type or ptype,
        "language": language, "citation_style": citation_style, "depth": depth,
        "description": description,
        "status": "planned", "progress": 0.0,
        "path": str(pdir),
        "created_at": _now(), "updated_at": _now(),
        "research_manifest": "research/manifest.json",
        "exports": [], "figures_count": 0, "sources_count": 0, "word_count": 0,
        "history": [{"ts": _now(), "event": "created"}],
    }
    (pdir / "project.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    reg = _load_registry()
    reg["projects"][slug] = {
        "slug": slug, "name": name, "type": ptype, "scope": scope,
        "status": "planned", "path": str(pdir), "updated_at": _now(),
    }
    if not reg.get("active_project"):
        reg["active_project"] = slug
    _save_registry(reg)
    return meta


def _read_meta(slug: str) -> Optional[Dict[str, Any]]:
    reg = _load_registry()
    p = reg["projects"].get(slug)
    if not p:
        return None
    mp = Path(p["path"]) / "project.json"
    if mp.exists():
        return json.loads(mp.read_text())
    return None


def update_project(slug: str, **fields) -> Optional[Dict[str, Any]]:
    meta = _read_meta(slug)
    if not meta:
        return None
    event = fields.pop("_event", None)
    meta.update(fields)
    meta["updated_at"] = _now()
    if event:
        meta.setdefault("history", []).append({"ts": _now(), "event": event})
    (Path(meta["path"]) / "project.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    reg = _load_registry()
    if slug in reg["projects"]:
        for k in ("status", "name", "type", "scope", "word_count", "sources_count", "figures_count"):
            if k in meta:
                reg["projects"][slug][k] = meta[k]
        reg["projects"][slug]["updated_at"] = _now()
        _save_registry(reg)
    return meta


def set_status(slug: str, status: str) -> Optional[Dict[str, Any]]:
    if status not in VALID_STATUS:
        return None
    return update_project(slug, status=status, _event=f"status->{status}")


def set_active(slug: str) -> bool:
    reg = _load_registry()
    if slug not in reg["projects"]:
        return False
    reg["active_project"] = slug
    _save_registry(reg)
    return True


def get_active() -> Optional[Dict[str, Any]]:
    reg = _load_registry()
    a = reg.get("active_project")
    return _read_meta(a) if a else None


def list_projects(scope: str = None, status: str = None) -> List[Dict[str, Any]]:
    reg = _load_registry()
    out = []
    for slug, p in reg["projects"].items():
        if scope and p.get("scope") != scope:
            continue
        if status and p.get("status") != status:
            continue
        out.append(p)
    return sorted(out, key=lambda x: x.get("updated_at", ""), reverse=True)


def scan() -> Dict[str, Any]:
    """Reconcile registry with disk (discover orphan project dirs)."""
    _ensure_dirs()
    reg = _load_registry()
    found = 0
    for scope, base in (("external", EXTERNAL), ("internal", INTERNAL)):
        for d in base.iterdir() if base.exists() else []:
            if not d.is_dir():
                continue
            mp = d / "project.json"
            if mp.exists():
                try:
                    meta = json.loads(mp.read_text())
                    slug = meta.get("slug", d.name)
                    if slug not in reg["projects"]:
                        reg["projects"][slug] = {
                            "slug": slug, "name": meta.get("name", slug),
                            "type": meta.get("type", "other"), "scope": scope,
                            "status": meta.get("status", "planned"),
                            "path": str(d), "updated_at": _now()}
                        found += 1
                except Exception:
                    pass
    _save_registry(reg)
    return {"discovered": found, "total": len(reg["projects"])}


def main():
    ap = argparse.ArgumentParser(description="ILMA Project Registry")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("create")
    c.add_argument("--name", required=True)
    c.add_argument("--type", default="other")
    c.add_argument("--scope", default="external")
    c.add_argument("--topic", default="")
    c.add_argument("--doc-type", default=None)
    c.add_argument("--language", default="id")
    c.add_argument("--citation-style", default="auto")
    c.add_argument("--depth", default="deep")
    c.add_argument("--description", default="")
    sub.add_parser("list").add_argument("--scope", default=None)
    s = sub.add_parser("show"); s.add_argument("slug")
    ss = sub.add_parser("set-status"); ss.add_argument("slug"); ss.add_argument("status")
    sa = sub.add_parser("set-active"); sa.add_argument("slug")
    sub.add_parser("active")
    sub.add_parser("scan")
    a = ap.parse_args()

    if a.cmd == "create":
        m = create_project(a.name, a.type, a.scope, a.topic, a.doc_type,
                           a.language, a.citation_style, a.depth, a.description)
        print(json.dumps(m, indent=2, ensure_ascii=False))
    elif a.cmd == "list":
        for p in list_projects(scope=getattr(a, "scope", None)):
            print(f"  [{p['status']:11}] {p['scope']:8} {p['slug']:30} ({p['type']})")
    elif a.cmd == "show":
        m = _read_meta(a.slug)
        print(json.dumps(m, indent=2, ensure_ascii=False) if m else "not found")
    elif a.cmd == "set-status":
        print("ok" if set_status(a.slug, a.status) else "failed")
    elif a.cmd == "set-active":
        print("ok" if set_active(a.slug) else "failed")
    elif a.cmd == "active":
        m = get_active()
        print(json.dumps(m, indent=2, ensure_ascii=False) if m else "no active project")
    elif a.cmd == "scan":
        print(json.dumps(scan(), indent=2))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
