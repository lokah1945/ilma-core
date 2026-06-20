# Autonomous Memory Lifecycle (v10)

Patch v10 EXTENDS v9 (extends v8). Memory sovereignty + control-plane tetap;
v10 menambahkan **memory as evolving, not growing**. Setiap memory adalah
object dengan field-prescribed dan melewati pipeline check.

> **Memory does not grow. Memory evolves.** Growth without compression is failure.

## Layer A0 — Memory Object Model

Setiap memory object WAJIB punya fields:

```
memory_id      # unique id (uuid/short-hash)
class          # constitutional|strategic|architectural|operational|transient
owner          # _bos, _runtime_evidence, _self
created_at     # ISO-8601
last_used      # ISO-8601 (updated saat dipakai)
expires_at     # ISO-8601 (computed dari TTL/kelas)
confidence     # validated | partial | unverified | contradicted
evidence_ref   # tool output / commit / curl
contract_ref   # optional: v9 G1 contract id
source_hash    # hash of file/commit at write-time
merge_key      # semantic key untuk dedup
utility_score  # dihitung oleh Court (utility*confidence/cost)
state          # NEW|ACTIVE|COMPRESSED|ARCHIVED|QUARANTINED|DELETED
```

**Aturan:** Tidak ada anonymous memory. Setiap object punya minimal 7 field di atas.

State transition:

```
NEW → ACTIVE → COMPRESSED → ARCHIVED → DELETED
              ↓
              QUARANTINED (M7 fraud)
```

## Layer A1 — Event→Memory Pipeline

Pipeline wajib dilalui saat memory akan disimpan:

```
event (apa yang terjadi)
  ↓
evidence (cek F0 chain)
  ↓
decision (apakah valid + kelas berapa)
  ↓
candidate (object draft)
  ↓
validation (M2.5: gate)
  ↓
memory (dipersisten)
```

**Raw outputs auto-expire.** Hanya structured artifact (contract, evidence, decision, telemetry, embedding) yang boleh survive.

**Dilarang:** store report text, full transcript, unverified observation, internal monologue.

## Layer A2 — Dedup Engine

Sebelum write, compute:

```
merge_key       # semantic/intent-cluster key
semantic_hash   # embedding-based hash
source_hash     # hash of source artifact
```

Rule:

| condition | action |
|---|---|
| same evidence + same memory + same conclusion | **MERGE** |
| same event + different version | **MERGE with version pointer** |

Threshold: `0.82` cosine-similarity (atau rule-of-thumb equivalent).

Tujuan: **merge, not append.** Pencegahan report-on-report loops.

## Layer A3 — Memory Compactor

Epoch background:

```
ACTIVE
  ↓ compress (compress narrative)
  ↓ summarize (cluster intent)
  ↓ archive (ke cold store kalau perlu)
  ↓ delete (kalau redundant)
```

Keep:
- latest state
- root cause summaries
- evidence references

Delete:
- verbose history
- duplicate evidence
- redundant "Yang terbaru" metanote

**Compression target: 80% minimum** — narrative >80% lebih pendek dari sebelumnya.

## Layer A4 — Memory Indexing

Indexes by:
- topic
- decision
- evidence
- confidence

**Dilarang retrieve in chronological order.** Retrieve by **intent clusters** — yaitu grouping berdasarkan apa keputusan dilakukan, bukan kapan.

## Layer A5 — Learning Loop (proposal-only)

Setiap epoch:

```
sample:
  - wins
  - losses
  - drift
  - false memories
generate:
  - improvement proposals
```

**Rule:** Learning CANNOT write memory. Learning PROPOSES.
Court approves. Court executes (atau eksekutor lain).

v10 ini memisahkan **proposer** (Learning Loop) dari **approver** (Court) — implementasi gating.

## Layer A6 — Memory Court Daemon

Background, low priority. Actions:

```
KEEP     # retain as-is
MERGE    # dedup
COMPRESS # cluster & summarize
ARCHIVE  # move to cold
DELETE   # forensic removes
```

**Court tidak mengeksekusi** — Court hanya **merekomendasikan**. Eksekutor lain (sub-agent, cron, dll.) yang harus mengeksekusi.

Inputs: utility, cost, freshness, evidence.

## Layer A7 — Trust Evolution

```
trust(score) = (accuracy × freshness × evidence) ÷ cost
```

**Trust half-life = 30 epochs.** (epoch = one Memory Court run).

Trust of old memory decays. Past success ≠ future trust.

## Layer A8 — Drift Watcher

Detect:
- spec drift
- memory drift
- behavior drift
- policy drift

Trigger:
- **review ticket** (comm ke user atau open issue)
- **never silent repair** (perubahan memori tanpa noreply)

## Layer A9 — Background Scheduler (idle-only)

```
scheduler:
  max_cpu: 5%
  max_memory: 3%
  priority: lowest
  idle_only: true
  pause_under_load: true
```

Tasks: compact, dedup, court, index, drift-scan.

**Runtime wins.** Kalau sistem beban → pause scheduler.

## Layer A10 — Memory Metrics

Track:

| Metric | Target |
|---|---|
| duplicate_ratio | **<5%** |
| compression_rate | **>80%** |
| false_memory_rate | **<2%** |
| retrieval_hit_rate | maximize |
| decision_quality | maximize |
| memory_cost (chars/embeddings) | minimize |

## Final Law (v10)

- Pembangunan: **smaller memory**.
- Pembangunan: **truer memory**.
- Pembangunan: **more useful memory**.
- Bukan: bigger memory, more memory, more retrieval.

## Behavioral Conventions (instantly applied)

1. **Saat menambah memory baru**: cek apakah ada old memory dengan semantik sama → MERGE.
2. **Saat akan append notes**: COMPRESS lebih dulu. Sebelum menulis baru, verifikasi old memory masih akurat.
3. **Setiap memory WAJIB dapat evidence_ref valid** (bukan "_").
4. **State ACTIVE default.** Kalau ada storage collision → pindah ke COMPRESSED atau QUARANTINED.
5. **Saat temukan gap fakta→memory**: LAUNCH drift-ticket (or open question via `clarify`), bukan silent overwrite.
6. **Jangan simpan prose laporan.** Simpan: id, intent, evidence, decision, result, confidence.
7. **Memory cost (chars) — pilih compressed by default.** Ringkas selalu lebih baik.

## Convergence dengan v8 + v9

| v8/v9 | v10 extend |
|---|---|
| M0 Utility | A0 Memory Object → field utility_score wajib |
| M2.5 Verification Gate | A0 Memory Object → state transition mulai dari NEW/ACTIVE |
| M4 Memory Decay | A3 Compactor + A7 Trust Evolution |
| M5 Memory Court | A6 Court Daemon (recommend only) → step tambahan A6 cannot execute |
| M7 Fraud Detector | → state QUARANTINED (lebih eksplisit) |
| G2 Evidence Log | A1 Pipeline: evidence dulu sebelum candidate |
| G6 Capability Boundary | A2 Dedup: UNKNOWN hasil bukan bahan memory |
| G1 Contract First | → dengan contract_ref di memory object |
