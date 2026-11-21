---
name: ilma-playwright-stealth
description: ILMA Playwright stealth + CDP patterns for browser automation. Human-like interaction adapters.
category: ilma
version: 1.1.0
last_updated: 2026-11-13
---

# ILMA Playwright Stealth

Reference patterns for ILMA's custom Playwright Chromium CDP runtime with human-like interaction.

## References

- `references/playwright-stealth-cdp-patterns.md` — Stealth + CDP integration patterns
- `references/response_waiting_patterns_2026-05-12.md` — Response wait strategies for dynamic content
- `references/browser-cache-cleanup.md` — Playwright Chromium cache storage cleanup patterns (1.3G freed)

## Usage

Load this skill when working on browser automation, CDP integration, or stealth patterns. The canonical browser engine is `scripts/ilma_browser_engine.py` with `HumanInteractionAdapter` as default interaction layer (Phase 69).