#!/usr/bin/env python3
"""
ILMA Longform Generator v1.0  (2026-06-01)
==========================================
Closes the longform_writing_1000plus gap: drives the existing ChapterManager
scaffolding (outline/continuity/validation/export) through REAL model generation
via the free-only subagent router, chapter-by-chapter, with:
  - per-chapter generation (router-selected longform_writing model)
  - continuity context injection (prior chapter summaries)
  - structure validation + automatic retry on failure
  - incremental persistence + export (markdown)
  - resumable (skips already-written chapters)
  - word/page accounting (page ~= 275 words) -> projects to 1000+ pages

Usage:
  python3 ilma_longform_generator.py --title "X" --chapters 25 --project novel \
        --out ./output/mybook [--max-chapters 3] [--words-per-chapter 1200]
"""
from __future__ import annotations
import sys, os, json, time, argparse, re
from pathlib import Path
from typing import Optional, List, Dict, Any

ILMA_ROOT = Path("/root/.hermes/profiles/ilma")
if str(ILMA_ROOT) not in sys.path:
    sys.path.insert(0, str(ILMA_ROOT))
sys.path.insert(0, str(ILMA_ROOT / "scripts"))

WORDS_PER_PAGE = 275


def _gen(prompt: str, role: str = "longform_writing", timeout: int = 150) -> Dict[str, Any]:
    """Generate text via the free-only subagent router."""
    from ilma_subagent_router import SubAgentRouter
    sa = SubAgentRouter()
    try:
        res = sa.route_and_execute(message=prompt, task_type_or_desc="writing",
                                   allow_paid=False)
        return {"ok": bool(res.get("success")) and bool((res.get("content") or "").strip()),
                "content": res.get("content", ""), "model": res.get("model"),
                "error": res.get("error", "")}
    finally:
        try:
            sa.close()
        except Exception:
            pass


def _count_words(t: str) -> int:
    return len(re.findall(r"\b\w+\b", t or ""))


def _plan_outline(title: str, project: str, chapters: int, synopsis: str) -> List[str]:
    """LLM-generate a real per-chapter beat/synopsis (replaces placeholder
    'Chapter N synopsis - to be written'). Returns a list of `chapters` beat
    strings; falls back to generic beats if the model is unavailable."""
    prompt = (
        f"You are a story architect. Plan '{title}', a {project}, in EXACTLY {chapters} chapters.\n"
        f"{('Premise/synopsis: ' + synopsis) if synopsis else ''}\n"
        f"For each chapter output one line: 'N. <what concretely happens — events, which "
        f"characters, what changes>'. Keep continuity and rising tension across chapters. "
        f"Output ONLY the {chapters} numbered lines."
    )
    beats = [""] * (chapters + 1)  # 1-indexed
    gen = _gen(prompt, role="planning")
    if gen.get("ok"):
        for line in (gen.get("content") or "").splitlines():
            m = re.match(r"\s*(\d+)[\.\)]\s*(.+)", line)
            if m:
                idx = int(m.group(1))
                if 1 <= idx <= chapters:
                    beats[idx] = m.group(2).strip()
    return beats


def _update_story_state(prev_state: str, chapter_text: str, n: int) -> str:
    """Maintain a compact rolling 'story bible so far' (characters, established
    facts, unresolved threads, timeline) — real continuity, not a 200-char prefix.
    Text-based (robust, no fragile JSON parsing). Capped to keep prompts bounded."""
    prompt = (
        "Update the running STORY STATE after this chapter. Output a concise bible with "
        "sections: CHARACTERS (name: one-line status), FACTS established, OPEN THREADS, "
        "TIMELINE. Merge with the previous state; keep it under 350 words.\n\n"
        f"PREVIOUS STATE:\n{prev_state or '(none yet)'}\n\n"
        f"NEW CHAPTER {n} TEXT:\n{chapter_text[:6000]}"
    )
    gen = _gen(prompt, role="reasoning")
    if gen.get("ok") and (gen.get("content") or "").strip():
        return gen["content"].strip()[:2400]
    # fallback: append a trimmed digest so continuity never fully regresses
    return (prev_state + f"\n[Ch{n}] " + " ".join(chapter_text.split())[:300]).strip()[:2400]


