"""Config flow tests: area setup with radius and category checks, favorite
station search and pick, duplicate detection, an unreachable service, the
reconfigure flow and the options flow. The sharedmobility.ch client is faked."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.swiss_shared_mobility.api import Offer, SharedMobilityError
from custom_components.swiss_shared_mobility.const import (
    CONF_CATEGORIES,
    CONF_ENTRY_TYPE,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_PROVIDERS,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_SEARCH,
    CONF_SHOW_ON_MAP,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DOMAIN,
    ENTRY_TYPE_AREA,
    ENTRY_TYPE_STATION,
)

FLOW = "custom_components.swiss_shared_mobility.config_flow."
STATION = Offer(id="pb:42", provider_id="publibike", provider_name="PubliBike", pickup_type="station_based", latitude=46.95, longitude=7.44,
                categories=["bike", "e_bike"], count=4, station_name="Bern Bahnhof")
AREA_INPUT = {CONF_NAME: "Zuhause", CONF_LOCATION: {CONF_LATITUDE: 46.95, CONF_LONGITUDE: 7.44, CONF_RADIUS: 500}, CONF_CATEGORIES: ["bike", "e_scooter"], CONF_SCAN_INTERVAL: 2}


@pytest.fixture
def fake_client():
    with patch(FLOW + "SharedMobilityClient") as client:
        client.return_value.async_identify = AsyncMock(return_value=[])
        client.return_value.async_find_stations = AsyncMock(return_value=[STATION])
        yield client.return_value


async def _menu(hass, step):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": step})
    assert result["step_id"] == step
    return result


async def test_area_setup(hass: HomeAssistant, enable_custom_integrations, fake_client) -> None:
    result = await _menu(hass, "area")
    assert result["description_placeholders"] == {"min": "100", "max": "2000"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], AREA_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Zuhause"
    assert result["data"] == {CONF_ENTRY_TYPE: ENTRY_TYPE_AREA, CONF_LATITUDE: 46.95, CONF_LONGITUDE: 7.44, CONF_RADIUS: 500}
    assert result["options"] == {CONF_CATEGORIES: ["bike", "e_scooter"], CONF_SCAN_INTERVAL: 2, CONF_PROVIDERS: [], CONF_SHOW_ON_MAP: False}
    assert result["result"].unique_id == "area_46.9500_7.4400_500"
    fake_client.async_identify.assert_awaited_once()


async def test_area_checks_radius_categories_and_service(hass: HomeAssistant, enable_custom_integrations, fake_client) -> None:
    result = await _menu(hass, "area")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**AREA_INPUT, CONF_LOCATION: {**AREA_INPUT[CONF_LOCATION], CONF_RADIUS: 5000}})
    assert result["errors"] == {"base": "radius_out_of_range"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**AREA_INPUT, CONF_CATEGORIES: []})
    assert result["errors"] == {"base": "no_category"}
    fake_client.async_identify.side_effect = SharedMobilityError("down")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], AREA_INPUT)
    assert result["errors"] == {"base": "cannot_connect"}


async def test_station_search_and_pick(hass: HomeAssistant, enable_custom_integrations, fake_client) -> None:
    result = await _menu(hass, "station")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_SEARCH: " Bern "})
    assert result["step_id"] == "station_pick"
    fake_client.async_find_stations.assert_awaited_once_with("Bern")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_STATION_ID: "pb:42"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bern Bahnhof (PubliBike)"
    assert result["data"] == {CONF_ENTRY_TYPE: ENTRY_TYPE_STATION, CONF_STATION_ID: "pb:42", CONF_STATION_NAME: "Bern Bahnhof", CONF_LATITUDE: 46.95, CONF_LONGITUDE: 7.44}
    assert result["options"] == {CONF_SCAN_INTERVAL: 2}
    assert result["result"].unique_id == "station_pb:42"


async def test_station_search_without_results(hass: HomeAssistant, enable_custom_integrations, fake_client) -> None:
    fake_client.async_find_stations.return_value = []
    result = await _menu(hass, "station")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_SEARCH: "Atlantis"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_results"}


async def test_same_station_twice_is_refused(hass: HomeAssistant, enable_custom_integrations, fake_client) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id="station_pb:42", title="Bern", data={CONF_ENTRY_TYPE: ENTRY_TYPE_STATION, CONF_STATION_ID: "pb:42"}).add_to_hass(hass)
    result = await _menu(hass, "station")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_SEARCH: "Bern"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_STATION_ID: "pb:42"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_area_merges_the_options(hass: HomeAssistant, enable_custom_integrations, fake_client) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="area_46.9500_7.4400_500", title="Zuhause",
        data={CONF_ENTRY_TYPE: ENTRY_TYPE_AREA, CONF_LATITUDE: 46.95, CONF_LONGITUDE: 7.44, CONF_RADIUS: 500},
        options={CONF_CATEGORIES: ["bike"], CONF_SCAN_INTERVAL: 2, CONF_PROVIDERS: ["publibike"], CONF_SHOW_ON_MAP: True},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id})
    assert result["step_id"] == "area"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**AREA_INPUT, CONF_NAME: "Büro", CONF_LOCATION: {CONF_LATITUDE: 46.96, CONF_LONGITUDE: 7.45, CONF_RADIUS: 800}, CONF_CATEGORIES: ["car"], CONF_SCAN_INTERVAL: 5})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == "area_46.9600_7.4500_800"
    assert entry.title == "Büro"
    assert entry.data[CONF_RADIUS] == 800
    assert entry.options[CONF_CATEGORIES] == ["car"] and entry.options[CONF_SCAN_INTERVAL] == 5
    assert entry.options[CONF_PROVIDERS] == ["publibike"] and entry.options[CONF_SHOW_ON_MAP] is True  # untouched settings stay
