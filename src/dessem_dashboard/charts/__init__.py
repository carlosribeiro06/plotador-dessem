"""Chart registry package: mechanics plus the default catalogue, registered at import time."""

from __future__ import annotations

from dessem_dashboard.charts.specs import register_default_specs

register_default_specs()
