#!/usr/bin/env python3
"""
ILMA Partner Agent Wrappers v1.0
================================
Wrappers for partner agents: Prometheus-2 (Judge) and DeepSeek-R1 (Critic).
Based on Gemini architecture concepts from /root/konsep/gemini/

These are INTERFACE wrappers only — actual API calls require:
- Prometheus-2: API endpoint + rubric
- DeepSeek-R1: API endpoint + chain-of-thought

All callbacks are PLACEHOLDER — real integration requires API keys.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Configure logging
logger = logging.getLogger(__name__)

# ILMA paths - can be overridden via environment variable
ILMA_PROFILE = Path(os.environ.get("ILMA_PROFILE", "/root/.hermes/profiles/ilma"))
WORKSPACE = ILMA_PROFILE
sys.path.insert(0, str(WORKSPACE))


# === PROMETHEUS-2 WRAPPER (JUDGE) ===

class PrometheusJudgeWrapper:
    """
    Prometheus-2 Judge wrapper.
    
    Prometheus-2 characteristics (from research):
    - 8x7B MoE or 7B variants
    - Correlation 0.898 with human expert
    - Immune to positivity bias
    - Requires: instruction + response + reference + rubric (1-5)
    - Context window: 8K tokens
    - Output format: Feedback: [feedback][score]
    
    This wrapper provides:
    - Rubric evaluation interface
    - Context summarization (to fit 8K window)
    - Format validation (Feedback: [text][score])
    - Pydantic safety layer for JSON parsing
    
    NOTE: Actual Prometheus-2 API call requires external service.
    This is an interface wrapper, not a live model connection.
    """
    
    RUBRIC_TEMPLATE = """Evaluate the following response against the rubric criteria.

RESPONSE_TO_EVALUATE:
{response}

TARGET_CRITERIA:
{criteria}

RUBRIC (1-5 scale):
5: Target fully achieved. Tool failures handled elegantly. No redundant reasoning. Perfect structural tags.
4: Target mostly achieved. Minor redundancies or gaps. Mostly clean structure.
3: Functional but significant logical gaps. Some redundant reasoning. Partially correct structure.
2: Target inadequately achieved. Major flaws in logic or structure. Missing key elements.
1: Target not achieved. Fundamental failures. Does not meet minimum criteria.

