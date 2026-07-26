#!/usr/bin/env python3
"""
ILMA Cost Tracker v1.0 (Phase 1.1 Block 5)
===========================================
Per-request cost tracking. Calculates cost from input/output tokens and
provider pricing from llm_providers schema.

Usage:
    from ilma_cost_tracker import track_cost, get_daily_total
    track_cost(model_id, provider, input_tokens, output_tokens)
    print(get_daily_total())

Output:
    - cost_log.json (append-only, daily rotation)
    - agent.log line: "COST | model=X | provider=Y | in=Z | out=W | cost=$V"
"""
from __future__ import annotations

import json
import time
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Tuple

COST_LOG = Path("/root/.hermes/profiles/ilma/data/cost_log.json")
AGENT_LOG = Path("/root/.hermes/profiles/ilma/logs/agent.log")

# Fallback pricing (per 1M tokens) when provider pricing unknown
DEFAULT_PRICE_INPUT = 0.0   # free tier default
DEFAULT_PRICE_OUTPUT = 0.0


def track_cost(
    model_id: str,
    provider: str,
    input_tokens: int,
    output_tokens: int,
    price_per_m_input: Optional[float] = None,
    price_per_m_output: Optional[float] = None,
) -> float:
    """Calculate and log cost for one request. Returns cost in USD."""
    pi = price_per_m_input if price_per_m_input is not None else DEFAULT_PRICE_INPUT
    po = price_per_m_output if price_per_m_output is not None else DEFAULT_PRICE_OUTPUT

    cost = (input_tokens * pi / 1_000_000) + (output_tokens * po / 1_000_000)

    # 1. Append to cost_log.json (daily rotation)
    record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "model": model_id,
        "provider": provider,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "price_per_m_input": pi,
        "price_per_m_output": po,
        "cost_usd": round(cost, 8),
    }
    try:
        COST_LOG.parent.mkdir(parents=True, exist_ok=True)
        if COST_LOG.exists():
            data = json.loads(COST_LOG.read_text())
        else:
            data = []
        data.append(record)
        COST_LOG.write_text(json.dumps(data, indent=2))
    except Exception as e:
        # Don't fail the request on cost log error
        pass

    # 2. Log to agent.log
    try:
        line = f"COST | model={model_id} | provider={provider} | in={input_tokens} | out={output_tokens} | cost=${cost:.6f}\n"
        with open(AGENT_LOG, "a") as f:
            f.write(line)
    except Exception:
        pass

    return cost


def get_daily_total(target_date: Optional[date] = None) -> dict:
    """Aggregate costs for a given date (default: today UTC)."""
    target = target_date or date.today()
    if not COST_LOG.exists():
        return {"date": target.isoformat(), "total_cost": 0.0, "by_model": {}, "by_provider": {}}
    try:
        data = json.loads(COST_LOG.read_text())
    except Exception:
        return {"date": target.isoformat(), "total_cost": 0.0, "by_model": {}, "by_provider": {}}

    by_model = {}
    by_provider = {}
    total = 0.0
    for r in data:
        ts = r.get("timestamp", "")
        if not ts.startswith(target.isoformat()):
            continue
        c = r.get("cost_usd", 0.0)
        total += c
        by_model[r.get("model", "unknown")] = by_model.get(r.get("model", "unknown"), 0.0) + c
        by_provider[r.get("provider", "unknown")] = by_provider.get(r.get("provider", "unknown"), 0.0) + c
    return {
        "date": target.isoformat(),
        "total_cost": round(total, 6),
        "by_model": {k: round(v, 6) for k, v in by_model.items()},
        "by_provider": {k: round(v, 6) for k, v in by_provider.items()},
    }


if __name__ == "__main__":
    # Smoke test
    c1 = track_cost("MiniMax-M3", "minimax", 1000, 500)
    c2 = track_cost("deepseek-v4-pro", "nvidia", 2000, 1000, price_per_m_input=0.5, price_per_m_output=1.5)
    print(f"Cost 1: ${c1:.6f}")
    print(f"Cost 2: ${c2:.6f}")
    print()
    print(f"Daily total: {get_daily_total()}")
