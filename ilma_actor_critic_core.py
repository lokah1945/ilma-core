#!/usr/bin/env python3
"""
ILMA Actor-Critic Core v1.0
============================
Actor-Critic orchestration system based on Gemini multi-agent architecture.
Implements the asymmetric triad: Actor (ILMA), Critic (DeepSeek), Judge (Prometheus-2).

Actor: ILMA (temperature 0.4-0.7) — executes, proposes solutions
Critic: Partner model (temperature 0.0-0.1) — finds flaws, analyzes
Judge: Prometheus-2 (temperature 0.0) — final rubric evaluation (1-5)

Zero human-in-the-loop when self_improve=True.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ILMA paths - configurable via environment variable
ILMA_PROFILE = Path(os.environ.get("ILMA_PROFILE", "/root/.hermes/profiles/ilma"))
WORKSPACE = ILMA_PROFILE

# Add ILMA paths
sys.path.insert(0, str(WORKSPACE))


# === ENUMS ===

class AgentRole(Enum):
    """Actor-Critic-Judge roles."""
    ACTOR = "actor"       # ILMA — executor, solution proposer
    CRITIC = "critic"     # DeepSeek — flaw finder, logical analyzer
    JUDGE = "judge"       # Prometheus-2 — final rubric evaluator


class VerdictLevel(Enum):
    """Pass/Fail/Warn levels."""
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    ERROR = "ERROR"


class DebateStatus(Enum):
    """Debate round status."""
    PENDING = "pending"
    ACTOR_TURN = "actor_turn"
    CRITIC_TURN = "critic_turn"
    JUDGE_TURN = "judge_turn"
    COMPLETE = "complete"
    EXHAUSTED = "exhausted"


# === DATA CLASSES ===

@dataclass
class TemperatureConfig:
    """Temperature configuration for asymmetric roles."""
    actor: float = 0.5          # ILMA: creative, flexible (0.4-0.7)
    critic: float = 0.05        # DeepSeek: deterministic (0.0-0.1)
    judge: float = 0.0          # Prometheus: strict, no creativity
    actor_max_tokens: int = 4096
    critic_max_tokens: int = 8192
    judge_max_tokens: int = 2048


@dataclass
class ActorCriticMessage:
    """Single message in the debate thread."""
    id: str
    role: AgentRole
    content: str
    timestamp: datetime
    round_num: int
    is_revision: bool = False
    flaw_detected: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "round_num": self.round_num,
            "is_revision": self.is_revision,
            "flaw_detected": self.flaw_detected,
            "metadata": self.metadata
        }


@dataclass
class DebateRound:
    """Single debate round."""
    round_num: int
    actor_input: Optional[str] = None
    actor_output: Optional[str] = None
    critic_feedback: Optional[str] = None
    flaws_found: List[str] = field(default_factory=list)
    judge_score: Optional[float] = None
    judge_feedback: Optional[str] = None
    status: DebateStatus = DebateStatus.PENDING
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "actor_input": self.actor_input,
            "actor_output": self.actor_output,
            "critic_feedback": self.critic_feedback,
            "flaws_found": self.flaws_found,
            "judge_score": self.judge_score,
            "judge_feedback": self.judge_feedback,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class DebateSession:
    """Complete debate session with multi-round history."""
    session_id: str
    task: str
    target_criteria: str
    max_rounds: int = 5
    temperature: TemperatureConfig = field(default_factory=TemperatureConfig)
    rounds: List[DebateRound] = field(default_factory=list)
    current_round: int = 0
    final_verdict: Optional[VerdictLevel] = None
    final_score: Optional[float] = None
    lessons_extracted: List[str] = field(default_factory=list)
    rubric: Optional[RubricCriteria] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    def add_round(self, round_data: DebateRound):
        self.rounds.append(round_data)
        self.current_round = len(self.rounds)
    
    def get_debate_thread(self) -> List[ActorCriticMessage]:
        """Extract all messages from all rounds."""
        messages = []
        for r in self.rounds:
            if r.actor_output:
                messages.append(ActorCriticMessage(
                    id=str(uuid.uuid4()),
                    role=AgentRole.ACTOR,
                    content=r.actor_output,
                    timestamp=r.timestamp,
                    round_num=r.round_num,
                    is_revision=(r.round_num > 1)
                ))
            if r.critic_feedback:
                messages.append(ActorCriticMessage(
                    id=str(uuid.uuid4()),
                    role=AgentRole.CRITIC,
                    content=r.critic_feedback,
                    timestamp=r.timestamp,
                    round_num=r.round_num,
                    flaw_detected="; ".join(r.flaws_found) if r.flaws_found else None
                ))
            if r.judge_feedback:
                messages.append(ActorCriticMessage(
                    id=str(uuid.uuid4()),
                    role=AgentRole.JUDGE,
                    content=r.judge_feedback,
                    timestamp=r.timestamp,
                    round_num=r.round_num,
                    metadata={"score": r.judge_score}
                ))
        return messages
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "task": self.task,
            "target_criteria": self.target_criteria,
            "max_rounds": self.max_rounds,
            "current_round": self.current_round,
            "final_verdict": self.final_verdict.value if self.final_verdict else None,
            "final_score": self.final_score,
            "rounds": [r.to_dict() for r in self.rounds],
            "lessons_extracted": self.lessons_extracted,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


@dataclass
class RubricCriteria:
    """Judge rubric — 1-5 scale for each criterion."""
    level_5: str  # Perfect: all criteria met, handles tool failures elegantly, no redundant reasoning, perfect tag structure
    level_4: str  # Excellent: meets most criteria, minor redundancies
    level_3: str  # Good: functional but has logical gaps
    level_2: str  # Adequate: works but major flaws
    level_1: str  # Failing: does not meet basic criteria
    
    @staticmethod
    def default_rubric() -> "RubricCriteria":
        return RubricCriteria(
            level_5="Target fully achieved. Tool failures handled elegantly. No redundant reasoning. Perfect structural tags.",
            level_4="Target mostly achieved. Minor redundancies or gaps. Mostly clean structure.",
            level_3="Functional but significant logical gaps. Some redundant reasoning. Partially correct structure.",
            level_2="Target inadequately achieved. Major flaws in logic or structure. Missing key elements.",
            level_1="Target not achieved. Fundamental failures. Does not meet minimum criteria."
        )
    
    def evaluate(self, score: float) -> str:
        """Return rubric description for score."""
        if score >= 4.5:
            return self.level_5
        elif score >= 3.5:
            return self.level_4
        elif score >= 2.5:
            return self.level_3
        elif score >= 1.5:
            return self.level_2
        else:
            return self.level_1


# === ACTOR-CRITIC CORE ===

class ActorCriticCore:
    """
    Main Actor-Critic orchestrator.
    
    Implements the Gemini multi-agent architecture:
    - Actor (ILMA): Receives task, produces solution attempts
    - Critic (DeepSeek): Observes Actor output, finds flaws
    - Judge (Prometheus-2): Evaluates final synthesis against rubric
    
    Zero human-in-the-loop when self_improve=True.
    """
    
    def __init__(
        self,
        model_router=None,
        self_improve: bool = False,
        max_rounds: int = 5,
        judge_threshold: float = 4.0,
        temperature: Optional[TemperatureConfig] = None
    ):
        self.self_improve = self_improve
        self.max_rounds = max_rounds
        self.judge_threshold = judge_threshold
        self.temperature = temperature or TemperatureConfig()
        
        # Model router (ILMA's built-in)
        self.model_router = model_router
        
        # Session storage
        self.active_sessions: Dict[str, DebateSession] = {}
        self.completed_sessions: Dict[str, DebateSession] = {}
        
        # Callbacks for external models (DeepSeek, Prometheus-2)
        # These are PLACEHOLDER — actual integration requires API keys
        self._critic_callback: Optional[Callable] = None
        self._judge_callback: Optional[Callable] = None
        
        # ILMA's own Actor callback (uses model router)
        self._actor_callback: Optional[Callable] = self._ilma_actor_execute
        
        # Lesson storage
        self.lesson_memory: List[Dict[str, Any]] = []
        
    def set_critic_callback(self, callback: Callable[[str, str], str]):
        """Set external critic callback (DeepSeek or equivalent).
        
        Args:
            callback: Function that takes (actor_output, task) and returns critic feedback.
        """
        self._critic_callback = callback
    
    def set_judge_callback(self, callback: Callable[[str, str, str, RubricCriteria], Tuple[float, str]]):
        """Set external judge callback (Prometheus-2 or equivalent).
        
        Callback signature: (task, actor_output, reference, rubric) -> (score, feedback)
        """
        self._judge_callback = callback
    
    def _ilma_actor_execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """ILMA as Actor — executes task using model router."""
        if self.model_router:
            try:
                # Route to best model with Actor temperature
                result = self.model_router(task, mode="solve")
                return result if result else self._fallback_actor(task, context)
            except Exception:
                return self._fallback_actor(task, context)
        return self._fallback_actor(task, context)
    
    def _fallback_actor(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Fallback actor when model router unavailable."""
        return f"[ACTOR PLACEHOLDER] Task: {task[:200]}... Context keys: {list(context.keys()) if context else []}"
    
    def _default_critic(self, actor_output: str, task: str) -> Tuple[List[str], str]:
        """
        Default critic implementation (when no external callback).
        
        Analyzes actor output for:
        - Logical flaws
        - Missing edge cases
        - Tool failure handling
        - Redundant reasoning
        - Tag structure issues
        
        Returns: (flaws_list, feedback_string)
        """
        flaws = []
        feedback_parts = []
        
        # Check for empty output
        if not actor_output or len(actor_output.strip()) < 10:
            flaws.append("EMPTY_OUTPUT")
            feedback_parts.append("Actor output is empty or too short.")
            return flaws, "CRITIC_FEEDBACK: " + "; ".join(feedback_parts)
        
        # Check for placeholder markers
        # Note: [TODO] is intentionally included to detect placeholder content, not as an actual TODO
        placeholder_patterns = [
            r"\[ACTOR\s+ERROR\]",
            r"\[PLACEHOLDER\]",
            r"\[TODO\]",
            r"\<TBD\>",
            r"STUB",
        ]
        for pattern in placeholder_patterns:
            if re.search(pattern, actor_output, re.IGNORECASE):
                flaws.append("PLACEHOLDER_DETECTED")
                feedback_parts.append("Solution contains placeholder or stub content.")
                break
        
        # Check for redundant reasoning markers
        reflection_count = actor_output.count("<REFLECTION>")
        if reflection_count > 3:
            flaws.append("EXCESSIVE_REFLECTION")
            feedback_parts.append(f"Excessive <REFLECTION> tags ({reflection_count}) indicate circular reasoning.")
        elif reflection_count == 0:
            flaws.append("MISSING_REFLECTION")
            feedback_parts.append("No <REFLECTION> tag found - no self-verification performed.")
        
        # Check for tool failure mentions
        has_error = "error" in actor_output.lower()
        has_handle = "handle" in actor_output.lower() or "handling" in actor_output.lower()
        if has_error and not has_handle:
            flaws.append("UNHANDLED_TOOL_FAILURE")
            feedback_parts.append("Tool failures detected without proper error handling.")
        elif has_error and has_handle:
            feedback_parts.append("✓ Error handling present.")
        
        # Check structure tags
        has_plan = "<PLAN>" in actor_output or "<SCRATCHPAD>" in actor_output
        has_execution = "<EXECUTION>" in actor_output or "<SOLUTION>" in actor_output
        has_result = "<RESULT>" in actor_output or "<OUTPUT>" in actor_output
        
        if not has_plan:
            flaws.append("MISSING_PLAN")
            feedback_parts.append("Missing <PLAN> or <SCRATCHPAD> tag.")
        else:
            feedback_parts.append("✓ Planning structure present.")
            
        if not has_execution:
            flaws.append("MISSING_EXECUTION")
            feedback_parts.append("Missing <EXECUTION> or <SOLUTION> tag.")
        else:
            feedback_parts.append("✓ Execution structure present.")
        
        if not has_result:
            flaws.append("MISSING_RESULT")
            feedback_parts.append("Missing <RESULT> or <OUTPUT> tag - no clear deliverable.")
        
        # Check solution completeness (rough heuristic)
        # Good solutions should have substantial content
        content_lines = [l for l in actor_output.split('\n') if l.strip() and not l.startswith('<')]
        if len(content_lines) < 3:
            flaws.append("THIN_SOLUTION")
            feedback_parts.append(f"Solution only has {len(content_lines)} content lines - appears incomplete.")
        
        # Check for confidence without justification
        lines = actor_output.split('\n')
        confident_unsupported = 0
        for line in lines:
            if any(w in line.lower() for w in ['certainly', 'definitely', 'absolutely', 'clearly']):
                if not any(m in line.lower() for m in ['because', 'since', 'evidence', 'reason', 'based on']):
                    confident_unsupported += 1
        
        if confident_unsupported > 2:
            flaws.append("UNSUPPORTED_CONFIDENCE")
            feedback_parts.append(f"{confident_unsupported} confident statements without justification.")
        elif confident_unsupported == 0 and len(lines) > 5:
            feedback_parts.append("✓ Appropriate hedging in reasoning.")
        
        # Check for task alignment
        task_keywords = set(task.lower().split()[:10])
        content_keywords = set(' '.join(content_lines).lower().split()[:50])
        overlap = task_keywords & content_keywords
        if len(overlap) < 2 and len(task_keywords) > 3:
            flaws.append("WEAK_TASK_ALIGNMENT")
            feedback_parts.append("Solution appears misaligned with task requirements.")
        
        # Build feedback
        if flaws:
            feedback = "CRITIC_FEEDBACK: " + "; ".join(feedback_parts)
        else:
            feedback = "CRITIC_FEEDBACK: No critical flaws detected. Solution appears sound."
        
        return flaws[:10], feedback
    
    def _default_judge(
        self,
        task: str,
        actor_output: str,
        reference: str,
        rubric: RubricCriteria
    ) -> Tuple[float, str]:
        """
        Default judge implementation (when no external callback).
        
        Evaluates actor output against rubric criteria (1-5).
        Returns: (score, feedback)
        """
        score = 2.5  # Start at minimum viable
        feedback_parts = []
        
        # === STRUCTURE CHECKS (max 1.0 point) ===
        structure_score = 0.0
        has_plan = "<PLAN>" in actor_output or "<SCRATCHPAD>" in actor_output
        has_execution = "<EXECUTION>" in actor_output or "<SOLUTION>" in actor_output
        has_result = "<RESULT>" in actor_output or "<OUTPUT>" in actor_output or "<CONCLUSION>" in actor_output
        has_reflection = "<REFLECTION>" in actor_output
        
        if has_plan:
            structure_score += 0.25
        if has_execution:
            structure_score += 0.25
        if has_result:
            structure_score += 0.25
        if has_reflection:
            structure_score += 0.25
        
        score += structure_score
        if structure_score >= 0.75:
            feedback_parts.append(f"✓ Excellent structure ({structure_score:.2f}/1.0)")
        elif structure_score >= 0.5:
            feedback_parts.append(f"~ Adequate structure ({structure_score:.2f}/1.0)")
        else:
            feedback_parts.append(f"✗ Poor structure ({structure_score:.2f}/1.0)")
        
        # === COMPLETENESS CHECKS (max 1.0 point) ===
        content_lines = [l for l in actor_output.split('\n') if l.strip() and not l.startswith('<')]
        completeness_score = 0.0
        
        if len(content_lines) >= 10:
            completeness_score += 0.4
        elif len(content_lines) >= 5:
            completeness_score += 0.2
        elif len(content_lines) < 3:
            completeness_score -= 0.3  # Penalize thin solutions
        
        # Check for code blocks or actual content
        has_code = "```" in actor_output or "def " in actor_output or "class " in actor_output
        has_list = any(m in actor_output for m in ['1.', '2.', '3.', '- ', '* ', '• '])
        
        if has_code:
            completeness_score += 0.3
        if has_list:
            completeness_score += 0.2
        
        score += completeness_score
        if completeness_score >= 0.7:
            feedback_parts.append(f"✓ Comprehensive solution ({completeness_score:.2f}/1.0)")
        elif completeness_score >= 0.4:
            feedback_parts.append(f"~ Partial solution ({completeness_score:.2f}/1.0)")
        else:
            feedback_parts.append(f"✗ Incomplete solution ({completeness_score:.2f}/1.0)")
        
        # === CORRECTNESS CHECKS (max 1.5 points) ===
        correctness_score = 0.0
        
        # Error handling
        if "error" in actor_output.lower():
            if any(h in actor_output.lower() for h in ["handle", "try", "except", "catch"]):
                correctness_score += 0.4
            else:
                correctness_score -= 0.2  # Mentions error but no handling
        
        # No placeholder indicators
        placeholder_found = any(p in actor_output.lower() for p in ["[placeholder]", "[todo]", "[tbd]", "stub", "not implemented"])
        if placeholder_found:
            correctness_score -= 0.5
        else:
            correctness_score += 0.2
        
        # No excessive reflection (circular reasoning)
        reflection_count = actor_output.count("<REFLECTION>")
        if reflection_count == 0:
            correctness_score -= 0.2  # No self-verification
        elif reflection_count <= 2:
            correctness_score += 0.2  # Appropriate
        elif reflection_count <= 4:
            correctness_score += 0.0  # Acceptable
        else:
            correctness_score -= 0.3  # Excessive
        
        # Proper hedging vs overconfidence
        lines = actor_output.split('\n')
        confident_unsupported = 0
        appropriately_hedged = 0
        for line in lines:
            if any(w in line.lower() for w in ['certainly', 'definitely', 'absolutely', 'clearly']):
                if any(m in line.lower() for m in ['because', 'since', 'evidence', 'reason', 'based on']):
                    appropriately_hedged += 1
                elif len(line) > 20:
                    confident_unsupported += 1
        
        if confident_unsupported > 3:
            correctness_score -= 0.3
        elif appropriately_hedged >= 2:
            correctness_score += 0.3
        
        # Alignment with task
        if len(task) > 10:
            task_keywords = set(task.lower().split()[:10])
            content_words = ' '.join(content_lines).lower()
            content_keywords = set(content_words.split()[:50])
            overlap = task_keywords & content_keywords
            if len(overlap) >= 3:
                correctness_score += 0.3
            elif len(overlap) < 1 and len(task_keywords) > 3:
                correctness_score -= 0.3
        
        score += correctness_score
        if correctness_score >= 1.0:
            feedback_parts.append(f"✓ Sound reasoning ({correctness_score:.2f}/1.5)")
        elif correctness_score >= 0.5:
            feedback_parts.append(f"~ Reasonable with issues ({correctness_score:.2f}/1.5)")
        else:
            feedback_parts.append(f"✗ Reasoning problems ({correctness_score:.2f}/1.5)")
        
        # === TOOL USE CHECKS (max 0.5 points) ===
        tool_score = 0.0
        if "terminal" in actor_output.lower() or "bash" in actor_output.lower():
            tool_score += 0.1
        if "read_file" in actor_output or "write_file" in actor_output:
            tool_score += 0.1
        if "search" in actor_output.lower() or "grep" in actor_output.lower():
            tool_score += 0.1
        if "import" in actor_output and "os" in actor_output:
            tool_score += 0.1
        if "error" in actor_output.lower() and "handle" in actor_output.lower():
            tool_score += 0.1
        
        score += tool_score
        if tool_score >= 0.4:
            feedback_parts.append(f"✓ Good tool utilization ({tool_score:.2f}/0.5)")
        elif tool_score >= 0.2:
            feedback_parts.append(f"~ Some tool use ({tool_score:.2f}/0.5)")
        else:
            feedback_parts.append(f"~ Limited tool use ({tool_score:.2f}/0.5)")
        
        # === EDGE CASE HANDLING (max 1.0 points) ===
        edge_score = 0.0
        content_lower = actor_output.lower()
        
        edge_keywords = [
            "edge case", "boundary", "null", "none", "empty", "invalid",
            "timeout", "retry", "fallback", "concurrent", "race condition"
        ]
        edge_mentions = sum(1 for kw in edge_keywords if kw in content_lower)
        if edge_mentions >= 3:
            edge_score += 0.5
        elif edge_mentions >= 1:
            edge_score += 0.25
        
        # Error recovery patterns
        if "retry" in content_lower or "fallback" in content_lower:
            edge_score += 0.25
        if "timeout" in content_lower or "deadline" in content_lower:
            edge_score += 0.25
        
        score += edge_score
        if edge_score >= 0.75:
            feedback_parts.append(f"✓ Handles edge cases well ({edge_score:.2f}/1.0)")
        elif edge_score >= 0.4:
            feedback_parts.append(f"~ Some edge case awareness ({edge_score:.2f}/1.0)")
        else:
            feedback_parts.append(f"~ Edge case handling not evident ({edge_score:.2f}/1.0)")
        
        # === FINALIZE SCORE ===
        # Clamp to 1-5 range
        score = max(1.0, min(5.0, score))
        
        # Round to nearest 0.5
        score = round(score * 2) / 2
        
        rubric_desc = rubric.evaluate(score)
        feedback = f"Judge: {score}/5. " + " ".join(feedback_parts) + f" | {rubric_desc}"
        
        return score, feedback
    
    def create_session(
        self,
        task: str,
        target_criteria: str,
        max_rounds: Optional[int] = None,
        rubric: Optional[RubricCriteria] = None
    ) -> DebateSession:
        """Create new debate session."""
        session = DebateSession(
            session_id=str(uuid.uuid4())[:8],
            task=task,
            target_criteria=target_criteria,
            max_rounds=max_rounds or self.max_rounds,
            temperature=self.temperature,
            rubric=rubric or RubricCriteria.default_rubric()
        )
        self.active_sessions[session.session_id] = session
        return session
    
    def execute_round(
        self,
        session_id: str,
        actor_context: Optional[Dict[str, Any]] = None
    ) -> DebateRound:
        """Execute single debate round.
        
        Args:
            session_id: The debate session ID.
            actor_context: Optional context dict for the actor callback.
            
        Returns:
            DebateRound with actor output, critic feedback, and judge score.
            
        Raises:
            ValueError: If session not found.
            RuntimeError: If session exhausted max rounds.
        """
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found or completed.")
        
        session = self.active_sessions[session_id]
        
        if session.current_round >= session.max_rounds:
            session.final_verdict = VerdictLevel.FAIL
            session.completed_at = datetime.now()
            self.completed_sessions[session_id] = session
            del self.active_sessions[session_id]
            raise RuntimeError(f"Session {session_id} exhausted max rounds ({session.max_rounds}).")
        
        # Initialize round
        round_num = session.current_round + 1
        debate_round = DebateRound(round_num=round_num, status=DebateStatus.ACTOR_TURN)
        
        # === ACTOR TURN ===
        if session.current_round == 0:
            # First round: Actor gets original task
            actor_input = session.task
            debate_round.actor_input = actor_input
        else:
            # Subsequent rounds: Actor gets critic feedback from previous round
            prev_round = session.rounds[-1]
            if prev_round.critic_feedback:
                actor_input = f"TASK: {session.task}\n\nCRITIC_FEEDBACK: {prev_round.critic_feedback}"
                debate_round.actor_input = actor_input
        
        # Execute Actor (ILMA)
        actor_output = ""
        if self._actor_callback:
            try:
                actor_output = self._actor_callback(session.task, actor_context)
            except Exception as e:
                actor_output = f"[ACTOR_ERROR] {str(e)}"
        
        debate_round.actor_output = actor_output
        
        # === CRITIC TURN ===
        debate_round.status = DebateStatus.CRITIC_TURN
        
        if self._critic_callback:
            try:
                critic_output = self._critic_callback(actor_output, session.task)
                debate_round.critic_feedback = critic_output
                debate_round.flaws_found = self._parse_flaws(critic_output)
            except Exception as e:
                debate_round.critic_feedback = f"[CRITIC_ERROR] {str(e)}"
                debate_round.flaws_found = []
        else:
            # Use default critic
            flaws, feedback = self._default_critic(actor_output, session.task)
            debate_round.critic_feedback = feedback
            debate_round.flaws_found = flaws
        
        # === JUDGE TURN ===
        debate_round.status = DebateStatus.JUDGE_TURN
        
        if self._judge_callback:
            try:
                score, feedback = self._judge_callback(
                    session.task,
                    actor_output,
                    session.target_criteria,
                    session.rubric
                )
                debate_round.judge_score = score
                debate_round.judge_feedback = feedback
            except Exception as e:
                debate_round.judge_score = None
                debate_round.judge_feedback = f"[JUDGE_ERROR] {str(e)}"
        else:
            # Use default judge
            score, feedback = self._default_judge(
                session.task,
                actor_output,
                session.target_criteria,
                session.rubric
            )
            debate_round.judge_score = score
            debate_round.judge_feedback = feedback
        
        # === VERDICT ===
        if debate_round.judge_score is not None:
            if debate_round.judge_score >= self.judge_threshold:
                debate_round.status = DebateStatus.COMPLETE
                session.final_verdict = VerdictLevel.PASS
                session.final_score = debate_round.judge_score
                session.completed_at = datetime.now()
                self.completed_sessions[session_id] = session
                del self.active_sessions[session_id]
            elif session.current_round + 1 >= session.max_rounds:
                debate_round.status = DebateStatus.EXHAUSTED
                session.final_verdict = VerdictLevel.FAIL
                session.final_score = debate_round.judge_score
                session.completed_at = datetime.now()
                self.completed_sessions[session_id] = session
                del self.active_sessions[session_id]
            else:
                debate_round.status = DebateStatus.PENDING
        else:
            debate_round.status = DebateStatus.PENDING

        # === LAYER 9 SELF-IMPROVEMENT: Record verdict to learning system ===
        # Wire verdict → SelfImproveIntegrator (legacy module name dropped 2026-06-19)
        if session.final_verdict in (VerdictLevel.PASS, VerdictLevel.FAIL):
            self._record_verdict_to_learning(session)
        
        # Add round to session
        session.add_round(debate_round)
        
        return debate_round
    
    def _parse_flaws(self, critic_output: str) -> List[str]:
        """Parse flaws from critic output."""
        flaws = []
        
        # Look for structured flaw markers
        patterns = [
            r'FLAW[:\s]+(.+)',
            r'FLAW_\d+[:\s]+(.+)',
            r'\[(\w+)\]',  # [MISSING_X] or [ERROR_Y]
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, critic_output, re.IGNORECASE)
            for m in matches:
                if isinstance(m, tuple):
                    flaws.append(m[0].strip())
                else:
                    flaws.append(m.strip())
        
        # Fallback: split by semicolons if structured
        if not flaws and '; ' in critic_output:
            for part in critic_output.split(';'):
                if len(part) > 5:
                    flaws.append(part.strip())
        
        return flaws[:10]  # Max 10 flaws
    
    def run_debate(
        self,
        task: str,
        target_criteria: str,
        max_rounds: Optional[int] = None,
        verbose: bool = False
    ) -> DebateSession:
        """Run full debate until verdict or exhaustion.
        
        Args:
            task: The task to solve.
            target_criteria: Success criteria for the judge.
            max_rounds: Maximum debate rounds (defaults to self.max_rounds).
            verbose: If True, print round progress.
            
        Returns:
            Completed DebateSession with final verdict and score.
        """
        session = self.create_session(task, target_criteria, max_rounds)
        
        while session.session_id in self.active_sessions:
            try:
                round_result = self.execute_round(session.session_id)
                
                if verbose:
                    logger.info(f"Round {round_result.round_num} - Status: {round_result.status.value}, "
                                f"Score: {round_result.judge_score}, Flaws: {round_result.flaws_found}")
                
                if round_result.status in [DebateStatus.COMPLETE, DebateStatus.EXHAUSTED]:
                    break
                    
            except RuntimeError as e:
                if "exhausted" in str(e).lower():
                    break
                raise
        
        return session
    
    def extract_lessons(self, session: DebateSession) -> List[str]:
        """Extract lessons from completed debate session.
        
        Args:
            session: Completed DebateSession to extract lessons from.
            
        Returns:
            List of lesson strings extracted from the debate.
        """
        lessons = []
        
        if session.final_verdict == VerdictLevel.PASS:
            lessons.append(f"SUCCESS: Task '{session.task[:50]}...' achieved score {session.final_score}")
            
            # What worked
            for r in session.rounds:
                if r.actor_output:
                    # Extract successful patterns
                    if "<PLAN>" in r.actor_output:
                        lessons.append("Used <PLAN> tag for structuring approach")
                    if "<SOLUTION>" in r.actor_output:
                        lessons.append("Delivered solution with <SOLUTION> tag")
                    if "error" in r.actor_output.lower() and "handle" in r.actor_output.lower():
                        lessons.append("Handled errors gracefully")
        
        elif session.final_verdict == VerdictLevel.FAIL:
            lessons.append(f"FAILURE: Task '{session.task[:50]}...' failed after {len(session.rounds)} rounds")
            
            # What went wrong
            for r in session.rounds:
                for flaw in r.flaws_found:
                    lessons.append(f"Flaw detected: {flaw}")
        
        # Store in memory
        self.lesson_memory.extend(lessons)
        
        return lessons
    
    def get_lessons_for_task(self, task: str, limit: int = 5) -> List[str]:
        """Retrieve relevant lessons for similar task."""
        # Simple keyword matching
        task_keywords = set(task.lower().split()[:10])
        
        relevant = []
        for lesson in reversed(self.lesson_memory):
            lesson_keywords = set(lesson.lower().split()[:10])
            overlap = task_keywords & lesson_keywords
            if len(overlap) >= 2:
                relevant.append(lesson)
                if len(relevant) >= limit:
                    break
        
        return relevant
    
    def get_session(self, session_id: str) -> Optional[DebateSession]:
        """Get session by ID (active or completed)."""
        if session_id in self.active_sessions:
            return self.active_sessions[session_id]
        if session_id in self.completed_sessions:
            return self.completed_sessions[session_id]
        return None

    def _record_verdict_to_learning(self, session: DebateSession) -> None:
        """
        LAYER 9 SELF-IMPROVEMENT: Record debate verdict to learning system.
        Wires ActorCritic verdict → SelfImproveIntegrator.
        Called automatically when a debate session completes with PASS or FAIL.
        """
        try:
            import sys as _sys
            from pathlib import Path as _Path

            _ilma_root = _Path("/root/.hermes/profiles/ilma")
            _sys.path.insert(0, str(_ilma_root))

            from ilma_self_improve_integrator import get_integrator

            integrator = get_integrator()

            # Infer task type from task description
            task_lower = session.task.lower()
            if any(w in task_lower for w in ["code", "build", "implement", "api", "function"]):
                task_type = "coding"
            elif any(w in task_lower for w in ["write", "blog", "article", "content"]):
                task_type = "writing"
            elif any(w in task_lower for w in ["research", "find", "search", "analys"]):
                task_type = "research"
            else:
                task_type = "general"

            # Determine quality from verdict
            if session.final_verdict == VerdictLevel.PASS:
                quality = session.final_score / 5.0 if session.final_score else 0.85
            else:
                quality = session.final_score / 5.0 * 0.5 if session.final_score else 0.3

            # Collect errors from flaws
            errors = []
            for r in session.rounds:
                for flaw in r.flaws_found:
                    errors.append(flaw[:80])

            # Extract models from agent roles
            actor_model = "actor-ILMA"
            critic_model = "critic-DeepSeek"
            judge_model = "judge-Prometheus"

            # Record to self-improve integrator
            integrator.record_result(
                task_type=task_type,
                task_description=session.task[:100],
                model_used=actor_model,
                provider="actor-critic",
                result_quality=quality,
                execution_time_ms=0.0,
                errors=errors[:3] if errors else [],
                verified=(session.final_verdict == VerdictLevel.PASS),
            )

            # Extract lessons if self_improve is enabled
            if self.self_improve:
                lessons = self.extract_lessons(session)
                for lesson in lessons[:5]:
                    try:
                        integrator.learning_logger.log_insight(
                            summary=f"Debate lesson from {task_type}",
                            what_discovered=lesson[:100],
                            why_useful="Actor-Critic verdict analysis",
                            source="actor_critic_debate",
                            area=task_type,
                            tags=["actor-critic", "debate", "verdict", task_type],
                        )
                    except Exception:
                        pass

        except Exception as e:
            logger.debug(f"Learning recording skipped in ActorCritic: {e}")

    def list_active_sessions(self) -> List[str]:
        return list(self.active_sessions.keys())
    
    def list_completed_sessions(self) -> List[str]:
        return list(self.completed_sessions.keys())


