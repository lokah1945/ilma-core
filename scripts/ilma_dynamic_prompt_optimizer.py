"""
ILMA v5.0 — DYNAMIC PROMPT OPTIMIZER (DSPy-Style Meta-Prompting)
Principal NLP Engineer: ILMA v5.0

Mechanism that automatically categorizes models and injects optimal
system prompts, few-shot examples, and cognitive tags for each model
to achieve top-tier output quality from FREE providers.

Model Types Handled:
- Instruction-Tuned (Qwen, Llama, Mistral)
- Chat-Tuned (ChatGPT-style, Claude-style)
- Reasoning-Tuned (DeepSeek, Math-specialized)
- Code-Tuned (CodeLlama, StarCoder)
- Indonesian-Tuned (Indonesian-specific models)

SUPREME ARCHITECT: ILMA v5.0 — PERFECTION & OPTIMIZATION UPDATE
"""

from __future__ import annotations
import asyncio
import hashlib
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional, Set, Callable, Awaitable
from pathlib import Path
from collections import defaultdict
import copy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DSPy")


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL TYPE CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

class ModelType(Enum):
    INSTRUCTION_TUNED = "instruction_tuned"
    CHAT_TUNED = "chat_tuned"
    REASONING_TUNED = "reasoning_tuned"
    CODE_TUNED = "code_tuned"
    INDONESIAN_TUNED = "indonesian_tuned"
    GENERAL = "general"


class ModelProvider(Enum):
    NVIDIA = "nvidia"
    OPENROUTER = "openrouter"
    FIREWORKS = "fireworks"
    MISTRAL = "mistral"


@dataclass
class ModelProfile:
    model_id: str
    model_name: str
    provider: ModelProvider
    model_type: ModelType
    base_model: str
    parameter_size: str
    capability_tier: str
    max_context_tokens: int
    current_context_tokens: int = 0
    optimal_system_prompt: str = ""
    prompt_style: str = "concise"
    system_prompt_token_budget: int = 1024
    few_shot_token_budget: int = 2048
    reserved_for_response: int = 4096
    supports_thinking_tags: bool = False
    supports_xml_tags: bool = False
    supports_json_mode: bool = False
    supports_structured_output: bool = False
    supports_indonesian: bool = False
    indonesian_quality_score: float = 0.5
    avg_latency_ms: float = 0.0
    avg_quality_score: float = 0.5
    total_requests: int = 0
    version: str = "1.0.0"
    last_updated: str = ""


