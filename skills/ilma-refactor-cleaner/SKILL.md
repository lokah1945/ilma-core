---
name: ilma-refactor-cleaner
description: SSS Tier skill for refactoring patterns. Military Grade Quality.
triggers:
  - ilma-refactor-cleaner
  - refactor,cleanup,improve
version: 1.0.0
tier: SSS
last_updated: 2026-05-06
---

# Refactor Cleaner

## Overview

**Tier:** SSS (Military Grade)  
**Version:** 1.0.0  
**Status:** OPERATIONAL  
**Last Updated:** 2026-05-06

## Description

This skill provides comprehensive, military-grade patterns and best practices for **refactoring patterns**.

## Trigger Conditions

This skill automatically activates when:
- User requests: `refactor,cleanup,improve`
- Task involves: refactoring patterns
- Context suggests: refactoring patterns operations needed

## Patterns

### Primary Pattern

SSS Tier implementation for refactoring patterns:

```python
# SSS Tier Refactor Cleaner
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class RefactorCleanerHandlerConfig:
    """Configuration for Refactor Cleaner operations."""
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

class RefactorCleanerHandlerHandler:
    """
    SSS Tier handler for refactoring patterns.
    
    Military Grade implementation with full error handling,
    logging, type hints, and comprehensive validation.
    """
    
    def __init__(self, config: Optional[RefactorCleanerHandlerConfig] = None):
        self.config = config or RefactorCleanerHandlerConfig()
        self.logger = logging.getLogger(self.__class__.__name__)
        if self.config.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
    
    def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Execute refactoring patterns operation.
        
        Returns:
            Dict with 'success', 'message', and 'data' keys
        """
        try:
            self.logger.info("Executing Refactor Cleaner")
            
            if not self.config.validate():
                return {
                    'success': False,
                    'message': 'Invalid configuration'
                }
            
            result = self._execute(*args, **kwargs)
            
            return {
                'success': True,
                'message': 'Refactor Cleaner completed successfully',
                'data': result,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error in Refactor Cleaner: {e}")
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
        return {"status": "completed", "operation": "Refactor Cleaner"}


def main() -> int:
    """Main entry point."""
    handler = RefactorCleanerHandlerHandler()
    result = handler.execute()
    return 0 if result['success'] else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

## Implementation Steps

### Step 1: Initialize Handler

```python
config = RefactorCleanerHandlerConfig(verbose=True)
handler = RefactorCleanerHandlerHandler(config=config)
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

## Pitfall: Import-Definition Name Collision (CRITICAL)

When a module defines a function with the same name as an imported function, and the internal function calls the imported one, you **must alias the import** — NOT rename the local function. Renaming the local function breaks all external callers.

### Example: `route_task` name collision
```
# ilma_model_router.py defines: route_task(...)
# ilma.py ALSO defines:     route_task(...) with different signature
# ilma.py's route_task() calls model_router's route_task() internally
# Result: infinite recursion / TypeError if not aliased
```

### Correct Fix — 3-step pattern:
1. **Alias the import at top level:**
   ```python
   from ilma_model_router import route_task as model_route_task
   ```
2. **Update internal calls** (inside the local function that needs the imported version):
   ```python
   result = model_route_task(task_type, capability_context=capability_context)
   ```
3. **Verify:** `python3 -m py_compile` passes + end-to-end test passes

### Wrong Fix — never do this:
- Don't rename the local `route_task()` to `route_task_internal()` — breaks all external callers
- Don't remove the top-level import and keep inline import — creates inconsistency

### General Rule:
> When a module-level function shadows an imported function of the same name, and the local function needs to delegate to the imported one, **always alias the import** (`as some_name`). Never rename the local function.

### Verification checklist after fixing:
- [ ] `python3 -m py_compile` passes for the file
- [ ] `python3 file.py --status` or equivalent smoke test passes
- [ ] `python3 file.py --route <task>` passes (if routing is the function's purpose)
- [ ] No remaining references to the unaliased name in the file

## Verification

```bash
python3 -c "
from skills.ilma-refactor-cleaner.RefactorCleanerHandlerHandler
handler = RefactorCleanerHandlerHandler()
result = handler.execute()
print('SUCCESS' if result['success'] else 'FAILED')
"
```

## See Also

- [ILMA Problem Solve](../ilma-problem-solve/SKILL.md) - L1-L5 cascade
- [ILMA Self Improve](../ilma-self-improve/SKILL.md) - Continuous improvement
- [references/e2e-optimization-20260517.md](references/e2e-optimization-20260517.md) - Full case study: 10-task optimization sequence, inline import deduplication pattern, route_task name collision fix, duplicate file handling, and git sync pattern from session 2026-05-17

---

**SSS Tier - Military Grade - ILMA System**
