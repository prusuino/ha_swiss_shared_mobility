"""Repair notices: an unreachable sharedmobility.ch after three failed
refreshes, a favorite station not reported for about an hour, both
withdrawn when the data is back."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.swiss_shared_mobility.api import Offer, SharedMobilityError
from custom_components.swiss_shared_mobility.const import (
    CONF_ENTRY_TYPE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DOMAIN,
    ENTRY_TYPE_AREA,
    ENTRY_TYPE_STATION,
)
from custom_components.swiss_shared_mobility.coordinator import AreaCoordinator, StationCoordinator

STATION = Offer(id="pb:42", provider_id="publibike", provider_name="PubliBike", pickup_type="station_based", latitude=47.35, longitude=7.90,
                categories=["bike"], count=3, by_category={"bike": 3}, station_name="Olten Bahnhof")


def _issue(hass, key, entry):
    return ir.async_get(hass).async_get_issue(DOMAIN, f"{key}_{entry.entry_id}")


async def test_area_unreachable_after_three_refreshes(hass: HomeAssistant, enable_custom_integrations) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="area_x", title="Zuhause", data={CONF_ENTRY_TYPE: ENTRY_TYPE_AREA, CONF_LATITUDE: 47.35, CONF_LONGITUDE: 7.90, CONF_RADIUS: 500})
    entry.add_to_hass(hass)
    with patch("custom_components.swiss_shared_mobility.coordinator.SharedMobilityClient") as client:
        client.return_value.async_identify = AsyncMock(side_effect=SharedMobilityError("down"))
        coordinator = AreaCoordinator(hass, entry)
        for n in range(3):
            await coordinator.async_refresh()
            assert (_issue(hass, "unreachable", entry) is not None) is (n == 2)
        client.return_value.async_identify = AsyncMock(return_value=[STATION])
        await coordinator.async_refresh()
    assert coordinator.data.total == 3
    assert _issue(hass, "unreachable", entry) is None


async def test_station_missing_after_an_hour(hass: HomeAssistant, enable_custom_integrations) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="station_pb:42", title="Olten Bahnhof (PubliBike)",
                            data={CONF_ENTRY_TYPE: ENTRY_TYPE_STATION, CONF_STATION_ID: "pb:42", CONF_STATION_NAME: "Olten Bahnhof", CONF_LATITUDE: 47.35, CONF_LONGITUDE: 7.90})
    entry.add_to_hass(hass)
    with patch("custom_components.swiss_shared_mobility.coordinator.SharedMobilityClient") as client:
        client.return_value.async_identify = AsyncMock(return_value=[])
        coordinator = StationCoordinator(hass, entry)
        for n in range(30):
            await coordinator.async_refresh()
            assert coordinator.last_update_success is True
            assert (_issue(hass, "station_missing", entry) is not None) is (n == 29), f"after poll {n + 1}"
        assert _issue(hass, "station_missing", entry).translation_placeholders == {"station": "Olten Bahnhof (PubliBike)"}
        client.return_value.async_identify = AsyncMock(return_value=[STATION])
        await coordinator.async_refresh()
    assert coordinator.data.count == 3
    assert _issue(hass, "station_missing", entry) is None
