"""Cross-platform subprocess options for the local Human Interface."""

from __future__ import annotations

import os
import subprocess


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def hidden_subprocess_kwargs() -> dict[str, int]:
    """Prevent helper processes from creating a visible Windows console."""
    if os.name == "nt":
        return {"creationflags": CREATE_NO_WINDOW}
    return {}