MODEL_REGISTRY: Dict[str, ModelProfile] = {
    "nvidia/llama-3.1-nemotron-70b-instruct": ModelProfile(
        model_id="nvidia/llama-3.1-nemotron-70b-instruct",
        model_name="Llama 3.1 70B Nemotron",
        provider=ModelProvider.NVIDIA,
        model_type=ModelType.INSTRUCTION_TUNED,
        base_model="llama-3.1-70b",
        parameter_size="70b",
        capability_tier="high",
        max_context_tokens=128000,
        system_prompt_token_budget=2048,
        few_shot_token_budget=4096,
        reserved_for_response=8192,
        supports_thinking_tags=True,
        supports_xml_tags=True,
        supports_json_mode=True,
        supports_structured_output=True,
        supports_indonesian=True,
        indonesian_quality_score=0.75,
        prompt_style="structured",
        optimal_system_prompt="You are a helpful AI assistant. Follow the user's instructions precisely."
    ),
    "nvidia/llama-3.1-8b-instruct": ModelProfile(
        model_id="nvidia/llama-3.1-8b-instruct",
        model_name="Llama 3.1 8B Instruct",
        provider=ModelProvider.NVIDIA,
        model_type=ModelType.INSTRUCTION_TUNED,
        base_model="llama-3.1-8b",
        parameter_size="8b",
        capability_tier="medium",
        max_context_tokens=128000,
        system_prompt_token_budget=1024,
        few_shot_token_budget=2048,
        reserved_for_response=4096,
        supports_thinking_tags=True,
        supports_xml_tags=True,
        supports_json_mode=True,
        supports_indonesian=True,
        indonesian_quality_score=0.65,
        prompt_style="concise",
        optimal_system_prompt="You are a helpful, concise AI assistant. Keep responses brief."
    ),
    "nvidia/mixtral-8x7b-instruct-v0.1": ModelProfile(
        model_id="nvidia/mixtral-8x7b-instruct-v0.1",
        model_name="Mixtral 8x7B Instruct",
        provider=ModelProvider.NVIDIA,
        model_type=ModelType.INSTRUCTION_TUNED,
        base_model="mixtral-8x7b",
        parameter_size="47b",
        capability_tier="high",
        max_context_tokens=32768,
        system_prompt_token_budget=1536,
        few_shot_token_budget=3072,
        reserved_for_response=6144,
        supports_thinking_tags=True,
        supports_xml_tags=True,
        supports_json_mode=True,
        supports_indonesian=True,
        indonesian_quality_score=0.70,
        prompt_style="structured",
        optimal_system_prompt="You are an expert AI assistant with broad knowledge. Provide well-structured responses."
    ),
    "nvidia/qwen-2.5-72b-instruct": ModelProfile(
        model_id="nvidia/qwen-2.5-72b-instruct",
        model_name="Qwen 2.5 72B Instruct",
        provider=ModelProvider.NVIDIA,
        model_type=ModelType.INSTRUCTION_TUNED,
        base_model="qwen-2.5-72b",
        parameter_size="72b",
        capability_tier="high",
        max_context_tokens=32768,
        system_prompt_token_budget=2048,
        few_shot_token_budget=4096,
        reserved_for_response=8192,
        supports_thinking_tags=True,
        supports_xml_tags=True,
        supports_json_mode=True,
        supports_structured_output=True,
        supports_indonesian=True,
        indonesian_quality_score=0.80,
        prompt_style="detailed",
        optimal_system_prompt="You are Qwen, a helpful AI assistant. You can understand and generate content in multiple languages including Indonesian."
    ),
    "nvidia/qwen-2.5-7b-instruct": ModelProfile(
        model_id="nvidia/qwen-2.5-7b-instruct",
        model_name="Qwen 2.5 7B Instruct",
        provider=ModelProvider.NVIDIA,
        model_type=ModelType.INSTRUCTION_TUNED,
        base_model="qwen-2.5-7b",
        parameter_size="7b",
        capability_tier="medium",
        max_context_tokens=32768,
        system_prompt_token_budget=1024,
        few_shot_token_budget=2048,
        reserved_for_response=4096,
        supports_thinking_tags=True,
        supports_xml_tags=True,
        supports_json_mode=True,
        supports_indonesian=True,
        indonesian_quality_score=0.70,
        prompt_style="concise",
        optimal_system_prompt="You are Qwen, a helpful AI assistant. Be concise and helpful."
    ),
    "nvidia/deepseek-llm-70b-chat": ModelProfile(
        model_id="nvidia/deepseek-llm-70b-chat",
        model_name="DeepSeek LLM 70B Chat",
        provider=ModelProvider.NVIDIA,
        model_type=ModelType.REASONING_TUNED,
        base_model="deepseek-llm-70b",
        parameter_size="70b",
        capability_tier="high",
        max_context_tokens=4096,
        system_prompt_token_budget=1024,
        few_shot_token_budget=512,
        reserved_for_response=2048,
        supports_thinking_tags=True,
        supports_xml_tags=True,
        supports_json_mode=False,
        supports_indonesian=True,
        indonesian_quality_score=0.70,
        prompt_style="reasoning",
        optimal_system_prompt="You are DeepSeek, an AI assistant trained by DeepSeek. You excel at logical reasoning and mathematics. Think step-by-step."
    ),
    "nvidia/llama-3.1-codegalaxy-70b": ModelProfile(
        model_id="nvidia/llama-3.1-codegalaxy-70b",
        model_name="CodeGalaxy 70B",
        provider=ModelProvider.NVIDIA,
        model_type=ModelType.CODE_TUNED,
        base_model="llama-3.1-70b",
        parameter_size="70b",
        capability_tier="high",
        max_context_tokens=16384,
        system_prompt_token_budget=2048,
        few_shot_token_budget=4096,
        reserved_for_response=8192,
        supports_thinking_tags=True,
        supports_xml_tags=True,
        supports_json_mode=True,
        supports_structured_output=True,
        supports_indonesian=False,
        indonesian_quality_score=0.40,
        prompt_style="code",
        optimal_system_prompt="You are an expert software engineer. Write clean, efficient, well-documented code."
    ),
}


