---
name: ilma-long-response-delivery
description: Bos's hard rule — 1 long response must equal exactly 1 Telegram delivery, no duplication of conclusion. Trigger whenever ILMA is about to produce a long-form response (audit, report, deep dive, long code walkthrough). When response length will exceed ~2,000 chars OR content has distinct sections (findings → root cause → fix → summary), apply the Conclusion-Split Pattern and Pre-Compact Pattern below BEFORE writing.
---

# ilma-long-response-delivery

## Why this skill exists

On 2026-06-20, Bos explicitly flagged that a previous long audit reply arrived in Telegram as **15+ duplicate copies of the conclusion** — but the runtime body streamed normally with NO internal duplication. ILMA's state DB held exactly 1 record; gateway logs showed correct `Suppressing normal final send` messages; user-visible duplication came from upstream Telegram/Hermes delivery paths (flood retry, fresh-final re-send, trailing footer path, planned-restart startup notification), not from ILMA's processing.

This is a **first-class style + operational preference**:
- **Style**: When ILMA responds long, the *final* message must be visibly terminal — the user should be able to tell where the response ends.
- **Operational**: Bos does not want to scroll past 15 copies of the same conclusion. Once duplication is observed, every subsequent long reply must preempt it.

The class is "formatting long responses so duplication cannot happen visually", regardless of whether the underlying bug in Hermes is fixed.

## Golden Rule

> If the response will be **long** (>2,000 chars), **structured** (sections + summary), or **conclusion-heavy** (audit/review/diagnosis with a TL;DR/Executive Summary block at the end), apply ONE of the two patterns below before writing. Do not free-write and hope.

## When to apply (triggers)

Apply this skill when ANY of the following are true for the upcoming response:

- Estimated length > 2,000 characters OR > 8 tool calls accumulated during research
- Response has explicit sections (e.g. `## Audit Findings`, `## Root Cause`, `## Recommendations`)
- Task is an `AUDIT`, `REVIEW`, `DIAGNOSE`, `TRACE` analysis_4w1h classification
- Response includes a TL;DR / Executive Summary / Kesimpulan block at the top or bottom
- Last response in this session was > 4 KB and Bos flagged duplication (re-entry guard)

Do NOT apply:
- Short conversational replies (< 2 KB)
- Single-tool answers (one `read_file` + one line)
- Pure streaming output that already has its own `streaming.enabled: false` config in ILMA profile

## Pattern A — Conclusion-Split Pattern (DEFAULT for audits/reviews)

The duplication mechanism: Hermes stream_final path + Telegram fresh-final + flood retry all act on the *last* accumulated chunk. When that last chunk is the user-visible "conclusion", Telegram can broadcast it as multiple messages.

**The fix ILMA-side**: physically separate the conclusion into its own short, terminal message BEFORE the long body.

Format:

```
[Brief 1-3 line opening — states what will follow]

(then tool calls / analysis — long body, streamed normally)

[Brief 1-2 line WRAP-UP — everything already in the body is NOT repeated here.
 This wrap-up is intentionally 2-3 sentences MAX and refers to the conclusion
 section that's already inside the body.]
```

Rules:
- The opening must say "full audit follows" or equivalent — user knows something long is coming.
- The wrap-up must NOT restate the conclusion's bullets. Reference them: "Audit complete — see Prioritized Root Causes section above."
- Never put a TL;DR or Executive Summary AFTER a long body. Put it BEFORE (as opening) or skip it entirely.
- The wrap-up must end with a single character that signals terminal completion: `✅` (preferred), `Selesai.`, or an explicit "End of report."
- NEVER write "Jika Boss ingin..." / "Let me know if..." / "Apakah ada..." as the final sentence — these are open-ended and trigger follow-up prompts that the gateway may treat as new turns to re-deliver.

## Pattern B — Pre-Compact Pattern (when response is forced to be huge)

When a single response genuinely cannot fit (e.g. full code dump of a 5K-line analysis), do NOT delete content to fit. Instead:

1. Stream the body in markdown sections using normal `##` headers — no truncation.
2. Put **all** analysis, findings, tables inside the body.
3. End with literally: `---\nEnd of report. (single send verified by pattern.)`
4. Do NOT add a separate "Kesimpulan Akhir" section after the body. The body IS the conclusion.

If the body would still exceed Telegram's 4,096-char single-message limit, ILMA must acknowledge upfront that the response will be chunked by the gateway (this is unavoidable — Telegram cannot ship a 12KB message as one bubble regardless of pattern). State: "Response panjang — akan terkirim sebagai N bagian oleh gateway format chunk. Mohon hold."

## Anti-Patterns (REFUSE)

These are the specific failure modes observed on 2026-06-20:

- ❌ Ending a long report with a multi-paragraph "Kesimpulan Akhir", "Final Summary", or "TL;DR" that *re-states* what was already in the report. This double-broadcasts the same content as separate Telegram bubbles.
- ❌ Adding "Apakah ada langkah selanjutnya?" / "Mau saya patch sekarang?" as the final sentence. Open-ended closers get re-injected by queued-message follow-up paths.
- ❌ Writing "##### Phase 5 — Final Report" as a section header followed by 500+ chars that *repeat* bullets from Phase 1-4. Duplication arises from re-stating, not from missing content.
- ❌ Using the closing phrase "Jika Bos memerlukan ... saya siap lanjut di session berikutnya." Mid-stream this is fine; as the very LAST line, it triggers queued-followup re-delivery.

## Evidence Anchors

- 2026-06-20 audit of Telegram delivery duplication — `hermes-agent/gateway/stream_consumer.py` and `hermes-agent/gateway/run.py` were traced. Five delivery paths converge on the last chunk (overflow split, fresh-final, fallback-final, trailing footer, planned-restart startup notification). The fix in Hermes core is non-trivial and out of audit-only scope.
- Gateway log file `/root/.hermes/profiles/master-chief/logs/gateway.log` line `2026-06-20 13:59:27,243` is Bos's previous duplicate-flag event, captured in agent log for cross-reference.
- Telegram retry + flood handling in `hermes-agent/gateway/platforms/telegram.py:2555-2568` and `_send_with_retry` in `base.py:3423` are the runtime-level amplification paths.

## What this skill does NOT cover

- Fixing the underlying Hermes stream_final duplication bug (audit-only deliverable — patch payloads are gated behind Bos approval).
- Cron-triggered notifications (separate problem domain).
- Other channels (Discord, Slack, WhatsApp) — same lesson likely applies but is unverified.

## Verification

Before sending a long response, ask:
1. Will the LAST paragraph restate earlier bullets? → Apply Pattern A.
2. Will the FIRST sentence be an open question to Bos? → Rewrite to statement.
3. Does the document end without a terminal marker? → Append `✅`.
4. Is the response > 12,096 chars (3 × Telegram cap)? → Apply Pattern B with chunk disclaimer.

⚠️ If all four checks pass, the response is duplicate-safe by construction. If any fail, fix the failure mode before sending.
