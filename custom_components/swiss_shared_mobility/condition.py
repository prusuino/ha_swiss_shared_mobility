"""Conditions for Swiss Shared Mobility.

"Vehicles are available" (at least N) and "Nearest vehicle is within" (a
distance in metres) for the automation editor's condition list. As with
the triggers, a target that expands to other entities is narrowed to the
sensors this integration created.

The condition platform API arrived in Home Assistant 2026.11. On an older
version the module still imports, but offers no conditions.
"""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import CONF_FOR, CONF_OPTIONS, CONF_TARGET
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import DOMAIN

CONF_LEVEL = "level"
CONF_METRES = "metres"

try:
    from homeassistant.helpers.automation import DomainSpec
    from homeassistant.helpers.condition import (
        ATTR_BEHAVIOR,
        BEHAVIOR_ALL,
        BEHAVIOR_ANY,
        Condition,
        EntityConditionBase,
    )
except ImportError:  # Home Assistant before 2026.11: no condition platform API
    CONDITIONS: dict = {}
else:
    COUNT_SPECS = {SENSOR_DOMAIN: DomainSpec()}
    DISTANCE_SPECS = {SENSOR_DOMAIN: DomainSpec(device_class=SensorDeviceClass.DISTANCE)}

    def _schema(option, validator):
        return vol.Schema(
            {
                vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
                vol.Required(CONF_OPTIONS, default={}): {
                    vol.Required(ATTR_BEHAVIOR, default=BEHAVIOR_ANY): vol.In([BEHAVIOR_ANY, BEHAVIOR_ALL]),
                    vol.Optional(CONF_FOR): cv.positive_time_period,
                    option: validator,
                },
            }
        )

    LEVEL_SCHEMA = _schema(vol.Optional(CONF_LEVEL, default=1), vol.All(vol.Coerce(int), vol.Range(min=1, max=100)))
    METRES_SCHEMA = _schema(vol.Optional(CONF_METRES, default=500), vol.All(vol.Coerce(float), vol.Range(min=1, max=50000)))

    def _own_entities(hass: HomeAssistant, entities: set[str], distance: bool) -> set[str]:
        registry = er.async_get(hass)
        kept: set[str] = set()
        for entity_id in entities:
            entry = registry.async_get(entity_id)
            if entry is None or entry.platform != DOMAIN:
                continue
            if (entry.unique_id or "").endswith("_nearest") == distance:
                kept.add(entity_id)
        return kept

    def _number(state: State) -> float | None:
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None

    class _VehiclesAvailable(EntityConditionBase):
        """At least the configured number of vehicles is available."""

        _domain_specs = COUNT_SPECS
        _schema = LEVEL_SCHEMA

        def __init__(self, hass: HomeAssistant, config) -> None:
            super().__init__(hass, config)
            self._level = int((config.options or {}).get(CONF_LEVEL) or 1)

        def entity_filter(self, entities: set[str]) -> set[str]:
            return _own_entities(self._hass, super().entity_filter(entities), distance=False)

        def is_valid_state(self, entity_state: State) -> bool:
            count = _number(entity_state)
            return count is not None and count >= self._level

    class _NearestVehicleWithin(EntityConditionBase):
        """The nearest vehicle is within the configured distance."""

        _domain_specs = DISTANCE_SPECS
        _schema = METRES_SCHEMA

        def __init__(self, hass: HomeAssistant, config) -> None:
            super().__init__(hass, config)
            self._metres = float((config.options or {}).get(CONF_METRES) or 500)

        def entity_filter(self, entities: set[str]) -> set[str]:
            return _own_entities(self._hass, super().entity_filter(entities), distance=True)

        def is_valid_state(self, entity_state: State) -> bool:
            distance = _number(entity_state)
            return distance is not None and distance <= self._metres

    CONDITIONS: dict[str, type[Condition]] = {
        "vehicles_available": _VehiclesAvailable,
        "nearest_vehicle_within": _NearestVehicleWithin,
    }


async def async_get_conditions(hass: HomeAssistant) -> dict:
    """Return the conditions of this integration."""
    return CONDITIONS