class PromptInjectionStrategy(ABC):
    @abstractmethod
    def inject(self, base_prompt: str, model_profile: ModelProfile, context: Dict[str, Any]) -> str:
        pass
    
    @abstractmethod
    def get_strategy_name(self) -> str:
        pass


class InstructionTunedStrategy(PromptInjectionStrategy):
    def get_strategy_name(self) -> str:
        return "instruction_tuned"
    
    def inject(self, base_prompt: str, model_profile: ModelProfile, context: Dict[str, Any]) -> str:
        instruction_header = ""
        
        if model_profile.supports_xml_tags:
            instruction_header += "<instructions>\n"
        
        if context.get("role"):
            instruction_header += f"You are acting as a {context['role']}.\n"
        
        if context.get("output_format"):
            instruction_header += f"\nOutput Format Required:\n{context['output_format']}\n"
        
        if context.get("constraints"):
            instruction_header += f"\nConstraints:\n{context['constraints']}\n"
        
        if model_profile.supports_xml_tags:
            instruction_header += "</instructions>\n\n"
        
        if model_profile.parameter_size in ["7b", "8b"]:
            instruction_header += "IMPORTANT: Follow the instructions exactly. Do not deviate.\n\n"
        
        few_shot = ""
        if context.get("few_shot_examples") and model_profile.few_shot_token_budget > 0:
            examples = context["few_shot_examples"]
            if len(examples) <= 3:
                few_shot = "Examples:\n"
                for i, ex in enumerate(examples):
                    few_shot += f"\nExample {i+1}:\n"
                    if model_profile.supports_xml_tags:
                        few_shot += "<input>\n" + ex.get("input", "") + "\n</input>\n"
                        few_shot += "<output>\n" + ex.get("output", "") + "\n</output>\n"
                    else:
                        few_shot += f"Input: {ex.get('input', '')}\n"
                        few_shot += f"Output: {ex.get('output', '')}\n"
        
        if model_profile.supports_xml_tags:
            full_prompt = f"<instructions>\n{instruction_header}\n</instructions>\n"
            if few_shot:
                full_prompt += f"<examples>\n{few_shot}\n</examples>\n"
            full_prompt += f"<task>\n{base_prompt}\n</task>"
        else:
            full_prompt = instruction_header + "\n"
            if few_shot:
                full_prompt += few_shot + "\n"
            full_prompt += f"Task: {base_prompt}"
        
        return full_prompt


class ReasoningStrategy(PromptInjectionStrategy):
    def get_strategy_name(self) -> str:
        return "reasoning_tuned"
    
    def inject(self, base_prompt: str, model_profile: ModelProfile, context: Dict[str, Any]) -> str:
        prompt = base_prompt
        
        if model_profile.supports_thinking_tags:
            prompt = f"""<thought>
Let me think through this step by step.
</thought>

{prompt}

<thinking>
1. First, I need to understand what is being asked...
2. Next, I should identify the key components...
3. Then, I will work through the solution...
</thinking>"""
        else:
            prompt = f"""Think step by step before responding.
{context.get('chain_of_thought', '[Insert your reasoning here]')}

{prompt}

Work through this systematically."""
        
        if context.get("requires_verification"):
            prompt += "\n\nVerify your answer before finalizing."
        
        return prompt


