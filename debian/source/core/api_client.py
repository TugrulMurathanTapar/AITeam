"""Backward-compatible import shim for the legacy core.api_client module.

This project exposes the API client API via core.api_handler, but older tests and
callers still import from core.api_client. Keep both locations compatible by
re-exporting the canonical classes from the current implementation.
"""

from core.api_handler import (
    AIProvider,
    APIClient,
    APIClientError,
    EffortLevel,
    HealthResult,
    ProviderNotFoundError,
    ProviderRequestError,
    SchemaType,
)

__all__ = [
    "AIProvider",
    "APIClient",
    "APIClientError",
    "EffortLevel",
    "HealthResult",
    "ProviderNotFoundError",
    "ProviderRequestError",
    "SchemaType",
]
