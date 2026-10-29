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
    CONF_STATION_CATEGORIES,
    CONF_STATION_ID,
    CONF_STATION_SPLIT,
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
        if offer.by_category:
            # Known split: only the selected types count.
            for category in matching:
                data.by_category[category] += offer.by_category.get(category, 0)
            data.total += sum(offer.by_category.get(c, 0) for c in matching)
        else:
            # Unknown split: the station counts towards each type it offers.
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
        offer = next((o for o in offers if o.id == station_id), None)
        if offer is not None and offer.count > 0:
            self._remember_categories(offer)
        return offer

    @property
    def categories(self) -> list[str]:
        """Vehicle categories seen at the station so far."""
        return list(self.config_entry.data.get(CONF_STATION_CATEGORIES, []))

    @property
    def split_known(self) -> bool:
        """Whether the station reports how its vehicles split by type."""
        return bool(self.config_entry.data.get(CONF_STATION_SPLIT, False))

    def _remember_categories(self, offer: Offer) -> None:
        # An empty station reports no vehicle types, so the categories are
        # collected over time. A new one updates the entry, which reloads it
        # with the matching sensors. Without a known split the station's own
        # type list counts.
        found = {c for c, n in offer.by_category.items() if n > 0} if offer.by_category else set(offer.categories)
        seen = sorted(set(self.categories) | found)
        # Sticky, so one odd poll does not reload the entry back and forth.
        split = self.split_known or bool(offer.by_category)
        if seen != self.categories or split != self.split_known:
            entry = self.config_entry
            self.hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_STATION_CATEGORIES: seen, CONF_STATION_SPLIT: split}
            )