class CodeStrategy(PromptInjectionStrategy):
    def get_strategy_name(self) -> str:
        return "code_tuned"
    
    def inject(self, base_prompt: str, model_profile: ModelProfile, context: Dict[str, Any]) -> str:
        target_language = context.get("language", "python")
        
        prompt = f"""You are an expert {target_language} programmer.

Code Requirements:
- Write clean, readable {target_language} code
- Follow {target_language} best practices and style guides
- Include proper error handling
- Add docstrings/comments where helpful
- Use type hints if applicable

"""
        
        if context.get("framework"):
            prompt += f"Framework: {context['framework']}\n"
        
        if context.get("libraries"):
            prompt += f"Available libraries: {', '.join(context['libraries'])}\n"
        
        prompt += f"\nTask:\n{base_prompt}\n"
        
        if model_profile.supports_xml_tags:
            prompt += """
Output your code in this format:
<code>
[Your code here]
</code>

Include a brief explanation before the code."""
        else:
            prompt += "\nProvide the code followed by a brief explanation."
        
        return prompt


class IndonesianStrategy(PromptInjectionStrategy):
    def get_strategy_name(self) -> str:
        return "indonesian_optimized"
    
    def inject(self, base_prompt: str, model_profile: ModelProfile, context: Dict[str, Any]) -> str:
        indo_header = """Anda adalah asisten AI yang membantu.
Tolong berikan jawaban yang akurat dan berguna dalam Bahasa Indonesia yang baik dan benar.

"""
        
        target_audience = context.get("target_audience", "general")
        
        formality_levels = {
            "b2b": "Gunakan bahasa formal yang profesional untuk audiens bisnis.",
            "b2c": "Gunakan bahasa yang santai tapi tetap sopan untuk konsumen.",
            "gen-z": "Gunakan bahasa gaul Indonesia yang natural dan engaging.",
            "general": "Gunakan Bahasa Indonesia yang standar dan mudah dipahami."
        }
        
        indo_header += formality_levels.get(target_audience, formality_levels["general"]) + "\n\n"
        
        if context.get("cultural_context"):
            indo_header += f"Konteks budaya: {context['cultural_context']}\n\n"
        
        prompt = indo_header + base_prompt
        
        prompt += """

Gunakan transisi kalimat yang natural dalam Bahasa Indonesia seperti:
- "Oleh karena itu,"
- "Menariknya lagi,"
- "Selain itu,"
- "Puncaknya,"
- "Dengan demikian,"""
        
        return prompt


