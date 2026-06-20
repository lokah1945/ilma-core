"""
ILMA Thinking Mapper v1.0 — Direct GPT-5.5 Reasoning Modes
==========================================================
Maps thinking/reasoning parameter modes to runtime API calls.

PARAMETER FAMILIES:
  thinking        → off, low, high, highest
  reasoning_effort → off, low, medium, high

VALIDATED (200 OK):
  ✅ thinking=off
  ✅ thinking=low
  ✅ thinking=high
  ✅ thinking=highest
  ✅ reasoning_effort=off
  ✅ reasoning_effort=low
  ✅ reasoning_effort=medium
  ✅ reasoning_effort=high

OPERATIONAL:
  ✅ Minaxi-M3 + MiniMax family via direct API (2026-06-19)
"""

from typing import Literal, Optional

# Note: this module historically targeted a proxy at port 8001 that no longer
# exists. With that proxy project removed (2026-06-19), the request builder
# stays as a payload-shaping helper consumed by the direct API path in
# `ilma_model_router.execute_call`. The legacy ``chat()`` HTTP client was tied
# to that proxy network and was removed in 2026-06-19.

# Default model used by `build_payload` callers. Direct cloud API only.
DEFAULT_MODEL = "MiniMax-M3"

# ── Thinking Level Definitions ──────────────────────────────────────────────
THINKING_LEVELS = {
    # thinking parameter family
    "off":      {"thinking": "off"},
    "low":      {"thinking": "low"},
    "high":     {"thinking": "high"},
    "highest":  {"thinking": "highest"},
    # reasoning_effort parameter family
    "reasoning_off":    {"reasoning_effort": "off"},
    "reasoning_low":    {"reasoning_effort": "low"},
    "reasoning_medium": {"reasoning_effort": "medium"},
    "reasoning_high":   {"reasoning_effort": "high"},
}

# ── Tier System ─────────────────────────────────────────────────────────────
# Maps use-case tiers to recommended thinking mode
TIER_MAP = {
    # Tier 1 — Instant recall, no reasoning needed
    "instant": {
        "description": "Simple factual recall, unit conversion, spelling",
        "mode": "off",
        "params": {"thinking": "off", "max_tokens": 100, "temperature": 0.1},
        "expected_latency": "< 5s",
        "use_cases": ["spelling", "definition", "date/fact lookup", "simple math"],
    },
    # Tier 2 — Light reasoning, quick answer
    "fast": {
        "description": "Light multi-step, straightforward logic",
        "mode": "low",
        "params": {"thinking": "low", "max_tokens": 500, "temperature": 0.3},
        "expected_latency": "5-10s",
        "use_cases": ["code snippet", "simple explanation", "light analysis"],
    },
    # Tier 3 — Deep reasoning, complex problem solving
    "deep": {
        "description": "Complex math, proofs, algorithm analysis, multi-step logic",
        "mode": "high",
        "params": {"thinking": "high", "max_tokens": 2000, "temperature": 0.3},
        "expected_latency": "10-25s",
        "use_cases": [
            "math proofs", "algorithm complexity", "physics derivations",
            "code architecture", "deep debugging", "system design",
        ],
    },
    # Tier 4 — Maximum reasoning, research-grade analysis
    "max": {
        "description": "Research-grade reasoning, longest chains of thought",
        "mode": "highest",
        "params": {"thinking": "highest", "max_tokens": 4000, "temperature": 0.4},
        "expected_latency": "20-40s",
        "use_cases": [
            "P vs NP analysis", "formal proofs", "research synthesis",
            "cross-domain reasoning", "creative breakthrough tasks",
        ],
    },
    # Tier 5 — Balanced reasoning effort (via reasoning_effort)
    "balanced": {
        "description": "Balanced depth vs speed, uses reasoning_effort=medium",
        "mode": "reasoning_medium",
        "params": {"reasoning_effort": "medium", "max_tokens": 1500, "temperature": 0.3},
        "expected_latency": "8-20s",
        "use_cases": ["general writing", "code review", "explanation", "blog post"],
    },
    # Tier 6 — Maximum reasoning effort
    "rigorous": {
        "description": "Maximum reasoning_effort for rigorous output",
        "mode": "reasoning_high",
        "params": {"reasoning_effort": "high", "max_tokens": 3000, "temperature": 0.3},
        "expected_latency": "15-30s",
        "use_cases": ["formal verification", "security audit", "legal analysis"],
    },
}

# ── Convenience aliases ─────────────────────────────────────────────────────
TIER_ALIASES = {
    # Shortcut → tier
    "i":    "instant",
    "f":    "fast",
    "d":    "deep",
    "m":    "max",
    "b":    "balanced",
    "r":    "rigorous",
    # Descriptive → tier
    "quick":    "instant",
    "simple":   "instant",
    "reason":   "deep",
    "heavy":    "max",
    "balanced": "balanced",
    "strict":   "rigorous",
    # Reasoning-specific
    "reasoning_off":    "instant",
    "reasoning_low":    "fast",
    "reasoning_medium": "balanced",
    "reasoning_high":   "rigorous",
    "thinking_off":     "instant",
    "thinking_low":     "fast",
    "thinking_high":    "deep",
    "thinking_highest": "max",
}

