# Memory Audit with Source-of-Truth Priority (F0)

Audit tidak cukup "bandingkan dengan tool". Sekarang ada **8-tier priority chain**:

```
1. Observed Reality      (curl/ps/ss -- live test)
2. Runtime State         (env, /proc, mounted fs, conn)
3. Source Code           (current HEAD .py/.yaml/.sh/.json)
4. Current Files         (working tree, including untracked)
5. Contracts             (schemas, API specs, protocol docs)
6. Validated Tests       (pytest --pass, e2e artifacts)
7. Verified Memory       (memory entries MARKED validated)
8. Inference             (LLM-deduced reasoning)
9. Assumption            (LLM-stated guess)
```

Hati: memory **tidak pernah bisa override observation** kecuali sudah lewat Verification Gate dan bertanda VALIDATED.

# Memory Constitution (M0) — utility-enforced

Setiap memory baru/legacy WAJIB punya 6 kolom:

| Field | Required | Default |
|---|---|---|
| `purpose` | ✅ | — |
| `reuse`  | ✅ | — |
| `impact` | ✅ | — |
| `verification` (evidence_id + tool ref) | ✅ | UNVERIFIED |
| `cost` (chars + maintenance) | ✅ | — |
| `confidence` (validated/partial/unverified/contradicted) | ✅ | unverified |

Plus opsional:
- `ttl` (expiry date / kelas)
- `priority` (low/med/high/critical)
- `compression` (full/summary/pointer)
- `owner` (_bos, _runtime_evidence, _self)
- `expiration_trigger` (event, time, re-verification)

**Default memory = ephemeral**. Yang tidak lulus verifikasi = `unverified`, dan hanya boleh **temporary** — tidak persistent.

# Verification Gate (M2.5) — label before storage

Setiap memory baru WAJIB lulus gate:

```
1. Evidence        → ada tool output / commit hash / curl response
2. Consistency     → cocok dengan F0 priority chain
3. Freshness       → dibuat/artikan saat ini, bukan turunan
4. Confidence      → skala: validated (>85%), partial (50-85%), unverified (<50%)
```

Label yang boleh dipakai: **VALIDATED / PARTIAL / UNVERIFIED / CONTRADICTED**.

Hanya `VALIDATED` → persistent. Sisanya → `transient` (≤24h) atau langsung di-compress jadi 1-baris pointer.

# Memory Classes (M1) — TTL-aware promotion

| Kelas | TTL | Verifikasi | Auto-promote? |
|---|---|---|---|
| Transient | minutes | optional | ❌ |
| Operational | hours | evidence required | ❌ |
| Architectural | weeks | validation required | ❌ |
| Strategic | months | reuse history | ❌ |
| Constitutional | permanent | explicit approval | ❌ |

Promotion **TIDAK PERNAH otomatis**. Reuse history ≥3× untuk naik kelas.

# Memory Ingestion Pipeline (M2)

```
observe → verify → extract → compress → score → store
```

Raw events TIDAK boleh disimpan. Yang disimpan:
- **summary** (≤1 kalimat)
- **contracts** (endpoint, format, schema)
- **telemetry** (latency, status, error rate)
- **decision_artifacts** (commit hash, decision_id)
- **embeddings** (semantic vector)

Yang **dilarang**:
- full transcripts, unverified observations, raw debug output

Compression WAJIB.

# Memory Retrieval (M3) — workers dapat minimal package

Retrieval order:
```
Constitution → Current Spec → Observed Facts → Architecture → Incidents → Historical Memory
```

**Max 12 objects per retrieval**. Worker tidak boleh invent data; kalau missing → request retrieval.

# Memory Decay (M4) — recalc tiap epoch

Score per memory:
```
utility × confidence ÷ cost
```

Action: `compress → summarize → archive → delete`. **Validated architecture tidak boleh dihapus.**

# Memory Court (M5) — governance-only

Pertanyaan hanya: **KEEP / COMPRESS / ARCHIVE / DELETE**. Tidak boleh create. Trigger: utilitas turun, evidence kadaluarsa.

# RAG Engine (M6) — minimal context

Ranking: **relevance × freshness × confidence × cost**. Workers dapat retrieval package, **no direct DB access**. Memory tidak boleh bypass retrieval.

# Fraud Detector (M7) — quarantine immediately

Detect:
- self-confirming memories (loop internal validation tanpa tool)
- hallucinated patterns (imaginary metrics)
- obsolete assumptions (terpakai tapi nggak pernah direfresh)
- duplicate incidents (hebat clone tanpa akarnya)
- recursive belief loops (memory bilang X, memory andaikan X)

Quarantine → Purge (jika berulang).

# Execution Principle (Ω)

Setiap aksi besar:

```
1. Understand   → apa yang diketahui dan belum?
2. Validate     → copi dengan F0 chain
3. Plan         → bite-sized tasks
4. Execute      → satu langkah bermakna
5. Observe      → baca output aktual
6. Update       → tulis memory jika VALID
```

Refrain: **"Tidak boleh mengeksekusi yang tidak dipahami."**

# Anti-skip Helpers (untuk ILMA runtime pakai ini saat keraguan)

```bash
# F0 quick probe
echo '---F0 priority probe---'
echo '1. reality: '$(curl -s --max-time 2 -o /dev/null -w '%{http_code}' "$URL" || echo na)
echo '2. runtime: '$(ps -p $PID -o stat= 2>/dev/null || echo dead)
echo '3. source:  '$(git -C $REPO rev-parse HEAD 2>/dev/null || echo na)
echo '4. files:   '$(ls $FILE 2>/dev/null || echo missing)
echo '5. contracts: '$(jq -e . $SCHEMA 2>/dev/null >/dev/null && echo valid || echo broken)
echo '6. tests:   '$(test -f $LOG && echo pass || echo none)
echo '7. memory:  '$(echo has been verified through memory tool log?)
```