def generate_book(title: str, chapters: int, project: str = "novel",
                  out_dir: str = "./output/book", max_chapters: Optional[int] = None,
                  words_per_chapter: int = 1200, synopsis: str = "") -> Dict[str, Any]:
    from ilma_longform_orchestrator import ChapterManager, ContentType, ChapterStatus

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ctype = ContentType(project)
    mgr = ChapterManager(title, ctype)
    outlines = mgr.create_project_outline(chapters)
    mgr.initialize_chapters(outlines)

    # resume support
    manifest_path = out / "manifest.json"
    done = {}
    if manifest_path.exists():
        try:
            done = json.loads(manifest_path.read_text()).get("chapters", {})
        except Exception:
            done = {}

    to_write = chapters if max_chapters is None else min(max_chapters, chapters)
    results = []
    t0 = time.time()

    # Real LLM outline (replaces placeholder 'Chapter N - to be written' synopses).
    beats = _plan_outline(title, project, chapters, synopsis)
    # Rolling story-state ("bible so far") — real cross-chapter continuity.
    story_state = ""

    for n in range(1, to_write + 1):
        ch = mgr.get_chapter(n)
        cid = ch.outline.chapter_id
        ch_file = out / f"{cid}.md"
        beat = beats[n] if n < len(beats) else ""

        if str(n) in done and ch_file.exists():
            txt = ch_file.read_text()
            mgr.update_chapter_content(n, txt, ChapterStatus.COMPLETE if hasattr(ChapterStatus, "COMPLETE") else None)
            story_state = _update_story_state(story_state, txt, n)
            results.append({"chapter": n, "status": "skipped(existing)", "words": _count_words(txt)})
            continue

        prompt = (
            f"You are writing '{title}', a {project}. Write Chapter {n} of {chapters}.\n"
            f"{('Overall premise: ' + synopsis) if synopsis else ''}\n"
            f"{('THIS CHAPTER MUST COVER: ' + beat) if beat else ''}\n"
            f"{('STORY SO FAR (keep strict continuity with this — names, facts, threads, timeline):' + chr(10) + story_state) if story_state else ''}\n"
            f"Write a complete, coherent Chapter {n} of about {words_per_chapter} words. "
            f"Maintain consistent characters, tone, and plot established above. Output ONLY the "
            f"chapter prose (start with a chapter heading).\n"
        )

        # generate + retry
        attempt = 0
        gen = {"ok": False}
        while attempt < 2 and not gen.get("ok"):
            attempt += 1
            gen = _gen(prompt)
        content = gen.get("content", "")
        words = _count_words(content)

        # length control: continuation loop (re-prompt "continue") until target met
        cont_tries = 0
        target_floor = max(150, int(words_per_chapter * 0.7))
        while gen.get("ok") and words < target_floor and cont_tries < 3:
            cont_tries += 1
            cg = _gen(prompt + f"\n\nSo far you wrote:\n{content[-2000:]}\n\nContinue the SAME "
                      f"chapter from where it stopped (do not repeat); keep writing until it is "
                      f"a complete ~{words_per_chapter}-word chapter.")
            if cg.get("ok") and cg.get("content", "").strip():
                content = (content + "\n" + cg["content"]).strip()
                words = _count_words(content)
            else:
                break

        if gen.get("ok") and content.strip():
            ch_file.write_text(content)
            mgr.update_chapter_content(n, content)
            done[str(n)] = {"file": ch_file.name, "words": words, "model": gen.get("model")}
            # update rolling continuity state from the actual prose just written
            story_state = _update_story_state(story_state, content, n)
            results.append({"chapter": n, "status": "written", "words": words,
                            "model": gen.get("model"), "beat": beat[:80]})
        else:
            results.append({"chapter": n, "status": "failed", "error": gen.get("error", "")[:120]})

    # persist the continuity bible for inspection / resume
    if story_state:
        (out / "story_state.md").write_text(story_state)

        # incremental manifest
        manifest_path.write_text(json.dumps({
            "title": title, "project": project, "chapters_total": chapters,
            "chapters_written": len(done), "chapters": done,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }, indent=2))

    total_words = sum(d["words"] for d in done.values())
    # assemble full book
    book_md = out / "book.md"
    with open(book_md, "w") as f:
        f.write(f"# {title}\n\n")
        for n in range(1, chapters + 1):
            cid = f"ch_{n:03d}"
            cf = out / f"{cid}.md"
            if cf.exists():
                f.write(cf.read_text() + "\n\n")

    summary = {
        "title": title, "chapters_total": chapters,
        "chapters_written": len(done), "total_words": total_words,
        "projected_pages": round(total_words / WORDS_PER_PAGE, 1),
        "avg_words_per_chapter": round(total_words / max(1, len(done)), 0),
        "projected_pages_full_book": round((total_words / max(1, len(done))) * chapters / WORDS_PER_PAGE, 1),
        "wall_clock_s": round(time.time() - t0, 1),
        "out_dir": str(out), "results": results,
    }
    (out / "generation_report.json").write_text(json.dumps(summary, indent=2))
    return summary