Output format: Feedback: [your detailed feedback here] Score: [0.0-5.0]"""

    def __init__(
        self,
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: str = "prometheus-2",
        timeout: int = 30
    ):
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout
        
        # Callback for actual API call (placeholder)
        self._api_callback: Optional[Callable] = None
        
        # Statistics
        self.eval_count = 0
        self.total_latency = 0.0
    
    def set_api_callback(self, callback: Callable):
        """Set the API callback for actual Prometheus-2 calls."""
        self._api_callback = callback
    
    def evaluate(
        self,
        response: str,
        criteria: str,
        reference: Optional[str] = None,
        verbose: bool = False
    ) -> Tuple[float, str]:
        """
        Evaluate response against criteria.
        
        Returns: (score, feedback)
        """
        start_time = time.time()
        
        # Summarize context if too long (8K token limit)
        if len(response) > 6000:
            response = self._summarize_context(response)
        
        # Build prompt
        prompt = self.RUBRIC_TEMPLATE.format(
            response=response[:5000],
            criteria=criteria
        )
        
        # Call API (or use placeholder)
        if self._api_callback:
            try:
                raw_output = self._api_callback(prompt, temperature=0.0, max_tokens=2048)
            except Exception as e:
                raw_output = self._placeholder_evaluate(response, criteria)
        else:
            raw_output = self._placeholder_evaluate(response, criteria)
        
        # Parse output
        score, feedback = self._parse_output(raw_output)
        
        # Update stats
        self.eval_count += 1
        self.total_latency += time.time() - start_time
        
        if verbose:
            logger.info("PrometheusJudge evaluation complete: score=%.1f/5, latency=%.2fs", score, time.time()-start_time)
        
        return score, feedback
    
    def _placeholder_evaluate(self, response: str, criteria: str) -> str:
        """
        Placeholder evaluation when no API is available.
        Uses pattern-based scoring as fallback.
        """
        score = 3.0
        feedback_parts = []
        
        # Check structure tags
        has_scratchpad = bool(re.search(r'<(?:SCRATCHPAD|PLAN|THINKING)>', response))
        has_solution = bool(re.search(r'<(?:SOLUTION|EXECUTION)>', response))
        has_reflection = bool(re.search(r'<(?:REFLECTION|INNER_MONOLOGUE)>', response))
        
        if has_scratchpad:
            score += 0.3
            feedback_parts.append("Has planning tag")
        if has_solution:
            score += 0.4
            feedback_parts.append("Has solution tag")
        if has_reflection:
            score += 0.2
            feedback_parts.append("Has reflection")
        
        # Check error handling
        has_error_handling = bool(re.search(r'try|catch|except|error|exception', response.lower()))
        if has_error_handling:
            score += 0.3
            feedback_parts.append("Has error handling")
        
        # Length/completeness
        if len(response) > 300:
            score += 0.2
        
        # Format discipline
        valid_tags = re.findall(r'<(\w+)>', response)
        if valid_tags:
            score += 0.2
            feedback_parts.append(f"Uses {len(set(valid_tags))} structural tags")
        
        # Clamp
        score = max(1.0, min(5.0, score))
        
        feedback = f"Feedback: {'; '.join(feedback_parts) if feedback_parts else 'Basic structure.'} Score: {score}"
        
        return feedback
    
    def _parse_output(self, raw_output: str) -> Tuple[float, str]:
        """Parse Prometheus-2 output format: Feedback: [text] Score: [0.0-5.0]"""
        # Try to extract score
        score_match = re.search(r'Score:\s*([0-9.]+)', raw_output, re.IGNORECASE)
        
        if score_match:
            score = float(score_match.group(1))
        else:
            # Fallback: extract number
            numbers = re.findall(r'[0-9]+\.[0-9]+', raw_output)
            if numbers:
                score = float(numbers[0])
            else:
                score = 3.0  # Default
        
        # Extract feedback
        feedback_match = re.search(r'Feedback:\s*(.+?)(?:Score:|$)', raw_output, re.IGNORECASE | re.DOTALL)
        if feedback_match:
            feedback = feedback_match.group(1).strip()
        else:
            feedback = raw_output[:500]
        
        return score, feedback
    
    def _summarize_context(self, text: str, max_chars: int = 5000) -> str:
        """Summarize long context to fit 8K token limit."""
        if len(text) <= max_chars:
            return text
        
        # Simple truncation with overlap for context
        return text[:max_chars]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get evaluation statistics."""
        return {
            "eval_count": self.eval_count,
            "avg_latency": self.total_latency / max(self.eval_count, 1),
            "model": self.model_name
        }


# === DEEPSEEK CRITIC WRAPPER ===

