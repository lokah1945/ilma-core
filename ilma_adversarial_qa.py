#!/usr/bin/env python3
"""
ILMA Adversarial QA — self-contained adversarial probing of an answer/claim.

History: this used to be a shim importing `hermes_profile_ilma/ilma_adversarial_qa.py`,
a path that does NOT exist — so get_adversarial_qa() raised ModuleNotFoundError on first
use (audit 2026-06-20 Q5). Replaced with a dependency-free implementation that actually
generates adversarial questions and a heuristic robustness score. Public symbols
(AdversarialQAEngine, AdversarialQuestion, QAResult, get_adversarial_qa) are preserved so
runtime wiring / capability registry references stay valid.

An optional judge callback — signature (task, answer, reference, rubric) -> (score, feedback),
compatible with ilma_actor_critic_core — can be supplied to stress-test answers with a real
model; otherwise a deterministic heuristic is used.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

# Signals of common LLM failure modes that an adversary should probe.
_ABSOLUTES = re.compile(r"\b(all|always|never|every|none|no one|everyone|guaranteed|impossible|certainly|definitely)\b", re.I)
_SPECIFICS = re.compile(r"\b\d{2,}(\.\d+)?%?\b|\b(19|20)\d{2}\b")  # numbers, percentages, years
_CITATION = re.compile(r"https?://|\[\d+\]|\bsource\b|\bcitation\b|\baccording to\b|\bref\b", re.I)
_HEDGES = re.compile(r"\b(may|might|could|approximately|roughly|likely|possibly|tends to|generally)\b", re.I)


@dataclass
class AdversarialQuestion:
    question: str
    category: str               # overgeneralization | unsupported | hallucination | completeness | contradiction
    severity: str = "medium"    # low | medium | high


@dataclass
class QAResult:
    answer: str
    questions: List[AdversarialQuestion] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    robustness_score: float = 1.0   # 0..1, higher = more robust to adversarial probing
    passed: bool = True

    def to_dict(self) -> dict:
        return {
            "robustness_score": round(self.robustness_score, 3),
            "passed": self.passed,
            "weaknesses": self.weaknesses,
            "questions": [{"q": q.question, "category": q.category, "severity": q.severity}
                          for q in self.questions],
        }


class AdversarialQAEngine:
    """Generates adversarial questions for an answer and scores its robustness."""

    def __init__(self, pass_threshold: float = 0.6,
                 judge_callback: Optional[Callable[[str, str, str, object], Tuple[float, str]]] = None):
        self.pass_threshold = pass_threshold
        self._judge_callback = judge_callback

    def set_judge_callback(self, cb):
        self._judge_callback = cb

    def generate_questions(self, answer: str, context: str = "", n: int = 6) -> List[AdversarialQuestion]:
        a = answer or ""
        qs: List[AdversarialQuestion] = []

        m = _ABSOLUTES.search(a)
        if m:
            qs.append(AdversarialQuestion(
                f"The answer uses the absolute term '{m.group(0)}'. What is a counterexample where this does NOT hold?",
                "overgeneralization", "high"))
        if _SPECIFICS.search(a) and not _CITATION.search(a):
            qs.append(AdversarialQuestion(
                "Specific figures/dates are stated without a source. How can each number be verified, and could any be hallucinated?",
                "hallucination", "high"))
        if not _CITATION.search(a) and len(a.split()) > 25:
            qs.append(AdversarialQuestion(
                "What evidence or source supports the central claim? Would it survive fact-checking?",
                "unsupported", "medium"))
        if len(a.split()) < 15:
            qs.append(AdversarialQuestion(
                "The answer is very short. Which required aspects of the task are left unaddressed?",
                "completeness", "medium"))
        # always include these generic adversarial probes
        qs.append(AdversarialQuestion(
            "Under what edge cases or boundary conditions would this answer be wrong or incomplete?",
            "completeness", "medium"))
        qs.append(AdversarialQuestion(
            "Does any part of the answer contradict another part, or contradict the task constraints?",
            "contradiction", "medium"))
        return qs[:n]

    def _heuristic_score(self, answer: str) -> Tuple[float, List[str]]:
        a = answer or ""
        score = 1.0
        weaknesses: List[str] = []
        if _ABSOLUTES.search(a):
            score -= 0.25
            weaknesses.append("absolute/overgeneralized claim")
        if _SPECIFICS.search(a) and not _CITATION.search(a):
            score -= 0.30
            weaknesses.append("specific figures without a source (hallucination risk)")
        if not _CITATION.search(a) and len(a.split()) > 25:
            score -= 0.15
            weaknesses.append("central claim unsupported by any source")
        if len(a.split()) < 15:
            score -= 0.20
            weaknesses.append("answer too short / likely incomplete")
        if not _HEDGES.search(a) and _ABSOLUTES.search(a):
            score -= 0.10
            weaknesses.append("strong claims with no calibrated hedging")
        return max(0.0, min(1.0, score)), weaknesses

    def evaluate(self, answer: str, task: str = "", reference: str = "") -> QAResult:
        questions = self.generate_questions(answer, context=reference)
        # Prefer a real model judge if wired; fall back to the deterministic heuristic.
        if self._judge_callback:
            try:
                probe = ("Adversarially stress-test the ANSWER against the TASK. Identify weaknesses, "
                         "unsupported claims, and edge-case failures. Score robustness 0-5.")
                score5, fb = self._judge_callback(task or probe, answer, reference, None)
                score = max(0.0, min(1.0, float(score5) / 5.0))
                weaknesses = [fb] if fb else []
                _, hw = self._heuristic_score(answer)
                weaknesses.extend(hw)
                return QAResult(answer, questions, weaknesses, score, score >= self.pass_threshold)
            except Exception:
                pass  # fall through to heuristic
        score, weaknesses = self._heuristic_score(answer)
        return QAResult(answer, questions, weaknesses, score, score >= self.pass_threshold)

    # backwards-compatible alias
    def run(self, answer: str, task: str = "", reference: str = "") -> QAResult:
        return self.evaluate(answer, task, reference)


_global_aqa_instance: Optional[AdversarialQAEngine] = None


def get_adversarial_qa() -> AdversarialQAEngine:
    """Get singleton AdversarialQAEngine instance."""
    global _global_aqa_instance
    if _global_aqa_instance is None:
        _global_aqa_instance = AdversarialQAEngine()
    return _global_aqa_instance


if __name__ == "__main__":
    eng = get_adversarial_qa()
    demo = "This approach always works and improves performance by 73% with zero downside."
    res = eng.evaluate(demo, task="Explain the approach's reliability")
    import json
    print(json.dumps(res.to_dict(), indent=2))
