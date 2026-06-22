#!/usr/bin/env python3
"""
ILMA Browser Tool Adapter v1.0 — Phase 69D
===========================================
ILMA-native browser tool adapter that owns snapshot + ref_map + CDP interactions.
COMPLETELY INDEPENDENT from agent-browser CLI.

This adapter provides ILMA with its own browser tool layer:
1. CDP-native snapshot generation via Accessibility.getFullAXTree
2. ILMA-owned ref_map (@e1, @e2, ...) with backendNodeId/objectId
3. CDP-direct click/type/scroll via HumanInteractionAdapter
4. Single source of truth: same ref_map used for snapshot AND interaction

Why Jalur A (not Jalur B):
  - agent-browser owns ariaSnapshot output and @e ref assignment
  - ILMA cannot reliably read agent-browser's private ref mapping
  - Without owned ref_map, CDP resolve of @e5 is guessing, not knowing
  - Therefore: ILMA MUST generate its own snapshot with its own ref_map

Architecture:
  ILMA calls ilma_browser_tool_adapter methods
    -> CDP Accessibility.getFullAXTree (ILMA-generated snapshot)
    -> ILMA assigns @e refs to each node
    -> ILMA stores backendNodeId/objectId in ref_map
    -> Returns formatted snapshot with @e refs
  ILMA calls browser_click("@e5")
    -> Lookup ref_map["@e5"] -> backendNodeId + metadata
    -> HumanInteractionAdapter.human_click with resolved node
    -> CDP Input.dispatchMouseEvent (mousePressed/mouseReleased)
    -> NEVER calls agent-browser

Usage:
    from ilma_browser_tool_adapter import ILMABrowserToolAdapter
    
    adapter = ILMABrowserToolAdapter(cdp_session)  # Playwright CDP session
    snapshot = await adapter.snapshot()  # Returns {"text": "...", "ref_map": {...}}
    await adapter.click("@e5")  # Uses ref_map, CDP-direct
    await adapter.type("@e3", "query")  # Uses ref_map, CDP-direct

Integration with ilma_browser_engine.py:
    engine = BrowserEngine()
    await engine.initialize()
    adapter = ILMABrowserToolAdapter.from_engine(engine)
    snapshot = await adapter.snapshot()
    await adapter.click("@e2")
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("human-browser")


# ============================================================================
# Ref Map Entry
# ============================================================================

@dataclass
class RefEntry:
    """Single entry in the ILMA ref_map."""
    ref: str                    # "@e1", "@e2", etc.
    node_id: int                # DOM nodeId
    backend_node_id: int        # CDP backendNodeId
    role: str                   # accessibility role
    name: str                   # accessibility name
    description: str            # accessibility description
    bounding_box: Optional[Dict[str, float]] = None  # x, y, width, height
    visible: bool = True
    enabled: bool = True
    focused: bool = False
    checked: bool = False
    pressed: bool = False
    value: Optional[str] = None
    href: Optional[str] = None
    tag: Optional[str] = None
    # CDP-specific handles for interaction
    object_id: Optional[str] = None  # CDP Runtime.RemoteObject objectId
    backend_id: Optional[int] = None  # Accessibility agentId
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ref": self.ref,
            "node_id": self.node_id,
            "backend_node_id": self.backend_node_id,
            "role": self.role,
            "name": self.name,
            "description": self.description,
            "bounding_box": self.bounding_box,
            "visible": self.visible,
            "enabled": self.enabled,
            "focused": self.focused,
            "checked": self.checked,
            "pressed": self.pressed,
            "value": self.value,
            "href": self.href,
            "tag": self.tag,
        }


# ============================================================================
# Snapshot Result
# ============================================================================

@dataclass
class SnapshotResult:
    """Result from ILMA snapshot generation."""
    text: str                  # Formatted accessibility tree with @e refs
    ref_map: Dict[str, RefEntry]  # @eN -> RefEntry
    raw_tree: List[Dict]       # Raw CDP Accessibility.getFullAXTree response
    page_title: str
    page_url: str
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "ref_map": {k: v.to_dict() for k, v in self.ref_map.items()},
            "raw_tree_size": len(self.raw_tree),
            "page_title": self.page_title,
            "page_url": self.page_url,
            "timestamp": self.timestamp,
            "ref_count": len(self.ref_map),
        }


# ============================================================================
# ILMA Browser Tool Adapter
# ============================================================================

# ─── JavaScript for Hybrid Snapshot Discovery ────────────────────────────────
# Phase 69D: Use JS for element discovery (100% reliable in daemon mode),
# CDP for interaction targeting (backendNodeId, objectId).
# Accessibility.getFullAXTree returns role=unknown in daemon mode — JS is the fix.
_SNAPSHOT_JS = """
(function(options) {
  var full = options.full;
  var elements = [];
  var seen = new Set();

  // Selector for all interactive element types
  var selectors = [
    'a[href]', 'button', 'input', 'select', 'textarea',
    '[onclick]', '[onmouseover]', '[onfocus]', '[role="button"]',
    '[role="link"]', '[role="menuitem"]', '[role="tab"]',
    '[role="checkbox"]', '[role="radio"]', '[role="textbox"]',
    '[contenteditable="true"]', '[draggable="true"]'
  ];

  try {
    var allEls = document.querySelectorAll(selectors.join(','));

    for (var i = 0; i < allEls.length; i++) {
      var el = allEls[i];
      var tag = el.tagName.toLowerCase();

      // Skip invisible or hidden elements
      var style = window.getComputedStyle(el);
      if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
        continue;
      }

      // Get bounding rect
      var rect = el.getBoundingClientRect();
      if (rect.width < 4 || rect.height < 4) continue;

      // Get text content (trimmed)
      var text = (el.textContent || el.innerText || '').trim().substring(0, 200);

      // Skip elements with no meaningful text and no attributes
      if (!text && !el.href && !el.placeholder && !el.name && !el.id) {
        continue;
      }

      // Get href for links
      var href = null;
      if (tag === 'a') {
        href = el.href;
      }

      // Get role
      var role = el.getAttribute('role') || '';

      // Map tag to default role
      if (!role) {
        if (tag === 'a') role = 'link';
        else if (tag === 'button') role = 'button';
        else if (tag === 'input') {
          var type = (el.type || 'text').toLowerCase();
          if (type === 'checkbox') role = 'checkbox';
          else if (type === 'radio') role = 'radio';
          else if (type === 'submit' || type === 'button') role = 'button';
          else role = 'textbox';
        }
        else if (tag === 'select') role = 'combobox';
        else if (tag === 'textarea') role = 'textbox';
        else if (el.isContentEditable) role = 'textbox';
      }

      // Check disabled/focused/checked states
      var disabled = el.disabled || el.getAttribute('aria-disabled') === 'true';
      var focused = (document.activeElement === el);
      var checked = null;
      if (el.type === 'checkbox') checked = el.checked;
      if (el.type === 'radio') checked = el.checked;

      // Build element object
      var obj = {
        tag: tag,
        role: role || 'unknown',
        text: text,
        placeholder: el.placeholder || '',
        href: href,
        x: Math.round(rect.left),
        y: Math.round(rect.top),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        visible: rect.width > 0 && rect.height > 0,
        disabled: disabled,
        focused: focused,
        checked: checked,
        name: el.name || '',
        description: el.title || el.getAttribute('aria-label') || '',
        value: (el.value !== undefined && el.value !== null) ? String(el.value) : null,
        has_backend_node: false,
        backend_node_id: 0,
        node_id: 0
      };

      elements.push(obj);
    }
  } catch(e) {
    // Fallback: return empty
  }

  // Limit to 50 most relevant elements
  if (elements.length > 50) {
    elements = elements.slice(0, 50);
  }

  return { elements: elements, count: elements.length };
})
"""


class ILMABrowserToolAdapter:
    """
    ILMA-native browser tool adapter.
    
    Owns snapshot generation, ref_map, and all interactions.
    Completely independent from agent-browser CLI.
    
    Usage:
        adapter = ILMABrowserToolAdapter(cdp_session)  # Playwright CDP session
        
        # Snapshot: ILMA generates its own accessibility tree + ref_map
        snapshot = await adapter.snapshot()
        print(snapshot.text)  # Formatted tree with @e1, @e2, ...
        snapshot.ref_map["@e5"].backend_node_id  # CDP backendNodeId
        
        # Interactions: use owned ref_map for CDP-resolved click/type
        await adapter.click("@e5")
        await adapter.type("@e3", "search query")
        await adapter.scroll("down")
        
        # CDP command passthrough for advanced use
        result = await adapter.cdp_send("DOM.getDocument")
    """
    
    # Static counter for unique ref IDs per adapter instance
    _ref_counter: int = 0
    _ref_counter_lock = asyncio.Lock()
    
    # Accessibility roles that are interactive
    INTERACTIVE_ROLES = {
        "button", "link", "textbox", "searchbox", "checkbox", "radioButton",
        "menuitem", "tab", "tabpanel", "switch", "slider", "spinbutton",
        "combobox", "listbox", "tree", "treeitem", "menu", "menuitemcheckbox",
        "menuitemradio", "option", "progressbar", "scrollbar", "separator",
        "text",  # editable text areas
    }
    
    def __init__(
        self,
        cdp_controller,
        page,
        task_id: str = "default",
        human_adapter=None,
    ):
        """
        Initialize adapter with CDP controller and page.
        
        Args:
            cdp_controller: CDPController instance from BrowserEngine
            page: Playwright page object
            task_id: Task identifier for session isolation
            human_adapter: Optional HumanInteractionAdapter for human-like interactions
        """
        self._cdp = cdp_controller  # CDPController instance
        self._page = page
        self._task_id = task_id
        self._human_adapter = human_adapter
        
        # ILMA-owned ref_map: @eN -> RefEntry
        self._ref_map: Dict[str, RefEntry] = {}
        self._snapshot: Optional[SnapshotResult] = None
        self._ref_counter = 0
        
        # Logging prefix for trace
        self._log_prefix = f"[human-browser|{task_id}]"
    
    @classmethod
    async def from_engine(cls, engine, human_adapter=None):
        """
        Create adapter from BrowserEngine instance.
        
        Args:
            engine: BrowserEngine instance (must be initialized)
            human_adapter: Optional HumanInteractionAdapter instance
            
        Returns:
            ILMABrowserToolAdapter instance
        """
        if not engine._initialized:
            raise RuntimeError("BrowserEngine must be initialized before creating adapter")
        
        # Use BrowserEngine's existing CDP controller
        if engine._cdp is None:
            raise RuntimeError(
                "BrowserEngine CDP not initialized — call engine.initialize() first, "
                "or use engine.connect_to_daemon=True"
            )
        
        return cls(
            cdp_controller=engine._cdp,
            page=engine._page,
            task_id=engine.session_name or "default",
            human_adapter=human_adapter,
        )
    
    # ─── CDP Core ────────────────────────────────────────────────────────────
    
    async def cdp_send(self, method: str, params: Optional[Dict] = None) -> Dict:
        """Send raw CDP command. Returns result dict or {} on error."""
        try:
            return await self._cdp.send(method, params or {})
        except Exception as e:
            logger.warning(f"{self._log_prefix} CDP {method} failed: {e}")
            return {}

    async def navigate(self, url: str, timeout: int = 30000) -> Dict[str, Any]:
        """
        Navigate to URL and return result.
        
        Args:
            url: URL to navigate to
            timeout: Navigation timeout in milliseconds
            
        Returns:
            Dict with success, url, title, status, error
        """
        self._log("navigate", f"URL={url}")
        try:
            response = await self._page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            status = response.status if response else 200
            title = await self._page.title()
            
            self._log("navigate", f"SUCCESS — status={status} title={title[:50]}")
            return {
                "success": True,
                "url": self._page.url,
                "title": title,
                "status": status,
            }
        except Exception as e:
            self._log("navigate", f"FAILED — {e}")
            return {
                "success": False,
                "error": str(e),
                "url": url,
            }

    async def screenshot(self, path: Optional[str] = None) -> str:
        """
        Take screenshot of current page.
        
        Args:
            path: Optional file path to save screenshot. If None, returns base64.
            
        Returns:
            File path (if saved) or base64 string
        """
        self._log("screenshot", "capturing page")
        try:
            if path:
                await self._page.screenshot(path=path, full_page=False)
                self._log("screenshot", f"saved to {path}")
                return path
            else:
                import base64
                img = await self._page.screenshot(full_page=False)
                return base64.b64encode(img).decode()
        except Exception as e:
            self._log("screenshot", f"FAILED: {e}")
            return ""

    async def evaluate(self, expression: str) -> Any:
        """
        Evaluate JavaScript expression in page context.
        
        Args:
            expression: JavaScript expression to evaluate
            
        Returns:
            Evaluated result or None on error
        """
        self._log("evaluate", f"expression={expression[:50]}...")
        try:
            result = await self._page.evaluate(expression)
            return result
        except Exception as e:
            self._log("evaluate", f"FAILED: {e}")
            return None

    # ─── Logging ─────────────────────────────────────────────────────────────
    
    def _log(self, action: str, detail: str = "") -> None:
        """Log human-browser action."""
        msg = f"{self._log_prefix} {action}"
        if detail:
            msg += f" — {detail}"
        logger.info(msg)
    
    # ─── Ref Counter ──────────────────────────────────────────────────────────
    
    @classmethod
    async def _next_ref(cls) -> str:
        """Get next unique @e ref string (thread-safe)."""
        async with cls._ref_counter_lock:
            cls._ref_counter += 1
            return f"@e{cls._ref_counter}"
    
    def _reset_ref_counter(self) -> None:
        """Reset ref counter for new snapshot."""
        self._ref_counter = 0
    
    # ─── Snapshot Generation ──────────────────────────────────────────────────
    
    async def snapshot(self, full: bool = False) -> SnapshotResult:
        """
        Generate accessibility tree snapshot with ILMA-owned @e refs.

        HYBRID APPROACH (Phase 69D) — more reliable than CDP-only:
        1. page.evaluate() → discover all interactive elements (100% reliable)
        2. CDP DOM.resolveNode → get backendNodeId for each element
        3. ILMA assigns @e refs
        4. ILMA stores backendNodeId in ref_map

        Why hybrid over CDP-only:
        - CDP Accessibility.getFullAXTree returns empty properties in daemon mode
        - CDP Accessibility.getPartialAXTree requires precise nodeId input
        - page.evaluate() returns the complete DOM with bounding rects
        - CDP DOM.resolveNode bridges JS element → CDP backendNodeId

        Args:
            full: If True, include all elements. If False, interactive only.

        Returns:
            SnapshotResult with text, ref_map, raw_tree, page_title, page_url
        """
        self._log("snapshot", "generating ILMA-native snapshot (hybrid approach)")
        self._reset_ref_counter()

        # Get page URL and title
        page_url = self._page.url
        try:
            page_title = await self._page.title()
        except Exception:
            page_title = ""

        # Enable DOM for CDP.resolveNode
        await self.cdp_send("DOM.enable")
        await asyncio.sleep(0.05)

        # Step 1: Discover all interactive elements via JS (reliable)
        try:
            js_result = await self._page.evaluate(_SNAPSHOT_JS, {"full": full})
            js_elements = js_result.get("elements", []) if js_result else []
        except Exception as e:
            logger.warning(f"{self._log_prefix} JS snapshot failed: {e}")
            js_elements = []

        # Step 2: Build ILMA ref_map with backendNodeId from CDP
        ref_map: Dict[str, RefEntry] = {}
        text_lines: List[str] = []

        for el in js_elements:
            ref_str = await self._next_ref()

            # Try to get backendNodeId via CDP
            backend_node_id = 0
            node_id = 0
            object_id = None

            if el.get("has_backend_node"):
                # This element was found via backendNodeId lookup in JS
                backend_node_id = el.get("backend_node_id", 0)
                node_id = el.get("node_id", 0)

            # Get bounding box (already in element from JS)
            bbox = None
            if el.get("x") is not None and el.get("width", 0) > 0:
                bbox = {
                    "x": el["x"],
                    "y": el["y"],
                    "width": el["width"],
                    "height": el["height"],
                }

            entry = RefEntry(
                ref=ref_str,
                node_id=node_id,
                backend_node_id=backend_node_id,
                role=el.get("role", "unknown"),
                name=el.get("text", "") or el.get("placeholder", "") or "",
                description=el.get("description", "") or "",
                bounding_box=bbox,
                visible=el.get("visible", True),
                enabled=not el.get("disabled", False),
                focused=el.get("focused", False),
                checked=el.get("checked", False),
                pressed=el.get("pressed", False),
                value=el.get("value", None),
                href=el.get("href", None),
                tag=el.get("tag", "div"),
                object_id=object_id,
                backend_id=backend_node_id,
            )
            ref_map[ref_str] = entry

            # Format text line
            indent = "  "
            line = f"{indent}{ref_str} {entry.role}"
            if entry.name:
                line += f": {entry.name}"
            if entry.href:
                line += f" [href={entry.href[:50]}...]"
            if entry.tag == "input":
                line += f" (placeholder: {el.get('placeholder', '')})"
            text_lines.append(line)

        self._ref_map = ref_map
        self._snapshot = SnapshotResult(
            text="\n".join(text_lines),
            ref_map=ref_map,
            raw_tree=js_elements,
            page_title=page_title,
            page_url=page_url,
        )

        self._log("snapshot", f"generated {len(ref_map)} refs")
        return self._snapshot

    async def _build_ref_tree(
        self,
        nodes: List[Dict],
        full: bool = False,
        depth: int = 0,
    ) -> Tuple[Dict[str, RefEntry], List[str]]:
        """
        Fallback: recursively build ref_map from raw accessibility nodes.
        Used when hybrid snapshot produces no results.
        """
        ref_map: Dict[str, RefEntry] = {}
        lines: List[str] = []

        for node in nodes:
            props = self._extract_props(node)
            role = props.get("role", "unknown")
            name = props.get("name", "")
            description = props.get("description", "")

            is_interactive = role.lower() in self.INTERACTIVE_ROLES
            children = node.get("cachedChildren", [])
            has_controls = any(
                isinstance(r, dict) and r.get("role", "").lower() in self.INTERACTIVE_ROLES
                for r in children
            )

            if not full and not is_interactive and not has_controls:
                if "cachedChildren" in node:
                    child_map, child_lines = await self._build_ref_tree(
                        node["cachedChildren"], full=full, depth=depth
                    )
                    ref_map.update(child_map)
                    lines.extend(child_lines)
                continue

            backend_node_id = node.get("backendDOMNodeId", 0) or node.get("nodeId", 0)
            node_id = node.get("nodeId", 0)
            bbox = None
            if backend_node_id and is_interactive:
                bbox = await self._get_bounding_box(backend_node_id)

            href = None
            value = props.get("value")
            if value and isinstance(value, str) and value.startswith("http"):
                href = value

            ref_str = await self._next_ref()
            entry = RefEntry(
                ref=ref_str,
                node_id=node_id,
                backend_node_id=backend_node_id,
                role=role,
                name=name,
                description=description,
                bounding_box=bbox,
                visible=True,
                enabled="disabled" not in props,
                focused=False,
                checked=False,
                pressed=False,
                value=value,
                href=href,
                tag=self._role_to_tag(role),
                backend_id=backend_node_id,
            )
            ref_map[ref_str] = entry

            indent = "  " * depth
            line = f"{indent}{ref_str} {role}"
            if name:
                line += f": {name}"
            lines.append(line)

            if "cachedChildren" in node:
                child_map, child_lines = await self._build_ref_tree(
                    node["cachedChildren"], full=full, depth=depth + 1
                )
                ref_map.update(child_map)
                lines.extend(child_lines)

        return ref_map, lines

    def _extract_props(self, node: Dict) -> Dict[str, Any]:
        """Extract properties from accessibility node."""
        props = {}
        if "properties" in node:
            for prop in node["properties"]:
                key = prop.get("name", "")
                val = prop.get("value", {})
                if isinstance(val, dict):
                    # Could be {type: "bool", value: true} or {type: "string", value: "..."}
                    if "value" in val:
                        props[key] = val["value"]
                    elif "type" in val and val["type"] == "bool":
                        props[key] = False  # absence of value = false for bool
                    else:
                        props[key] = val
                else:
                    props[key] = val
        return props
    
    def _role_to_tag(self, role: str) -> str:
        """Map accessibility role to HTML tag name."""
        role_map = {
            "button": "button",
            "link": "a",
            "textbox": "input",
            "searchbox": "input",
            "checkbox": "input",
            "radioButton": "input",
            "combobox": "select",
            "listbox": "select",
            "menuitem": "menuitem",
            "tab": "div",
            "tabpanel": "div",
            "switch": "div",
            "slider": "input",
            "spinbutton": "input",
            "progressbar": "progress",
            "scrollbar": "div",
            "separator": "hr",
        }
        return role_map.get(role.lower(), "div")
    
    async def _get_bounding_box(self, backend_node_id: int) -> Optional[Dict[str, float]]:
        """Get bounding box for a backendNodeId via DOM.getBoundingClientRect."""
        try:
            # First resolve the node to get an objectId
            resolve_result = await self.cdp_send("DOM.resolveNode", {
                "backendNodeId": backend_node_id,
            })
            object_id = resolve_result.get("object", {}).get("objectId")
            if not object_id:
                return None
            
            # Now evaluate JS to get bounding rect
            rect_result = await self.cdp_send("Runtime.callFunctionOn", {
                "objectId": object_id,
                "functionDeclaration": """
                    function() {
                        var r = this.getBoundingClientRect();
                        if (!r || r.width === 0) return null;
                        return {
                            x: r.x,
                            y: r.y,
                            width: r.width,
                            height: r.height,
                            top: r.top,
                            left: r.left,
                            right: r.right,
                            bottom: r.bottom
                        };
                    }
                """,
                "returnByValue": True,
            })
            
            if rect_result:
                value = rect_result.get("result", {}).get("value")
                if value:
                    return value
            
            return None
        except Exception as e:
            logger.debug(f"{self._log_prefix} bbox failed for nodeId {backend_node_id}: {e}")
            return None
    
    # ─── Ref Resolution ──────────────────────────────────────────────────────
    
    async def resolve_ref(self, ref: str) -> Optional[RefEntry]:
        """
        Resolve a @e ref to its RefEntry.
        
        This is the CRITICAL operation that Phase 69D makes reliable:
        - Snapshot generates ref_map with backendNodeId
        - Click/type/scroll look up ref_map to get backendNodeId
        - CDP interaction uses backendNodeId for precise targeting
        
        Args:
            ref: Element reference like "@e5"
            
        Returns:
            RefEntry if found, None if not found
        """
        if not ref.startswith("@"):
            ref = f"@{ref}"
        
        entry = self._ref_map.get(ref)
        
        if entry is None:
            self._log("resolve_ref", f"FAILED — {ref} not in ref_map ({len(self._ref_map)} refs available)")
            return None
        
        self._log("resolve_ref", f"{ref} -> backendNodeId={entry.backend_node_id} role={entry.role} name={entry.name[:30]}")
        return entry
    
    # ─── CDP-Direct Interaction ──────────────────────────────────────────────
    
    async def click(self, ref: str) -> bool:
        """
        Click an element by @e ref using CDP-direct human-like interaction.

        HYBRID APPROACH (Phase 69D):
        - If backend_node_id > 0: Use CDP DOM.resolveNode -> objectId -> Input.dispatchMouseEvent
        - If backend_node_id == 0: Use Playwright locator (same JS context as snapshot)
        - Both paths produce human-like behavior with delays and jitter

        Args:
            ref: Element reference like "@e5"

        Returns:
            True if click succeeded, False otherwise
        """
        import random

        entry = await self.resolve_ref(ref)
        if not entry:
            return False

        self._log("click", f"starting human-like click for {ref} (backendNodeId={entry.backend_node_id})")

        # ─── PATH A: CDP-direct via backendNodeId ─────────────────────────────
        if entry.backend_node_id > 0 and entry.backend_id:
            try:
                resolve_result = await self.cdp_send("DOM.resolveNode", {
                    "backendNodeId": entry.backend_node_id,
                })
                object_id = resolve_result.get("object", {}).get("objectId")

                if object_id:
                    # Scroll into view
                    self._log("scroll_into_view", f"{ref} via CDP")
                    await self.cdp_send("DOM.scrollIntoViewIfNeeded", {
                        "nodeId": entry.node_id or 0,
                    })
                    await asyncio.sleep(0.15)

                    # Get bounding box
                    bbox = await self._get_bounding_box(entry.backend_node_id)

                    if bbox:
                        cx = bbox["x"] + bbox["width"] / 2
                        cy = bbox["y"] + bbox["height"] / 2

                        # Human-like mouse move with jitter
                        self._log("mouse_move", f"({cx:.0f}, {cy:.0f})")
                        await self._dispatch_mouse_event("mouseMoved", cx + random.uniform(-2, 2), cy + random.uniform(-2, 2))
                        await asyncio.sleep(random.uniform(0.08, 0.2))

                        # Hover
                        self._log("hover", f"({cx:.0f}, {cy:.0f})")
                        await self._dispatch_mouse_event("mouseMoved", cx, cy)
                        await asyncio.sleep(random.uniform(0.1, 0.3))

                        # Human-like click
                        await asyncio.sleep(random.uniform(0.05, 0.15))
                        self._log("click", f"({cx:.0f}, {cy:.0f}) mousePressed")
                        await self._dispatch_mouse_event("mousePressed", cx, cy, click_count=1)
                        await asyncio.sleep(random.uniform(0.05, 0.12))
                        self._log("click", f"({cx:.0f}, {cy:.0f}) mouseReleased")
                        await self._dispatch_mouse_event("mouseReleased", cx, cy, click_count=1)

                        self._log("click", f"SUCCESS — {ref} via CDP path")
                        return True

                self._log("click", f"DOM.resolveNode returned no objectId, falling back to locator")
            except Exception as e:
                self._log("click", f"CDP path failed ({e}), falling back to locator")

        # ─── PATH B: Playwright locator fallback ─────────────────────────────
        # Used when backend_node_id=0 (JS-discovered elements without CDP handles)
        self._log("click", f"{ref} using Playwright locator (hybrid fallback)")

        tag = entry.tag or "div"
        name = entry.name
        href = entry.href
        locator = None

        # Strategy 1: href-based for links
        if href:
            locator = self._page.locator(f"a[href='{href}']")
            try:
                if await locator.count() == 0:
                    locator = self._page.locator(f"a[href*='{href[4:20]}']")
            except Exception:
                locator = None

        # Strategy 2: text-based
        if not locator and name:
            if tag == "a":
                locator = self._page.locator(f"a", { "hasText": name })
            elif tag == "button":
                locator = self._page.locator(f"button", { "hasText": name })
            elif tag == "input":
                locator = self._page.locator(f"input[placeholder*='{name[:20]}']")
            else:
                locator = self._page.locator(tag, { "hasText": name })

        # Strategy 3: tag-only
        if not locator:
            locator = self._page.locator(tag).first

        if not locator:
            self._log("click", f"FAILED — no locator strategy for {ref}")
            return False

        if await locator.count() == 0:
            self._log("click", f"FAILED — locator found 0 elements for {ref}")
            return False

        try:
            # Scroll into view
            self._log("scroll_into_view", f"{ref} via locator")
            await locator.scroll_into_view_if_needed()
            await asyncio.sleep(0.2)

            # Get bounding box for mouse move
            try:
                bbox = await locator.bounding_box()
                if bbox:
                    cx = bbox["x"] + bbox["width"] / 2
                    cy = bbox["y"] + bbox["height"] / 2
                    self._log("mouse_move", f"({cx:.0f}, {cy:.0f})")
                    await self._dispatch_mouse_event("mouseMoved", cx + random.uniform(-2, 2), cy + random.uniform(-2, 2))
                    await asyncio.sleep(random.uniform(0.08, 0.2))
                    self._log("hover", f"({cx:.0f}, {cy:.0f})")
                    await self._dispatch_mouse_event("mouseMoved", cx, cy)
            except Exception:
                pass

            # Human-like click
            await asyncio.sleep(random.uniform(0.05, 0.15))
            self._log("click", f"{ref} — locator.click() [humanized]")
            delay_ms = random.randint(40, 120)
            await locator.click(delay=delay_ms, timeout=5000)

            self._log("click", f"SUCCESS — {ref} clicked via Playwright locator")
            return True

        except asyncio.TimeoutError:
            self._log("click", f"FAILED — timeout clicking {ref}")
            return False
        except Exception as e:
            self._log("click", f"FAILED — {e}")
            return False
    
    async def type(
        self,
        ref: str,
        text: str,
        delay_ms: int = 50,
    ) -> bool:
        """
        Type text into an element by @e ref using CDP-direct human-like interaction.
        
        Steps:
        1. resolve_ref -> get backendNodeId
        2. human-like click to focus
        3. clear existing content
        4. type character-by-character with realistic delays
        
        Args:
            ref: Element reference like "@e3"
            text: Text to type
            delay_ms: Base delay between characters
            
        Returns:
            True if type succeeded, False otherwise
        """
        entry = await self.resolve_ref(ref)
        if not entry:
            return False
        
        self._log("type", f"starting human-like type for {ref} ({len(text)} chars)")
        
        try:
            # Step 1: Resolve backendNodeId to objectId
            resolve_result = await self.cdp_send("DOM.resolveNode", {
                "backendNodeId": entry.backend_node_id,
            })
            object_id = resolve_result.get("object", {}).get("objectId")
            
            if not object_id:
                self._log("type", f"FAILED — cannot resolve backendNodeId {entry.backend_node_id}")
                return False
            
            # Step 2: Focus the element
            self._log("focus", f"{ref}")
            await self.cdp_send("Runtime.callFunctionOn", {
                "objectId": object_id,
                "functionDeclaration": "function() { this.focus(); }",
            })
            await asyncio.sleep(0.1)
            
            # Step 3: Clear existing content
            self._log("clear", f"{ref}")
            await self.cdp_send("Runtime.callFunctionOn", {
                "objectId": object_id,
                "functionDeclaration": """
                    function() {
                        if (this.tagName === 'INPUT' || this.tagName === 'TEXTAREA') {
                            this.value = '';
                            // Dispatch input event
                            this.dispatchEvent(new Event('input', {bubbles: true}));
                        }
                    }
                """,
            })
            await asyncio.sleep(0.1)
            
            # Step 4: Type character by character
            import random
            for i, char in enumerate(text):
                # Press key for character
                key_info = self._char_to_key(char)
                
                if key_info["type"] == "key":
                    # Single key press
                    await self._dispatch_key_event("keyDown", key_info["key"])
                    await asyncio.sleep(random.uniform(0.02, 0.08))
                    await self._dispatch_key_event("keyUp", key_info["key"])
                else:
                    # Character needs to be typed via insertText
                    await self.cdp_send("Input.insertText", {"text": char})
                
                # Variable delay between keystrokes
                base_delay = delay_ms / 1000.0
                # Longer pause at word boundaries
                if char == ' ':
                    base_delay *= 1.5
                elif char in '.,!?:;':
                    base_delay *= 2.0
                
                await asyncio.sleep(base_delay + random.uniform(-0.02, 0.05))
            
            self._log("type", f"SUCCESS — {ref} ({len(text)} chars)")
            return True
            
        except Exception as e:
            self._log("type", f"FAILED — {ref}: {e}")
            return False
    
    async def scroll(
        self,
        direction: str = "down",
        amount: int = 500,
        repeats: int = 3,
    ) -> bool:
        """
        Scroll the page using CDP wheel events.
        
        Args:
            direction: "up" or "down"
            amount: Pixels to scroll per action (default 500)
            repeats: Number of scroll actions
            
        Returns:
            True if scroll succeeded
        """
        if direction not in ("up", "down"):
            self._log("scroll", f"FAILED — invalid direction: {direction}")
            return False
        
        self._log("scroll", f"starting chunked scroll {direction} x{repeats} ({amount}px each)")
        
        try:
            # Get viewport dimensions
            viewport = self._page.viewport_size or {"width": 1920, "height": 1080}
            x = viewport["width"] / 2
            y = viewport["height"] / 2
            
            delta_y = amount if direction == "down" else -amount
            
            import random
            for i in range(repeats):
                self._log("wheel", f"({x}, {y}) deltaY={delta_y}")
                await self.cdp_send("Input.dispatchMouseEvent", {
                    "type": "mouseWheel",
                    "x": x,
                    "y": y,
                    "deltaX": 0,
                    "deltaY": delta_y,
                    "timestamp": time.time(),
                })
                await asyncio.sleep(random.uniform(0.1, 0.25))
            
            self._log("scroll", f"SUCCESS — {direction} x{repeats}")
            return True
            
        except Exception as e:
            self._log("scroll", f"FAILED: {e}")
            return False
    
    async def scroll_into_view(self, ref: str) -> bool:
        """Scroll element into view via DOM.scrollIntoViewIfNeeded."""
        entry = await self.resolve_ref(ref)
        if not entry:
            return False
        
        try:
            await self.cdp_send("DOM.scrollIntoViewIfNeeded", {
                "nodeId": entry.node_id or 0,
            })
            self._log("scroll_into_view", f"SUCCESS — {ref}")
            return True
        except Exception as e:
            self._log("scroll_into_view", f"FAILED — {ref}: {e}")
            return False
    
    # ─── CDP Event Dispatch ──────────────────────────────────────────────────
    
    async def _dispatch_mouse_event(
        self,
        type: str,
        x: float,
        y: float,
        button: str = "left",
        click_count: int = 1,
    ) -> None:
        """Dispatch a mouse event via CDP Input.dispatchMouseEvent."""
        button_map = {"left": 0, "middle": 1, "right": 2}
        button_arg = button_map.get(button, 0)
        
        await self.cdp_send("Input.dispatchMouseEvent", {
            "type": type,
            "x": x,
            "y": y,
            "button": button,
            "buttons": 1 << button_arg,
            "clickCount": click_count,
            "timestamp": time.time(),
        })
    
    async def _dispatch_key_event(
        self,
        type: str,
        key: str,
        code: Optional[str] = None,
    ) -> None:
        """Dispatch a key event via CDP Input.dispatchKeyEvent."""
        # Try to derive code from key
        if code is None:
            code = f"Key{key.upper()}" if len(key) == 1 else f"{key.upper()}"
        
        await self.cdp_send("Input.dispatchKeyEvent", {
            "type": type,
            "key": key,
            "code": code,
            "windowsVirtualKeyCode": ord(key.upper()) if len(key) == 1 else 0,
            "timestamp": time.time(),
        })
    
    def _char_to_key(self, char: str) -> Dict[str, Any]:
        """Map character to key event info."""
        import random
        
        # Whitespace
        if char == ' ':
            return {"type": "key", "key": " "}
        
        # Newline
        if char == '\n':
            return {"type": "key", "key": "Enter"}
        
        # Special characters
        special_map = {
            '!': '!', '@': '@', '#': '#', '$': '$', '%': '%',
            '^': '^', '&': '&', '*': '*', '(': '(', ')': ')',
            '-': '-', '_': '_', '=': '=', '+': '+',
            '[': '[', ']': ']', '{': '{', '}': '}',
            '\\': '\\', '|': '|', ';': ';', ':': ':',
            "'": "'", '"': '"', ',': ',', '.': '.',
            '<': '<', '>': '>', '/': '/', '?': '?',
            '~': '~', '`': '`',
        }
        
        if char in special_map:
            # For special chars that need shift, we use insertText
            if char in '~`!@#$%^&*()_+{}|:"<>?' :
                return {"type": "insert", "text": char}
            return {"type": "key", "key": char}
        
        # Regular character
        if char.isupper():
            return {"type": "insert", "text": char}
        return {"type": "key", "key": char}
    
    # ─── Utility ─────────────────────────────────────────────────────────────
    
    @property
    def ref_map(self) -> Dict[str, RefEntry]:
        """Get current ref_map from last snapshot."""
        return self._ref_map
    
    @property
    def last_snapshot(self) -> Optional[SnapshotResult]:
        """Get last snapshot result."""
        return self._snapshot
    
    async def get_page_info(self) -> Dict[str, str]:
        """Get current page URL and title."""
        return {
            "url": self._page.url,
            "title": await self._page.title() or "",
        }
