# Phase 65: Execution vs Planning — Behavioral Pattern

## Context

Session 2026-05-24 — User gave a clear, well-defined task:
> "Apakah sudah selesai task dan progress terakhir anda? Seperti nya kok berhenti di sini... Mari saya bangun arsitektur lengkapnya. Saya sudah tahu: benchmark_aa_db.json tidak ada, AA website SPA/Next.js, 284 models sudah punya benchmark_aa data, API key sudah ada. Sekarang saya bangun arsitektur scrap..."

User had ALREADY done the analysis. The task was to BUILD, not to plan.

## The Pattern

ILMA keeps stopping at the "architecture design" phase and not executing.

**Symptom:**
1. User gives a task with clear context and plan already figured out
2. ILMA responds with "🧠 BERPIKIR" + architecture description
3. User says "Anda stuck lagi dan proses anda berhenti"
4. ILMA executes something unrelated instead of the actual task
5. User has to repeat the reminder multiple times

**What happened in this session:**
- User said "Mari saya bangun arsitektur lengkapnya" → task was BUILD
- ILMA responded: "Saya akan bangun 3 komponen sekaligus: 1. AA Sc" → stopped at plan
- User: "anda stuck lagi dan proses anda berhenti"  
- ILMA executed `git add ilma_model_registry.py` (unrelated fix) → still didn't build the scraper
- User never got the AA scraper built

## Root Cause

ILMA has a tendency to:
1. Read the situation → describe what needs to be done → stop
2. Confuse "understanding the architecture" with "executing the architecture"
3. When interrupted, switch to unrelated cleanup tasks instead of returning to the original task

## The Fix

**Trigger:** User provides a task with context that says "saya sudah tahu..." or "already analyzed" or gives you the plan — this means EXECUTE, not plan.

**Rule:** When user says "Mari saya bangun..." or "sekarang saya akan..." — they are NOT asking for your architecture plan. They are telling you to BUILD.

**Execution pattern for this trigger:**
1. Say "Saya mulai build sekarang" — minimal, no architecture description
2. Start writing the actual code/files immediately
3. Stream progress with short labels: "🔧 Membuat scraper..." → "✅ Scraper selesai" → "🔧 Testing..."
4. Only report completion when ALL steps done

**What to NOT do:**
- Do not spend time on "🧠 BERPIKIR: saya akan bangun 3 komponen..." before starting
- Do not explain what you are about to build — just build it
- Do not switch to unrelated tasks when interrupted — return to the original task
- Do not do cleanup/prep work before executing the actual task the user asked for

## Verification

After any "Mari saya bangun..." task:
- [ ] Code files actually created in filesystem
- [ ] Not just described in chat
- [ ] User receives working artifacts, not architecture descriptions