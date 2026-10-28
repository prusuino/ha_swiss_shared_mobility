"""Data update coordinators: one per config entry."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import Offer, SharedMobilityClient, SharedMobilityError
from .const import (
    CONF_CATEGORIES,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PROVIDERS,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_STATION_ID,
    DEFAULT_CATEGORIES,
    DEFAULT_SCAN_INTERVAL_MIN,
    DOMAIN,
    STATION_TOLERANCE_M,
)

_LOGGER = logging.getLogger(__name__)


def entry_value(entry: ConfigEntry, key: str, default=None):
    """Options override data, so the options flow can change settings."""
    if key in entry.options:
        return entry.options[key]
    return entry.data.get(key, default)


@dataclass
class AreaData:
    """Filtered offers within the area, nearest first."""

    offers: list[Offer] = field(default_factory=list)
    by_category: dict[str, int] = field(default_factory=dict)
    by_provider: dict[str, int] = field(default_factory=dict)
    total: int = 0
    # Everything in the radius before filtering (for the provider choice).
    all_offers: list[Offer] = field(default_factory=list)


def summarize(offers: list[Offer], categories: list[str], providers: list[str]) -> AreaData:
    """Keep available offers matching the filters and count them.

    A station holding several vehicle categories counts towards each selected
    category it offers; the total counts each available vehicle once.
    """
    data = AreaData(by_category={c: 0 for c in categories}, all_offers=offers)
    total_by_provider: dict[str, int] = {}
    for offer in offers:
        if offer.count <= 0:
            continue
        if providers and offer.provider_id not in providers:
            continue
        matching = [c for c in offer.categories if c in categories]
        if not matching:
            continue
        data.offers.append(offer)
        for category in matching:
            data.by_category[category] += offer.count
        data.total += offer.count
        name = offer.provider_name or offer.provider_id
        total_by_provider[name] = total_by_provider.get(name, 0) + offer.count
    data.by_provider = dict(sorted(total_by_provider.items(), key=lambda kv: -kv[1]))
    return data


class AreaCoordinator(DataUpdateCoordinator[AreaData]):
    """Polls all offers around a location."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        minutes = int(entry_value(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(minutes=minutes),
        )
        self.client = SharedMobilityClient(async_get_clientsession(hass))

    @property
    def categories(self) -> list[str]:
        return list(entry_value(self.config_entry, CONF_CATEGORIES, DEFAULT_CATEGORIES))

    async def _async_update_data(self) -> AreaData:
        entry = self.config_entry
        try:
            offers = await self.client.async_identify(
                entry.data[CONF_LATITUDE], entry.data[CONF_LONGITUDE], int(entry.data[CONF_RADIUS])
            )
        except SharedMobilityError as err:
            raise UpdateFailed(str(err)) from err
        return summarize(offers, self.categories, list(entry_value(entry, CONF_PROVIDERS, [])))


class StationCoordinator(DataUpdateCoordinator[Offer | None]):
    """Polls one favorite station; None while the station is not reported."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        minutes = int(entry_value(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(minutes=minutes),
        )
        self.client = SharedMobilityClient(async_get_clientsession(hass))

    async def _async_update_data(self) -> Offer | None:
        entry = self.config_entry
        try:
            offers = await self.client.async_identify(
                entry.data[CONF_LATITUDE], entry.data[CONF_LONGITUDE], STATION_TOLERANCE_M
            )
        except SharedMobilityError as err:
            raise UpdateFailed(str(err)) from err
        station_id = entry.data[CONF_STATION_ID]
        return next((o for o in offers if o.id == station_id), None)
