"""Installed Asterion application provider contracts."""

from asterion.applications.provider import (
    APPLICATION_PROVIDER_PROTOCOL,
    ApplicationProviderError,
    InstalledApplication,
    InstalledApplicationProvider,
    validate_installed_provider,
)

__all__ = (
    "APPLICATION_PROVIDER_PROTOCOL",
    "ApplicationProviderError",
    "InstalledApplication",
    "InstalledApplicationProvider",
    "validate_installed_provider",
)
