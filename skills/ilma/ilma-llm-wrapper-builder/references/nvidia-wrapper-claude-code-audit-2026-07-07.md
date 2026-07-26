# NVIDIA NIM Wrapper — Claude Code Compatibility Audit (2026-07-07)

## Context

Comprehensive end-to-end audit of `/root/wrapper/nvidia` (v8.6.0-node) when used as a custom provider endpoint by Claude Code.

## Key Findings

### Bug #1: Streaming Buffer Overflow Risk
- **Location:** `src/index.js` baris 1828
- **Pattern:** `MAX_STREAM_BUFFER = 128 * 1024` (128KB)
- **Issue:** Reasoning/thinking models can produce output exceeding 128KB before first usage chunk. Buffer rollover loses data.
- **Evidence:** Claude Code long sessions with vision/multimodal input cause truncation.
- **Fix:** Increase to 1MB minimum for reasoning-heavy workloads.

### Bug #2: Reasoning Not Counted as Content
- **Location:** `src/index.js` baris 1294, 1858
- **Pattern:** `hasContent = chunkStr.includes('choices') || chunkStr.includes('content') || chunkStr.includes('text')`
- **Issue:** Streams that ONLY send reasoning (no text) are marked as empty and trigger false error.
- **Fix:** Add `|| chunkStr.includes('reasoning') || chunkStr.includes('thinking')` to content detection.

### Bug #3: Usage Metrics No Fallback
- **Location:** `anthropic_compat.js` baris 535-542
- **Pattern:** Usage extracted via regex from `lastUsageChunk` only
- **Issue:** If upstream changes format or omits usage, metrics silently show 0 tokens.
- **Fix:** Add fallback estimation from response length when usage extraction fails.

### Bug #4: Heartbeat Timeout Too Aggressive
- **Location:** `anthropic_compat.js` baris 355
- **Pattern:** `HEARTBEAT_INTERVAL_MS = 5000` default
- **Issue:** 5-second heartbeat causes false timeout kills on slow models/vision processing.
- **Fix:** Increase default to 10000ms, make configurable.

### Bug #5: Redundant Error Type Derivation
- **Location:** `src/index.js` baris 845-927 AND 1485-1496
- **Pattern:** Both proxyOpenai and handleAnthropicMessages derive error types from status code
- **Issue:** Upstream error type can be overwritten by generic mapping.
- **Fix:** Create single `deriveErrorType(upstreamType, status)` helper, use everywhere.

### Bug #6: Close-Abort Race Condition
- **Location:** `src/index.js` baris 2000-2003
- **Pattern:** `res.on('close', () => controller.abort())` without guard
- **Issue:** Both `close` and `finish` events fire on normal completion, double-abort can affect next request.
- **Fix:** Use single-shot guard (`resClosed` flag) as in Pitfall #35.

### Capability Gaps for Claude Code

| Capability | Status | Notes |
|------------|--------|-------|
| Vision models | 11/134 | Detected correctly via classify() |
| Function calling | 109/134 | `supports_parallel_tool_calls: false` correctly set |
| Streaming | ✅ | SSE heartbeat implemented |
| Reasoning passthrough | ⚠️ | Tags parsed but buffer/content issues remain |
| Image generation | ⚠️ | Models in CURATED_GENAI but endpoint `/v1/images/generations` not tested |
| Embeddings | ✅ | Path exists, tested in test.js |
| Rerank | ⚠️ | Endpoint `/v1/ranking` exists but untested |

## Verification Commands Used

```bash
# Health check
curl -s http://localhost:9100/health

# Models with capabilities
curl -s http://localhost:9100/v1/models | jq '.data[] | select(.supports_parallel_tool_calls == false)'

# Model capabilities
curl -s "http://localhost:9100/v1/capabilities?model=meta/llama-3.1-8b-instruct"

# Logs analysis
journalctl -u wrapper-nvidia --since "1 hour ago" -n 50
```

## Recommended Immediate Actions

1. **Patch Buffer Size:** `MAX_STREAM_BUFFER = 1024 * 1024`
2. **Add Reasoning to Content Check:** `|| chunkStr.includes('reasoning')`
3. **Create Error Type Helper:** Unify error type derivation
4. **Verify image/rerank endpoints:** One-shot test with known-good payloads
5. **Document Claude Code integration:** Add section on exact capabilities supported

## Evidence ID

`ILMA-EVID-20260707-WRAPPER-AUDIT-001`