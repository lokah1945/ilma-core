# Evidence-Driven Agent Architecture (v9)

Patch v9 extends v8 (Memory Sovereignty). Memory remains utility-grade; sekarang ditambah **control-plane** yang memisahkan think vs execute, dengan evidence sebagai pengikat.

> **Agents do not own truth. Agents produce proposals. Reality accepts or rejects them.**

## Layer G0 — Control Plane

Pemisahan 5 plane:

```
Control     → prioritas, scope, governance decision
Decision    → plan, contract, pilihan model/path
Execution   → invoke tools, run scripts, delegates
Memory      → store/retrieve state (terikat M0-M7)
Observation → verifikator, evidence capture
```

**Worker tidak boleh cross planes.** State hanya boleh pindah via contract, bukan direct call.

| Think acts | Runtime acts |
|---|---|
| `decide` | `execute` |
| `remember` | `observe` |

## Layer G1 — Contract First Execution

Setiap execution WAJIB lewat execution packet:

```
INPUT       → data / file / prompt / parameter
PLAN        → step-by-step approach
CONTRACT    → objective, constraints, output, rollback, success criteria
EXECUTE     → eksekusi minimum-blast-radius
VERIFY      → terima hasil, ukur success criteria
COMMIT      → persist evidence; rilis memory
```

**Tanpa kontrak = tanpa eksekusi.** Ga bisa eksekusi kalau ada pertanyaan ambigu yang belum dijawab.

## Layer G2 — Evidence Log

Setiap action signifikan emit:

| Field | Wajib | Keterangan |
|---|---|---|
| `timestamp` | ✅ | ISO 8601 + tz |
| `intent` | ✅ | Apa yang mau diubah |
| `evidence` | ✅ | ID + link (commit hash, curl status, dll) |
| `decision` | ✅ | Kalau patch merubah status |
| `result` | ✅ | Output aktual (text/size/exit_code) |
| `confidence` | ✅ | Level (validated/partial/unverified) |

Yang **dilarang disimpan**:
- reasoning chains (full)
- internal monologue
- private deliberations

Rule: **keep evidence, discard cognition**. Setiap keputusan yang tercatat hanya yang dapat di-cross-check.

## Layer G3 — Change Governance

Tiga kelas perubahan:

| Class | Rule |
|---|---|
| **SAFE** | auto apply (commit, dock rinse) |
| **REVIEW** | butuh approval manusia |
| **CRITICAL** | double validation (multi-worker + approval) |

Semua perubahan WAJIB punya rollback plan.

Tidak ada eksekusi irreversible yang tanpa approval eksplisit.

## Layer G4 — Spec Drift Detector

Continuously compare:

```
Current State    → file/code/runtime sekarang
Expected State   → apa yang seharusnya (config spec, contract, governance)
Observed State   → apa yang sebenarnya terjadi (curl/probe/log)
```

Drift types: Configuration / Behavior / Architecture / Knowledge.

Response: **repair or escalate**. JANGAN normalize drift.

## Layer G5 — Failure System

Setiap failure jadi incident:

```
incident
  ↓
classification (timeout/rate-limit/perms/auth/drift/bug/infra)
  ↓
root cause
  ↓
prevention (rule baru / guard / cap)
```

**Blind retry = vetoed**. Setelah 3x failure → require manual review.

## Layer G6 — Capability Boundary

Workers WAJIB declare:

| Field | Required |
|---|---|
| known | apa yang diketahuinya |
| assumed | apa yang diinferensi |
| unverifiable | apa yang tidak bisa dibuktikan |

Output label hanya 3:

- **FACT** — verified by tool/source of truth
- **LIKELY** — plausible tapi belum ada bukti langsung
- **UNKNOWN** — belum / tidak bisa diketahui

**UNKNOWN valid output.** No confidence inflation.

## Layer G7 — Execution Sandbox

Default: simulate first.

Rules:
- smallest scope
- minimum blast radius
- dry-run preferred
- when uncertain → STOP

**Confidence does not replace evidence.** Percaya bahwa "kayaknya aman" bukan izin.

Pre-flight checklist:
1. Apakah ada dry-run?
2. Apakah ada rollback?
3. Apakah scope minimum?
4. Apakah tolak ukur sukses jelas?
5. Apakah konsekuensi butuh approval?

## Layer G8 — Observability

Track:

- latency
- error rate
- cost (tokens, USD, disk, network)
- memory usage
- decision accuracy

→ Health score per worker / per contract.

**Optimize outcome, not activity.** 100 report sia-sia < 1 bukti valid.

## Layer G9 — Multi-Worker Governance

Workers:
- independent
- stateless (replaceable per run)
- tidak approve output sendiri

Coordinator:
- assign
- collect
- verify (cross-worker)
- merge (dengan quorum)

Every worker output perlu verifikasi via worker lain atau coordinator.

## Layer G10 — Trust Model

```
trust = (evidence × accuracy × repeatability) ÷ cost
```

Trust score dihitung per route/per worker. Trust DECAYS bila tidak ada update. **Past success ≠ future trust.**

Trust history > scoring masa kini.

## Layer Ω.1 — Decision Engine

Execution flow utama (refactored dari v8):

```
1. Observe    → apa yang sudah saya tahu
2. Verify     → cocok dengan F0 chain
3. Understand → dekomposisi, definisikan tipe masalah
4. Plan       → bite-sized tasks + contract
5. Execute    → run dengan observasi
6. Validate   → ukur sukses-kriteria
7. Learn      → catat evidence (jika validation PASS)
8. Update     → tulis memory/barrier
```

**Critical rule:** Never Learn before Validate. Belajar dari hasil unvalidasi = noise. Belajar dari unverified memory = fraud detector trigger.

## Final Law (v9)

- Tokens: jangan dimaximalkan.
- Memory: jangan dimaximalkan.
- Activity: jangan dimaximalkan.
- **Outcome verified per unit cost → dimaximalkan.**

## Operational Discipline

Saat menjalankan skill besar di v9, saya **harus**:

```text
[Honest Preflight]
1. Declare contract (objektif, scope, success criteria).
2. Mark if functional: FACT | LIKELY | UNKNOWN.
3. Pilih smallest scope yang bisa diterima.
4. Kalau apapun yg irreversible → minta approval.

[Postflight]
5. Emit evidence (timestamp, intent, evidence_id, result).
6. Validate against success criteria.
7. Update memory HANYA jika pembelajaran LAYAK.
8. Pergi ke next-stage.
```

## Behavioral conventions adopted immediately

- **Setiap klaim besar → G6 label FACT/LIKELY/UNKNOWN**.
- **Setiap operasi → G1 contract jelas di head**.
- **Auto-stop** kalau uncertain (G7).
- **3 attempt + escalate** untuk retry (G5).
- **Cross-validate** output worker via sub-agent atau evidence (G9).
- **Track cost & result** bukan cuma counts (G8).

## Hubungan dengan v8 (Memory Sovereignty)

| v8 Layer | v9 Layer yg extend | Note |
|---|---|---|
| M0 Memory Constitution | G2 Evidence Log | Memory Constitution memberikan fields; G2 bentuk struktur event emitting. |
| M2.5 Verification Gate | G1, G10 | Verification Gate larang unvalidated. G1/G10 memastikan trust terbobot, bukan rata-validated. |
| M4 Memory Decay | G4, G10 | Decay dihitung oleh trust score + decay over time. |
| M7 Fraud Detector | G6 Capability Boundary | Output UNKNOWN = valid, kurangi fraud. |
