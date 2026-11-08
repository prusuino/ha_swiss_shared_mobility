"""Triggers for Swiss Shared Mobility.

"Vehicle count crossed a threshold" and "Nearest vehicle crossed a
distance" for the automation editor's trigger list. The count trigger
watches the available-vehicle sensors of an area or a station (all
vehicles or one category), the distance trigger the nearest-vehicle sensor
of an area. A target that expands to other entities (a device, an area) is
narrowed to the ones this integration created.

The trigger platform API arrived in Home Assistant 2026.10. On an older
version the module still imports, but offers no triggers.
"""
from __future__ import annotations

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

try:
    from homeassistant.helpers.automation import DomainSpec
    from homeassistant.helpers.trigger import (
        Trigger,
        make_entity_numerical_state_crossed_threshold_trigger,
    )
except ImportError:  # Home Assistant before 2026.10: no trigger platform API
    TRIGGERS: dict = {}
else:
    COUNT_SPECS = {SENSOR_DOMAIN: DomainSpec()}
    DISTANCE_SPECS = {SENSOR_DOMAIN: DomainSpec(device_class=SensorDeviceClass.DISTANCE)}

    def _own_entities(hass: HomeAssistant, entities: set[str], distance: bool) -> set[str]:
        """Keep only entities created by this integration: the nearest-vehicle
        sensor (distance=True) or the vehicle-count sensors (distance=False)."""
        registry = er.async_get(hass)
        kept: set[str] = set()
        for entity_id in entities:
            entry = registry.async_get(entity_id)
            if entry is None or entry.platform != DOMAIN:
                continue
            if (entry.unique_id or "").endswith("_nearest") == distance:
                kept.add(entity_id)
        return kept

    class _VehicleCountCrossed(make_entity_numerical_state_crossed_threshold_trigger(COUNT_SPECS, None)):
        """The number of available vehicles crosses the configured threshold."""

        def entity_filter(self, entities: set[str]) -> set[str]:
            return _own_entities(self._hass, super().entity_filter(entities), distance=False)

    class _NearestVehicleCrossed(make_entity_numerical_state_crossed_threshold_trigger(DISTANCE_SPECS, "m")):
        """The distance to the nearest vehicle crosses the configured threshold."""

        def entity_filter(self, entities: set[str]) -> set[str]:
            return _own_entities(self._hass, super().entity_filter(entities), distance=True)

    TRIGGERS: dict[str, type[Trigger]] = {
        "vehicle_count_crossed_threshold": _VehicleCountCrossed,
        "nearest_vehicle_crossed_distance": _NearestVehicleCrossed,
    }


async def async_get_triggers(hass: HomeAssistant) -> dict:
    """Return the triggers of this integration."""
    return TRIGGERS
