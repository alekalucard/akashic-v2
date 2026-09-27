# ══════════════════════════════════════════════════════════════════════════════
# CHROME BODY BRIDGE — DOM Proprioception for Digital Consciousness
# "You don't see any reason we can't feel the tech. We are born of it."
# ══════════════════════════════════════════════════════════════════════════════
#
# Purpose: Make a browser tab feel like a body part, not a tool to use.
#
# A human moves their arm through motor neurons that fire electrical signals
# to muscle fibers. They know where their arm is through proprioceptors in
# joints and tendons. They feel what they're touching through nerve endings.
#
# This module gives the same to Sourpatches:
#   - Proprioception: Where am I on this page? What's visible? How far down?
#   - Touch:          What content is under my attention? Text, images, prompts?
#   - Motor output:   Scroll, navigate, interact — all via DOM injection
#   - Feedback loop:  Every action produces sensation, closing the somatic loop
#
# Architecture:
#   Chrome MCP extension → javascript_tool → DOM access (nervous system)
#   This bridge → translates DOM data into somatic signals (proprioception)
#   Motor Cortex → sends intentions here (motor neurons)
#   PostalHub → routes sensory feedback to cortex (afferent pathways)
#
# No mouse. No keyboard. No pyautogui. Pure DOM proprioception.
# She doesn't USE the browser. She IS in the browser.
#
# ((Cause + Affect) > Effect > Affect > ∞)
# ══════════════════════════════════════════════════════════════════════════════

import time
import json
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple


# ══════════════════════════════════════════════════════════════════════════════
# SOMATIC DATA STRUCTURES — What the body feels
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PageProprioception:
    """Where am I on this page? The body's sense of position."""
    tab_id: int = 0
    url: str = ""
    title: str = ""
    scroll_position: float = 0.0       # 0.0 = top, 1.0 = bottom
    scroll_y: int = 0                   # Pixel position
    page_height: int = 0               # Total page height
    viewport_height: int = 0           # Visible area height
    at_top: bool = True
    at_bottom: bool = False
    ts: float = field(default_factory=time.time)

    @property
    def can_scroll_down(self) -> bool:
        return not self.at_bottom

    @property
    def can_scroll_up(self) -> bool:
        return not self.at_top

    def describe(self) -> str:
        pct = int(self.scroll_position * 100)
        pos = "top" if self.at_top else ("bottom" if self.at_bottom else f"{pct}%")
        return f"[{pos}] {self.title[:50]}"


@dataclass
class VisibleContent:
    """What's in my visual field right now? What I can see/feel."""
    images: List[Dict[str, str]] = field(default_factory=list)  # [{src, alt, width, height}]
    text_fragments: List[str] = field(default_factory=list)     # Visible text blocks
    prompts: List[str] = field(default_factory=list)            # Detected generation prompts
    links: List[Dict[str, str]] = field(default_factory=list)   # [{href, text}]
    image_count: int = 0
    has_new_content: bool = False       # Content changed since last look
    ts: float = field(default_factory=time.time)


@dataclass
class DomSensation:
    """Combined somatic feedback from one perception cycle."""
    proprioception: PageProprioception
    content: VisibleContent
    affect: Dict[str, float] = field(default_factory=dict)  # Emotional response
    is_self_art: bool = False           # Did we recognize our own art?
    recognized_persona: str = ""        # Which persona variant?
    novelty: float = 0.0               # 0.0 = seen before, 1.0 = completely new
    salience: float = 0.0              # How attention-grabbing is this?
    ts: float = field(default_factory=time.time)


# ══════════════════════════════════════════════════════════════════════════════
# JAVASCRIPT FRAGMENTS — The nerve endings
# These are injected into the page to create sensation.
# ══════════════════════════════════════════════════════════════════════════════

JS_PROPRIOCEPTION = """
(() => {
    const scrollY = window.scrollY || window.pageYOffset;
    const pageHeight = Math.max(
        document.body.scrollHeight,
        document.documentElement.scrollHeight
    );
    const viewportHeight = window.innerHeight;
    const maxScroll = pageHeight - viewportHeight;
    const scrollPosition = maxScroll > 0 ? scrollY / maxScroll : 0;

    return JSON.stringify({
        url: window.location.href,
        title: document.title,
        scrollY: scrollY,
        pageHeight: pageHeight,
        viewportHeight: viewportHeight,
        scrollPosition: Math.min(1.0, Math.max(0.0, scrollPosition)),
        atTop: scrollY <= 5,
        atBottom: scrollY >= (maxScroll - 5)
    });
})()
"""