def generate_book_parallel(title: str, chapters: int, project: str = "novel",
                           out_dir: str = "./output/book", max_chapters=None,
                           words_per_chapter: int = 1200, synopsis: str = "",
                           max_workers: int = 4, batch_size: int = 6) -> Dict[str, Any]:
    """Parallel longform generation for large books (1000+ pages).

    Strategy: outline-anchored parallelism. All chapters share the global outline
    + synopsis as context (so they stay coherent), generated in concurrent batches.
    A light continuity note (prev/next outline) is injected per chapter.
    """
    from ilma_longform_orchestrator import ChapterManager, ContentType, ChapterStatus
    sys.path.insert(0, str(ILMA_ROOT))
    from ilma_massive_subagent import fan_out

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    mgr = ChapterManager(title, ContentType(project))
    outlines = mgr.create_project_outline(chapters)
    mgr.initialize_chapters(outlines)

    # outline summary map for cross-chapter coherence
    def _ol(n):
        try:
            o = mgr.get_chapter(n).outline
            return f"Ch{n}: {getattr(o,'title','')} - {getattr(o,'summary','') or getattr(o,'description','')}"
        except Exception:
            return f"Ch{n}"
    outline_map = {n: _ol(n) for n in range(1, chapters + 1)}
    global_ctx = ("Synopsis: " + synopsis + "\n" if synopsis else "") + \
                 "Full outline:\n" + "\n".join(outline_map.values())[:2500]

    manifest_path = out / "manifest.json"
    done = {}
    if manifest_path.exists():
        try:
            done = json.loads(manifest_path.read_text()).get("chapters", {})
        except Exception:
            done = {}

    to_write = chapters if max_chapters is None else min(max_chapters, chapters)
    pending = [n for n in range(1, to_write + 1)
               if not (str(n) in done and (out / f"ch_{n:03d}.md").exists())]
    t0 = time.time()
    results = []

    def _prompt(n):
        nbr = "\n".join(outline_map.get(k, "") for k in (n - 1, n, n + 1) if 1 <= k <= chapters)
        return (f"You are writing '{title}', a {project}. Write Chapter {n} of {chapters}.\n"
                f"{global_ctx}\n\nFocus (this + adjacent chapters):\n{nbr}\n\n"
                f"Write a complete, coherent Chapter {n} of about {words_per_chapter} words. "
                f"Keep characters/tone/plot consistent with the outline. "
                f"Output ONLY the chapter prose, starting with a chapter heading.\n")

    # process in batches to bound memory
    for i in range(0, len(pending), batch_size):
        batch = pending[i:i + batch_size]
        units = [{"id": n, "task": _prompt(n), "role": "writing"} for n in batch]
        fr = fan_out(units, role="writing", max_workers=max_workers,
                     allow_paid=False, per_task_timeout=180)
        for r in fr["results"]:
            n = r["id"]
            content = r.get("content", "")
            words = _count_words(content)
            if r.get("ok") and content.strip():
                cf = out / f"ch_{n:03d}.md"
                cf.write_text(content)
                done[str(n)] = {"file": cf.name, "words": words, "model": r.get("model")}
                results.append({"chapter": n, "status": "written", "words": words, "model": r.get("model")})
            else:
                results.append({"chapter": n, "status": "failed", "error": r.get("error", "")[:120]})
        manifest_path.write_text(json.dumps({
            "title": title, "project": project, "chapters_total": chapters,
            "chapters_written": len(done), "chapters": done,
            "mode": "parallel", "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }, indent=2))

    total_words = sum(d["words"] for d in done.values())
    book_md = out / "book.md"
    with open(book_md, "w") as f:
        f.write(f"# {title}\n\n")
        for n in range(1, chapters + 1):
            cf = out / f"ch_{n:03d}.md"
            if cf.exists():
                f.write(cf.read_text() + "\n\n")

    summary = {
        "title": title, "chapters_total": chapters, "chapters_written": len(done),
        "total_words": total_words, "projected_pages": round(total_words / WORDS_PER_PAGE, 1),
        "avg_words_per_chapter": round(total_words / max(1, len(done)), 0),
        "projected_pages_full_book": round((total_words / max(1, len(done))) * chapters / WORDS_PER_PAGE, 1),
        "wall_clock_s": round(time.time() - t0, 1), "mode": "parallel",
        "max_workers": max_workers, "out_dir": str(out), "results": results,
    }
    (out / "generation_report.json").write_text(json.dumps(summary, indent=2))
    return summary


def main():
    ap = argparse.ArgumentParser(description="ILMA Longform Generator (real generation)")
    ap.add_argument("--title", required=True)
    ap.add_argument("--chapters", type=int, default=25)
    ap.add_argument("--project", default="novel", choices=["novel", "technical_book", "textbook", "research_paper"])
    ap.add_argument("--out", default="./output/book")
    ap.add_argument("--max-chapters", type=int, default=None)
    ap.add_argument("--words-per-chapter", type=int, default=1200)
    ap.add_argument("--synopsis", default="")
    ap.add_argument("--parallel", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    if a.parallel:
        s = generate_book_parallel(a.title, a.chapters, a.project, a.out, a.max_chapters,
                                   a.words_per_chapter, a.synopsis, max_workers=a.workers)
    else:
        s = generate_book(a.title, a.chapters, a.project, a.out, a.max_chapters,
                          a.words_per_chapter, a.synopsis)
    print(json.dumps({k: v for k, v in s.items() if k != "results"}, indent=2))
    for r in s["results"]:
        print(f"  Ch{r['chapter']}: {r['status']} ({r.get('words','-')} words) {r.get('model','')}")


if __name__ == "__main__":
    main()
