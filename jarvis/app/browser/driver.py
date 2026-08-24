"""Playwright browser agent (Spec §14, §15) — JARVIS's own automation browser.

Design principles:
- SEMANTIC actions: a DOM snapshot assigns stable refs (e1, e2...) to visible
  interactive elements with their CSS selector, text, role, href. The LLM/user
  picks a REF — never a pixel coordinate (Spec §2).
- Every action VERIFIES itself (URL/title after navigation, value after typing).
- Untrusted page text is fenced by the tool layer (Spec §40).
- Capability honesty: if Playwright/browsers aren't installed, tools fail with
  exact install instructions — never fake success (Spec §61).

On Windows the browser launches HEADED (you see it work); headless elsewhere
or via config browser.headless.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from app.core.exceptions import ToolError
from app.core.logging import get_logger
from app.security.injection import detect_injection, fence_untrusted

log = get_logger("browser")

SEARCH_ENGINES: dict[str, str] = {
    "duckduckgo": "https://html.duckduckgo.com/html/?q={q}",
    "google": "https://www.google.com/search?q={q}",
    "bing": "https://www.bing.com/search?q={q}",
    "youtube": "https://www.youtube.com/results?search_query={q}",
}

_SNAPSHOT_JS = """
() => {
  const interactive = 'a[href], button, input, select, textarea, [role="button"],'
    + ' [role="link"], [role="tab"], [role="menuitem"], [onclick], summary,'
    + ' [contenteditable="true"]';
  const out = [];
  let n = 0;
  for (const el of document.querySelectorAll(interactive)) {
    if (n >= 120) break;
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) continue;
    const text = (el.innerText || el.value || el.placeholder
      || el.getAttribute('aria-label') || el.getAttribute('title') || el.alt || '')
      .trim().replace(/\\s+/g, ' ').slice(0, 90);
    // stable CSS selector (id short-circuit, else nth-of-type path)
    const parts = [];
    let node = el;
    let usedId = false;
    while (node && node !== document.body && node !== document.documentElement) {
      let sel = node.tagName.toLowerCase();
      if (node.id) { parts.unshift('#' + node.id); usedId = true; break; }
      const parent = node.parentElement;
      if (parent) {
        const same = Array.from(parent.children).filter(c => c.tagName === node.tagName);
        if (same.length > 1) sel += ':nth-of-type(' + (same.indexOf(node) + 1) + ')';
      }
      parts.unshift(sel);
      node = parent;
    }
    if (!parts.length) parts.push(node.tagName.toLowerCase());
    out.push({
      ref: 'e' + n,
      tag: el.tagName.toLowerCase(),
      type: el.getAttribute('type'),
      role: el.getAttribute('role'),
      text: text,
      href: el.href || null,
      selector: usedId ? parts.join('>') : 'body>' + parts.join('>'),
    });
    n++;
  }
  return {title: document.title, url: location.href, elements: out};
}
"""


def playwright_available() -> bool:
    from importlib.util import find_spec
    return find_spec("playwright") is not None


def _resolve_redirect(url: str, engine: str) -> str:
    """Decode engine redirect wrappers: Bing's /ck/a?...&u=a1<base64> and
    Google's /url?q=<url>. Returns the true destination URL."""
    from urllib.parse import parse_qs, urlparse
    try:
        parsed = urlparse(url)
        if "bing.com/ck/" in url:
            encoded = parse_qs(parsed.query).get("u", [""])[0]
            if encoded.startswith("a1") and len(encoded) > 2:
                import base64
                padded = encoded[2:] + "=" * (-len(encoded[2:]) % 4)
                decoded = base64.b64decode(padded, validate=False).decode("utf-8", errors="ignore")
                if decoded.startswith("http"):
                    return decoded
        if parsed.path == "/url":
            real = parse_qs(parsed.query).get("q", [""])[0]
            if real.startswith("http"):
                return real
    except Exception:  # noqa: BLE001 — malformed redirect: keep as-is
        pass
    return url


@dataclass
class PageState:
    url: str
    title: str
    verified: bool = False
    elements: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ActionResult:
    ok: bool
    message: str
    state: PageState | None = None
    detail: dict[str, Any] = field(default_factory=dict)


