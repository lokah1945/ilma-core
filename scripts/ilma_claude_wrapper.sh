#!/usr/bin/env bash
# ILMA Claude Code wrapper (Bos command 2026-06-18)
# Purpose: Fix HOME mismatch — Claude Code reads ~/.claude/credentials.json
#          from real /root, but Hermes profile shell has HOME=/root/.hermes/profiles/ilma/home
# Usage:   ilma_claude_wrapper.sh [claude-args...]
#          same as: HOME=/root claude [args...]
set -euo pipefail
export HOME=/root
exec /usr/bin/claude "$@"
