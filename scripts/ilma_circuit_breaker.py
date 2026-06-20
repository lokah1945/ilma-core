#!/usr/bin/env python3
"""
ILMA Circuit Breaker v1.0
============================
Circuit breaker pattern for ILMA.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Callable, Any

WORKSPACE = Path("/root/.hermes/profiles/ilma")

class CircuitBreaker:
    """Circuit breaker pattern implementation."""
    
    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        if self.state == "open":
            if self.last_failure_time:
                elapsed = (datetime.now() - self.last_failure_time).total_seconds()
                if elapsed > self.timeout_seconds:
                    self.state = "half_open"
                else:
                    raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            if self.state == "half_open":
                self.state = "closed"
                self.failures = 0
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure_time = datetime.now()
            if self.failures >= self.failure_threshold:
                self.state = "open"
            raise e
    
    def get_state(self) -> dict:
        return {
            "state": self.state,
            "failures": self.failures,
            "threshold": self.failure_threshold
        }

if __name__ == "__main__":
    cb = CircuitBreaker()
    print(json.dumps(cb.get_state(), indent=2))
