"""Domain error hierarchy for dessem_dashboard."""

from __future__ import annotations


class DashboardError(Exception):
    """Base of the dessem_dashboard error hierarchy."""


class ConfigError(DashboardError):
    """Raised when settings.json is missing, malformed, or fails validation."""