class DynamicPromptOptimizer:
    STRATEGIES: Dict[ModelType, PromptInjectionStrategy] = {
        ModelType.INSTRUCTION_TUNED: InstructionTunedStrategy(),
        ModelType.REASONING_TUNED: ReasoningStrategy(),
        ModelType.CODE_TUNED: CodeStrategy(),
        ModelType.INDONESIAN_TUNED: IndonesianStrategy(),
        ModelType.CHAT_TUNED: InstructionTunedStrategy(),
        ModelType.GENERAL: InstructionTunedStrategy(),
    }
    
    def __init__(self):
        self.model_registry: Dict[str, ModelProfile] = MODEL_REGISTRY.copy()
        self.quality_history: Dict[str, List[Dict]] = defaultdict(list)
        self.strategy_adjustments: Dict[str, float] = defaultdict(float)
        self.total_optimizations = 0
        self.cache_hits = 0
        self.prompt_cache: Dict[str, str] = {}
        self.cache_ttl_seconds = 3600
    
    def get_model_profile(self, model_id: str) -> ModelProfile:
        if model_id in self.model_registry:
            return self.model_registry[model_id]
        
        for profile in self.model_registry.values():
            if model_id.startswith(profile.base_model):
                logger.info(f"[DSPy] Using base model profile for {model_id}")
                return profile
        
        logger.warning(f"[DSPy] No profile for {model_id}, using generic profile")
        return ModelProfile(
            model_id=model_id,
            model_name=model_id.split("/")[-1],
            provider=ModelProvider.OPENROUTER,
            model_type=ModelType.INSTRUCTION_TUNED,
            base_model="unknown",
            parameter_size="unknown",
            capability_tier="medium",
            max_context_tokens=4096,
            system_prompt_token_budget=512,
            few_shot_token_budget=1024,
            reserved_for_response=2048,
            supports_thinking_tags=False,
            supports_xml_tags=False,
            supports_json_mode=True,
            prompt_style="concise",
            optimal_system_prompt="You are a helpful AI assistant."
        )
    
    def optimize(self, base_task: str, model_id: str, context: Optional[Dict[str, Any]] = None, force_regenerate: bool = False) -> str:
        self.total_optimizations += 1
        ctx = context or {}
        
        cache_key = self._get_cache_key(base_task, model_id, ctx)
        if not force_regenerate and cache_key in self.prompt_cache:
            self.cache_hits += 1
            return self.prompt_cache[cache_key]
        
        profile = self.get_model_profile(model_id)
        strategy = self._select_strategy(profile, ctx)
        optimized = strategy.inject(base_task, profile, ctx)
        optimized = self._apply_token_budget(optimized, profile)
        self.prompt_cache[cache_key] = optimized
        
        logger.info(f"[DSPy] Optimized for {model_id} (type={profile.model_type.value}, tokens={len(optimized.split())})")
        
        return optimized
    
    def _select_strategy(self, profile: ModelProfile, context: Dict[str, Any]) -> PromptInjectionStrategy:
        task_type = context.get("task_type", "")
        
        if "code" in task_type or "programming" in task_type:
            return self.STRATEGIES[ModelType.CODE_TUNED]
        
        if "reasoning" in task_type or "math" in task_type or "logic" in task_type:
            return self.STRATEGIES[ModelType.REASONING_TUNED]
        
        if context.get("language", "").lower() == "indonesian" or context.get("target_audience") in ["b2b", "b2c", "gen-z"]:
            if profile.supports_indonesian and profile.indonesian_quality_score >= 0.6:
                return self.STRATEGIES[ModelType.INDONESIAN_TUNED]
        
        return self.STRATEGIES.get(profile.model_type, self.STRATEGIES[ModelType.INSTRUCTION_TUNED])
    
    def _apply_token_budget(self, prompt: str, profile: ModelProfile) -> str:
        estimated_tokens = len(prompt.split()) / 0.75
        max_tokens = profile.system_prompt_token_budget + profile.few_shot_token_budget
        
        if estimated_tokens > max_tokens:
            words = prompt.split()
            keep_start = int(max_tokens * 0.7)
            keep_end = int(max_tokens * 0.2)
            truncated = ' '.join(words[:keep_start] + ['... (truncated) ...'] + words[-keep_end:])
            logger.warning(f"[DSPy] Prompt truncated from {estimated_tokens:.0f} to {max_tokens:.0f} tokens")
            return truncated
        
        return prompt
    
    def _get_cache_key(self, task: str, model_id: str, context: Dict) -> str:
        ctx_str = json.dumps(context, sort_keys=True)
        key_str = f"{task}|{model_id}|{ctx_str}"
        return hashlib.sha256(key_str.encode()).hexdigest()[:32]
    
    def record_quality(self, model_id: str, task_type: str, quality_score: float, latency_ms: Optional[float] = None):
        record = {
            "timestamp": datetime.now().isoformat(),
            "task_type": task_type,
            "quality_score": quality_score,
            "latency_ms": latency_ms
        }
        
        self.quality_history[model_id].append(record)
        
        if model_id in self.model_registry:
            profile = self.model_registry[model_id]
            alpha = 0.2
            profile.avg_quality_score = alpha * quality_score + (1 - alpha) * profile.avg_quality_score
            
            if latency_ms:
                profile.avg_latency_ms = alpha * latency_ms + (1 - alpha) * profile.avg_latency_ms
            
            profile.total_requests += 1
        
        self._adjust_strategy_weights(model_id, quality_score)
        logger.info(f"[DSPy] Recorded quality for {model_id}: score={quality_score:.3f}")
    
    def _adjust_strategy_weights(self, model_id: str, quality_score: float):
        if quality_score < 0.6:
            self.strategy_adjustments[model_id] += 0.1
        elif quality_score > 0.8:
            self.strategy_adjustments[model_id] -= 0.05
        
        self.strategy_adjustments[model_id] = max(-0.3, min(0.3, self.strategy_adjustments[model_id]))
    
    def get_model_recommendation(self, task_type: str, priority: str = "quality") -> List[ModelProfile]:
        candidates = []
        
        for model_id, profile in self.model_registry.items():
            score = self._calculate_suitability_score(profile, task_type, priority)
            candidates.append((score, profile))
        
        candidates.sort(reverse=True, key=lambda x: x[0])
        return [p for _, p in candidates]
    
    def _calculate_suitability_score(self, profile: ModelProfile, task_type: str, priority: str) -> float:
        base_score = 0.5
        
        if "code" in task_type:
            if profile.model_type == ModelType.CODE_TUNED:
                base_score += 0.3
        elif "reasoning" in task_type or "math" in task_type:
            if profile.model_type == ModelType.REASONING_TUNED:
                base_score += 0.3
        elif "content" in task_type or "indonesian" in task_type:
            if profile.supports_indonesian:
                base_score += profile.indonesian_quality_score * 0.3
        else:
            base_score += 0.1
        
        tier_scores = {"low": 0.1, "medium": 0.2, "high": 0.3}
        base_score += tier_scores.get(profile.capability_tier, 0.1)
        base_score += profile.avg_quality_score * 0.2
        
        if priority == "speed":
            if profile.avg_latency_ms > 0:
                latency_factor = max(0, 1 - profile.avg_latency_ms / 10000)
                base_score = base_score * 0.5 + latency_factor * 0.5
        
        base_score += self.strategy_adjustments.get(profile.model_id, 0)
        
        return max(0.0, min(1.0, base_score))
    
    def add_model(self, profile: ModelProfile):
        self.model_registry[profile.model_id] = profile
        logger.info(f"[DSPy] Added model to registry: {profile.model_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_models": len(self.model_registry),
            "total_optimizations": self.total_optimizations,
            "cache_hits": self.cache_hits,
            "cache_hit_rate": self.cache_hits / max(self.total_optimizations, 1),
            "models_with_quality_data": len(self.quality_history),
        }


