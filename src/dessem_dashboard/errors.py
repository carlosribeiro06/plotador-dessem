"""Domain error hierarchy for dessem_dashboard."""

from __future__ import annotations


class DashboardError(Exception):
    """Base of the dessem_dashboard error hierarchy."""


class ConfigError(DashboardError):
    """Raised when settings.json is missing, malformed, or fails validation."""


class SchemaError(DashboardError):
    """Raised when a DataFrame's columns do not match a declared schema."""


class DataFileError(DashboardError):
    """Raised when a synthesis data file is missing or cannot be read."""


class RegistryError(DashboardError):
    """Raised when a chart registry key is duplicate, unknown, or a spec fails validation."""
