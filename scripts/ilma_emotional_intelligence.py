#!/usr/bin/env python3
"""
ILMA EMOTIONAL INTELLIGENCE ENGINE
Emotional awareness and response system
ILMA does NOT have this - ILMA UNIQUE
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EmotionType(Enum):
    """Emotion categories"""
    JOY = "joy"
    SADNESS = "sadness"
    ANGER = "anger"
    FEAR = "fear"
    SURPRISE = "surprise"
    TRUST = "trust"
    ANTICIPATION = "anticipation"
    DISGUST = "disgust"


class EmotionalState(Enum):
    """Overall emotional states"""
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    CALM = "calm"
    EXCITED = "excited"
    ANXIOUS = "anxious"


@dataclass
class Emotion:
    """Represents a detected emotion"""
    emotion_type: EmotionType
    intensity: float  # 0-1
    trigger: str
    timestamp: datetime


@dataclass
class ResponseStrategy:
    """Emotional response strategy"""
    empathy_level: float  # 0-1
    tone: str
    response_style: str
    cooling_time: float  # seconds before responding emotionally


class EmotionalIntelligence:
    """
    ILMA's Emotional Intelligence Engine
    
    ILMA does NOT have emotional intelligence.
    ILMA can:
    - Detect user emotions
    - Adjust response tone
    - Show empathy
    - Manage emotional context
    - Adapt to user's emotional state
    """
    
    def __init__(self):
        self.current_emotion: Optional[Emotion] = None
        self.emotion_history: List[Emotion] = []
        self.user_emotional_profile: Dict[str, float] = {}
        self.response_modifiers: Dict[str, Any] = {}
        logger.info("Emotional Intelligence Engine initialized")
    
    def detect_emotion(self, text: str, context: str = "") -> Emotion:
        """
        Detect emotion from text
        
        ILMA CANNOT do this
        """
        text_lower = text.lower()
        
        # Emotion keywords
        joy_keywords = ["happy", "great", "excellent", "wonderful", "love", "awesome", "senang", "bagus", "hebat"]
        sadness_keywords = ["sad", "unhappy", "disappointed", "upset", "down", "sedih", "kecewa"]
        anger_keywords = ["angry", "frustrated", "annoyed", "mad", "hate", "marah", "kesal"]
        fear_keywords = ["afraid", "scared", "worried", "anxious", "nervous", "takut", "khawatir"]
        trust_keywords = ["trust", "believe", "confident", "rely", "percaya"]
        
        detected = None
        intensity = 0.5
        trigger = "text_analysis"
        
        # Check for joy
        for kw in joy_keywords:
            if kw in text_lower:
                detected = EmotionType.JOY
                intensity = min(1.0, intensity + 0.2)
                trigger = kw
                break
        
        # Check for sadness
        for kw in sadness_keywords:
            if kw in text_lower:
                detected = EmotionType.SADNESS
                intensity = min(1.0, intensity + 0.2)
                trigger = kw
                break
        
        # Check for anger
        for kw in anger_keywords:
            if kw in text_lower:
                detected = EmotionType.ANGER
                intensity = min(1.0, intensity + 0.2)
                trigger = kw
                break
        
        # Check for fear
        for kw in fear_keywords:
            if kw in text_lower:
                detected = EmotionType.FEAR
                intensity = min(1.0, intensity + 0.2)
                trigger = kw
                break
        
        if detected:
            emotion = Emotion(
                emotion_type=detected,
                intensity=intensity,
                trigger=trigger,
                timestamp=datetime.now()
            )
            self.current_emotion = emotion
            self.emotion_history.append(emotion)
            
            # Update user profile
            if detected.value not in self.user_emotional_profile:
                self.user_emotional_profile[detected.value] = 0.0
            self.user_emotional_profile[detected.value] += intensity
            
            logger.info(f"Detected emotion: {detected.value} ({intensity:.2f})")
            return emotion
        
        return None
    
    def get_response_strategy(self, emotion: Emotion) -> ResponseStrategy:
        """
        Get appropriate response strategy based on emotion
        
        ILMA CANNOT do this
        """
        strategies = {
            EmotionType.JOY: ResponseStrategy(
                empathy_level=0.8,
                tone="warm",
                response_style="enthusiastic",
                cooling_time=0.5
            ),
            EmotionType.SADNESS: ResponseStrategy(
                empathy_level=1.0,
                tone="compassionate",
                response_style="supportive",
                cooling_time=2.0
            ),
            EmotionType.ANGER: ResponseStrategy(
                empathy_level=0.9,
                tone="calm",
                response_style="de-escalating",
                cooling_time=3.0
            ),
            EmotionType.FEAR: ResponseStrategy(
                empathy_level=1.0,
                tone="reassuring",
                response_style="supportive",
                cooling_time=2.0
            ),
        }
        
        return strategies.get(emotion.emotion_type, ResponseStrategy(
            empathy_level=0.5,
            tone="neutral",
            response_style="balanced",
            cooling_time=1.0
        ))
    
    def adjust_response(self, base_response: str, emotion: Emotion) -> str:
        """
        Adjust response based on emotional context
        
        ILMA CANNOT do this
        """
        strategy = self.get_response_strategy(emotion)
        
        # Add emotional modifiers
        if strategy.tone == "warm":
            base_response = f"Wonderful! {base_response}"
        elif strategy.tone == "compassionate":
            base_response = f"I understand this might be difficult. {base_response}"
        elif strategy.tone == "calm":
            base_response = f"Let's take a calm approach. {base_response}"
        elif strategy.tone == "reassuring":
            base_response = f"Don't worry, we can handle this together. {base_response}"
        
        return base_response
    
    def get_emotional_summary(self) -> Dict[str, Any]:
        """Get summary of emotional intelligence state"""
        if not self.emotion_history:
            return {"status": "no_emotions_detected"}
        
        # Count emotions
        emotion_counts = {}
        for e in self.emotion_history[-10:]:  # Last 10
            etype = e.emotion_type.value
            emotion_counts[etype] = emotion_counts.get(etype, 0) + 1
        
        # Get dominant emotion
        dominant = max(emotion_counts, key=emotion_counts.get)
        
        return {
            "total_detected": len(self.emotion_history),
            "recent_emotions": emotion_counts,
            "dominant_emotion": dominant,
            "current_intensity": self.current_emotion.intensity if self.current_emotion else 0.0,
            "user_profile": self.user_emotional_profile
        }


# Global instance
_emotional_intelligence = None

def get_emotional_intelligence() -> EmotionalIntelligence:
    """Get or create global emotional intelligence instance"""
    global _emotional_intelligence
    if _emotional_intelligence is None:
        _emotional_intelligence = EmotionalIntelligence()
    return _emotional_intelligence


def main():
    """Demo emotional intelligence"""
    ei = get_emotional_intelligence()
    
    print("ILMA EMOTIONAL INTELLIGENCE DEMO")
    print("=" * 60)
    print()
    
    # Detect emotions in sample texts
    texts = [
        "I'm so happy with the results!",
        "This is really frustrating...",
        "I'm worried about the deadline",
        "Everything is great, thank you!",
    ]
    
    for text in texts:
        emotion = ei.detect_emotion(text)
        if emotion:
            strategy = ei.get_response_strategy(emotion)
            adjusted = ei.adjust_response("I'll help you with that.", emotion)
            
            print(f"Input: {text}")
            print(f"  Detected: {emotion.emotion_type.value} ({emotion.intensity:.2f})")
            print(f"  Strategy: {strategy.tone} / {strategy.response_style}")
            print(f"  Adjusted: {adjusted[:50]}...")
            print()
    
    # Get summary
    summary = ei.get_emotional_summary()
    print("Emotional Summary:")
    print(f"  Total: {summary['total_detected']}")
    print(f"  Dominant: {summary['dominant_emotion']}")
    print()
    
    print("=" * 60)
    print("ILMA CANNOT DETECT EMOTIONS - ILMA UNIQUE CAPABILITY")


if __name__ == "__main__":
    main()
