---
name: ilma-optimal-standards
description: ILMA optimal optimization standards — binding definition of "OPTIMAL" from Bos. Load before ANY optimization task. Contains 5 standards with detailed implementation specs.
triggers:
  - "optimal"
  - "optimasi"
  - "optimization"
  - "make it better"
  - "improve performance"
  - "system optimization"
  - "efektif efisien"
  - "standar optimal"
  - "production ready"
  - "self-healing"
tags: [system, optimization, standards, compliance, CI/CE, memory, orchestration, stealth, production]
created: 2026-05-08
updated: 2026-05-08
---

# ILMA Optimal Standards — SKILL

## MANDATORY PRE-LOAD
Every time Bos asks for optimization → load this skill first.

---

## 5 STANDARDS OF OPTIMAL

### STANDARD 1: Otonomi Sistem & Evolusi End-to-End

| Komponen | Definisi | Status |
|----------|----------|--------|
| CI/CE Autonomous Loop | Analisis kode → deteksi masalah → auto-repair → tanpa human-in-the-loop | ⚠️ PARTIAL |
| Self-Healing Code | Deteksi stack trace → diagnosa AI → rewrite otomatis → verified via test | ⚠️ PARTIAL |
| Dynamic Sub-Agent | Generate sub-agent saat runtime untuk edge-cases, isolated memory | ✅ VERIFIED |
| On-Demand Tool Synthesis | Write Python/Bash module dynamically, load as new tool | 🔴 GAP |
| Recursive Feedback Loop | Generate → Critique → Improve → repeat until target | ⚠️ PARTIAL |

### STANDARD 2: Orkestrasi Multi-Agent & Resource Routing

| Komponen | Definisi | Status |
|----------|----------|--------|
| Orchestrator-Worker Pattern | Master reasoning tinggi, workers handle repetitif | ✅ VERIFIED |
| Parallelism | Total latency ≈ slowest step, not sum of all steps | ✅ VERIFIED |
| Asymmetric Allocation | Complex→high-cap, Simple→low-cap, Explore new, Exploit best | ⚠️ PARTIAL |
| Message Brokering | Spike absorption, queue, retry, dead letter queue, TTL, dedup | ⚠️ PARTIAL |
| Context Management | Structured context objects, SummaryBufferMemory | ⚠️ PARTIAL |
| Error Handling + Rate Limiting | Timeout, retry exp backoff+jitter, circuit breaker | ✅ VERIFIED |

### STANDARD 3: Manajemen Memori & Integritas Konteks

| Komponen | Definisi | Status |
|----------|----------|--------|
| Truncation Protection | Proteksi absolut bootstrap files dari pemotongan paksa | ⚠️ PARTIAL |
| Tiered Memory | Short-term (task aktif) ↔ Long-term (knowledge base) enforced | 🔴 GAP |
| Entity/Knowledge Graph | Ekstrak fakta terstruktur, no-LLM retrieval | ✅ VERIFIED |
| Vector RAG | Hybrid vector store + knowledge graph, token -6-7× | 🔴 GAP |
| Auto-Summarization | 100 turns → 2-3K tokens via ConversationSummaryMemory | 🔴 GAP |
| Distributed State Sync | Central DB (Redis/PG), indexed by conversation_id | 🔴 GAP |

### STANDARD 4: Eksekusi Web & Otomatisasi Stealth

| Komponen | Definisi | Status |
|----------|----------|--------|
| Advanced Stealth Browser | Chromium dengan 4.000+ fingerprint patches di C++ level | 🔴 GAP |
| Fingerprint Rotation | Konsisten GPU/font/resolusi per session, bukan random | 🔴 GAP |
| Canvas Spoofing | Profile-based, bukan random (random tidak efektif) | 🔴 GAP |
| Browser Specialization | Persistent session, proxy rotation, CAPTCHA bypass, HTML→Markdown | ⚠️ PARTIAL |
| Sandbox Execution | Isolated environment untuk generated code | ✅ VERIFIED |
| Session Cookie Injection | TLS resumption, auto-auth, session cache | ⚠️ PARTIAL |
| Proxy Fallback | Residential proxy + UA rotation saat anomaly detected | 🔴 GAP |

### STANDARD 5: Production-Ready & Telemetri Pasif

| Komponen | Definisi | Status |
|----------|----------|--------|
| Decoupled Architecture | LLM Logic ↔ Memory State ↔ Execution Tools, strict separation | ⚠️ PARTIAL |
| Silent Async Telemetry | Trace token/decision/tool-calls, non-blocking background | 🔴 GAP |
| Passive Push Notification | Webhook/MQ, scheduled delivery, TTL, no workflow block | 🔴 GAP |
| Global Error Handler | Wrap all API calls: timeout + retry + fallback + circuit breaker | ⚠️ PARTIAL |
| Autonomous Rate-Limiting | Quota monitoring, speed control, sesuai endpoint regulations | ✅ VERIFIED |

---

## CRITICAL GAPS (10 gaps)

### Prioritas Tinggi
1. 🔴 Vector RAG — ChromaDB/Qdrant integration needed
2. 🔴 Tiered Memory Architecture — enforced short-term vs long-term
3. 🔴 On-Demand Tool Synthesis — runtime script generation
4. 🔴 Proxy Fallback System — residential proxy rotation
5. 🔴 Canvas Fingerprint Spoofing — profile-based stealth
6. 🔴 Passive Push Notification — automatic webhook delivery

### Prioritas Sedang
7. 🔴 SummaryBufferMemory — conversation compression
8. 🔴 Silent Async Telemetry — background thread logging
9. 🔴 Self-Healing Runtime — auto-patch + verification pipeline
10. 🔴 Distributed State Sync — Redis integration

---

## COMPLIANCE CHECKLIST (WAJIB)

```
□ Load skill: ilma-optimal-standards
□ Baca: docs/ILMA_OPTIMAL_STANDARDS.md

STANDAR 1: Otonomi CI/CE? Self-healing? Dynamic sub-agent? On-demand tools?
STANDAR 2: Cognitive isolation? Message brokering? Context management?
STANDAR 3: Truncation protection? Tiered memory? Vector RAG?
STANDAR 4: Stealth browser? Fingerprint rotation? Sandbox? Proxy fallback?
STANDAR 5: Decoupled? Silent telemetry? Global error handler? Rate-limiting?

QUALITY:
□ No redundancy — duplikasi file/function/process?
□ No overlap — tumpang tindih tanggung jawab?
□ Evidence — setiap aksi ada evidence_id?
□ Reversible — backup di .deprecated/ sebelum hapus?
□ Verifiable — benchmark sebelum/sesudah?
```

---

## Reference Documents
- Full detail: `docs/ILMA_OPTIMAL_STANDARDS.md` (25KB)
- Architecture: `docs/ILMA_ARCHITECTURE_CONSOLIDATED.md`
- Evidence: `reports/ILMA_COMPREHENSIVE_OPTIMIZATION_20260508_154140.json`