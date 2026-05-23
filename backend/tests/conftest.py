"""Pytest config.

Adds backend/ to sys.path so `import app...` works whether pytest is run
from backend/ or from the repo root.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