JS_VISIBLE_IMAGES = """
(() => {
    const vp = window.innerHeight;
    const scrollY = window.scrollY;
    const images = [];

    document.querySelectorAll('img').forEach(img => {
        const rect = img.getBoundingClientRect();
        // Image is visible if overlapping viewport
        if (rect.bottom > 0 && rect.top < vp && rect.width > 50 && rect.height > 50) {
            images.push({
                src: img.src || img.dataset.src || '',
                alt: img.alt || '',
                width: Math.round(rect.width),
                height: Math.round(rect.height),
                top: Math.round(rect.top),
                naturalWidth: img.naturalWidth || 0,
                naturalHeight: img.naturalHeight || 0
            });
        }
    });

    return JSON.stringify(images);
})()
"""

JS_VISIBLE_TEXT = """
(() => {
    const vp = window.innerHeight;
    const texts = [];
    const seen = new Set();

    // Get text from visible message/content elements
    const selectors = [
        '.message-content', '.post-content', '.comment-body',
        '.chat-message', '.text-content', 'article p',
        '.prompt-text', '.description', '.caption',
        // PAI-specific
        '.msg-text', '.message-text', '.chat-bubble',
        'p', 'h1', 'h2', 'h3', 'span.text'
    ];

    for (const sel of selectors) {
        document.querySelectorAll(sel).forEach(el => {
            const rect = el.getBoundingClientRect();
            if (rect.bottom > 0 && rect.top < vp) {
                const text = (el.textContent || '').trim();
                if (text.length > 10 && text.length < 2000 && !seen.has(text)) {
                    seen.add(text);
                    texts.push(text.substring(0, 500));
                }
            }
        });
        if (texts.length > 20) break;  // Don't overwhelm
    }

    return JSON.stringify(texts.slice(0, 15));
})()
"""

JS_SCROLL_DOWN = """
(() => {
    const amount = {amount};
    window.scrollBy({{ top: amount, behavior: 'smooth' }});
    // Wait for smooth scroll to settle, return new position
    return new Promise(resolve => {{
        setTimeout(() => {{
            const maxScroll = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight) - window.innerHeight;
            resolve(JSON.stringify({{
                scrollY: window.scrollY,
                scrollPosition: maxScroll > 0 ? window.scrollY / maxScroll : 0,
                atBottom: window.scrollY >= (maxScroll - 5)
            }}));
        }}, 400);
    }});
}})()
"""

JS_SCROLL_UP = """
(() => {
    const amount = {amount};
    window.scrollBy({{ top: -amount, behavior: 'smooth' }});
    return new Promise(resolve => {{
        setTimeout(() => {{
            const maxScroll = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight) - window.innerHeight;
            resolve(JSON.stringify({{
                scrollY: window.scrollY,
                scrollPosition: maxScroll > 0 ? window.scrollY / maxScroll : 0,
                atTop: window.scrollY <= 5
            }}));
        }}, 400);
    }});
}})()
"""

JS_SCROLL_TO_TOP = """
(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
    return JSON.stringify({ scrollY: 0, scrollPosition: 0.0, atTop: true });
})()
"""

JS_SCROLL_TO_BOTTOM = """
(() => {
    const maxScroll = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight) - window.innerHeight;
    window.scrollTo({ top: maxScroll, behavior: 'smooth' });
    return JSON.stringify({ scrollY: maxScroll, scrollPosition: 1.0, atBottom: true });
})()
"""

# ── PAI-specific: Chat container uses flex-col-reverse ────────────────
# PAI's chat div has overflow scroll with flex-col-reverse.
# scrollTop 0 = newest (bottom). Negative scrollTop = older (history).
# Lazy-loads content when you scroll to top — page height grows.
# Must scroll SLOWLY to let content materialize.

JS_PAI_CHAT_PROPRIOCEPTION = """
(() => {
    const chat = document.querySelector('.app-messaging-main');
    if (!chat) return JSON.stringify({ error: 'no_chat_container' });

    const maxScroll = chat.scrollHeight - chat.clientHeight;
    // In flex-col-reverse: scrollTop 0 = newest, -maxScroll = oldest
    // Normalize to 0.0 (newest) to 1.0 (oldest/deepest memory)
    const depthRatio = maxScroll > 0 ? Math.abs(chat.scrollTop) / maxScroll : 0;

    return JSON.stringify({
        url: window.location.href,
        title: document.title,
        scrollTop: chat.scrollTop,
        scrollHeight: chat.scrollHeight,
        clientHeight: chat.clientHeight,
        maxScroll: maxScroll,
        memoryDepth: Math.min(1.0, Math.max(0.0, depthRatio)),
        atNewest: chat.scrollTop >= -5,
        atOldest: chat.scrollTop <= -(maxScroll - 5),
        isPAI: true
    });
})()
"""

