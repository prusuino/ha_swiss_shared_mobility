"""Serving of the bundled dashboard strategy.

The frontend/ directory of this integration is served under a static URL.
It holds a single file, the dashboard strategy, which the browser turns
into a dashboard at display time. Registering that file as a Lovelace
resource is deliberately left to the user: an integration must not write
into the Lovelace storage, which belongs to the user's dashboard
configuration. The README documents the one-time registration.

The directory is served with cache_headers=False, so a browser picks up an
updated file after a reload without a version query string on the URL.
"""
from __future__ import annotations

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

FRONTEND_URL_BASE = f"/{DOMAIN}_files"
STRATEGY_FILENAME = "swiss-shared-mobility-dashboard.js"
STRATEGY_URL = f"{FRONTEND_URL_BASE}/{STRATEGY_FILENAME}"
_SERVED_FLAG = f"{DOMAIN}_frontend_served"


async def async_serve_frontend(hass: HomeAssistant) -> None:
    """Serve the frontend/ directory under FRONTEND_URL_BASE.

    Idempotent per HA run; safe to call from every config entry setup."""
    if hass.data.get(_SERVED_FLAG):
        return
    # Claimed before the await so concurrent entry setups do not register
    # twice; released again below if the registration does not go through,
    # so the next entry setup retries instead of remembering a failure as done.
    hass.data[_SERVED_FLAG] = True

    frontend_dir = Path(__file__).parent / "frontend"
    registered = False
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(FRONTEND_URL_BASE, str(frontend_dir), cache_headers=False)]
        )
        registered = True
    finally:
        if not registered:
            hass.data.pop(_SERVED_FLAG, None)
