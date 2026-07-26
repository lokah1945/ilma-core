#!/usr/bin/env python3
"""
Headless Browser Execution Plane — ILMA Canonical Copy
=======================================================

Originally: /root/.hermes/profiles/ilma/scripts/browser_plane.py
Copied to: /root/.hermes/profiles/ilma/scripts/ilma_browser_plane.py

Purpose:
- Canonical browser layer for ALL ILMA browser automation
- Playwright + stealth + CDP for JavaScript-heavy pages
- Bot detection evasion (Cloudflare, reCAPTCHA)
- DOM-aware automation with error recovery
- NO external AYDA dependency — self-contained in ILMA

This copy ensures:
1. ILMA browser scripts don't depend on external paths
2. Maintenance and modifications done in ILMA directory
3. Version control and stability within ILMA ecosystem

Usage:
    from ilma_browser_plane import PlaywrightBackend, BrowserBackend, DOMSnapshot
    browser = PlaywrightBackend(headless=True, stealth=True, cdp=True)
    await browser.initialize()
    snapshot = await browser.goto("https://example.com")
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & Constants
# ---------------------------------------------------------------------------

class ActionType(str, Enum):
    CLICK = "click"
    TYPE = "type"
    GOTO = "goto"
    SCROLL = "scroll"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    EVALUATE = "evaluate_js"
    SELECT = "select_option"
    HOVER = "hover"
    PRESS = "press"
    CLEAR = "clear"
    SUBMIT = "submit"
    BACK = "back"
    FORWARD = "forward"
    RELOAD = "reload"


class ErrorClass(str, Enum):
    STALE_REF = "stale_ref"           # Element no longer in DOM
    MODAL_OBSTRUCTION = "modal_obstruction"  # Modal dialog blocking
    PAGE_NOT_LOADED = "page_not_loaded"      # Element not present yet
    AUTH_REDIRECT = "auth_redirect"           # Redirected to login
    HIDDEN_ELEMENT = "hidden_element"         # Element is hidden
    ASYNC_RENDER_RACE = "async_render_race"   # React/Vue render incomplete
    TIMEOUT = "timeout"
    NAVIGATION = "navigation"
    UNKNOWN = "unknown"


class BrowserBackend(str, Enum):
    PLAYWRIGHT = "playwright"
    SELENIUM = "selenium"
    REQUESTS = "requests"  # Fallback: requests + BeautifulSoup


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ElementInfo:
    """Information about a DOM element."""
    tag: str
    text: Optional[str] = None
    href: Optional[str] = None
    src: Optional[str] = None
    rect: Optional[Dict[str, float]] = None
    visible: bool = True
    enabled: bool = True
    checked: bool = False
    value: Optional[str] = None
    placeholder: Optional[str] = None
    attributes: Dict[str, str] = field(default_factory=dict)
    css_selector: Optional[str] = None
    xpath: Optional[str] = None


@dataclass
class FormInfo:
    """Information about a form."""
    action: Optional[str] = None
    method: str = "get"
    inputs: List[ElementInfo] = field(default_factory=list)
    buttons: List[ElementInfo] = field(default_factory=list)


@dataclass
class DOMSnapshot:
    """Complete DOM snapshot at a point in time."""
    url: str
    title: str
    elements: List[ElementInfo] = field(default_factory=list)
    forms: List[FormInfo] = field(default_factory=list)
    html: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    viewport: Optional[Dict[str, float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BrowserAction:
    """A single browser action to execute."""
    type: ActionType
    target: str  # CSS selector, XPath, or text content
    value: Optional[str] = None
    timeout_ms: int = 10000
    index: int = 0  # For multiple matches, which one
    verify_after: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationResult:
    """Result of verifying a state change."""
    success: bool
    message: str
    before: Optional[DOMSnapshot] = None
    after: Optional[DOMSnapshot] = None
    changes_detected: List[str] = field(default_factory=list)


@dataclass
class BrowserResult:
    """Result of executing a plan."""
    success: bool
    final_url: str = ""
    final_title: str = ""
    actions_executed: List[BrowserAction] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)
    error: Optional[str] = None
    error_class: Optional[ErrorClass] = None
    failed_action: Optional[BrowserAction] = None
    dom_snapshots: List[DOMSnapshot] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Planner: DOM-to-Goal
# ---------------------------------------------------------------------------

class DOMToGoalPlanner:
    """
    Converts high-level instructions into sequences of browser actions.
    Uses heuristics to map text/content to element selectors.
    """

    def __init__(self, backend: BrowserBackend = BrowserBackend.PLAYWRIGHT):
        self.backend = backend

    def plan(self, instruction: str, current_dom: Optional[DOMSnapshot] = None) -> List[BrowserAction]:
        """
        Convert a high-level instruction into a list of BrowserActions.
        
        Args:
            instruction: Natural language instruction (e.g., "click the login button")
            current_dom: Current DOM snapshot for context (optional)
        
        Returns:
            List of BrowserAction objects to execute in order
        """
        instruction = instruction.lower().strip()
        actions: List[BrowserAction] = []

        # Navigation
        if instruction.startswith(("go to ", "navigate to ", "open ", "visit ")):
            url = instruction.split(" ", 1)[1].strip()
            if url.startswith(("http://", "https://")):
                actions.append(BrowserAction(type=ActionType.GOTO, target=url))
            else:
                actions.append(BrowserAction(type=ActionType.GOTO, target=f"https://{url}"))
            return actions

        # URL patterns
        if "://" in instruction or instruction.startswith(("www.", "http")):
            url = instruction if instruction.startswith(("http://", "https://")) else f"https://{instruction}"
            actions.append(BrowserAction(type=ActionType.GOTO, target=url))
            return actions

        # Common actions
        if any(k in instruction for k in ["click", "press", "tap", "select"]):
            actions.extend(self._plan_click(instruction, current_dom))

        if any(k in instruction for k in ["type", "fill", "enter", "write"]):
            actions.extend(self._plan_type(instruction, current_dom))

        if any(k in instruction for k in ["scroll", "scroll down", "scroll up"]):
            actions.extend(self._plan_scroll(instruction))

        if "screenshot" in instruction:
            actions.append(BrowserAction(type=ActionType.SCREENSHOT, target=""))

        if "wait" in instruction:
            # Extract wait duration
            import re
            match = re.search(r"wait[:\s]+(\d+)", instruction)
            ms = int(match.group(1)) * 1000 if match else 2000
            actions.append(BrowserAction(type=ActionType.WAIT, target="", timeout_ms=ms))

        if "submit" in instruction:
            actions.append(BrowserAction(type=ActionType.SUBMIT, target=""))

        if "hover" in instruction:
            actions.extend(self._plan_hover(instruction, current_dom))

        return actions

    def _plan_click(self, instruction: str, dom: Optional[DOMSnapshot]) -> List[BrowserAction]:
        """Plan click actions."""
        actions = []
        target = self._extract_target(instruction, dom)
        actions.append(BrowserAction(type=ActionType.CLICK, target=target))
        return actions

    def _plan_type(self, instruction: str, dom: Optional[DOMSnapshot]) -> List[BrowserAction]:
        """Plan type/fill actions."""
        actions = []
        import re
        
        # Extract value to type
        value_match = re.search(r"(?:type|fill|enter|write)[:\s]+['\"]([^'\"]+)['\"]", instruction)
        if not value_match:
            value_match = re.search(r"(?:type|fill|enter|write)[^\w]+(.+?)(?:\s+in|\s+into|\s+on|\s+field|\s+input)", instruction)
        
        value = value_match.group(1) if value_match else ""
        
        # Extract target field
        target = self._extract_target(instruction, dom)
        
        if target:
            actions.append(BrowserAction(type=ActionType.TYPE, target=target, value=value))
        return actions

    def _plan_scroll(self, instruction: str) -> List[BrowserAction]:
        """Plan scroll actions."""
        actions = []
        if "down" in instruction:
            actions.append(BrowserAction(type=ActionType.SCROLL, target="down"))
        elif "up" in instruction:
            actions.append(BrowserAction(type=ActionType.SCROLL, target="up"))
        else:
            actions.append(BrowserAction(type=ActionType.SCROLL, target="down"))
        return actions

    def _plan_hover(self, instruction: str, dom: Optional[DOMSnapshot]) -> List[BrowserAction]:
        """Plan hover actions."""
        actions = []
        target = self._extract_target(instruction, dom)
        actions.append(BrowserAction(type=ActionType.HOVER, target=target))
        return actions

    def _extract_target(self, instruction: str, dom: Optional[DOMSnapshot]) -> str:
        """Extract the target element from instruction text."""
        import re
        
        # CSS selector patterns
        css_patterns = [
            r"#[\w-]+",  # #id
            r"\.[\w-]+",  # .class
            r"\[[\w='\"]+\]",  # [attr=value]
            r"<\w+",  # <tag
        ]
        
        for pattern in css_patterns:
            match = re.search(pattern, instruction)
            if match:
                return match.group(0)
        
        # XPath pattern
        xpath_match = re.search(r"xpath[:\s]+(.+?)(?:\s|$)", instruction)
        if xpath_match:
            return xpath_match.group(1).strip()
        
        # Text content - find element by visible text
        text_match = re.search(r"['\"]([^'\"]+)['\"]", instruction)
        if text_match:
            return text_match.group(1)
        
        # Button/link by text content from DOM
        if dom:
            for word in instruction.split():
                if len(word) > 3:
                    for elem in dom.elements:
                        if elem.text and word.lower() in elem.text.lower():
                            return elem.text
        
        return ""


# ---------------------------------------------------------------------------
# Error Recovery
# ---------------------------------------------------------------------------

class ErrorRecovery:
    """Handles error recovery based on error classification."""

    RECOVERY_STRATEGIES: Dict[ErrorClass, Callable] = {}

    @classmethod
    def register_recovery(cls, error_class: ErrorClass, strategy: Callable):
        """Register a recovery strategy for an error class."""
        cls.RECOVERY_STRATEGIES[error_class] = strategy

    @classmethod
    def recover(cls, error_class: ErrorClass, context: Dict[str, Any]) -> BrowserAction:
        """Get a recovery action for the given error class."""
        strategy = cls.RECOVERY_STRATEGIES.get(error_class)
        if strategy:
            return strategy(context)
        
        # Default recovery: resnapshot and retry
        return BrowserAction(type=ActionType.WAIT, target="", timeout_ms=2000)


# Register default recovery strategies
def _make_default_recovery_strategies():
    ErrorRecovery.RECOVERY_STRATEGIES = {
        ErrorClass.STALE_REF: lambda ctx: BrowserAction(
            type=ActionType.WAIT, target="", timeout_ms=1000
        ),
        ErrorClass.MODAL_OBSTRUCTION: lambda ctx: BrowserAction(
            type=ActionType.EVALUATE, 
            target="document.querySelectorAll('.modal, [role=dialog], .overlay').forEach(e => e.remove())",
            timeout_ms=5000
        ),
        ErrorClass.PAGE_NOT_LOADED: lambda ctx: BrowserAction(
            type=ActionType.WAIT, target="", timeout_ms=3000
        ),
        ErrorClass.HIDDEN_ELEMENT: lambda ctx: BrowserAction(
            type=ActionType.EVALUATE,
            target=f"document.querySelector('{ctx.get('target', '')}').scrollIntoView()",
            timeout_ms=1000
        ),
        ErrorClass.ASYNC_RENDER_RACE: lambda ctx: BrowserAction(
            type=ActionType.WAIT, target="", timeout_ms=2000
        ),
    }

_make_default_recovery_strategies()


# ---------------------------------------------------------------------------
# Browser Backend Implementations
# ---------------------------------------------------------------------------

class PlaywrightBackend:
    """Canonical Playwright browser backend for AYDA/OpenClaw automation.

    This is the mature browser/computer-use execution layer. It intentionally
    reuses the existing Playwright + stealth + CDP stack instead of introducing
    another browser agent runtime. Higher-level agents should wrap this backend
    rather than launching independent browser engines.
    """

    def __init__(self, headless: bool = True, stealth: bool = True, cdp: bool = True):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.headless = headless
        self.stealth = stealth
        self.cdp = cdp
        self.stealth_applied = False
        self.cdp_session = None
        self.api_calls: List[Dict[str, str]] = []
        self.network_requests: List[Dict[str, str]] = []
        self.console_messages: List[Dict[str, str]] = []
        self.js_errors: List[Dict[str, str]] = []
        self.performance_metrics: Dict[str, Any] = {}
        self._initialized = False

    async def initialize(self):
        """Initialize Playwright."""
        if self._initialized:
            return
        try:
            from playwright.async_api import async_playwright
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-background-networking",
                    "--disable-background-timer-throttling",
                    "--disable-renderer-backgrounding",
                    "--mute-audio",
                ],
            )
            self.context = await self.browser.new_context(
                viewport={"width": 1365, "height": 768},
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                locale="id-ID",
                timezone_id="Asia/Jakarta",
                java_script_enabled=True,
                extra_http_headers={"Accept-Language": "id-ID,id;q=0.9,en;q=0.8"},
            )
            self.page = await self.context.new_page()

            if self.stealth:
                try:
                    from playwright_stealth import Stealth  # type: ignore
                    await Stealth(
                        navigator_languages_override=("id-ID", "id"),
                        navigator_platform_override="Linux x86_64",
                    ).apply_stealth_async(self.page)
                    self.stealth_applied = True
                except Exception as exc:
                    logger.warning(f"Playwright stealth unavailable: {exc}")

            self.page.on("request", self._on_request)
            self.page.on("console", self._on_console)
            self.page.on("pageerror", self._on_pageerror)

            if self.cdp:
                try:
                    self.cdp_session = await self.context.new_cdp_session(self.page)
                    await self.cdp_session.send("Performance.enable")
                    await self.cdp_session.send("Runtime.enable")
                except Exception as exc:
                    logger.warning(f"CDP session unavailable: {exc}")
            self._initialized = True
            logger.info("Playwright backend initialized")
        except ImportError:
            logger.warning("Playwright not installed, will fallback")
            raise

    async def close(self):
        """Close browser."""
        for obj in (self.page, self.context, self.browser):
            if obj:
                try:
                    await asyncio.wait_for(obj.close(), timeout=5)
                except Exception:
                    pass
        if self.playwright:
            try:
                await asyncio.wait_for(self.playwright.stop(), timeout=5)
            except Exception:
                pass
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
        self._initialized = False

    async def goto(self, url: str, timeout_ms: int = 30000) -> DOMSnapshot:
        """Navigate to URL."""
        if not self.page:
            raise RuntimeError("Browser not initialized")
        
        response = await self.page.goto(url, timeout=timeout_ms)
        try:
            await self.page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception:
            await self.page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        await self._handle_cookie_consent()
        await self._refresh_performance_metrics()
        return await self._snapshot()

    async def click(self, selector: str, timeout_ms: int = 10000, index: int = 0) -> DOMSnapshot:
        """Click element."""
        if not self.page:
            raise RuntimeError("Browser not initialized")
        
        elements = await self.page.query_selector_all(selector)
        if not elements:
            raise ElementNotFoundError(f"Element not found: {selector}")
        
        target = elements[min(index, len(elements) - 1)]
        await target.click(timeout=timeout_ms)
        await self.page.wait_for_load_state("networkidle", timeout=timeout_ms)
        return await self._snapshot()

    async def type(self, selector: str, value: str, timeout_ms: int = 10000, index: int = 0) -> DOMSnapshot:
        """Type into element."""
        if not self.page:
            raise RuntimeError("Browser not initialized")
        
        elements = await self.page.query_selector_all(selector)
        if not elements:
            raise ElementNotFoundError(f"Element not found: {selector}")
        
        target = elements[min(index, len(elements) - 1)]
        await target.fill(value, timeout=timeout_ms)
        return await self._snapshot()

    async def scroll(self, direction: str = "down", timeout_ms: int = 5000) -> DOMSnapshot:
        """Scroll page."""
        if not self.page:
            raise RuntimeError("Browser not initialized")
        
        scroll_amount = 500 if direction == "down" else -500
        await self.page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        await asyncio.sleep(0.5)
        return await self._snapshot()

    async def wait(self, timeout_ms: int = 2000) -> DOMSnapshot:
        """Wait for specified time."""
        await asyncio.sleep(timeout_ms / 1000)
        return await self._snapshot()

    async def screenshot(self) -> Tuple[str, DOMSnapshot]:
        """Take screenshot."""
        if not self.page:
            raise RuntimeError("Browser not initialized")
        
        screenshot_bytes = await self.page.screenshot(full_page=True)
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
        snapshot = await self._snapshot()
        return screenshot_b64, snapshot

    async def evaluate(self, js_code: str, timeout_ms: int = 10000) -> Any:
        """Execute JavaScript."""
        if not self.page:
            raise RuntimeError("Browser not initialized")
        
        return await self.page.evaluate(js_code, timeout=timeout_ms)

    async def select_option(self, selector: str, value: str, timeout_ms: int = 10000) -> DOMSnapshot:
        """Select option in dropdown."""
        if not self.page:
            raise RuntimeError("Browser not initialized")
        
        await self.page.select_option(selector, value, timeout=timeout_ms)
        await self.page.wait_for_load_state("networkidle", timeout=timeout_ms)
        return await self._snapshot()

    async def hover(self, selector: str, timeout_ms: int = 10000) -> DOMSnapshot:
        """Hover over element."""
        if not self.page:
            raise RuntimeError("Browser not initialized")
        
        await self.page.hover(selector, timeout=timeout_ms)
        return await self._snapshot()

    async def submit(self, selector: str = "form", timeout_ms: int = 10000) -> DOMSnapshot:
        """Submit a form."""
        if not self.page:
            raise RuntimeError("Browser not initialized")
        
        await self.page.evaluate(f"document.querySelector('{selector}').submit()")
        await self.page.wait_for_load_state("networkidle", timeout=timeout_ms)
        return await self._snapshot()

    async def _snapshot(self) -> DOMSnapshot:
        """Capture current DOM snapshot."""
        if not self.page:
            raise RuntimeError("Browser not initialized")
        
        url = self.page.url
        title = await self.page.title()
        
        elements = []
        try:
            elem_data = await self.page.evaluate("""
                () => {
                    const result = [];
                    const interactables = document.querySelectorAll('a, button, input, select, textarea, [onclick], [role="button"]');
                    interactables.forEach((el, i) => {
                        const rect = el.getBoundingClientRect();
                        const visible = rect.width > 0 && rect.height > 0 &&
                                        getComputedStyle(el).display !== 'none' &&
                                        getComputedStyle(el).visibility !== 'hidden';
                        result.push({
                            tag: el.tagName.toLowerCase(),
                            text: el.textContent?.trim().substring(0, 200) || null,
                            href: el.href || null,
                            src: el.src || null,
                            rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                            visible: visible,
                            enabled: !el.disabled,
                            value: el.value || null,
                            placeholder: el.placeholder || null,
                            attributes: Array.from(el.attributes).reduce((acc, attr) => {
                                acc[attr.name] = attr.value;
                                return acc;
                            }, {}),
                            css_selector: null,  // Would need more complex logic
                            xpath: null
                        });
                    });
                    return result;
                }
            """)
            
            for e in elem_data:
                elements.append(ElementInfo(**e))
        except Exception as ex:
            logger.warning(f"Failed to get element data: {ex}")

        forms = []
        try:
            form_data = await self.page.evaluate("""
                () => {
                    return Array.from(document.querySelectorAll('form')).map(form => ({
                        action: form.action || null,
                        method: form.method || 'get',
                        inputs: Array.from(form.querySelectorAll('input, select, textarea')).map(input => ({
                            tag: input.tagName.toLowerCase(),
                            name: input.name || null,
                            type: input.type || null,
                            value: input.value || null
                        }))
                    }));
                }
            """)
            for f in form_data:
                forms.append(FormInfo(**f))
        except Exception as ex:
            logger.warning(f"Failed to get form data: {ex}")

        return DOMSnapshot(
            url=url,
            title=title,
            elements=elements,
            forms=forms,
            metadata={
                "backend": "playwright",
                "stealth_applied": self.stealth_applied,
                "cdp_used": self.cdp_session is not None,
                "api_call_count": len(self.api_calls),
                "network_request_count": len(self.network_requests),
                "console_message_count": len(self.console_messages),
                "js_error_count": len(self.js_errors),
                "performance_metrics": self.performance_metrics,
            },
        )

    def _on_request(self, request: Any) -> None:
        url = request.url
        item = {"url": url, "method": request.method}
        self.network_requests.append(item)
        if any(token in url for token in ("/api/", "/data/", "/v1/", "/v2/", ".json")) and not any(
            token in url for token in (".css", ".jpg", ".png", ".woff", ".ico")
        ):
            self.api_calls.append(item)

    def _on_console(self, message: Any) -> None:
        if message.type in ("log", "info", "warn", "error"):
            self.console_messages.append({"type": message.type, "text": message.text[:300]})

    def _on_pageerror(self, error: Any) -> None:
        self.js_errors.append({"text": str(error)[:300], "timestamp": str(time.time())})

    async def _refresh_performance_metrics(self) -> None:
        if not self.cdp_session:
            return
        try:
            metrics = await self.cdp_session.send("Performance.getMetrics")
            perf = {m["name"]: round(m["value"], 3) for m in metrics.get("metrics", [])}
            self.performance_metrics = {
                "ScriptDuration_ms": perf.get("ScriptDuration"),
                "TaskDuration_ms": perf.get("TaskDuration"),
                "Nodes": perf.get("Nodes"),
                "JSHeapUsedSize": perf.get("JSHeapUsedSize"),
                "LayoutCount": perf.get("LayoutCount"),
                "RecalcStyleCount": perf.get("RecalcStyleCount"),
            }
        except Exception as exc:
            logger.debug(f"CDP performance metrics unavailable: {exc}")

    async def _handle_cookie_consent(self) -> None:
        if not self.page:
            return
        selectors = [
            "button[title='Agree']",
            "button[id='onetrust-accept-btn-handler']",
            "button[class*='consent']",
            "button[class*='accept']",
            "button[class*='agree']",
            "[aria-label*='Agree']",
            "[aria-label*='Accept']",
            "#cookieConsentAccept",
        ]
        for selector in selectors:
            try:
                button = await self.page.query_selector(selector)
                if button and await button.is_visible():
                    await button.click(timeout=3000)
                    await self.page.wait_for_timeout(500)
                    self.console_messages.append({"type": "info", "text": f"Clicked consent button: {selector}"})
                    break
            except Exception:
                continue


class SeleniumBackend:
    """Selenium-based browser automation (fallback)."""

    def __init__(self, headless: bool = True):
        self.driver = None
        self.headless = headless
        self._initialized = False

    def initialize(self):
        """Initialize Selenium."""
        if self._initialized:
            return
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            
            options = Options()
            if self.headless:
                options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1280,720")
            options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")
            
            self.driver = webdriver.Chrome(options=options)
            self._initialized = True
            logger.info("Selenium backend initialized")
        except ImportError:
            logger.warning("Selenium not installed")
            raise

    def close(self):
        """Close browser."""
        if self.driver:
            self.driver.quit()
        self._initialized = False

    def goto(self, url: str, timeout_ms: int = 30000) -> DOMSnapshot:
        """Navigate to URL."""
        if not self.driver:
            raise RuntimeError("Browser not initialized")
        
        self.driver.get(url)
        self._wait_for_load(timeout_ms)
        return self._snapshot()

    def click(self, selector: str, timeout_ms: int = 10000, index: int = 0) -> DOMSnapshot:
        """Click element."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
        if not elements:
            raise ElementNotFoundError(f"Element not found: {selector}")
        
        target = elements[min(index, len(elements) - 1)]
        WebDriverWait(self.driver, timeout_ms/1000).until(EC.element_to_be_clickable(target))
        target.click()
        self._wait_for_load(timeout_ms)
        return self._snapshot()

    def type(self, selector: str, value: str, timeout_ms: int = 10000, index: int = 0) -> DOMSnapshot:
        """Type into element."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
        if not elements:
            raise ElementNotFoundError(f"Element not found: {selector}")
        
        target = elements[min(index, len(elements) - 1)]
        WebDriverWait(self.driver, timeout_ms/1000).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
        target.clear()
        target.send_keys(value)
        return self._snapshot()

    def scroll(self, direction: str = "down", timeout_ms: int = 5000) -> DOMSnapshot:
        """Scroll page."""
        scroll_amount = 500 if direction == "down" else -500
        self.driver.execute_script(f"window.scrollBy(0, {scroll_amount})")
        import time
        time.sleep(0.5)
        return self._snapshot()

    def wait(self, timeout_ms: int = 2000) -> DOMSnapshot:
        """Wait for specified time."""
        import time
        time.sleep(timeout_ms / 1000)
        return self._snapshot()

    def screenshot(self) -> Tuple[str, DOMSnapshot]:
        """Take screenshot."""
        import base64
        screenshot_bytes = self.driver.get_screenshot_as_png()
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
        snapshot = self._snapshot()
        return screenshot_b64, snapshot

    def evaluate(self, js_code: str) -> Any:
        """Execute JavaScript."""
        return self.driver.execute_script(js_code)

    def select_option(self, selector: str, value: str, timeout_ms: int = 10000) -> DOMSnapshot:
        """Select option in dropdown."""
        from selenium.webdriver.support.ui import Select
        from selenium.webdriver.common.by import By
        
        element = self.driver.find_element(By.CSS_SELECTOR, selector)
        select = Select(element)
        select.select_by_value(value)
        self._wait_for_load(timeout_ms)
        return self._snapshot()

    def hover(self, selector: str, timeout_ms: int = 10000) -> DOMSnapshot:
        """Hover over element."""
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.common.by import By
        
        element = self.driver.find_element(By.CSS_SELECTOR, selector)
        ActionChains(self.driver).move_to_element(element).perform()
        return self._snapshot()

    def submit(self, selector: str = "form", timeout_ms: int = 10000) -> DOMSnapshot:
        """Submit a form."""
        from selenium.webdriver.common.by import By
        
        form = self.driver.find_element(By.CSS_SELECTOR, selector)
        form.submit()
        self._wait_for_load(timeout_ms)
        return self._snapshot()

    def _wait_for_load(self, timeout_ms: int):
        """Wait for page load."""
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        try:
            WebDriverWait(self.driver, timeout_ms/1000).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except:
            pass

    def _snapshot(self) -> DOMSnapshot:
        """Capture current DOM snapshot."""
        if not self.driver:
            raise RuntimeError("Browser not initialized")
        
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.action_chains import ActionChains
        
        url = self.driver.current_url
        title = self.driver.title
        
        elements = []
        try:
            interactables = self.driver.find_elements(By.CSS_SELECTOR, "a, button, input, select, textarea, [onclick], [role='button']")
            for el in interactables:
                try:
                    rect = el.rect
                    visible = rect['width'] > 0 and rect['height'] > 0
                    elements.append(ElementInfo(
                        tag=el.tag_name.lower(),
                        text=el.text.strip()[:200] if el.text else None,
                        href=el.get_attribute("href"),
                        src=el.get_attribute("src"),
                        rect=rect,
                        visible=visible,
                        enabled=not el.get_attribute("disabled"),
                        value=el.get_attribute("value"),
                        placeholder=el.get_attribute("placeholder"),
                        attributes={}
                    ))
                except:
                    pass
        except Exception as ex:
            logger.warning(f"Failed to get elements: {ex}")

        return DOMSnapshot(
            url=url,
            title=title,
            elements=elements
        )


class RequestsBackend:
    """Fallback backend using requests + BeautifulSoup."""

    def __init__(self):
        self.session = None
        self.current_url = ""
        self.current_html = ""
        self._initialized = False

    def initialize(self):
        """Initialize requests session."""
        import requests
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        })
        self._initialized = True
        logger.info("Requests backend initialized")

    def close(self):
        """Close session."""
        if self.session:
            self.session.close()
        self._initialized = False

    def goto(self, url: str, timeout_ms: int = 30000) -> DOMSnapshot:
        """Navigate to URL."""
        if not self.session:
            raise RuntimeError("Backend not initialized")
        
        response = self.session.get(url, timeout=timeout_ms/1000)
        response.raise_for_status()
        self.current_url = response.url
        self.current_html = response.text
        return self._snapshot()

    def _snapshot(self) -> DOMSnapshot:
        """Capture current DOM snapshot."""
        if not self.current_html:
            return DOMSnapshot(url=self.current_url, title="", elements=[])
        
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(self.current_html, "html.parser")
        title = soup.title.string if soup.title else ""
        
        elements = []
        for el in soup.find_all(["a", "button", "input", "select", "textarea"]):
            elements.append(ElementInfo(
                tag=el.name,
                text=el.get_text(strip=True)[:200] or None,
                href=el.get("href"),
                src=el.get("src"),
                value=el.get("value"),
                placeholder=el.get("placeholder"),
                visible=True,  # Can't determine in requests mode
                enabled=True
            ))
        
        return DOMSnapshot(
            url=self.current_url,
            title=title,
            elements=elements,
            html=self.current_html[:10000]  # Limit HTML size
        )

    # Note: click, type, scroll, etc. are limited in requests mode
    # These would require JavaScript execution which isn't possible


class ElementNotFoundError(Exception):
    """Raised when an element is not found in the DOM."""
    pass


class BrowserError(Exception):
    """General browser automation error."""
    def __init__(self, message: str, error_class: ErrorClass = ErrorClass.UNKNOWN):
        super().__init__(message)
        self.error_class = error_class


# ---------------------------------------------------------------------------
# Main BrowserPlane Class
# ---------------------------------------------------------------------------

class BrowserPlane:
    """
    DOM-aware browser automation with visual verification.
    
    Features:
    - Multi-backend support (Playwright, Selenium, Requests fallback)
    - DOM-to-goal planning from natural language
    - Action retry taxonomy with recovery strategies
    - State verification and fingerprinting
    """

    def __init__(
        self,
        backend: Optional[str] = None,
        headless: bool = True,
        viewport: Tuple[int, int] = (1280, 720)
    ):
        """
        Initialize BrowserPlane.
        
        Args:
            backend: Backend to use ("playwright", "selenium", "requests", or "auto")
            headless: Run browser in headless mode
            viewport: Browser viewport size
        """
        self.headless = headless
        self.viewport = viewport
        self._backend = None
        self._backend_type = None
        self._planner = DOMToGoalPlanner()
        self._session_id = str(uuid.uuid4())[:8]
        
        # Determine backend
        if backend == "auto" or backend is None:
            backend = self._detect_backend()
        
        self._set_backend(backend)
        
        logger.info(f"BrowserPlane initialized with {self._backend_type.value} backend")

    def _detect_backend(self) -> str:
        """Detect best available backend."""
        try:
            import playwright
            return "playwright"
        except ImportError:
            pass
        
        try:
            from selenium import webdriver
            return "selenium"
        except ImportError:
            pass
        
        return "requests"

    def _set_backend(self, backend: str):
        """Set the browser backend."""
        if backend == "playwright":
            self._backend_type = BrowserBackend.PLAYWRIGHT
            self._backend = PlaywrightBackend(headless=self.headless)
        elif backend == "selenium":
            self._backend_type = BrowserBackend.SELENIUM
            self._backend = SeleniumBackend(headless=self.headless)
        else:
            self._backend_type = BrowserBackend.REQUESTS
            self._backend = RequestsBackend()

    async def initialize_async(self):
        """Async initialization for async backends."""
        if hasattr(self._backend, 'initialize'):
            if asyncio.iscoroutinefunction(self._backend.initialize):
                await self._backend.initialize()
            else:
                self._backend.initialize()

    def initialize(self):
        """Initialize the browser backend."""
        if not hasattr(self._backend, 'initialize'):
            return
        if asyncio.iscoroutinefunction(self._backend.initialize):
            # Should use initialize_async instead
            raise RuntimeError("Use initialize_async() for async backends")
        self._backend.initialize()

    def close(self):
        """Close the browser and cleanup."""
        if hasattr(self._backend, 'close'):
            if asyncio.iscoroutinefunction(self._backend.close):
                # Can't await here, but shouldn't be called in async context anyway
                pass
            else:
                self._backend.close()
        logger.info(f"BrowserPlane closed (session: {self._session_id})")

    # -------------------------------------------------------------------------
    # Core Methods
    # -------------------------------------------------------------------------

    def execute_plan(
        self,
        high_level_instruction: str,
        target_url: Optional[str] = None,
        max_retries: int = 3
    ) -> BrowserResult:
        """
        Execute a high-level instruction as a sequence of browser actions.
        
        Args:
            high_level_instruction: Natural language instruction
            target_url: Starting URL (if navigation needed)
            max_retries: Maximum retry attempts per action
        
        Returns:
            BrowserResult with execution details
        """
        actions = self._planner.plan(high_level_instruction)
        
        if not actions:
            return BrowserResult(
                success=False,
                actions_executed=[],
                final_url="",
                final_title="",
                error="Could not parse instruction into actions"
            )

        # Prepend goto if URL provided
        if target_url:
            actions.insert(0, BrowserAction(type=ActionType.GOTO, target=target_url))
        
        return self._execute_actions(actions, max_retries)

    def _execute_actions(
        self,
        actions: List[BrowserAction],
        max_retries: int = 3
    ) -> BrowserResult:
        """Execute a list of actions with retry logic."""
        executed = []
        screenshots = []
        dom_snapshots = []
        final_url = ""
        final_title = ""
        
        for action in actions:
            retry_count = 0
            current_dom = dom_snapshots[-1] if dom_snapshots else None
            
            while retry_count <= max_retries:
                try:
                    result_dom = self._execute_single_action(action)
                    dom_snapshots.append(result_dom)
                    final_url = result_dom.url
                    final_title = result_dom.title
                    executed.append(action)
                    
                    # Take screenshot if requested or on error
                    if action.type == ActionType.SCREENSHOT or action.type == ActionType.WAIT:
                        try:
                            if hasattr(self._backend, 'screenshot'):
                                ss_method = self._backend.screenshot
                                if asyncio.iscoroutinefunction(ss_method):
                                    ss, _ = asyncio.run(ss_method())
                                else:
                                    ss, _ = ss_method()
                                screenshots.append(ss)
                        except:
                            pass
                    
                    break  # Success, move to next action
                    
                except Exception as ex:
                    error_class = self._classify_error(ex)
                    logger.warning(f"Action {action.type} failed: {ex} (class: {error_class})")
                    
                    if retry_count >= max_retries:
                        return BrowserResult(
                            success=False,
                            actions_executed=executed,
                            final_url=final_url,
                            final_title=final_title,
                            screenshots=screenshots,
                            error=str(ex),
                            error_class=error_class,
                            failed_action=action,
                            dom_snapshots=dom_snapshots
                        )
                    
                    # Get recovery action
                    recovery = ErrorRecovery.recover(error_class, {
                        "action": action,
                        "error": str(ex),
                        "target": action.target
                    })
                    
                    # Execute recovery
                    try:
                        recovery_dom = self._execute_single_action(recovery)
                        dom_snapshots.append(recovery_dom)
                    except:
                        pass
                    
                    retry_count += 1

        return BrowserResult(
            success=True,
            actions_executed=executed,
            final_url=final_url,
            final_title=final_title,
            screenshots=screenshots,
            dom_snapshots=dom_snapshots
        )

    def _execute_single_action(self, action: BrowserAction) -> DOMSnapshot:
        """Execute a single action and return the resulting DOM snapshot."""
        if not hasattr(self._backend, '_initialized'):
            pass
        elif not self._backend._initialized:
            # Handle both sync and async initialize
            if asyncio.iscoroutinefunction(getattr(self._backend.initialize, '__func__', None)) or \
               asyncio.iscoroutinefunction(self._backend.initialize):
                asyncio.run(self._backend.initialize())
            else:
                self._backend.initialize()
        
        backend = self._backend
        timeout = action.timeout_ms
        
        # Handle async backends (Playwright) with asyncio.run()
        def _call_async(method, *args):
            if asyncio.iscoroutinefunction(method):
                return asyncio.run(method(*args))
            return method(*args)
        
        if action.type == ActionType.GOTO:
            return _call_async(backend.goto, action.target, timeout)
        
        elif action.type == ActionType.CLICK:
            return _call_async(backend.click, action.target, timeout, action.index)
        
        elif action.type == ActionType.TYPE:
            return _call_async(backend.type, action.target, action.value or "", timeout, action.index)
        
        elif action.type == ActionType.SCROLL:
            return _call_async(backend.scroll, action.target, timeout)
        
        elif action.type == ActionType.WAIT:
            return _call_async(backend.wait, timeout)
        
        elif action.type == ActionType.SCREENSHOT:
            if hasattr(backend, 'screenshot'):
                ss, snap = backend.screenshot()
                return snap
            return self._get_current_snapshot()
        
        elif action.type == ActionType.EVALUATE:
            return _call_async(backend.evaluate, action.target)
        
        elif action.type == ActionType.SELECT:
            return _call_async(backend.select_option, action.target, action.value or "", timeout)
        
        elif action.type == ActionType.HOVER:
            return _call_async(backend.hover, action.target, timeout)
        
        elif action.type == ActionType.SUBMIT:
            return _call_async(backend.submit, action.target, timeout)
        
        else:
            raise BrowserError(f"Unsupported action type: {action.type}")

    def _get_current_snapshot(self) -> DOMSnapshot:
        """Get snapshot from current backend state."""
        if hasattr(self._backend, '_snapshot'):
            method = self._backend._snapshot
            if asyncio.iscoroutinefunction(method):
                return asyncio.run(method())
            return method()
        return DOMSnapshot(url="", title="", elements=[])

    def dom_snapshot(self) -> DOMSnapshot:
        """Get current DOM snapshot."""
        method = self._get_current_snapshot
        if asyncio.iscoroutinefunction(method):
            return asyncio.run(method())
        return method()

    def verify_state_change(
        self,
        before: DOMSnapshot,
        action: BrowserAction,
        after: DOMSnapshot
    ) -> VerificationResult:
        """
        Verify that a state change occurred as expected after an action.
        
        Args:
            before: DOM snapshot before action
            action: The action that was executed
            after: DOM snapshot after action
        
        Returns:
            VerificationResult with change details
        """
        changes = []
        
        # URL change
        if before.url != after.url:
            changes.append(f"URL changed: {before.url} -> {after.url}")
        
        # Title change
        if before.title != after.title:
            changes.append(f"Title changed: {before.title} -> {after.title}")
        
        # Element count change
        if len(before.elements) != len(after.elements):
            changes.append(f"Element count: {len(before.elements)} -> {len(after.elements)}")
        
        # Element visibility change (for click/hover)
        if action.type in (ActionType.CLICK, ActionType.HOVER):
            target_text = action.target
            for elem in after.elements:
                if elem.text and target_text.lower() in elem.text.lower():
                    if not elem.visible:
                        changes.append(f"Element '{elem.text}' became hidden")
        
        # Check for new/removed elements
        before_hrefs = {e.href for e in before.elements if e.href}
        after_hrefs = {e.href for e in after.elements if e.href}
        new_links = after_hrefs - before_hrefs
        removed_links = before_hrefs - after_hrefs
        
        if new_links:
            changes.append(f"New links appeared: {len(new_links)}")
        if removed_links:
            changes.append(f"Links removed: {len(removed_links)}")
        
        success = len(changes) > 0
        
        return VerificationResult(
            success=success,
            message="State change verified" if success else "No state change detected",
            before=before,
            after=after,
            changes_detected=changes
        )

    def page_state_fingerprint(self, dom_snapshot: DOMSnapshot) -> str:
        """
        Generate a hash of key elements for stale detection.
        
        Args:
            dom_snapshot: DOM snapshot to fingerprint
        
        Returns:
            SHA256 hash string
        """
        key_parts = [
            dom_snapshot.url,
            dom_snapshot.title,
            str(len(dom_snapshot.elements)),
            str(len(dom_snapshot.forms))
        ]
        
        # Add first few element texts/hrefs for content fingerprint
        for elem in dom_snapshot.elements[:10]:
            if elem.href:
                key_parts.append(elem.href[:50])
            if elem.text:
                key_parts.append(elem.text[:30])
        
        fingerprint = "|".join(key_parts)
        return hashlib.sha256(fingerprint.encode()).hexdigest()[:16]

    def recover_from_error(
        self,
        action: BrowserAction,
        error_class: ErrorClass
    ) -> BrowserResult:
        """
        Attempt to recover from an error and retry the action.
        
        Args:
            action: The action that failed
            error_class: Classification of the error
        
        Returns:
            BrowserResult from recovery attempt
        """
        recovery_action = ErrorRecovery.recover(error_class, {
            "action": action,
            "target": action.target
        })
        
        try:
            result_dom = self._execute_single_action(recovery_action)
            
            # Retry original action once
            retry_dom = self._execute_single_action(action)
            
            return BrowserResult(
                success=True,
                actions_executed=[recovery_action, action],
                final_url=retry_dom.url,
                final_title=retry_dom.title,
                error=None
            )
        except Exception as ex:
            return BrowserResult(
                success=False,
                actions_executed=[recovery_action],
                final_url="",
                final_title="",
                error=str(ex),
                error_class=error_class,
                failed_action=action
            )

    def _classify_error(self, error: Exception) -> ErrorClass:
        """Classify an error into an ErrorClass."""
        error_msg = str(error).lower()
        
        if "not found" in error_msg or "no such element" in error_msg:
            return ErrorClass.STALE_REF if "stale" in error_msg else ErrorClass.PAGE_NOT_LOADED
        if "modal" in error_msg or "dialog" in error_msg or "overlay" in error_msg:
            return ErrorClass.MODAL_OBSTRUCTION
        if "auth" in error_msg or "login" in error_msg or "redirect" in error_msg:
            return ErrorClass.AUTH_REDIRECT
        if "hidden" in error_msg or "not visible" in error_msg:
            return ErrorClass.HIDDEN_ELEMENT
        if "timeout" in error_msg:
            return ErrorClass.TIMEOUT
        if "navigation" in error_msg or "load" in error_msg:
            return ErrorClass.NAVIGATION
        
        return ErrorClass.UNKNOWN

    # -------------------------------------------------------------------------
    # Convenience Methods
    # -------------------------------------------------------------------------

    def get_element_by_text(self, text: str, tag: str = "*") -> Optional[str]:
        """Find element CSS selector by text content."""
        dom = self._get_current_snapshot()
        for elem in dom.elements:
            if elem.text and text.lower() in elem.text.lower():
                if tag == "*" or elem.tag == tag.lower():
                    return elem.text
        return None

    def get_form_inputs(self, form_index: int = 0) -> List[ElementInfo]:
        """Get inputs from a form by index."""
        dom = self._get_current_snapshot()
        if form_index < len(dom.forms):
            return dom.forms[form_index].inputs
        return []

    def fill_form(self, data: Dict[str, str]) -> BrowserResult:
        """Fill form inputs with data dict {name: value}."""
        actions = []
        for name, value in data.items():
            actions.append(BrowserAction(
                type=ActionType.TYPE,
                target=f"[name='{name}']",
                value=value
            ))
        return self._execute_actions(actions)


# ---------------------------------------------------------------------------
# Sync Wrapper for Sync Usage
# ---------------------------------------------------------------------------

class SyncBrowserPlane:
    """Synchronous wrapper around BrowserPlane."""

    def __init__(self, *args, **kwargs):
        self._async_plane = BrowserPlane(*args, **kwargs)

    def __enter__(self):
        self._async_plane.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._async_plane.close()

    def execute_plan(self, instruction: str, url: Optional[str] = None) -> BrowserResult:
        """Execute plan synchronously."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self._async_plane.execute_plan_async(instruction, url)
        )


# ---------------------------------------------------------------------------
# Example Usage
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Example usage
    plane = BrowserPlane(backend="auto", headless=True)
    
    try:
        plane.initialize()
        
        # Execute a plan
        result = plane.execute_plan(
            "click the 'Sign In' button",
            target_url="https://example.com"
        )
        
        print(f"Success: {result.success}")
        print(f"Actions executed: {len(result.actions_executed)}")
        print(f"Final URL: {result.final_url}")
        
        if result.error:
            print(f"Error: {result.error} ({result.error_class})")
        
    finally:
        plane.close()
