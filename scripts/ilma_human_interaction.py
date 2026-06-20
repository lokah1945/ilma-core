#!/usr/bin/env python3
"""
ILMA HumanInteractionAdapter v1.0 — Phase 69
=============================================
Human-like interaction layer for Playwright browser automation.

Purpose: Make browser interactions more stable and natural by simulating
real human behavior — hover states, mouse movements, scroll patterns,
character-by-character typing, and realistic timing.

SECURITY POLICY — NEVER use for:
  - Bypassing CAPTCHA
  - Circumventing rate limits
  - Access controls or fraud detection
  - Any unauthorized access

ALLOWED uses:
  - UI stability (hover states, lazy loading, deferred rendering)
  - Accessibility behavior (menus, tooltips, modals)
  - Scroll-to-load content (infinite scroll, pagination)
  - Form interactions with complex validation
  - Robust workflow execution on complex SPAs

Usage:
    from ilma_human_interaction import HumanInteractionAdapter

    adapter = HumanInteractionAdapter(page)
    await adapter.human_click(locator)
    await adapter.human_type(locator, "hello world")
    await adapter.human_scroll("down")
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field

import logging

logger = logging.getLogger("human-browser")


# ─── Config ──────────────────────────────────────────────────────────────────

@dataclass
class HumanInteractionConfig:
    hover_before_click: bool = True
    scroll_into_view_before_click: bool = True
    move_mouse_before_click: bool = True
    click_offset_jitter: bool = True
    min_delay_ms: int = 120
    max_delay_ms: int = 550
    mouse_steps_min: int = 12
    mouse_steps_max: int = 36
    type_char_delay_ms_min: int = 35
    type_char_delay_ms_max: int = 180
    scroll_chunk_min: int = 3
    scroll_chunk_max: int = 8


# ─── Adapter ─────────────────────────────────────────────────────────────────

class HumanInteractionAdapter:
    """
    Wraps a Playwright page with human-like interaction patterns.

    All methods are async. Initialize with a Playwright page instance.

    Example:
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        browser = await pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
        page = await browser.new_page()

        adapter = HumanInteractionAdapter(page, config=HumanInteractionConfig())
        await adapter.human_click(page.locator("#submit-btn"))
        await adapter.human_type(page.locator("#search-box"), "query here")
    """

    def __init__(
        self,
        page,
        config: HumanInteractionConfig | None = None,
    ):
        self.page = page
        self.config = config or HumanInteractionConfig()
        self._last_mouse: tuple[float, float] | None = None
        self._action_log: list[str] = []

    def _log(self, action: str) -> None:
        """Log human-browser action."""
        self._action_log.append(action)
        logger.info(f"[human-browser] {action}")

    def _sleep_ms(self, low: int | None = None, high: int | None = None) -> None:
        """Sleep for a random duration in milliseconds."""
        low_val = low if low is not None else self.config.min_delay_ms
        high_val = high if high is not None else self.config.max_delay_ms
        time.sleep(random.randint(low_val, high_val) / 1000)

    async def _bbox_center(
        self, locator
    ) -> tuple[float, float, dict]:
        """Get bounding box center with optional jitter."""
        box = await locator.bounding_box()
        if not box:
            raise RuntimeError("Element has no bounding box")

        x = box["x"] + box["width"] / 2
        y = box["y"] + box["height"] / 2

        if self.config.click_offset_jitter:
            jitter_x = min(box["width"] * 0.18, 8)
            jitter_y = min(box["height"] * 0.18, 8)
            x += random.uniform(-jitter_x, jitter_x)
            y += random.uniform(-jitter_y, jitter_y)

        return x, y, box

    # ─── Scroll ──────────────────────────────────────────────────────────────

    async def human_scroll_into_view(self, locator) -> None:
        """Scroll element into view with smooth behavior."""
        self._log("scroll_into_view")
        await locator.evaluate(
            """el => el.scrollIntoView({
                behavior: 'smooth',
                block: 'center',
                inline: 'center'
            })"""
        )
        self._sleep_ms(220, 700)

    async def human_scroll(
        self,
        direction: str = "down",
        amount: int | None = None,
    ) -> None:
        """
        Scroll in chunks with natural movement.

        Args:
            direction: 'down' or 'up'
            amount: total scroll pixels (random if None)
        """
        self._log(f"scroll_{direction}")
        amount = amount or random.randint(420, 980)
        if direction == "up":
            amount = -abs(amount)
        else:
            amount = abs(amount)

        chunks = random.randint(
            self.config.scroll_chunk_min,
            self.config.scroll_chunk_max,
        )
        for _ in range(chunks):
            delta = amount / chunks + random.uniform(-35, 35)
            await self.page.mouse.wheel(0, delta)
            self._sleep_ms(70, 240)

    # ─── Mouse Movement ───────────────────────────────────────────────────────

    async def human_mouse_move(
        self,
        x: float,
        y: float,
    ) -> None:
        """
        Move mouse along a Bezier-like curved path.
        Starts from last known position (or random viewport origin).
        """
        self._log("mouse_move")

        steps = random.randint(
            self.config.mouse_steps_min,
            self.config.mouse_steps_max,
        )

        if self._last_mouse is None:
            viewport = self.page.viewport_size or {"width": 1280, "height": 720}
            start_x = random.randint(20, max(30, viewport["width"] - 20))
            start_y = random.randint(20, max(30, viewport["height"] - 20))
        else:
            start_x, start_y = self._last_mouse

        # Control point for Bezier curve with random offset
        cp_x = (start_x + x) / 2 + random.uniform(-90, 90)
        cp_y = (start_y + y) / 2 + random.uniform(-60, 60)

        for i in range(1, steps + 1):
            t = i / steps
            # Quadratic bezier easing
            eased = 0.5 - math.cos(t * math.pi) / 2

            px = (1 - eased) ** 2 * start_x + 2 * (1 - eased) * eased * cp_x + eased ** 2 * x
            py = (1 - eased) ** 2 * start_y + 2 * (1 - eased) * eased * cp_y + eased ** 2 * y

            await self.page.mouse.move(px, py)
            await self.page.wait_for_timeout(random.randint(5, 22))

        self._last_mouse = (x, y)

    # ─── Hover ────────────────────────────────────────────────────────────────

    async def human_hover(self, locator) -> None:
        """Hover over element with natural mouse movement."""
        self._log("hover")
        x, y, _ = await self._bbox_center(locator)
        await self.human_mouse_move(x, y)
        await locator.hover()
        self._sleep_ms(160, 650)

    # ─── Click ────────────────────────────────────────────────────────────────

    async def human_click(self, locator) -> None:
        """
        Human-like click: scroll → move → hover → click with realistic timing.
        """
        self._log("click")
        await locator.wait_for(state="visible", timeout=15000)

        if self.config.scroll_into_view_before_click:
            await self.human_scroll_into_view(locator)

        x, y, _ = await self._bbox_center(locator)

        if self.config.move_mouse_before_click:
            await self.human_mouse_move(x, y)

        if self.config.hover_before_click:
            await locator.hover()
            self._sleep_ms(120, 500)

        await self.page.mouse.down()
        self._sleep_ms(45, 145)
        await self.page.mouse.up()

        self._sleep_ms()

    # ─── Type ─────────────────────────────────────────────────────────────────

    async def human_type(
        self,
        locator,
        text: str,
        clear_first: bool = True,
    ) -> None:
        """
        Type text character-by-character with random delays.
        """
        self._log(f"type ({len(text)} chars)")
        await locator.wait_for(state="visible", timeout=15000)
        await self.human_scroll_into_view(locator)
        await self.human_hover(locator)
        await locator.click()

        if clear_first:
            # Select all and clear
            await self.page.keyboard.press("Control+a")
            await self.page.keyboard.press("Backspace")
            self._sleep_ms(50, 150)

        for ch in text:
            await self.page.keyboard.type(ch)
            self._sleep_ms(
                self.config.type_char_delay_ms_min,
                self.config.type_char_delay_ms_max,
            )

        self._sleep_ms(120, 400)

    # ─── Double Click ─────────────────────────────────────────────────────────

    async def human_double_click(self, locator) -> None:
        """Human-like double click."""
        self._log("double_click")
        await locator.wait_for(state="visible", timeout=15000)

        if self.config.scroll_into_view_before_click:
            await self.human_scroll_into_view(locator)

        x, y, _ = await self._bbox_center(locator)

        if self.config.move_mouse_before_click:
            await self.human_mouse_move(x, y)
            await locator.hover()
            self._sleep_ms(120, 500)

        await self.page.mouse.dblclick(x, y)
        self._sleep_ms()

    # ─── Right Click ──────────────────────────────────────────────────────────

    async def human_right_click(self, locator) -> None:
        """Human-like right-click (context menu)."""
        self._log("right_click")
        await locator.wait_for(state="visible", timeout=15000)

        if self.config.scroll_into_view_before_click:
            await self.human_scroll_into_view(locator)

        x, y, _ = await self._bbox_center(locator)

        if self.config.move_mouse_before_click:
            await self.human_mouse_move(x, y)
            await locator.hover()
            self._sleep_ms(120, 500)

        await self.page.mouse.click(x, y, button="right")
        self._sleep_ms()

    # ─── Utility ──────────────────────────────────────────────────────────────

    def get_action_log(self) -> list[str]:
        """Return the list of actions performed."""
        return list(self._action_log)

    def clear_action_log(self) -> None:
        """Clear the action log."""
        self._action_log.clear()

    async def reset_mouse_position(self) -> None:
        """Reset mouse to a random position (e.g., after a modal closes)."""
        viewport = self.page.viewport_size or {"width": 1280, "height": 720}
        x = random.randint(10, max(20, viewport["width"] - 20))
        y = random.randint(10, max(20, viewport["height"] - 20))
        await self.page.mouse.move(x, y)
        self._last_mouse = None