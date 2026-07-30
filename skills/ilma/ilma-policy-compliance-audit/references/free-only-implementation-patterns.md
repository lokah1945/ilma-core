# FREE_ONLY Implementation Patterns

## Pattern 1: Core Functions (opencode, nous, blackbox)

```python
def free_only_enabled() -> bool:
    v = (os.environ.get('FREE_ONLY') or 'no').strip().lower()
    return v in ('yes', 'true', '1', 'on', 'y')

def is_free_model(model_id: str) -> bool:
    if not model_id:
        return False
    mid = str(model_id).lower().strip()
    if 'free' in mid:
        return True
    allow = (os.environ.get('FREE_MODEL_ALLOWLIST') or '').strip()
    if not allow:
        return False
    extras = {x.strip().lower() for x in allow.split(',') if x.strip()}
    bare = mid.split('/')[-1] if '/' in mid else mid
    return mid in extras or bare in extras

def model_allowed(model_id: str) -> bool:
    if not free_only_enabled():
        return True
    if not model_id:
        return False
    return is_free_model(model_id)
```

## Pattern 2: OpenRouter (suffix-based)

```python
def is_free_model(model_id: str) -> bool:
    if not model_id:
        return False
    mid = str(model_id).lower().strip()
    return bool(mid.endswith((':free', '-free')))
```

## Pattern 3: Enforcement Points

### Via Error Response (opencode, nous, blackbox)
```python
def free_only_error(model_id: str) -> dict:
    return {
        'error': {
            'type': 'invalid_request_error',
            'message': f'Model "{model_id}" is blocked by FREE_ONLY=yes...',
            'code': 'free_only_restricted',
            'param': 'model',
        }
    }
```

### Via Middleware Check (openrouter)
```python
def _check_free_only(model: str) -> JSONResponse | None:
    if free_only_enabled() and model and not is_free_model(model):
        return JSONResponse(
            {"error": {"message": f"FREE_ONLY mode: model '{model}' is not a free model..."}},
            status_code=400,
        )
    return None
```

## Verification Commands

```bash
# Check FREE_ONLY setting
grep "^FREE_ONLY" /root/wrapper/*/.env

# Check is_free_model implementation
grep -A 10 "def is_free_model" /root/wrapper/*/src/main.py

# Test model allowed check
curl -s http://localhost:9102/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4", "messages": []}'
```