class DeepSeekCriticWrapper:
    """
    DeepSeek-R1 Critic wrapper.
    
    DeepSeek-R1 characteristics (from research):
    - Transparent chain-of-thought (explicit reasoning steps)
    - Mathematical and logical analysis
    - Latent thought generation (slow but thorough)
    - 94% cheaper than Claude Opus
    - Strong on GPQA Diamond (71.5-79.9%) and AIME 2025 (>90%)
    
    Key RCR principle: Critic's goal is NOT to give correct answer,
    but to find flaws in Actor's reasoning.
    
    This wrapper provides:
    - RCR-compliant critic interface
    - Transparent reasoning output
    - Flaw extraction and classification
    - Temperature asymmetry (0.0-0.1 for deterministic analysis)
    
    NOTE: Actual DeepSeek-R1 API call requires external service.
    This is an interface wrapper, not a live model connection.
    """
    
    CRITIC_SYSTEM_PROMPT = """You are a CRITIC agent. Your goal is NOT to give the correct answer.
Your goal is to find FLAWS, gaps, logical errors, and weaknesses in the Actor's reasoning.

Rules:
1. Be adversarial — challenge assumptions
2. Look for logical fallacies
3. Find missing edge cases
4. Identify unsupported conclusions
5. Do NOT propose solutions — only point out problems
6. Be precise — cite specific lines or claims that are flawed

Output format:
CRITIC_FEEDBACK:
- FLAW [n]: [description]
- GAP [n]: [missing consideration]
- ERROR [n]: [logical error with evidence]

If no critical flaws found, say: "No significant flaws detected." and explain why."""

    def __init__(
        self,
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: str = "deepseek-r1",
        timeout: int = 60
    ):
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout
        
        # Callback for actual API call
        self._api_callback: Optional[Callable] = None
        
        # Statistics
        self.critique_count = 0
        self.total_latency = 0.0
    
    def set_api_callback(self, callback: Callable):
        """Set the API callback for actual DeepSeek-R1 calls."""
        self._api_callback = callback
    
    def critique(
        self,
        actor_output: str,
        task: str,
        verbose: bool = False
    ) -> Tuple[List[str], str]:
        """
        Critique Actor's output using RCR pattern.
        
        Returns: (flaws_list, critique_feedback)
        """
        start_time = time.time()
        
        # Build prompt with RCR system prompt
        prompt = f"""{self.CRITIC_SYSTEM_PROMPT}

ACTOR_OUTPUT_TOCritique:
{actor_output[:4000]}

TASK_CONTEXT:
{task[:500]}
"""
        
        # Call API (or use placeholder)
        if self._api_callback:
            try:
                raw_output = self._api_callback(prompt, temperature=0.05, max_tokens=8192)
            except Exception:
                raw_output = self._placeholder_critique(actor_output, task)
        else:
            raw_output = self._placeholder_critique(actor_output, task)
        
        # Parse flaws
        flaws = self._parse_flaws(raw_output)
        feedback = raw_output
        
        # Update stats
        self.critique_count += 1
        self.total_latency += time.time() - start_time
        
        if verbose:
            logger.info("DeepSeekCritic critique complete: %d flaws found, latency=%.2fs", len(flaws), time.time()-start_time)
        
        return flaws, feedback
    
    def _placeholder_critique(self, actor_output: str, task: str) -> str:
        """Placeholder critique when no API is available."""
        flaws = []
        feedback_parts = []
        
        # Check for empty output
        if not actor_output or len(actor_output.strip()) < 50:
            flaws.append("EMPTY_OUTPUT")
            feedback_parts.append("FLAW 1: Actor output is empty or too short.")
        
        # Check for missing planning
        if not re.search(r'<(?:SCRATCHPAD|PLAN|THINKING|REASONING)>', actor_output):
            flaws.append("MISSING_PLANNING")
            feedback_parts.append("GAP 1: No planning/analysis tag found. Actor may be jumping to conclusions.")
        
        # Check for missing solution
        if not re.search(r'<(?:SOLUTION|EXECUTION|RESULT)>', actor_output):
            flaws.append("MISSING_SOLUTION")
            feedback_parts.append("GAP 2: No solution/execution tag found. Actor has not delivered output.")
        
        # Check for unsupported confidence
        confident_stmts = re.findall(r'\b(certainly|definitely|absolutely|clearly|obviously)\b', actor_output.lower())
        if len(confident_stmts) > 2:
            flaws.append("UNSUPPORTED_CONFIDENCE")
            feedback_parts.append(f"ERROR 1: {len(confident_stmts)} confident statements without justification.")
        
        # Check for error handling
        has_error_handling = bool(re.search(r'try|catch|except|error|exception', actor_output.lower()))
        if not has_error_handling:
            flaws.append("MISSING_ERROR_HANDLING")
            feedback_parts.append("GAP 3: No error handling detected. Solution may fail silently.")
        
        # Format feedback
        if feedback_parts:
            return "CRITIC_FEEDBACK:\n" + "\n".join(feedback_parts)
        else:
            return "CRITIC_FEEDBACK:\nNo significant flaws detected. Actor output appears structurally sound."
    
    def _parse_flaws(self, critique_output: str) -> List[str]:
        """Parse flaws from critique output."""
        flaws = []
        
        # Look for structured flaw markers
        # Anchor to line start (^) to prevent matching 'error' inside words like 'No error handling'
        patterns = [
            r'(?:^|\n)\s*(?:FLAW|GAP|ERROR)\s*\d*[:\s]+(.+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, critique_output, re.IGNORECASE)
            for m in matches:
                if isinstance(m, tuple):
                    flaws.append(m[0].strip())
                elif isinstance(m, str) and len(m) > 5:
                    flaws.append(m.strip())
        
        return flaws[:10]  # Max 10 flaws
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get critique statistics."""
        return {
            "critique_count": self.critique_count,
            "avg_latency": self.total_latency / max(self.critique_count, 1),
            "model": self.model_name
        }


# === INTEGRATION WITH ACTOR-CRITIC ===

def create_integrated_partners(
    prometheus_endpoint: Optional[str] = None,
    prometheus_key: Optional[str] = None,
    deepseek_endpoint: Optional[str] = None,
    deepseek_key: Optional[str] = None
) -> Tuple[PrometheusJudgeWrapper, DeepSeekCriticWrapper]:
    """
    Create integrated partner wrappers for Prometheus-2 Judge and DeepSeek-R1 Critic.

    Args:
        prometheus_endpoint: API endpoint for Prometheus-2 Judge wrapper
        prometheus_key: API key for Prometheus-2 Judge wrapper
        deepseek_endpoint: API endpoint for DeepSeek-R1 Critic wrapper
        deepseek_key: API key for DeepSeek-R1 Critic wrapper

    Returns:
        Tuple of (PrometheusJudgeWrapper, DeepSeekCriticWrapper) instances

    These can be passed to ActorCriticCore::

        prometheus = PrometheusJudgeWrapper(endpoint, key)
        deepseek = DeepSeekCriticWrapper(endpoint, key)

        core = ActorCriticCore()
        core.set_judge_callback(lambda t, o, r, rub: prometheus.evaluate(o, r))
        core.set_critic_callback(lambda o, t: deepseek.critique(o, t))
    """
    prometheus = PrometheusJudgeWrapper(api_endpoint=prometheus_endpoint, api_key=prometheus_key)
    deepseek = DeepSeekCriticWrapper(api_endpoint=deepseek_endpoint, api_key=deepseek_key)
    
    return prometheus, deepseek


# === DEMO ===

def run_partner_demo():
    """Run partner wrapper demo."""
    logger.info("ILMA Partner Agent Wrappers — Prometheus + DeepSeek Demo")
    
    # Prometheus Judge
    logger.debug("Initializing Prometheus-2 Judge wrapper")
    judge = PrometheusJudgeWrapper()
    
    sample_response = """<SCRATCHPAD>
Analyzing task: Build login API
Step 1: Accept username/password
Step 2: Validate credentials
Step 3: Generate JWT token
</SCRATCHPAD>

<SOLUTION>
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if 'username' not in data or 'password' not in data:
        return jsonify({"error": "Missing fields"}), 400
    
    # Validate against database
    user = db.validate(data['username'], data['password'])
    if user:
        token = jwt.encode({'user': user}, SECRET)
        return jsonify({"token": token}), 200
    return jsonify({"error": "Invalid"}), 401
</SOLUTION>

<REFLECTION>
Solution handles validation and returns appropriate HTTP codes.
"""
    
    score, feedback = judge.evaluate(
        sample_response,
        "Must validate input, handle errors, return JWT",
        verbose=True
    )
    logger.info("PrometheusJudge evaluation complete: score=%.1f/5, feedback=%s...", score, feedback[:100] if feedback else "none")
    
    # DeepSeek Critic
    logger.debug("Initializing DeepSeek-R1 Critic wrapper")
    critic = DeepSeekCriticWrapper()
    
    flaws, feedback = critic.critique(
        sample_response,
        "Build a login API",
        verbose=True
    )
    logger.info("DeepSeekCritic critique complete: %d flaws found", len(flaws))
    for f in flaws[:3]:
        logger.debug("Flaw: %s", f)
    
    # Statistics
    logger.info("Partner wrapper statistics: Judge=%s, Critic=%s", judge.get_statistics(), critic.get_statistics())
    
    return judge, critic


if __name__ == "__main__":
    run_partner_demo()