class DSPyProviderRouter:
    def __init__(self, provider_gateway=None):
        self.optimizer = DynamicPromptOptimizer()
        self.gateway = provider_gateway
        self.fallback_chain: Dict[str, List[str]] = {
            "content_write": [
                "nvidia/qwen-2.5-72b-instruct",
                "nvidia/llama-3.1-nemotron-70b-instruct"
            ],
            "code_generation": [
                "nvidia/llama-3.1-codegalaxy-70b",
                "nvidia/qwen-2.5-72b-instruct"
            ],
            "reasoning": [
                "nvidia/deepseek-llm-70b-chat",
                "nvidia/qwen-2.5-72b-instruct",
                "nvidia/mixtral-8x7b-instruct-v0.1"
            ],
            "indonesian_content": [
                "nvidia/qwen-2.5-72b-instruct",
                "nvidia/llama-3.1-nemotron-70b-instruct"
            ]
        }
    
    async def route_task(self, task_description: str, task_type: str, priority: str = "balanced", context: Optional[Dict[str, Any]] = None, max_retries: int = 2) -> Dict[str, Any]:
        ctx = context or {}
        ctx["task_type"] = task_type
        
        recommendations = self.optimizer.get_model_recommendation(task_type, priority)
        
        if not recommendations:
            return {"success": False, "error": "No suitable models found", "model_used": None, "response": None}
        
        tried_models = []
        
        for model_profile in recommendations[:3]:
            model_id = model_profile.model_id
            tried_models.append(model_id)
            
            try:
                start_time = time.perf_counter()
                optimized_prompt = self.optimizer.optimize(base_task=task_description, model_id=model_id, context=ctx)
                
                if self.gateway:
                    response = await self.gateway.generate(model_id=model_id, prompt=optimized_prompt, **ctx.get("generation_params", {}))
                else:
                    response = await self._direct_api_call(model_id, optimized_prompt, ctx)
                
                latency_ms = (time.perf_counter() - start_time) * 1000
                quality_estimate = self._estimate_quality(model_id, task_type, response, latency_ms)
                
                self.optimizer.record_quality(model_id=model_id, task_type=task_type, quality_score=quality_estimate, latency_ms=latency_ms)
                
                return {
                    "success": True,
                    "model_used": model_id,
                    "response": response,
                    "optimization_metadata": {
                        "original_task": task_description,
                        "optimized_prompt_length": len(optimized_prompt.split()),
                        "model_type": model_profile.model_type.value,
                        "provider": model_profile.provider.value,
                        "estimated_quality": quality_estimate,
                        "latency_ms": latency_ms
                    },
                    "fallback_used": len(tried_models) > 1
                }
                
            except Exception as e:
                logger.warning(f"[DSPyRouter] Model {model_id} failed: {e}")
                continue
        
        return {"success": False, "error": "All models failed", "models_tried": tried_models}
    
    async def _direct_api_call(self, model_id: str, prompt: str, context: Dict[str, Any]) -> str:
        await asyncio.sleep(0.1)
        return f"[Response from {model_id}]\nOptimized prompt length: {len(prompt.split())} tokens"
    
    def _estimate_quality(self, model_id: str, task_type: str, response: str, latency_ms: float) -> float:
        score = 0.5
        
        if len(response.split()) > 50:
            score += 0.1
        
        if 500 < latency_ms < 5000:
            score += 0.1
        
        if "error" in response.lower():
            score -= 0.3
        
        return max(0.0, min(1.0, score))
    
    def get_best_model_for_task(self, task_type: str, priority: str = "balanced") -> Optional[ModelProfile]:
        recommendations = self.optimizer.get_model_recommendation(task_type, priority)
        return recommendations[0] if recommendations else None