# === STANDALONE EXECUTION ===

def run_actor_critic_demo():
    """Run demo of Actor-Critic system."""
    logger.info("=" * 60)
    logger.info("ILMA Actor-Critic Core v1.0 — Demo")
    logger.info("=" * 60)
    
    core = ActorCriticCore(self_improve=False, max_rounds=3, judge_threshold=4.0)
    
    # Demo task
    task = "Build a REST API endpoint that handles user authentication with JWT tokens."
    target_criteria = "API harus: (1) validate input, (2) generate JWT, (3) handle errors gracefully, (4) return proper HTTP codes"
    
    logger.info(f"TASK: {task}")
    logger.info(f"TARGET: {target_criteria}")
    logger.info(f"MAX_ROUNDS: 3, JUDGE_THRESHOLD: 4.0")
    
    # Run debate (with default callbacks — no external models)
    session = core.run_debate(task, target_criteria, verbose=True)
    
    logger.info(f"{'=' * 60}")
    logger.info(f"FINAL VERDICT: {session.final_verdict.value if session.final_verdict else 'UNKNOWN'}")
    logger.info(f"FINAL SCORE: {session.final_score}")
    logger.info(f"ROUNDS: {len(session.rounds)}/{session.max_rounds}")
    
    # Extract and show lessons
    lessons = core.extract_lessons(session)
    logger.info(f"LESSONS EXTRACTED: {len(lessons)}")
    for l in lessons:
        logger.info(f"  - {l}")
    
    logger.info(f"SESSION_ID: {session.session_id}")
    logger.info(f"THREAD_LENGTH: {len(session.get_debate_thread())} messages")
    
    return session


