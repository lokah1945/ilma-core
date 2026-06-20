# Response Waiting Patterns — Debug Log 2026-05-12

## Problem: Stop Button Doesn't Appear in Headless/xvfb

When automating chat interfaces (Qwen, Arena, etc.) in headless Chrome or xvfb-run environments, the "Stop" button that typically appears during response generation **never renders**, even when responses are actively being generated.

**Why:** Headless Chrome and xvfb-run Chrome have different rendering behavior. Elements with CSS `visibility: hidden` or that are conditionally rendered based on user interaction state may not appear in headless mode.

## Verified Solution: Body Text Polling

Instead of waiting for stop button, poll `body.inner_text()` for completion markers:

```python
def _wait_for_response(self, timeout: int = 120000) -> str:
    start_time = time.time()
    poll_interval = 3  # seconds between polls
    
    while time.time() - start_time < timeout:
        body = self._page.query_selector('body')
        txt = body.inner_text()
        
        # Check for completion markers (varies by site)
        markers = [
            'Thinking completed',       # Qwen
            'Response completed',       # Generic
            'Generating response',       # Generic
            'Regenerate',                # Chat UI (means response done)
        ]
        
        for marker in markers:
            if marker in txt:
                idx = txt.find(marker)
                response = txt[idx + len(marker):].strip()
                # Find boundary (triple newline separates response from UI)
                boundary = response.find('\n\n\n')
                if boundary > 100:
                    response = response[:boundary]
                return response[:8000]
        
        time.sleep(poll_interval)
    
    # Fallback: extract last substantial lines
    lines = [l for l in txt.split('\n') if len(l.strip()) > 20]
    return '\n'.join(lines[-20:])[:8000]
```

## Sites Tested

### Qwen.ai (2026-05-12)
- **Marker:** `'Thinking completed'` — appears in body text when response is complete
- **Stop button:** Never appears in headless or xvfb mode
- **Fix:** Body text polling works reliably

### Arena.ai (2026-05-12)
- **Marker:** `'Regenerate'` button appears when response is done — but button detection also unreliable
- **Stop button:** Never appears
- **Fix:** Body text polling, look for "Regenerate" in text

## Key Insights

1. **Body text is always accessible** — even when UI elements are not rendered, body.inner_text() reflects current DOM state
2. **Completion markers are site-specific** — you must find what text indicates response is done
3. **Triple newline separator** — most chat UIs separate response from subsequent UI elements with `\n\n\n`
4. **Polling interval** — 3 seconds is good balance between responsiveness and server load
5. **Fallback always** — if no marker found, return last substantial text

## Finding Markers

To find the right completion marker for a new site:

```python
# Debug: print body text at intervals
for i in range(10):
    page.wait_for_timeout(5000)
    txt = page.inner_text('body')
    print(f"=== {i*5}s ===")
    print(txt[-500:])
    print()
    if 'Regenerate' in txt or 'Thinking completed' in txt:
        print("FOUND MARKER!")
        break
```

## Arena-specific: Terms Dialog Timing

**Critical discovery (2026-05-12):** Terms dialog on Arena appears AFTER sending message, not before.

```
1. Navigate to arena.ai → No terms shown
2. Fill textarea + press Enter → Message sent
3. Terms dialog appears NOW (asking to agree)
4. User clicks Agree → Log In modal appears
```

**Solution:** Check for terms AFTER sending, not before:
```python
textarea.fill(message)
textarea.press('Enter')

# Check if terms dialog appeared AFTER sending
body = self._page.inner_text('body')
if 'Terms of Use' in body and 'Agree' in body:
    self._accept_terms_if_shown()  # Click Agree button

self._page.wait_for_timeout(timeout)
```

**Why clicking Agree button is better than keyboard Enter:** If focus is on textarea and you press Enter, it sends another message instead of accepting terms. Clicking the button directly is more reliable.

## Testing Script

```python
import sys
sys.path.insert(0, '/root/.hermes/profiles/ilma/scripts')
from playwright.sync_api import sync_playwright

p = sync_playwright().start()
browser = p.chromium.launch(
    headless=True,
    args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
)

ctx = browser.new_context(
    storage_state='/root/.openclaw/browser_sessions/lokah2150/state.json'
)
page = ctx.new_page()

# Navigate to chat site
page.goto('https://chat.qwen.ai', wait_until='domcontentloaded', timeout=30000)
page.wait_for_timeout(3000)

# Find textarea and send message
textarea = page.query_selector('textarea')
textarea.fill('Hello, test message')
textarea.press('Enter')

# Poll for response
print("Waiting for response...")
for i in range(40):  # 120 seconds max
    page.wait_for_timeout(3000)
    txt = page.inner_text('body')
    
    markers = ['Thinking completed', 'Response completed', 'Regenerate']
    for marker in markers:
        if marker in txt:
            idx = txt.find(marker)
            response = txt[idx + len(marker):].strip()
            boundary = response.find('\n\n\n')
            if boundary > 100:
                response = response[:boundary]
            print(f"Response ({len(response)} chars): {response[:200]}")
            break
    else:
        print(f"Waiting... {i*3}s")
        continue
    break
```

## Reference: Stop Button Detection (BROKEN in headless)

```python
# ❌ DOES NOT WORK in headless or xvfb
def wait_for_response_broken(self, timeout: int = 180000) -> str:
    start_time = time.time()
    
    # Wait for stop button to appear
    while time.time() - start_time < timeout:
        stop_btn = self._page.query_selector('button:has-text("Stop")')
        if stop_btn and stop_btn.is_visible():
            break
        self._page.wait_for_timeout(2000)
    
    # Wait for stop button to disappear
    while time.time() - start_time < timeout:
        stop_btn = self._page.query_selector('button:has-text("Stop")')
        if not stop_btn or not stop_btn.is_visible():
            break
        self._page.wait_for_timeout(2000)
```

**Why broken:** In headless Chrome or xvfb, `stop_btn.is_visible()` returns `False` even when the button exists in the DOM. The rendering state differs from actual DOM presence.