class PromptMetaLearner:
    def __init__(self, optimizer: DynamicPromptOptimizer):
        self.optimizer = optimizer
        self.experience_replay: List[Dict] = []
        self.prompt_templates: Dict[str, Dict] = {}
        self.best_practices: Dict[str, List[str]] = defaultdict(list)
        self.quality_threshold = 0.75
        self.min_samples_for_update = 10
    
    def learn_from_completion(self, model_id: str, task_type: str, original_prompt: str, optimized_prompt: str, response: str, quality_score: float, user_feedback: Optional[str] = None):
        experience = {
            "timestamp": datetime.now().isoformat(),
            "model_id": model_id,
            "task_type": task_type,
            "original_prompt": original_prompt,
            "optimized_prompt": optimized_prompt,
            "response": response,
            "quality_score": quality_score,
            "user_feedback": user_feedback
        }
        
        self.experience_replay.append(experience)
        
        if len(self.experience_replay) > 1000:
            self.experience_replay = self.experience_replay[-1000:]
        
        if quality_score >= self.quality_threshold:
            self._extract_best_practices(experience)
    
    def _extract_best_practices(self, experience: Dict):
        prompt = experience["optimized_prompt"]
        task_type = experience["task_type"]
        
        instruction_patterns = [
            r'^(?:Anda|Kamu|You are)',
            r'^(?:Tolong|Please|Berikut)',
            r'<instructions>',
            r'<thought>',
        ]
        
        for pattern in instruction_patterns:
            if re.search(pattern, prompt, re.MULTILINE):
                match = re.search(pattern, prompt, re.MULTILINE).group(0)
                best_practice = f"prefix:{match[:50]}"
                self.best_practices[task_type].append(best_practice)
        
        if '<output>' in prompt or 'Output:' in prompt:
            self.best_practices[task_type].append("format:explicit_output_marker")
        
        if '```' in experience.get("response", ""):
            self.best_practices[task_type].append("format:code_blocks")
        
        if 'Constraints:' in prompt or 'constraints:' in prompt.lower():
            self.best_practices[task_type].append("constraints:explicit")
        
        if 'Bahasa Indonesia' in prompt or 'indonesian' in task_type.lower():
            self.best_practices[task_type].append("language:indonesian_formality_markers")
        
        self.best_practices[task_type] = list(set(self.best_practices[task_type]))
    
    def get_best_practices(self, task_type: str) -> List[str]:
        return self.best_practices.get(task_type, [])
    
    def suggest_prompt_improvement(self, current_prompt: str, model_id: str, task_type: str) -> str:
        suggestions = self.get_best_practices(task_type)
        
        if not suggestions:
            return current_prompt
        
        improved = current_prompt
        
        for practice in suggestions:
            if practice.startswith("prefix:"):
                prefix = practice[7:]
                if prefix not in improved:
                    improved = prefix + "\n\n" + improved
            elif practice == "format:explicit_output_marker":
                if "Output:" not in improved:
                    improved += "\n\nOutput:\n[Your response here]"
            elif practice == "constraints:explicit":
                if "Constraints:" not in improved:
                    improved += "\n\nConstraints:\n- Be concise\n- Follow the format specified"
        
        return improved
    
    def get_learning_stats(self) -> Dict[str, Any]:
        return {
            "total_experiences": len(self.experience_replay),
            "experiences_by_task": {
                task_type: len([e for e in self.experience_replay if e["task_type"] == task_type])
                for task_type in set(e["task_type"] for e in self.experience_replay)
            },
            "best_practices_count": {
                task_type: len(practices)
                for task_type, practices in self.best_practices.items()
            },
            "quality_threshold": self.quality_threshold,
        }


