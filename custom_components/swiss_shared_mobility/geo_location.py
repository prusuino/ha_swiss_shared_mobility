"""Map markers (geo_location) for the nearest available offers of an area.

Off by default (option "Show on map"). At most MAX_MAP_MARKERS markers per
area entry; the nearest win. Markers come and go with the vehicles.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import Offer
from .const import ATTRIBUTION, CATEGORY_ICONS, CONF_SHOW_ON_MAP, GEO_SOURCE, MAX_MAP_MARKERS
from .coordinator import AreaCoordinator, entry_value


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    if not entry_value(entry, CONF_SHOW_ON_MAP, False):
        return
    coordinator: AreaCoordinator = entry.runtime_data
    markers: dict[str, OfferMarker] = {}

    @callback
    def _sync() -> None:
        wanted = {o.id: o for o in coordinator.data.offers[:MAX_MAP_MARKERS]}
        for offer_id in list(markers):
            if offer_id not in wanted:
                hass.async_create_task(markers.pop(offer_id).async_remove())
        new = []
        for offer_id, offer in wanted.items():
            if offer_id in markers:
                markers[offer_id].update_offer(offer)
            else:
                markers[offer_id] = OfferMarker(offer)
                new.append(markers[offer_id])
        if new:
            async_add_entities(new)

    _sync()
    # Unloading the platform removes the remaining markers.
    entry.async_on_unload(coordinator.async_add_listener(_sync))


class OfferMarker(GeolocationEvent):
    _attr_should_poll = False
    _attr_source = GEO_SOURCE
    _attr_unit_of_measurement = UnitOfLength.METERS
    _attr_attribution = ATTRIBUTION

    def __init__(self, offer: Offer) -> None:
        self._offer = offer
        self._attr_unique_id = None  # transient: vehicles move, no registry entries

    def update_offer(self, offer: Offer) -> None:
        self._offer = offer
        if self.hass is not None:
            self.async_write_ha_state()

    @property
    def name(self) -> str:
        o = self._offer
        label = o.station_name or o.categories[0].replace("_", "-")
        return f"{o.provider_name} {label}"

    @property
    def icon(self) -> str | None:
        return CATEGORY_ICONS.get(self._offer.categories[0])

    @property
    def distance(self) -> float:
        return round(self._offer.distance_m)

    @property
    def latitude(self) -> float:
        return self._offer.latitude

    @property
    def longitude(self) -> float:
        return self._offer.longitude

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        o = self._offer
        return {"provider": o.provider_name, "categories": o.categories, "available": o.count}
