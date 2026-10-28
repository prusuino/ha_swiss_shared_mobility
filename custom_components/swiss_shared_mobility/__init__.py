"""Swiss Shared Mobility (sharedmobility.ch) – Home Assistant integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_ENTRY_TYPE, ENTRY_TYPE_STATION
from .coordinator import AreaCoordinator, StationCoordinator

PLATFORMS_AREA = [Platform.SENSOR, Platform.GEO_LOCATION]
PLATFORMS_STATION = [Platform.SENSOR]


def _platforms(entry: ConfigEntry) -> list[Platform]:
    return PLATFORMS_STATION if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_STATION else PLATFORMS_AREA


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_STATION:
        coordinator = StationCoordinator(hass, entry)
    else:
        coordinator = AreaCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _platforms(entry))
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    # Categories, interval and map markers change entities -> full reload.
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, _platforms(entry))
