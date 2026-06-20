#!/usr/bin/env python3
"""
ILMA LEARNING CAPABILITY
========================
Self-learning and improvement as a capability.
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime

ILMA_DIR = Path("/root/.hermes/profiles/ilma")
MEMORY_DIR = ILMA_DIR / "memories"

class LearningCapability:
    """
    ILMA's ability to learn from experience.
    Pattern recognition, meta-learning, self-improvement.
    """
    
    def __init__(self):
        self.learning_data = ILMA_DIR / "learning_data.json"
        self.patterns = {}
        self.feedback_history = []
        self._load_learning_data()
    
    def _load_learning_data(self):
        """Load learning data from file."""
        if self.learning_data.exists():
            try:
                data = json.loads(self.learning_data.read_text())
                self.patterns = data.get('patterns', {})
                self.feedback_history = data.get('feedback_history', [])
            except Exception:
                self.patterns = {}
                self.feedback_history = []
    
    def _save_learning_data(self):
        """Save learning data to file."""
        data = {
            'patterns': self.patterns,
            'feedback_history': self.feedback_history[-100:]  # Keep last 100
        }
        self.learning_data.write_text(json.dumps(data, indent=2))
    
    def learn_from_feedback(self, task, outcome, rating):
        """
        Learn from task outcome.
        rating: 1-5 (1=bad, 5=excellent)
        """
        entry = {
            'task': task,
            'outcome': outcome,
            'rating': rating,
            'timestamp': time.time()
        }
        
        self.feedback_history.append(entry)
        
        # Extract patterns
        task_lower = task.lower()
        words = task_lower.split()
        
        # Learn from successful outcomes (rating >= 4)
        if rating >= 4:
            for word in words:
                if len(word) > 3:
                    if word not in self.patterns:
                        self.patterns[word] = {'success': 0, 'failure': 0}
                    self.patterns[word]['success'] += 1
        
        # Learn from failed outcomes (rating <= 2)
        elif rating <= 2:
            for word in words:
                if len(word) > 3:
                    if word not in self.patterns:
                        self.patterns[word] = {'success': 0, 'failure': 0}
                    self.patterns[word]['failure'] += 1
        
        self._save_learning_data()
        
        return {
            'learned': True,
            'patterns_updated': len(words)
        }
    
    def predict_success(self, task):
        """
        Predict if a task will succeed based on patterns.
        Returns confidence score 0-1.
        """
        task_lower = task.lower()
        words = task_lower.split()
        
        if not words:
            return 0.5
        
        scores = []
        for word in words:
            if len(word) > 3 and word in self.patterns:
                p = self.patterns[word]
                total = p['success'] + p['failure']
                if total > 0:
                    scores.append(p['success'] / total)
        
        if scores:
            return sum(scores) / len(scores)
        return 0.5
    
    def get_best_approach(self, task_type):
        """
        Get the best approach for a task type based on history.
        """
        relevant = [f for f in self.feedback_history if task_type in f['task'].lower()]
        
        if not relevant:
            return None
        
        # Sort by rating
        relevant.sort(key=lambda x: x['rating'], reverse=True)
        
        return {
            'task_type': task_type,
            'attempts': len(relevant),
            'best_outcome': relevant[0]['outcome'],
            'best_rating': relevant[0]['rating']
        }
    
    def get_pattern_stats(self):
        """Get pattern statistics."""
        total = len(self.patterns)
        successful = sum(1 for p in self.patterns.values() if p['success'] > p['failure'])
        
        return {
            'total_patterns': total,
            'successful_patterns': successful,
            'feedback_entries': len(self.feedback_history)
        }
    
    def clear_patterns(self):
        """Clear all learning patterns."""
        self.patterns = {}
        self.feedback_history = []
        self._save_learning_data()
        return {'cleared': True}

def execute(task):
    """Execute learning capability."""
    learner = LearningCapability()
    
    task_lower = task.lower()
    
    if task_lower.startswith('learn '):
        # learn <task> <outcome> <rating>
        parts = task[6:].rsplit(' ', 1)
        if len(parts) == 2:
            task_part = parts[0].rsplit(' ', 1)
            if len(task_part) == 2:
                outcome = task_part[0]
                try:
                    rating = int(task_part[1])
                    return learner.learn_from_feedback(outcome, "", rating)
                except ValueError:
                    pass
            return learner.learn_from_feedback(parts[0], "", int(parts[1]))
        return {'error': 'Usage: learn <task> <rating>'}
    
    elif task_lower.startswith('predict '):
        task_part = task[8:].strip()
        confidence = learner.predict_success(task_part)
        return {'task': task_part, 'confidence': confidence}
    
    elif 'stats' in task_lower:
        return learner.get_pattern_stats()
    
    elif 'clear' in task_lower:
        return learner.clear_patterns()
    
    else:
        return {
            'patterns': learner.patterns,
            'stats': learner.get_pattern_stats()
        }

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result = execute(' '.join(sys.argv[1:]))
        print(result)
    else:
        learner = LearningCapability()
        print("Learning capability loaded")
        print(f"Patterns: {len(learner.patterns)}")
        print(f"Feedback entries: {len(learner.feedback_history)}")
