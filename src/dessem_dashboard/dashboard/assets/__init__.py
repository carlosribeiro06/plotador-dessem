"""Package marker for the static dashboard assets shipped as package data.

This file exists for packaging, not for code. `[tool.setuptools.package-data]` in pyproject.toml
keys `dessem_dashboard.dashboard.assets`, but `[tool.setuptools.packages.find]` only discovers
directories that contain an `__init__.py`; without this marker the key resolves to nothing and a
built wheel ships no CSS, JavaScript or HTML template at all.
"""

from __future__ import annotations
