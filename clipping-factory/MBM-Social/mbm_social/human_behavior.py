"""
human_behavior -- shared anti-flagging helpers for all Playwright-based
publishers in MBM-Social. Provides human-like delays, cursor movement, and
typing so automated uploads mimic real human interaction patterns and avoid
YouTube / Instagram / TikTok bot detection.

Imported by: youtube_api_publisher.py, youtube_cdp_publisher.py
"""
from __future__ import annotations

import random
import time


def human_delay(min_seconds: float = 0.5, max_seconds: float = 3.0) -> None:
    """Sleep for a random human-like duration between min and max seconds."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def human_move_delay() -> None:
    """Short pause simulating human cursor movement (0.1–0.4s)."""
    time.sleep(random.uniform(0.1, 0.4))


def mouse_move_random(page, max_x: int = 1920, max_y: int = 1080, moves: int = 3) -> None:
    """Jitter mouse cursor in a human-like pattern across the viewport."""
    try:
        for _ in range(moves):
            x = random.randint(0, max_x)
            y = random.randint(0, max_y)
            page.mouse.move(x, y)
            human_move_delay()
    except Exception:
        pass


def type_human(page, text: str, **kwargs) -> None:
    """
    Type text with human-like per-key delays.

    Uses keyboard.type when possible (cross-platform). For very long text
    (e.g. descriptions), chunks are sent with small pauses to avoid pattern
    detection.
    """
    delay = kwargs.get("delay", None) or random.randint(50, 150)
    try:
        page.keyboard.type(text, delay=delay)
    except Exception:
        # Fallback: insert char by char
        for char in text:
            page.keyboard.insert_text(char)
            human_move_delay()


def apply_browser_fingerprints(page) -> None:
    """Strip automation-detection signals from the page via init scripts."""
    try:
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'permissions', {
                query: (Parameters) => Promise.resolve({ state: 'granted' })
            });
            window.matchMedia = window.matchMedia || function(query) {
                return { matches: false, media: query, onchange: null,
                         addListener: () => {}, removeListener: () => {} };
            };
        """)
    except Exception:
        pass


def random_viewport(page) -> None:
    """Set a randomized viewport size to diversify browser fingerprints."""
    try:
        width = random.choice([1366, 1440, 1536, 1920, 1280])
        height = random.choice([768, 864, 900, 1080, 800])
        page.set_viewport_size({"width": width, "height": height})
    except Exception:
        pass