# === MAIN ===

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ILMA Actor-Critic Core")
    parser.add_argument("--task", type=str, help="Task to solve")
    parser.add_argument("--criteria", type=str, help="Target criteria")
    parser.add_argument("--rounds", type=int, default=3, help="Max debate rounds")
    parser.add_argument("--threshold", type=float, default=4.0, help="Judge threshold (1-5)")
    parser.add_argument("--demo", action="store_true", help="Run demo")
    
    args = parser.parse_args()
    
    if args.demo or not args.task:
        run_actor_critic_demo()
    else:
        core = ActorCriticCore(max_rounds=args.rounds, judge_threshold=args.threshold)
        session = core.run_debate(args.task, args.criteria or "No specific criteria", verbose=True)
        
        logger.info(f"FINAL VERDICT: {session.final_verdict.value}")
        logger.info(f"FINAL SCORE: {session.final_score}")
        
        lessons = core.extract_lessons(session)
        for l in lessons:
            logger.info(f"  LESSON: {l}")

_global_actor_critic_instance = None

def get_actor_critic() -> "ActorCriticCore":
    """Get singleton ActorCriticCore instance."""
    global _global_actor_critic_instance
    if _global_actor_critic_instance is None:
        _global_actor_critic_instance = ActorCriticCore()
    return _global_actor_critic_instance