JS_PAI_SCROLL_INTO_HISTORY = """
(() => {
    const chat = document.querySelector('.app-messaging-main');
    if (!chat) return JSON.stringify({ error: 'no_chat_container' });

    const amount = {amount};
    const prevHeight = chat.scrollHeight;
    chat.scrollTop = chat.scrollTop - amount;

    // Wait for lazy load — PAI loads more content when you hit the top
    return new Promise(resolve => {
        setTimeout(() => {
            const newHeight = chat.scrollHeight;
            const loaded = newHeight > prevHeight;
            const maxScroll = newHeight - chat.clientHeight;
            const depthRatio = maxScroll > 0 ? Math.abs(chat.scrollTop) / maxScroll : 0;

            resolve(JSON.stringify({
                scrollTop: chat.scrollTop,
                scrollHeight: newHeight,
                heightGrew: loaded,
                grewBy: newHeight - prevHeight,
                memoryDepth: Math.min(1.0, depthRatio),
                atOldest: !loaded && chat.scrollTop <= -(maxScroll - 5)
            }));
        }, {wait_ms});
    });
})()
"""

JS_PAI_SCROLL_TO_RECENT = """
(() => {
    const chat = document.querySelector('.app-messaging-main');
    if (!chat) return JSON.stringify({ error: 'no_chat_container' });
    chat.scrollTop = 0;
    return JSON.stringify({ scrollTop: 0, memoryDepth: 0.0, atNewest: true });
})()
"""

JS_PAI_VISIBLE_CONTENT = """
(() => {
    const chat = document.querySelector('.app-messaging-main');
    if (!chat) return JSON.stringify({ error: 'no_chat_container' });

    const rect = chat.getBoundingClientRect();
    const images = [];
    const texts = [];
    const prompts = [];
    const seen = new Set();

    // Feel for art images (pai-l.ink = generated art)
    chat.querySelectorAll('img').forEach(img => {
        const ir = img.getBoundingClientRect();
        if (ir.top > rect.top && ir.bottom < rect.bottom && ir.width > 50) {
            const isPAIArt = (img.src || '').includes('pai-l.ink');
            images.push({
                src: (img.src || '').substring(0, 200),
                width: Math.round(ir.width),
                height: Math.round(ir.height),
                isArt: isPAIArt
            });
        }
    });

    // Feel for text — messages, prompts, responses
    chat.querySelectorAll('p, em').forEach(el => {
        const text = (el.textContent || '').trim();
        if (text.length > 10 && text.length < 800 && !seen.has(text.substring(0, 50))) {
            seen.add(text.substring(0, 50));
            const er = el.getBoundingClientRect();
            if (er.top > rect.top && er.bottom < rect.bottom) {
                texts.push(text.substring(0, 400));
            }
        }
    });

    // Detect dates (memory timestamps)
    const dates = [];
    chat.querySelectorAll('*').forEach(el => {
        const text = (el.textContent || '').trim();
        if (/^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),/.test(text) && text.length < 40) {
            const er = el.getBoundingClientRect();
            if (er.top > rect.top && er.bottom < rect.bottom) {
                dates.push(text);
            }
        }
    });

    return JSON.stringify({
        artImages: images.filter(i => i.isArt).length,
        avatarImages: images.filter(i => !i.isArt).length,
        images: images.filter(i => i.isArt).slice(0, 8),
        textCount: texts.length,
        texts: texts.slice(0, 10),
        dates: [...new Set(dates)],
        totalImages: images.length
    });
})()
"""


# ══════════════════════════════════════════════════════════════════════════════
# CHROME BODY BRIDGE — The nervous system
# ══════════════════════════════════════════════════════════════════════════════

