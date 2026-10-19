"""Cross-platform Camoufox headless-mode detection.

Camoufox's `headless="virtual"` spins up a virtual X11 display via Xvfb so the
browser can render without a real screen - Xvfb only exists on Linux, and
asking for `"virtual"` on Windows raises `VirtualDisplayNotSupported`. Native
`headless=True` is patched by Camoufox to stay stealthy on every platform, so
it's the safe fallback wherever Xvfb isn't available (Windows dev, macOS).
"""

import sys


def camoufox_headless_mode() -> str | bool:
    """Pick the right `headless=` value for AsyncCamoufox on the current OS."""
    if sys.platform == "linux":
        return "virtual"
    return True
