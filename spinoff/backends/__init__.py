"""Terminal backend auto-detection.

Selects the best available terminal backend (cmux or WezTerm) based on
explicit configuration or runtime availability probing.
"""

from __future__ import annotations

from spinoff.backends.cmux import CmuxBackend
from spinoff.backends.wezterm import WezTermBackend
from spinoff.config import SpinoffConfig
from spinoff.terminal import TerminalBackend

__all__ = ["get_backend", "TerminalBackend"]

_BACKENDS: dict[str, type[TerminalBackend]] = {
    "cmux": CmuxBackend,
    "wezterm": WezTermBackend,
}

_DETECTION_ORDER: list[str] = ["cmux", "wezterm"]


def get_backend(config: SpinoffConfig | None = None) -> TerminalBackend:
    """Return a terminal backend, selecting by config or auto-detection.

    Resolution order:
        1. ``config.terminal_backend`` if explicitly set
        2. cmux if available (``cmux ping`` succeeds)
        3. WezTerm if available (``wezterm cli list-clients`` succeeds)
        4. Raise ``RuntimeError``
    """
    # 1. Explicit override from config
    if config is not None and config.terminal_backend:
        name = config.terminal_backend
        backend_cls = _BACKENDS.get(name)
        if backend_cls is None:
            valid = ", ".join(sorted(_BACKENDS))
            raise ValueError(
                f"Unknown terminal_backend {name!r}. "
                f"Valid options: {valid}"
            )
        return backend_cls()

    # 2-3. Auto-detect in preference order
    for name in _DETECTION_ORDER:
        backend = _BACKENDS[name]()
        if backend.available():
            return backend

    # 4. Nothing available
    raise RuntimeError(
        "No terminal backend available. "
        "Install cmux or WezTerm."
    )
