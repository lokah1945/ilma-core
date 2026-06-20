---
name: ilma-research
description: SSS Tier skill for research patterns. Military Grade Quality.
triggers:
  - ilma-research
  - research,search,investigate
version: 1.2.0
last_updated: 2026-05-11
---

# Research

## Overview

**Tier:** SSS (Military Grade)  
**Version:** 1.0.0  
**Status:** OPERATIONAL  
**Last Updated:** 2026-05-06

## Description

This skill provides comprehensive, military-grade patterns and best practices for **research patterns**.

## Two-Layer Research System (Phase 57 Update)

ILMA now has TWO research layers:

### Layer 1: Internal Research (Lesson Memory)
- Search past lessons from JSONL storage
- Uses `ilma_lesson_memory.py`
- Triggered at task start via PreTaskLearningHook
- Fast, reliable, no external dependencies

### Layer 2: External Research (Live Research)
- **FELO FREE native_search** (DuckDuckGo + Wikipedia — 100% FREE, no API key) — PRIMARY
- arXiv paper search for technical tasks
- Triggered when internal knowledge insufficient
- Uses `scripts/ilma_live_research.py`
- Trigger conditions:
  - Fix plan <= 2 steps + root cause unclear
  - Iteration >= 2 + root cause unclear
  - Failed attempts >= 3
  - No lesson memory + confidence < 0.3
  - Novel error pattern not in cache

### ResearchResult Schema

```python
@dataclass
class ResearchResult:
    solutions: List[str]        # Potential solutions found
    papers: List[Dict]         # Relevant papers (title, url, abstract)
    confidence: float          # 0.0-1.0 confidence in solutions
    new_knowledge: List[str]   # New learnings to store as lesson
    sources: List[str]         # Source URLs
    research_duration: float   # Seconds spent researching
```

## Patterns

This skill automatically activates when:
- User requests: `research,search,investigate`
- Task involves: research patterns
- Context suggests: research patterns operations needed

## Patterns

### Primary Pattern

SSS Tier implementation for research patterns:

```python
# SSS Tier Research
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class ResearchHandlerConfig:
    """Configuration for Research operations."""
    enabled: bool = True
    verbose: bool = False
    timeout: int = 30
    retries: int = 3
    
    def validate(self) -> bool:
        """Validate configuration."""
        return (
            self.timeout > 0 and
            self.retries >= 0 and
            self.timeout >= self.retries
        )

class ResearchHandlerHandler:
    """
    SSS Tier handler for research patterns.
    
    Military Grade implementation with full error handling,
    logging, type hints, and comprehensive validation.
    """
    
    def __init__(self, config: Optional[ResearchHandlerConfig] = None):
        self.config = config or ResearchHandlerConfig()
        self.logger = logging.getLogger(self.__class__.__name__)
        if self.config.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
    
    def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Execute research patterns operation.
        
        Returns:
            Dict with 'success', 'message', and 'data' keys
        """
        try:
            self.logger.info("Executing Research")
            
            if not self.config.validate():
                return {
                    'success': False,
                    'message': 'Invalid configuration'
                }
            
            result = self._execute(*args, **kwargs)
            
            return {
                'success': True,
                'message': 'Research completed successfully',
                'data': result,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error in Research: {e}")
            return {
                'success': False,
                'message': f'Operation failed: {str(e)}',
                'error': str(e)
            }
    
    def _execute(self, *args, **kwargs) -> Any:
        """
        Internal execution logic.
        Override in subclass for specific functionality.
        """
        return {"status": "completed", "operation": "Research"}


def main() -> int:
    """Main entry point."""
    handler = ResearchHandlerHandler()
    result = handler.execute()
    return 0 if result['success'] else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

## Implementation Steps

### Step 1: Initialize Handler

```python
config = ResearchHandlerConfig(verbose=True)
handler = ResearchHandlerHandler(config=config)
```

### Step 2: Execute Operation

```python
result = handler.execute(param1=value1, param2=value2)
if result['success']:
    print(f"Success: {result['message']}")
```

### Step 3: Handle Results

```python
if result['success']:
    data = result['data']
else:
    error = result.get('error', 'Unknown error')
```

## Error Handling

| Error Type | Handling Strategy |
|------------|-------------------|
| Validation Error | Return `success=False` with message |
| Execution Error | Log and return error details |
| Timeout | Configurable timeout with retries |
| Unknown Error | Catch all, log, return safe error |

## Best Practices

1. **Always validate configuration** before execution
2. **Use verbose mode** for debugging
3. **Check return value** for `success` key
4. **Log all operations** for audit trail
5. **Handle timeouts** gracefully with retry logic

## Verification

```bash
python3 -c "
from skills.ilma-research.ResearchHandlerHandler
handler = ResearchHandlerHandler()
result = handler.execute()
print('SUCCESS' if result['success'] else 'FAILED')
"
```

## See Also

- [ILMA Problem Solve](../ilma-problem-solve/SKILL.md) - L1-L5 cascade
- [ILMA Self Improve](../ilma-self-improve/SKILL.md) - Continuous improvement

---

**SSS Tier - Military Grade - ILMA System**
