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
- **2026-06-26 Hermes core patch session (P5-P6)** — 8 behavior patches (P5+P6) + 4 infra patches (P1-P4) deployed to `stream_consumer.py` and `telegram.py`. See `references/session-20260626-stream-consumer-sealed-split-fix.md` for full trace.
- **2026-06-26 Hermes core patch session (P7)** — `_normalize_empty_agent_response` in `gateway/run.py` line ~9127 called before `already_sent` gate at line ~9476, injecting spurious "no response generated" fallback on every streaming-delivered turn. Fix: added `and not agent_result.get("already_sent")` guard. This was the **most impactful single fix** — it eliminated the visible duplicate message that all P1-P6 could not catch. See `references/session-20260626-p7-normalize-already-sent-fix.md` for full detail.
- Gateway log file `/root/.hermes/profiles/master-chief/logs/gateway.log` line `2026-06-20 13:59:27,243` is Bos's previous duplicate-flag event, captured in agent log for cross-reference.
- Telegram retry + flood handling in `hermes-agent/gateway/platforms/telegram.py:2555-2568` and `_send_with_retry` in `base.py:3423` are the runtime-level amplification paths.

## Debugging Lessons (from 2026-06-26 Hermes core patch session)

When tracing Telegram duplicate delivery in `stream_consumer.py`:

1. **Separate sealed vs. stale IDs** — `_preview_message_ids` mixed two concerns: sealed chunks (carry final content, must keep) and continuation fragments (stale partials, must delete). Splitting into `_sealed_split_ids` + `_preview_message_ids` resolved the conflict.
2. **Always reset sealed set on segment break** — `_reset_segment_state` must clear `_sealed_split_ids` or false-positive detection in `got_done` blocks legitimate sends.
3. **Cleanup BEFORE tracking new IDs** — P6 #2 pattern: snapshot old preview IDs → cleanup stale → THEN track new IDs from current edit. If you track first, the cleanup deletes the just-tracked IDs.
4. **Check sealed set when `_message_id is None`** — proactive split resets `_message_id`, but content was already delivered. The `got_done` path must check `_sealed_split_ids`, not just `_preview_message_ids`.
5. **Fresh-final is safe for Telegram** — `_adapter_prefers_fresh_final` returns `False`, so `_try_fresh_final` never executes. No need to guard sealed chunks against fresh-final cleanup for Telegram.

See `references/session-20260626-stream-consumer-sealed-split-fix.md` for full patch map and architecture diagram.

6. **P7: `_normalize_empty_agent_response` must respect `already_sent`** — When streaming delivers content incrementally, the agent often returns an empty string. `_normalize_empty_agent_response()` in `gateway/run.py` line ~9127 was called BEFORE the `already_sent` gate at line ~9476. The normalize function saw empty response → injected "⚠️ Processing completed but no response was generated" → duplicate visible to user. **Fix:** `if not _intentional_silence and not agent_result.get("already_sent"):` — skip normalize when streaming already delivered. This was the **most impactful single fix** because it eliminated the spurious "no response generated" fallback message that appeared as a visible duplicate on every streaming-delivered turn.
7. **Trace finalize flow end-to-end** — Don't stop at `got_done` in `stream_consumer.py`. The response then flows to `run.py` where `_normalize_empty_agent_response` (line ~9127) and `already_sent` gate (line ~9476) process it. If normalize emits a message before the gate blocks it, the duplicate is already sent.
8. **Ordering matters: normalize BEFORE gate = bug** — Any function that can emit user-visible text must be gated by `already_sent` BEFORE execution, not after. The normalize-gate ordering in `run.py` was the latent bug that P1-P4 and P5-P6 could not catch because it was upstream of all dedup infrastructure.

See `references/session-20260626-p7-normalize-already-sent-fix.md` for the P7 patch detail.

## What this skill does NOT cover

- Fixing the underlying Hermes stream_final duplication bug (audit-only deliverable — patch payloads are gated behind Bos approval). **UPDATE 2026-06-26: Patches now deployed — see reference file. 7 total patches (P1 infrastructure through P7 behavior).**
- Cron-triggered notifications (separate problem domain).
- Other channels (Discord, Slack, WhatsApp) — same lesson likely applies but is unverified.

## Verification

Before sending a long response, ask:
1. Will the LAST paragraph restate earlier bullets? → Apply Pattern A.
2. Will the FIRST sentence be an open question to Bos? → Rewrite to statement.
3. Does the document end without a terminal marker? → Append `✅`.
4. Is the response > 12,096 chars (3 × Telegram cap)? → Apply Pattern B with chunk disclaimer.

⚠️ If all four checks pass, the response is duplicate-safe by construction. If any fail, fix the failure mode before sending.