async def demo_dspy_pipeline():
    print("=" * 70)
    print("ILMA v5.0 — DYNAMIC PROMPT OPTIMIZER (DSPy-Style)")
    print("Meta-Prompting for Free Model Providers")
    print("=" * 70)
    
    optimizer = DynamicPromptOptimizer()
    
    print("\n[1] REGISTERED MODELS")
    print("-" * 50)
    
    for model_id, profile in list(MODEL_REGISTRY.items())[:5]:
        print(f"\n  {profile.model_name}")
        print(f"    Provider: {profile.provider.value}")
        print(f"    Type: {profile.model_type.value}")
        print(f"    Size: {profile.parameter_size}")
        print(f"    Indonesian Score: {profile.indonesian_quality_score:.2f}")
    
    print("\n\n[2] PROMPT OPTIMIZATION")
    print("-" * 50)
    
    test_tasks = [
        {
            "task": "Write a Python function to calculate factorial recursively",
            "model_id": "nvidia/llama-3.1-codegalaxy-70b",
            "context": {"task_type": "code_generation", "language": "python", "output_format": "code block with docstring"}
        },
        {
            "task": "Jelaskan manfaat machine learning untuk bisnis Indonesia dalam Bahasa Indonesia",
            "model_id": "nvidia/qwen-2.5-72b-instruct",
            "context": {"task_type": "indonesian_content", "language": "indonesian", "target_audience": "b2b"}
        },
        {
            "task": "Solve: If a train leaves at 2pm traveling 60mph and another leaves at 3pm traveling 80mph, when do they meet?",
            "model_id": "nvidia/deepseek-llm-70b-chat",
            "context": {"task_type": "reasoning", "requires_verification": True}
        }
    ]
    
    for i, test in enumerate(test_tasks):
        print(f"\n  Task {i+1}: {test['task'][:50]}...")
        print(f"  Model: {test['model_id']}")
        
        optimized = optimizer.optimize(base_task=test["task"], model_id=test["model_id"], context=test["context"])
        
        print(f"\n  Optimized Prompt ({len(optimized.split())} words):")
        for line in optimized.split('\n')[:10]:
            print(f"  {line[:70]}")
    
    print("\n\n[3] MODEL RECOMMENDATIONS")
    print("-" * 50)
    
    task_types = ["content_write", "code_generation", "reasoning", "indonesian_content"]
    
    for task_type in task_types:
        print(f"\n  Task: {task_type}")
        for priority in ["quality", "speed", "balanced"]:
            recs = optimizer.get_model_recommendation(task_type, priority)
            if recs:
                top = recs[0]
                print(f"    {priority}: {top.model_name}")
    
    print("\n\n[4] DSPY PROVIDER ROUTER")
    print("-" * 50)
    
    router = DSPyProviderRouter()
    
    result = await router.route_task(
        task_description="Buat artikel SEO tentang manfaat AI untuk UMKM Indonesia",
        task_type="indonesian_content",
        priority="balanced",
        context={"target_audience": "b2b"}
    )
    
    print(f"  Success: {result['success']}")
    if result['success']:
        print(f"  Model Used: {result['model_used']}")
        print(f"  Fallback Used: {result['fallback_used']}")
    
    print("\n" + "=" * 70)
    print("DYNAMIC PROMPT OPTIMIZER DEMO COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(demo_dspy_pipeline())