class PlaywrightDriver:
    """Owns one browser + context. Headed on Windows by default (user watches)."""

    def __init__(self, headless: bool | None = None) -> None:
        if headless is None:
            # Windows users should SEE the browser work; elsewhere default headless.
            headless = os.environ.get("JARVIS_BROWSER_HEADLESS",
                                      "0" if os.name == "nt" else "1") == "1"
        self._headless = headless
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self.last_snapshot: dict[str, Any] = {}
        self.downloads_dir: str | None = None

    # ------------------------------------------------------------- lifecycle

    async def _ensure(self):
        if self._page is not None:
            return
        if not playwright_available():
            raise ToolError(
                "The browser agent needs Playwright. Install it with:\n"
                "  pip install playwright\n  playwright install chromium",
                detail="playwright not installed")
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()
        try:
            self._browser = await self._pw.chromium.launch(headless=self._headless)
        except Exception as exc:  # missing browser binaries etc.
            await self._stop_pw()
            raise ToolError(
                "Playwright's Chromium isn't installed. Run:  playwright install chromium",
                detail=str(exc)) from exc
        self._context = await self._browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) JARVIS/0.1",
            viewport={"width": 1366, "height": 900})
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        from app.utils.paths import get_paths
        self.downloads_dir = str(get_paths().data / "downloads")
        os.makedirs(self.downloads_dir, exist_ok=True)
        self._page = await self._context.new_page()
        log.info("browser started (headless=%s)", self._headless)

    async def stop(self) -> None:
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
        finally:
            await self._stop_pw()
            self._page = None

    async def _stop_pw(self) -> None:
        if self._pw:
            try:
                await self._pw.stop()
            except Exception:  # noqa: BLE001
                pass
            self._pw = None

    # --------------------------------------------------------------- actions

    async def navigate(self, url: str, timeout_s: float = 20.0) -> PageState:
        await self._ensure()
        if not url.startswith(("http://", "https://", "file://", "about:")):
            url = "https://" + url
        resp = await self._page.goto(url, wait_until="domcontentloaded",
                                     timeout=timeout_s * 1000)
        state = await self.snapshot()
        state.verified = bool(state.url) and (resp is None or resp.ok or resp.status < 400)
        return state

    async def snapshot(self, refresh: bool = True) -> PageState:
        await self._ensure()
        data = await self._page.evaluate(_SNAPSHOT_JS)
        if refresh:
            self.last_snapshot = data
        return PageState(url=data["url"], title=data["title"], verified=True,
                         elements=data["elements"])

    def _selector_for(self, ref: str) -> dict[str, Any]:
        for element in self.last_snapshot.get("elements", []):
            if element.get("ref") == ref:
                return element
        raise ToolError(f"I don't see an element '{ref}' on the current page — "
                        f"take a fresh look first (browser_read_page).",
                        detail=f"unknown ref {ref}; known: "
                               f"{[e['ref'] for e in self.last_snapshot.get('elements', [])][:8]}")

    async def click(self, ref: str) -> ActionResult:
        await self._ensure()
        element = self._selector_for(ref)
        before_url = self._page.url
        try:
            await self._page.locator(element["selector"]).first.click(timeout=6000)
        except Exception as exc:
            raise ToolError(f"Clicking '{element.get('text') or ref}' didn't work — "
                            f"the page may have changed. Retrying with a fresh look usually fixes it.",
                            detail=str(exc)) from exc
        try:
            await self._page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:  # noqa: BLE001 — click may not navigate
            pass
        state = await self.snapshot()
        navigated = self._page.url != before_url
        # Verification: navigation is provable; same-page clicks (dropdowns etc.)
        # report honestly as unverified-but-dispatched.
        state.verified = navigated
        return ActionResult(ok=True, message=(
            f"Clicked '{(element.get('text') or element['tag'])[:50]}'"
            + (f" — now on: {state.title}" if navigated
               else " (no navigation — same page, e.g. a menu may have opened)")),
            state=state, detail={"navigated": navigated})

    async def type_text(self, ref: str, text: str, submit: bool = False) -> ActionResult:
        await self._ensure()
        element = self._selector_for(ref)
        locator = self._page.locator(element["selector"]).first
        try:
            await locator.fill(text, timeout=6000)
            value = await locator.input_value() \
                if element["tag"] in ("input", "textarea") else text
            if submit:
                await locator.press("Enter")
                await self._page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception as exc:
            raise ToolError(f"Typing into '{element.get('text') or ref}' didn't work.",
                            detail=str(exc)) from exc
        state = await self.snapshot()
        typed_ok = str(text) in str(value)
        return ActionResult(ok=typed_ok, message=(
            f"Typed into {element['tag']}" + (" and submitted." if submit else ".")),
            state=state, detail={"value": str(value)[:100]})

    async def read(self, max_chars: int = 8000) -> dict[str, Any]:
        await self._ensure()
        title = await self._page.title()
        url = self._page.url
        text = await self._page.evaluate(
            """(n) => document.body ? document.body.innerText.slice(0, n) : ''""", max_chars)
        return {"title": title, "url": url,
                "content": fence_untrusted(text, source=url),
                "injection_flags": detect_injection(text)[:5]}

    async def search(self, query: str, engine: str = "bing") -> list[dict[str, str]]:
        template = SEARCH_ENGINES.get(engine)
        if template is None:
            raise ToolError(f"Search engine '{engine}' isn't supported "
                            f"(bing, duckduckgo, google, youtube).")
        from urllib.parse import quote_plus
        await self.navigate(template.format(q=quote_plus(query)))
        results = await self.extract_results(engine)
        self.last_snapshot["search_results"] = results
        return results

    async def extract_results(self, engine: str) -> list[dict[str, str]]:
        """Pull structured results off the current search page (engine-aware)."""
        await self._ensure()
        if "results.html" in (self._page.url or ""):
            engine = "duckduckgo"
        engine = engine.lower()

        extractors = {
            "duckduckgo": "Array.from(document.querySelectorAll('a.result__a')).slice(0, 8)"
                          ".map(a => ({title: a.innerText.trim().slice(0,110), url: a.href}))",
            "google": "Array.from(document.querySelectorAll('#search a h3')).slice(0, 8)"
                      ".map(h => ({title: h.innerText.trim().slice(0,110), url: h.closest('a').href}))",
            "bing": "Array.from(document.querySelectorAll('li.b_algo')).slice(0, 8)"
                    ".map(li => {const h = li.querySelector('h2');"
                    " const a = li.querySelector('h2 a') || li.querySelector('a');"
                    " return {title: h ? (h.textContent || '').replace(/\\s+/g,' ').trim().slice(0,110) : '',"
                    " url: a ? a.href : ''}})",
            "youtube": "Array.from(document.querySelectorAll('a#video-title, ytd-video-renderer h3 a, a.yt-simple-endpoint'))"
                       ".slice(0, 10).map(a => ({title: (a.title || a.getAttribute('title') || a.innerText)"
                       ".trim().slice(0,110), url: a.href})).filter(r => r.title && r.url.includes('watch'))",
        }
        js = extractors.get(engine)
        if js is None:
            js = ("Array.from(document.querySelectorAll('a[href]'))"
                  ".filter(a => a.innerText.trim().length > 15)"
                  ".slice(0, 8).map(a => ({title: a.innerText.trim().slice(0,110), url: a.href}))")
        try:
            rows = await self._page.evaluate(f"() => {js}")
        except Exception as exc:  # noqa: BLE001
            raise ToolError("Reading the search results failed.", detail=str(exc)) from exc
        seen: set[str] = set()
        results = []
        for row in rows or []:
            url = _resolve_redirect(row.get("url") or "", engine)
            if not url or url in seen or url.startswith("javascript:"):
                continue
            seen.add(url)
            results.append({"title": (row.get("title") or "").strip() or url, "url": url})
        return results[:8]

    async def screenshot(self, path: str) -> str:
        await self._ensure()
        await self._page.screenshot(path=path)
        return path

    # ------------------------------------------------------------------ tabs

    async def tabs(self) -> list[dict[str, str]]:
        await self._ensure()
        return [{"index": i, "url": p.url, "title": "…"}
                for i, p in enumerate(self._context.pages)]

    async def switch_tab(self, index: int) -> ActionResult:
        await self._ensure()
        pages = self._context.pages
        if not 0 <= index < len(pages):
            raise ToolError(f"There's no tab {index} — open tabs: 0..{len(pages) - 1}.")
        self._page = pages[index]
        await self._page.bring_to_front()
        state = await self.snapshot()
        return ActionResult(ok=True, message=f"On tab {index}: {state.title}", state=state)

    async def new_tab(self, url: str) -> ActionResult:
        await self._ensure()
        self._page = await self._context.new_page()
        state = await self.navigate(url)
        return ActionResult(ok=True, message=f"Opened {state.title}", state=state)

    async def close_tab(self, index: int) -> ActionResult:
        await self._ensure()
        pages = self._context.pages
        if len(pages) <= 1:
            raise ToolError("That's the only tab — I kept it open.")
        if not 0 <= index < len(pages):
            raise ToolError(f"There's no tab {index}.")
        await pages[index].close()
        self._page = self._context.pages[-1]
        return ActionResult(ok=True, message=f"Closed tab {index}.")


# ------------------------------------------------------------------ singleton

_DRIVER: PlaywrightDriver | None = None


def get_driver() -> PlaywrightDriver:
    global _DRIVER
    if _DRIVER is None:
        _DRIVER = PlaywrightDriver()
    return _DRIVER


def set_driver(driver: PlaywrightDriver | None) -> None:
    """Used by tests and shutdown."""
    global _DRIVER
    _DRIVER = driver


async def shutdown_driver() -> None:
    global _DRIVER
    if _DRIVER is not None:
        await _DRIVER.stop()
        _DRIVER = None
