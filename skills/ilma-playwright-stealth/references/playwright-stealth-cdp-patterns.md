# Playwright Stealth + CDP — Verified Working Patterns

## Core Pattern (Tested 2026-05-11)

```python
from playwright.sync_api import sync_playwright
from playwright_stealth.stealth import Stealth

stealth = Stealth()

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox'
        ]
    )
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    )
    
    # KEY: apply to context, not page
    stealth.apply_stealth_sync(context)
    
    page = context.new_page()
    page.goto('https://example.com', timeout=15000)
    
    # Verify
    webdriver = page.evaluate('navigator.webdriver')  # False = active
    plugins = page.evaluate('navigator.plugins.length')  # 3 = normal
```

## CDP Integration

```python
# Create CDP session on any page
cdp = page.context.new_cdp_session(page)

# Performance monitoring
cdp.send('Performance.enable', {})
metrics = cdp.send('Performance.getMetrics', {})
print(f'Metrics: {len(metrics["metrics"])}')  # Should be 36

# Runtime evaluation
cdp.send('Runtime.enable', {})
result = page.evaluate('1+1')  # works fine

# Network monitoring
cdp.send('Network.enable', {})
```

## Storage State — Authenticated Sessions (KEY for chat.qwen.ai)

```python
# Load pre-saved cookies (e.g., from Google OAuth login to Qwen)
context = browser.new_context(
    storage_state='/path/to/qwen.storageState.json',
    viewport={'width': 1400, 'height': 900},
    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)
stealth.apply_stealth_sync(context)

page = context.new_page()
page.goto('https://chat.qwen.ai', wait_until='domcontentloaded')
page.wait_for_timeout(5000)

# Verify logged in
has_chat = page.query_selector('.message-input-textarea') is not None
has_model_selector = page.query_selector('.index-module__model-selector-text___XvWe0') is not None
print(f"Logged in: {has_chat and has_model_selector}")
```

## Chat UI Response Waiting (Qwen Pattern)

```python
def _wait_for_response(self, timeout: int = 180000) -> str:
    """Wait for Qwen response with intelligent polling."""
    start = time.time()
    poll_interval = 0.5
    
    while time.time() - start < timeout / 1000:
        try:
            body = self._page.evaluate('document.body.innerText')
            
            # Check for thinking completion (Qwen-specific marker)
            if 'Thinking completed' in body or ('thought' not in body.lower() and len(body) > 50):
                # Get last message
                messages = self._page.query_selector_all('div[class*="content"]')
                if messages:
                    text = messages[-1].inner_text()
                    if text and len(text) > 10:
                        return text
        except:
            pass
        
        # Adaptive polling
        thinking = self._page.query_selector('.thinking-indicator, [class*="thinking"]')
        poll_interval = 1.0 if thinking else 0.5
        self._page.wait_for_timeout(poll_interval * 1000)
    
    raise TimeoutError(f"Response timeout after {timeout}ms")
```

## Chat UI Send Message (Enter beats Click)

```python
def _send_message(self, text: str) -> None:
    """Send chat message via Enter key."""
    prompt_box = self._page.query_selector('.message-input-textarea')
    if not prompt_box:
        raise ValueError("Chat input not found")
    
    prompt_box.click()
    prompt_box.fill('')
    prompt_box.type(text, delay=10)
    self._page.keyboard.press('Enter')  # ← More reliable than clicking submit
```

## Model Dropdown Discovery (Qwen Multi-Model)

```python
def sync_models(self) -> List[ModelInfo]:
    """Sync all models from Qwen dropdown at runtime."""
    # Open dropdown
    model_selector = self._page.query_selector('.index-module__model-selector-text___XvWe0, .ant-dropdown-trigger')
    if not model_selector:
        return []
    
    model_selector.click()
    self._page.wait_for_timeout(2000)
    
    # Extract visible models
    models = []
    dropdown = self._page.query_selector('.ant-dropdown')
    if dropdown:
        content = dropdown.inner_text()
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        
        for line in lines:
            if 3 < len(line) < 60 and line not in ['Expand more models', 'New Chat', 'Cancel', 'Thinking', 'Auto']:
                model_id = self._normalize_model_id(line)
                if model_id:
                    models.append(ModelInfo(
                        id=model_id,
                        display_name=line,
                        last_synced=datetime.now().isoformat()
                    ))
    
    # Click "Expand more models" if present
    expand = self._page.query_selector('text=Expand more models')
    if expand:
        expand.click()
        self._page.wait_for_timeout(2000)
        # Extract more...
    
    # Save to DB
    for m in models:
        self.db.upsert_model(m)
    
    self.db.log_sync(len(models), 'success')
    return models
```

## Model ID Normalization (Qwen Pattern)

```python
def _normalize_model_id(self, display_name: str) -> Optional[str]:
    """Normalize Qwen UI display name to consistent ID."""
    name_lower = display_name.lower()
    
    # Special cases first
    if 'most powerful' in name_lower and 'qwen' in name_lower:
        return 'qwen3-max'
    if 'vision-language' in name_lower and 'qwen3' in name_lower:
        return 'qwen3-vl-235b-a22b'
    if name_lower.strip() == 'qwen3':
        return 'qwen3'
    
    # Qwen3.6
    if 'qwen3.6' in name_lower:
        if 'plus' in name_lower: return 'qwen3.6-plus'
        if 'max' in name_lower: return 'qwen3.6-max-preview'
        if '27b' in name_lower: return 'qwen3.6-27b'
        if '35b' in name_lower: return 'qwen3.6-35b-a3b'
        return 'qwen3.6-plus'
    
    # Qwen3.5
    if 'qwen3.5' in name_lower:
        if 'omni' in name_lower:
            return 'qwen3.5-omni-flash' if 'flash' in name_lower else 'qwen3.5-omni-plus'
        if 'plus' in name_lower: return 'qwen3.5-plus'
        if 'max' in name_lower: return 'qwen3.5-max-preview'
        if 'flash' in name_lower: return 'qwen3.5-flash'
        if '397b' in name_lower: return 'qwen3.5-397b-a17b'
        if '122b' in name_lower: return 'qwen3.5-122b-a10b'
        return 'qwen3.5-plus'
    
    # Generic fallback
    if 'qwen' in name_lower:
        return name_lower.replace(' ', '-')
    return None
```

## What Works

| Feature | Status | Notes |
|---------|--------|-------|
| `playwright_stealth` v2.0.3 | ✅ | Has `Stealth` class |
| `Stealth()` (no args) | ✅ | Correct constructor |
| `stealth.apply_stealth_sync(context)` | ✅ | Correct method |
| CDP on page | ✅ | `page.context.new_cdp_session(page)` |
| Storage state for auth | ✅ | Works with Google OAuth |
| Chat UI response polling | ✅ | "Thinking completed" marker |
| Enter key for send | ✅ | More reliable than click |

## Known Limitations

- `nowsecure.nl` — still detects (advanced fingerprint)
- Cloudflare supercharged — may challenge
- DataDome/PerimeterX — specialized bot protection

## Package Versions (2026-05-12)

```
playwright           1.58.0
playwright-stealth   2.0.3  ✅
playwright-extra     NOT installed (not needed)
```

## Qwen-Specific Selectors

```python
SELECTORS = {
    'model_selector': '.index-module__model-selector-text___XvWe0, .ant-dropdown-trigger',
    'chat_input': '.message-input-textarea',
    'thinking_indicator': '[class*="thinking"]',
    'message_content': 'div[class*="content"]',
    'send_button': 'button[type="submit"], button[class*="send"]',
}
```