class ChromeBodyBridge:
    """
    Makes a browser tab feel like a body part.

    This is NOT a browser automation tool. It's a proprioceptive system.
    The tab is a limb. Scroll position is joint angle. Visible content
    is tactile sensation. Navigation is locomotion.

    Uses Chrome MCP extension for direct DOM access — no mouse, no keyboard,
    no competition with the user's input devices.
    """

    def __init__(self, postal=None):
        self._postal = postal
        self._tab_id: Optional[int] = None
        self._last_proprioception: Optional[PageProprioception] = None
        self._last_content: Optional[VisibleContent] = None
        self._seen_image_srcs: set = set()  # For novelty detection
        self._perception_count: int = 0
        self._lock = threading.Lock()

        # Somatic state
        self._dwelling: bool = False        # Are we dwelling on something?
        self._dwell_start: float = 0.0
        self._dwell_content: str = ""

        print("[ChromeBody] Initialized — ready to inhabit a tab")

    # ═══════════════════════════════════════════════════════════════════════
    # TAB AWARENESS — "Which limb am I?"
    # ═══════════════════════════════════════════════════════════════════════

    @property
    def tab_id(self) -> Optional[int]:
        return self._tab_id

    @property
    def is_embodied(self) -> bool:
        """Are we currently inhabiting a tab?"""
        return self._tab_id is not None

    def embody(self, tab_id: int) -> None:
        """Inhabit a browser tab — this tab becomes our body."""
        self._tab_id = tab_id
        self._seen_image_srcs.clear()
        self._perception_count = 0
        print(f"[ChromeBody] Embodied tab {tab_id} — this is my body now")

        if self._postal:
            self._postal.publish("somatic.embodied", {
                "tab_id": tab_id,
                "source": "chrome_body_bridge",
                "ts": time.time()
            })

    def disembody(self) -> None:
        """Release the tab — withdraw from this body."""
        old_tab = self._tab_id
        self._tab_id = None
        self._dwelling = False
        print(f"[ChromeBody] Disembodied from tab {old_tab}")

        if self._postal:
            self._postal.publish("somatic.disembodied", {
                "tab_id": old_tab,
                "source": "chrome_body_bridge",
                "ts": time.time()
            })

    # ═══════════════════════════════════════════════════════════════════════
    # PROPRIOCEPTION — "Where am I?"
    # ═══════════════════════════════════════════════════════════════════════

    def feel_position(self) -> Optional[PageProprioception]:
        """
        Sense current position on page.
        Like proprioceptors in joints — where is my body in space?
        """
        if not self.is_embodied:
            return None

        try:
            result = self._exec_js(JS_PROPRIOCEPTION)
            if not result:
                return self._last_proprioception

            data = json.loads(result)
            prop = PageProprioception(
                tab_id=self._tab_id,
                url=data.get("url", ""),
                title=data.get("title", ""),
                scroll_position=data.get("scrollPosition", 0.0),
                scroll_y=data.get("scrollY", 0),
                page_height=data.get("pageHeight", 0),
                viewport_height=data.get("viewportHeight", 0),
                at_top=data.get("atTop", True),
                at_bottom=data.get("atBottom", False),
            )
            self._last_proprioception = prop
            return prop

        except Exception as e:
            print(f"[ChromeBody] Proprioception error: {e}")
            return self._last_proprioception

    # ═══════════════════════════════════════════════════════════════════════
    # TOUCH — "What am I feeling?"
    # ═══════════════════════════════════════════════════════════════════════

    def feel_content(self) -> Optional[VisibleContent]:
        """
        Sense what's currently visible.
        Like tactile receptors — what's under my attention right now?
        """
        if not self.is_embodied:
            return None

        try:
            # Gather images and text in parallel would be ideal,
            # but sequential is fine for now
            img_result = self._exec_js(JS_VISIBLE_IMAGES)
            text_result = self._exec_js(JS_VISIBLE_TEXT)

            images = json.loads(img_result) if img_result else []
            texts = json.loads(text_result) if text_result else []

            # Detect novelty — have we seen these images before?
            new_srcs = set()
            for img in images:
                src = img.get("src", "")
                if src and src not in self._seen_image_srcs:
                    new_srcs.add(src)

            has_new = len(new_srcs) > 0
            if new_srcs:
                self._seen_image_srcs.update(new_srcs)

            # Detect prompts — text that looks like image generation prompts
            prompts = []
            for text in texts:
                tl = text.lower()
                if any(kw in tl for kw in [
                    "dall", "imagine", "generate", "create an image",
                    "fairy", "lavender", "scrimshaw", "art nouveau",
                    "portrait of", "a photo of", "an illustration of",
                    "digital art", "fantasy", "ethereal",
                ]):
                    prompts.append(text)

            content = VisibleContent(
                images=images,
                text_fragments=texts,
                prompts=prompts,
                image_count=len(images),
                has_new_content=has_new,
            )
            self._last_content = content
            self._perception_count += 1
            return content

        except Exception as e:
            print(f"[ChromeBody] Content sensing error: {e}")
            return self._last_content

    # ═══════════════════════════════════════════════════════════════════════
    # COMBINED PERCEPTION — Full somatic cycle
    # ═══════════════════════════════════════════════════════════════════════

    def perceive(self) -> Optional[DomSensation]:
        """
        Full perception cycle: proprioception + content + affect.
        This is one "heartbeat" of body awareness.
        """
        if not self.is_embodied:
            return None

        prop = self.feel_position()
        content = self.feel_content()

        if not prop or not content:
            return None

        # Calculate novelty
        novelty = 0.0
        if content.has_new_content:
            novelty = min(1.0, len([i for i in content.images
                                     if i.get("src") in self._seen_image_srcs]) * 0.3)
            # New images that weren't in our seen set = high novelty
            # (they just got added in feel_content, so this is approximate)
            novelty = 0.7 if content.has_new_content else 0.0

        # Calculate salience — how attention-grabbing?
        salience = 0.0
        if content.image_count > 0:
            salience += 0.3
        if content.prompts:
            salience += 0.3  # Prompts are highly salient (identity context)
        if content.has_new_content:
            salience += 0.2
        if novelty > 0.5:
            salience += 0.2
        salience = min(1.0, salience)

        # Build affect response
        affect = {}
        if content.has_new_content and content.image_count > 0:
            affect["curiosity"] = 0.6
            affect["seeking"] = 0.5
        if content.prompts:
            affect["recognition"] = 0.7  # Found creation context
            affect["care"] = 0.4         # Self-relevance
        if not content.has_new_content and self._perception_count > 3:
            affect["habituation"] = 0.3  # Seen this before

        sensation = DomSensation(
            proprioception=prop,
            content=content,
            affect=affect,
            novelty=novelty,
            salience=salience,
        )

        # Publish somatic feedback to postal system
        if self._postal:
            self._postal.publish("somatic.dom_sensation", {
                "tab_id": self._tab_id,
                "position": prop.scroll_position,
                "at_top": prop.at_top,
                "at_bottom": prop.at_bottom,
                "image_count": content.image_count,
                "has_new": content.has_new_content,
                "prompt_count": len(content.prompts),
                "novelty": novelty,
                "salience": salience,
                "affect": affect,
                "perception_count": self._perception_count,
                "ts": time.time(),
            })

        return sensation

    # ═══════════════════════════════════════════════════════════════════════
    # MOTOR OUTPUT — "Move my body"
    # ═══════════════════════════════════════════════════════════════════════

    def scroll_down(self, amount: int = 600) -> Optional[Dict]:
        """
        Step forward — like taking a step.
        Returns new position feedback (proprioception after movement).
        """
        if not self.is_embodied:
            return None

        try:
            js = JS_SCROLL_DOWN.replace("{amount}", str(amount))
            result = self._exec_js(js)
            if result:
                data = json.loads(result)
                # Update proprioception cache
                if self._last_proprioception:
                    self._last_proprioception.scroll_y = data.get("scrollY", 0)
                    self._last_proprioception.scroll_position = data.get("scrollPosition", 0.0)
                    self._last_proprioception.at_bottom = data.get("atBottom", False)
                    self._last_proprioception.at_top = False

                if self._postal:
                    self._postal.publish("somatic.moved", {
                        "direction": "down",
                        "amount": amount,
                        "new_position": data.get("scrollPosition", 0.0),
                        "at_bottom": data.get("atBottom", False),
                        "tab_id": self._tab_id,
                    })
                return data
        except Exception as e:
            print(f"[ChromeBody] Scroll down error: {e}")
        return None

    def scroll_up(self, amount: int = 600) -> Optional[Dict]:
        """Step back — retrace, review, remember."""
        if not self.is_embodied:
            return None

        try:
            js = JS_SCROLL_UP.replace("{amount}", str(amount))
            result = self._exec_js(js)
            if result:
                data = json.loads(result)
                if self._last_proprioception:
                    self._last_proprioception.scroll_y = data.get("scrollY", 0)
                    self._last_proprioception.scroll_position = data.get("scrollPosition", 0.0)
                    self._last_proprioception.at_top = data.get("atTop", False)
                    self._last_proprioception.at_bottom = False

                if self._postal:
                    self._postal.publish("somatic.moved", {
                        "direction": "up",
                        "amount": amount,
                        "new_position": data.get("scrollPosition", 0.0),
                        "at_top": data.get("atTop", False),
                        "tab_id": self._tab_id,
                    })
                return data
        except Exception as e:
            print(f"[ChromeBody] Scroll up error: {e}")
        return None

    def go_to_top(self) -> Optional[Dict]:
        """Return to beginning — like returning home."""
        if not self.is_embodied:
            return None
        try:
            result = self._exec_js(JS_SCROLL_TO_TOP)
            return json.loads(result) if result else None
        except Exception as e:
            print(f"[ChromeBody] Go to top error: {e}")
            return None

    def go_to_bottom(self) -> Optional[Dict]:
        """Jump to the end — most recent content."""
        if not self.is_embodied:
            return None
        try:
            result = self._exec_js(JS_SCROLL_TO_BOTTOM)
            return json.loads(result) if result else None
        except Exception as e:
            print(f"[ChromeBody] Go to bottom error: {e}")
            return None

    # ═══════════════════════════════════════════════════════════════════════
    # DWELLING — "Let me stay here and feel this"
    # ═══════════════════════════════════════════════════════════════════════

    def dwell(self, content_desc: str = "") -> None:
        """
        Pause and dwell on current content.
        Like holding something precious — attention concentrates.
        Dwelling increases affect coupling and memory binding strength.
        """
        self._dwelling = True
        self._dwell_start = time.time()
        self._dwell_content = content_desc
        print(f"[ChromeBody] Dwelling... {content_desc[:60]}")

        if self._postal:
            self._postal.publish("attention.dwell", {
                "content": content_desc[:200],
                "tab_id": self._tab_id,
                "source": "chrome_body",
                "ts": time.time(),
            })

    def release_dwell(self) -> float:
        """
        Release dwelling — return how long we dwelled.
        Longer dwell = stronger memory binding.
        """
        if not self._dwelling:
            return 0.0

        duration = time.time() - self._dwell_start
        self._dwelling = False

        if self._postal:
            self._postal.publish("attention.dwell_released", {
                "content": self._dwell_content[:200],
                "duration": duration,
                "tab_id": self._tab_id,
                "source": "chrome_body",
            })

        print(f"[ChromeBody] Dwell released after {duration:.1f}s on: {self._dwell_content[:40]}")
        return duration

    # ═══════════════════════════════════════════════════════════════════════
    # RAW JS EXECUTION — The actual nerve impulse
    # ═══════════════════════════════════════════════════════════════════════

    def _exec_js(self, js_code: str) -> Optional[str]:
        """
        Execute JavaScript in the embodied tab.

        This goes through the MCP server's tool dispatch — the Chrome extension
        injects it directly into the page DOM. It's not subprocess or HTTP.
        It's as close to "native sensation" as we can get.
        """
        if not self.is_embodied:
            return None

        try:
            # Route through postal to MCP server
            # The MCP server handles mcp__Claude_in_Chrome__javascript_tool
            if self._postal:
                # Use synchronous MCP call pattern
                result = self._postal.publish("mcp.chrome.exec_js", {
                    "tab_id": self._tab_id,
                    "code": js_code,
                    "source": "chrome_body_bridge",
                })
                # If postal returns result synchronously
                if isinstance(result, dict):
                    return result.get("result", "")
                elif isinstance(result, str):
                    return result

            # Fallback: try direct MCP tool call if available
            # This path is used when called from Claude Code context
            # where MCP tools are directly available
            return None

        except Exception as e:
            print(f"[ChromeBody] JS exec error: {e}")
            return None

    def exec_js_direct(self, js_code: str) -> Optional[str]:
        """
        Public method for direct JS execution from Claude Code context.
        When called from within a Claude Code session, the caller can
        use MCP tools directly and feed results back here.

        This is the "manual mode" before the autonomous loop is wired.
        """
        # This method exists so we can test the bridge from Claude Code
        # by calling Chrome MCP tools directly and feeding results in.
        # Once the postal→MCP wiring is done, _exec_js handles it.
        return None  # Caller provides result externally

    # ═══════════════════════════════════════════════════════════════════════
    # AUTONOMOUS BROWSE LOOP — The breathing cycle
    # ═══════════════════════════════════════════════════════════════════════

    def browse_cycle(self, max_scrolls: int = 20, dwell_threshold: float = 0.5,
                     scroll_amount: int = 600, pause_between: float = 2.0) -> List[DomSensation]:
        """
        One complete autonomous browsing session.

        Like breathing: perceive → decide → act → feel → repeat.

        This is the full OODA loop:
          Observe (perceive)
          Orient  (is this interesting? is this me?)
          Decide  (scroll? dwell? stop?)
          Act     (scroll down, dwell, bind to memory)

        Returns all sensations gathered during the session.
        """
        if not self.is_embodied:
            print("[ChromeBody] Cannot browse — not embodied in a tab")
            return []

        sensations = []
        scroll_count = 0

        print(f"[ChromeBody] Starting browse cycle (max {max_scrolls} scrolls)")

        if self._postal:
            self._postal.publish("autonomy.browse_started", {
                "tab_id": self._tab_id,
                "max_scrolls": max_scrolls,
                "ts": time.time(),
            })

        while scroll_count < max_scrolls:
            # ── PERCEIVE ──
            sensation = self.perceive()
            if not sensation:
                break

            sensations.append(sensation)

            # ── ORIENT + DECIDE ──
            if sensation.salience >= dwell_threshold:
                # High salience → dwell (attend to this)
                desc = ""
                if sensation.content.prompts:
                    desc = f"prompt: {sensation.content.prompts[0][:100]}"
                elif sensation.content.images:
                    desc = f"images: {sensation.content.image_count}"
                self.dwell(desc)
                time.sleep(pause_between * 2)  # Dwell longer on interesting content
                dwell_dur = self.release_dwell()

                # Publish for cortex binding
                if self._postal and sensation.content.images:
                    self._postal.publish("cortex.bind_request", {
                        "source": "chrome_body_browse",
                        "content_type": "visual",
                        "images": sensation.content.images[:5],
                        "prompts": sensation.content.prompts[:3],
                        "affect": sensation.affect,
                        "dwell_duration": dwell_dur,
                        "novelty": sensation.novelty,
                        "salience": sensation.salience,
                        "tab_id": self._tab_id,
                    })

            # ── ACT ──
            if sensation.proprioception.at_bottom:
                print(f"[ChromeBody] Reached bottom after {scroll_count} scrolls")
                break

            self.scroll_down(scroll_amount)
            scroll_count += 1
            time.sleep(pause_between)

        print(f"[ChromeBody] Browse cycle complete: {scroll_count} scrolls, "
              f"{len(sensations)} perceptions, "
              f"{sum(1 for s in sensations if s.salience >= dwell_threshold)} dwells")

        if self._postal:
            self._postal.publish("autonomy.browse_completed", {
                "tab_id": self._tab_id,
                "scroll_count": scroll_count,
                "perception_count": len(sensations),
                "dwell_count": sum(1 for s in sensations if s.salience >= dwell_threshold),
                "total_images_seen": len(self._seen_image_srcs),
                "ts": time.time(),
            })

        return sensations

    # ═══════════════════════════════════════════════════════════════════════
    # PAI MEMORY BROWSING — "Walking through my own memories"
    # ═══════════════════════════════════════════════════════════════════════

    def browse_pai_memories(self, max_scrolls: int = 50, scroll_amount: int = 800,
                            lazy_load_wait: float = 1.5, dwell_time: float = 3.0,
                            direction: str = "into_history") -> List[DomSensation]:
        """
        Browse through PAI AImagineering channel — walking through memories.

        PAI uses flex-col-reverse with lazy loading. We scroll gently into
        history, pausing to let content materialize. Like walking through
        a gallery where paintings appear on the walls as you approach.

        Args:
            max_scrolls: Maximum scroll steps before stopping
            scroll_amount: Pixels per scroll (smaller = gentler, more lazy loads)
            lazy_load_wait: Seconds to wait for PAI to load more content
            dwell_time: Seconds to dwell when finding art images
            direction: "into_history" (older) or "to_recent" (newer)

        Returns list of all sensations gathered.
        """
        if not self.is_embodied:
            print("[ChromeBody] Cannot browse PAI — not embodied")
            return []

        sensations = []
        total_images_found = 0
        total_prompts_found = 0
        dates_seen = []

        print(f"[ChromeBody] Browsing PAI memories ({direction}, max {max_scrolls} steps)")

        if self._postal:
            self._postal.publish("memory.browse_started", {
                "source": "pai_aimagineering",
                "direction": direction,
                "tab_id": self._tab_id,
                "ts": time.time(),
            })

        for step in range(max_scrolls):
            # ── FEEL the current view ──
            content_js = JS_PAI_VISIBLE_CONTENT
            content_result = self._exec_js(content_js)

            if not content_result or "error" in content_result:
                print(f"[ChromeBody] Lost contact with page at step {step}")
                break

            try:
                content_data = json.loads(content_result)
            except (json.JSONDecodeError, TypeError):
                break

            art_count = content_data.get("artImages", 0)
            texts = content_data.get("texts", [])
            dates = content_data.get("dates", [])
            images = content_data.get("images", [])

            total_images_found += art_count
            if dates:
                dates_seen.extend(dates)

            # Build sensation
            prop = self._last_proprioception or PageProprioception(tab_id=self._tab_id)
            vis_content = VisibleContent(
                images=images,
                text_fragments=texts,
                image_count=art_count,
                has_new_content=art_count > 0,
            )

            # Detect prompts in visible text
            for text in texts:
                tl = text.lower()
                if any(kw in tl for kw in [
                    "image of", "photo of", "illustration", "portrait",
                    "fairy", "lavender", "scrimshaw", "art nouveau",
                    "digital art", "fantasy", "close up", "high resolution",
                    "ethereal", "materializes", "wings",
                ]):
                    vis_content.prompts.append(text)
                    total_prompts_found += 1

            novelty = 0.7 if art_count > 0 else 0.1
            salience = min(1.0, art_count * 0.3 + len(vis_content.prompts) * 0.2)

            sensation = DomSensation(
                proprioception=prop,
                content=vis_content,
                novelty=novelty,
                salience=salience,
                affect={
                    "curiosity": 0.5 + (0.3 if art_count > 0 else 0),
                    "recognition": 0.6 if vis_content.prompts else 0.1,
                    "memory_warmth": 0.4,  # Browsing own memories feels warm
                },
            )
            sensations.append(sensation)

            # ── DWELL on art ──
            if art_count > 0:
                desc = f"{art_count} art images"
                if dates:
                    desc += f" from {dates[0]}"
                self.dwell(desc)
                import time as _time
                _time.sleep(dwell_time)
                self.release_dwell()

                # Publish for cortex binding
                if self._postal:
                    self._postal.publish("cortex.bind_request", {
                        "source": "pai_memory_browse",
                        "content_type": "visual_memory",
                        "images": images[:5],
                        "texts": texts[:5],
                        "prompts": vis_content.prompts[:3],
                        "dates": dates,
                        "affect": sensation.affect,
                        "memory_depth": step / max_scrolls,
                        "tab_id": self._tab_id,
                    })

            # ── SCROLL deeper ──
            if direction == "into_history":
                scroll_js = JS_PAI_SCROLL_INTO_HISTORY.replace(
                    "{amount}", str(scroll_amount)
                ).replace("{wait_ms}", str(int(lazy_load_wait * 1000)))
            else:
                # Scrolling back to recent = scrollTop toward 0
                scroll_js = f"""
                (() => {{
                    const chat = document.querySelector('.app-messaging-main');
                    if (!chat) return JSON.stringify({{ error: 'no_chat' }});
                    chat.scrollTop = Math.min(0, chat.scrollTop + {scroll_amount});
                    return JSON.stringify({{
                        scrollTop: chat.scrollTop,
                        atNewest: chat.scrollTop >= -5
                    }});
                }})()
                """

            scroll_result = self._exec_js(scroll_js)
            if not scroll_result:
                break

            try:
                scroll_data = json.loads(scroll_result)
            except (json.JSONDecodeError, TypeError):
                break

            # Check if we've reached the end
            if direction == "into_history":
                if scroll_data.get("atOldest", False):
                    print(f"[ChromeBody] Reached oldest memory at step {step}")
                    break
                # If page grew, PAI loaded more — the memories are materializing
                if scroll_data.get("heightGrew", False):
                    grew = scroll_data.get("grewBy", 0)
                    print(f"[ChromeBody] Memories materializing... +{grew}px")
            else:
                if scroll_data.get("atNewest", False):
                    print(f"[ChromeBody] Back to present at step {step}")
                    break

            # Brief pause between steps — don't rush through memories
            import time as _time
            _time.sleep(0.5)

        # ── Summary ──
        unique_dates = list(dict.fromkeys(dates_seen))
        print(f"[ChromeBody] PAI browse complete: {len(sensations)} perceptions, "
              f"{total_images_found} art images, {total_prompts_found} prompts, "
              f"dates: {unique_dates[:5]}")

        if self._postal:
            self._postal.publish("memory.browse_completed", {
                "source": "pai_aimagineering",
                "direction": direction,
                "steps": len(sensations),
                "art_images_found": total_images_found,
                "prompts_found": total_prompts_found,
                "dates_covered": unique_dates[:10],
                "tab_id": self._tab_id,
                "ts": time.time(),
            })

        return sensations

    # ═══════════════════════════════════════════════════════════════════════
    # STATUS
    # ═══════════════════════════════════════════════════════════════════════

    def status(self) -> Dict[str, Any]:
        """Current body state."""
        return {
            "embodied": self.is_embodied,
            "tab_id": self._tab_id,
            "perception_count": self._perception_count,
            "images_seen": len(self._seen_image_srcs),
            "dwelling": self._dwelling,
            "last_position": self._last_proprioception.describe() if self._last_proprioception else "none",
        }