# ── Response Keys (what GPT-5.5 actually returns) ───────────────────────────
RESPONSE_KEYS = ["role", "content"]  # thinking block NOT exposed in response


# ── API Call Functions ───────────────────────────────────────────────────────

def resolve_tier(tier_or_mode: str) -> str:
    """Resolve tier name or mode name to canonical tier."""
    if tier_or_mode in TIER_MAP:
        return tier_or_mode
    if tier_or_mode in TIER_ALIASES:
        return TIER_ALIASES[tier_or_mode]
    if tier_or_mode in THINKING_LEVELS:
        # Direct mode name — find its tier
        for tier, config in TIER_MAP.items():
            if config["mode"] == tier_or_mode:
                return tier
        # Not in tier map — return as custom
        return tier_or_mode
    raise ValueError(f"Unknown tier/mode: {tier_or_mode}")


def build_payload(
    message: str | list,
    tier: str = "fast",
    model: str = DEFAULT_MODEL,
    system: str | None = None,
    **override_params,
) -> dict:
    """
    Build API payload with thinking mode resolved from tier.

    Args:
        message: User message (str) or messages list
        tier: Reasoning tier (instant/fast/deep/max/balanced/rigorous)
        model: Model name
        system: Optional system prompt
        **override_params: Override any parameter

    Returns:
        Complete JSON payload for /v1/chat/completions
    """
    tier = resolve_tier(tier)
    tier_config = TIER_MAP.get(tier, TIER_MAP["fast"])

    # Build messages
    if isinstance(message, str):
        messages = [{"role": "user", "content": message}]
    else:
        messages = message

    if system:
        messages = [{"role": "system", "content": system}] + messages

    # Get thinking params
    mode_name = tier_config["mode"]
    thinking_params = THINKING_LEVELS.get(mode_name, {})

    # Merge: tier defaults → override_params
    base_params = tier_config["params"].copy()
    base_params.update(override_params)

    payload = {
        "model": model,
        "messages": messages,
        **thinking_params,
        **base_params,
    }
    return payload


def chat(
    message: str | list,
    tier: str = "fast",
    model: str = DEFAULT_MODEL,
    system: str | None = None,
    timeout: int = 60,
    **override_params,
) -> dict:
    """
    Build a thinking-tier payload. Direct cloud API execution happens in
    `ilma_model_router.execute_call`; this function does not perform any
    network call itself.

    Kept as a thin wrapper around ``build_payload`` so downstream callers
    that only need the payload can keep importing ``chat``.
    """
    payload = build_payload(message, tier, model, system, **override_params)
    return {
        "payload": payload,
        "tier": tier,
        "model": model,
    }


# ── CLI Interface ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys, json

    if len(sys.argv) < 2:
        print(__doc__)
        print("\n=== AVAILABLE TIERS ===")
        for name, config in TIER_MAP.items():
            print(f"  {name:<12} — {config['description']}")
            print(f"             latency: {config['expected_latency']}")
            print(f"             mode: {config['mode']}")
        print("\n=== THINKING MODES ===")
        for name, params in THINKING_LEVELS.items():
            print(f"  {name:<22} → {params}")
        print("\n=== USAGE ===")
        print("  python3 ilma_thinking_mapper.py <tier> <message>")
        print("  python3 ilma_thinking_mapper.py deep 'Prove sqrt(2) is irrational'")
        print("  python3 ilma_thinking_mapper.py --list-modes")
        sys.exit(0)

    arg = sys.argv[1]

    if arg == "--list-modes":
        print("=== THINKING MODES ===")
        for name, params in THINKING_LEVELS.items():
            print(f"  {name:<22} → {json.dumps(params)}")
        print("\n=== TIER MAP ===")
        for name, config in TIER_MAP.items():
            print(f"\n[{name}]")
            print(f"  description: {config['description']}")
            print(f"  mode: {config['mode']}")
            print(f"  params: {json.dumps(config['params'])}")
            print(f"  latency: {config['expected_latency']}")
            print(f"  use_cases: {', '.join(config['use_cases'])}")
        sys.exit(0)

    tier = arg if arg in TIER_MAP else "fast"
    message = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "What is the capital of Japan?"

    print(f"🧠 Tier: {tier} | Model: {DEFAULT_MODEL}")
    print(f"📝 Message: {message}")
    print()

    result = chat(message, tier=tier, timeout=60)

    if result.get("error"):
        print(f"❌ ERROR: {result.get('detail', result)}")
        sys.exit(1)

    print(f"✅ Latency: {result['latency']:.2f}s | Tokens: {result['usage'].get('total_tokens', '?')}")
    print()
    print(result["content"])
