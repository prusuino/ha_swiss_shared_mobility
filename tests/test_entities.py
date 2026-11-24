"""Entities and automation helpers: leftover sensors are removed at setup,
map markers are withdrawn while the service does not answer, a refresh is
bounded in time, a garbled count is skipped, an area name without letters
still gives a valid entity id, distances are compared in metres whatever the
display unit, and triggers/conditions appear only from the documented
Home Assistant versions."""
from __future__ import annotations

import asyncio
import importlib
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import const as ha_const
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfLength
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.swiss_shared_mobility import api as api_mod
from custom_components.swiss_shared_mobility.api import Offer, SharedMobilityClient, SharedMobilityError, parse_feature
from custom_components.swiss_shared_mobility.const import (
    CONF_CATEGORIES,
    CONF_ENTRY_TYPE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SHOW_ON_MAP,
    DOMAIN,
    ENTRY_TYPE_AREA,
    GEO_SOURCE,
)
from custom_components.swiss_shared_mobility.units import state_in_metres

CLIENT = "custom_components.swiss_shared_mobility.coordinator.SharedMobilityClient"


def _bike(oid: str, distance: float) -> Offer:
    return Offer(id=oid, provider_id="publibike", provider_name="PubliBike", pickup_type="free_floating",
                 latitude=46.95, longitude=7.44, categories=["bike"], count=1, by_category={"bike": 1},
                 distance_m=distance)


def _markers(hass: HomeAssistant) -> list[str]:
    return [s.entity_id for s in hass.states.async_all("geo_location") if s.attributes.get("source") == GEO_SOURCE]


def _area(title="Zuhause", **options) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN, unique_id="area_x", title=title,
        data={CONF_ENTRY_TYPE: ENTRY_TYPE_AREA, CONF_LATITUDE: 46.95, CONF_LONGITUDE: 7.44, CONF_RADIUS: 500},
        options={CONF_CATEGORIES: ["bike"], **options},
    )


async def test_leftover_sensor_removed_and_markers_follow_the_service(hass: HomeAssistant, enable_custom_integrations) -> None:
    entry = _area(**{CONF_SHOW_ON_MAP: True})
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    # e-scooters were selected before; their sensor row must not stay behind
    registry.async_get_or_create("sensor", DOMAIN, f"{entry.entry_id}_e_scooter_available", config_entry=entry,
                                 suggested_object_id="shared_mobility_zuhause_e_scooter_available")
    with patch(CLIENT) as client:
        client.return_value.async_identify = AsyncMock(return_value=[_bike("b1", 50), _bike("b2", 80)])
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        unique_ids = {e.unique_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)}
        assert f"{entry.entry_id}_e_scooter_available" not in unique_ids
        assert f"{entry.entry_id}_bike_available" in unique_ids
        assert hass.states.get("sensor.shared_mobility_zuhause_bike_available").state == "2"
        assert len(_markers(hass)) == 2

        coordinator = entry.runtime_data
        client.return_value.async_identify = AsyncMock(side_effect=SharedMobilityError("down"))
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert _markers(hass) == []  # no stale positions during the outage

        client.return_value.async_identify = AsyncMock(return_value=[_bike("b1", 50)])
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert len(_markers(hass)) == 1


async def test_title_without_letters_gives_a_valid_entity_id(hass: HomeAssistant, enable_custom_integrations) -> None:
    entry = _area(title="🚲🛴")
    entry.add_to_hass(hass)
    with patch(CLIENT) as client:
        client.return_value.async_identify = AsyncMock(return_value=[_bike("b1", 50)])
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    # slugify() falls back to "unknown" for a name without letters or digits
    assert hass.states.get("sensor.shared_mobility_unknown_available") is not None
    assert not [s for s in hass.states.async_entity_ids("sensor") if "__" in s]


async def test_refresh_is_bounded_in_time() -> None:
    client = SharedMobilityClient(session=None)

    async def slow(path, params):
        await asyncio.sleep(1)
        return []

    client._get = slow
    with patch.object(api_mod, "IDENTIFY_TIMEOUT_SECONDS", 0.05), pytest.raises(SharedMobilityError):
        await client.async_identify(46.95, 7.44, 500)


def test_garbled_station_count_is_skipped() -> None:
    feature = {"id": "s1", "geometry": {"x": 7.44, "y": 46.95},
               "attributes": {"id": "s1", "provider_id": "p", "provider_name": "P", "vehicle_type": ["Bike"],
                              "pickup_type": "station_based", "station_status_num_vehicle_available": "n/a"}}
    assert parse_feature(feature, 46.95, 7.44) is None


def test_distance_in_metres_whatever_the_unit() -> None:
    def state(value, unit):
        return State("sensor.x", value, {ATTR_UNIT_OF_MEASUREMENT: unit} if unit else {})

    assert state_in_metres(state("120", UnitOfLength.METERS)) == 120
    assert state_in_metres(state("0.4", UnitOfLength.KILOMETERS)) == pytest.approx(400)
    assert state_in_metres(state("1000", UnitOfLength.FEET)) == pytest.approx(304.8)
    assert state_in_metres(state("75", None)) == 75
    assert state_in_metres(state("unknown", UnitOfLength.METERS)) is None
    assert state_in_metres(state("3", "vehicles")) is None


@pytest.mark.parametrize(
    ("module", "first"),
    [("trigger", (2026, 10)), ("condition", (2026, 11))],
)
def test_automation_helpers_only_from_the_documented_version(module: str, first: tuple[int, int]) -> None:
    name = f"custom_components.swiss_shared_mobility.{module}"
    mod = importlib.import_module(name)
    table = "TRIGGERS" if module == "trigger" else "CONDITIONS"
    try:
        with patch.object(ha_const, "MAJOR_VERSION", first[0]), patch.object(ha_const, "MINOR_VERSION", first[1] - 1):
            assert getattr(importlib.reload(mod), table) == {}
        current = (ha_const.MAJOR_VERSION, ha_const.MINOR_VERSION)
        assert bool(getattr(importlib.reload(mod), table)) == (current >= first)
    finally:
        importlib.reload(mod)


def test_distance_trigger_converts_to_metres() -> None:
    from custom_components.swiss_shared_mobility import trigger

    if not trigger.TRIGGERS:
        pytest.skip("triggers need Home Assistant 2026.10")
    crossed = trigger.TRIGGERS["nearest_vehicle_crossed_distance"]
    km = State("sensor.shared_mobility_zuhause_nearest", "0.25", {ATTR_UNIT_OF_MEASUREMENT: UnitOfLength.KILOMETERS})
    assert crossed._get_tracked_value(None, km) == pytest.approx(250)
