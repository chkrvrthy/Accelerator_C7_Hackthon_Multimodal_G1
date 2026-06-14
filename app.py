"""Hugging Face Spaces entry point.

HF Spaces auto-runs the file named ``app.py`` at the repo root. The real
application lives in ``ui/app.py``; this module is a thin shim that
imports and starts it. Keep this file tiny — there is no logic here.

For local development run ``make run`` instead.
"""

from __future__ import annotations

from ui.app import main

if __name__ == "__main__":
    main()
