"""Config flow for Swiss Shared Mobility.

Two kinds of entry, chosen in the first step:
- Area: everything available within a radius around a location.
- Station: one favorite station of a station-based system (e.g. a Mobility
  car-sharing location or a bike-sharing dock), found by name.
Both are repeatable — add the integration again for another area or station.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    LocationSelector,
    LocationSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .api import Offer, SharedMobilityClient, SharedMobilityError
from .const import (
    CATEGORIES,
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
    DEFAULT_CATEGORIES,
    DEFAULT_RADIUS_M,
    DEFAULT_SCAN_INTERVAL_MIN,
    DOMAIN,
    ENTRY_TYPE_AREA,
    ENTRY_TYPE_STATION,
    MAX_RADIUS_M,
    MAX_SCAN_INTERVAL_MIN,
    MIN_RADIUS_M,
    MIN_SCAN_INTERVAL_MIN,
)
from .coordinator import entry_value

_CATEGORY_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=CATEGORIES,
        multiple=True,
        mode=SelectSelectorMode.LIST,
        translation_key="categories",
    )
)
_INTERVAL_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=MIN_SCAN_INTERVAL_MIN,
        max=MAX_SCAN_INTERVAL_MIN,
        step=1,
        unit_of_measurement="min",
        mode=NumberSelectorMode.SLIDER,
    )
)


class SwissSharedMobilityConfigFlow(ConfigFlow, domain=DOMAIN):
    """Setup wizard: area or favorite station."""

    VERSION = 1

    def __init__(self) -> None:
        self._candidates: dict[str, Offer] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SwissSharedMobilityOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["area", "station"])

    async def async_step_area(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            location = user_input[CONF_LOCATION]
            lat = float(location[CONF_LATITUDE])
            lon = float(location[CONF_LONGITUDE])
            radius = int(location.get(CONF_RADIUS) or DEFAULT_RADIUS_M)
            if not MIN_RADIUS_M <= radius <= MAX_RADIUS_M:
                errors["base"] = "radius_out_of_range"
            elif not user_input[CONF_CATEGORIES]:
                errors["base"] = "no_category"
            else:
                await self.async_set_unique_id(f"area_{lat:.4f}_{lon:.4f}_{radius}")
                self._abort_if_unique_id_configured()
                client = SharedMobilityClient(async_get_clientsession(self.hass))
                try:
                    # One page is enough to prove the API answers.
                    await client.async_identify(lat, lon, radius, max_pages=1)
                except SharedMobilityError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data={
                            CONF_ENTRY_TYPE: ENTRY_TYPE_AREA,
                            CONF_LATITUDE: lat,
                            CONF_LONGITUDE: lon,
                            CONF_RADIUS: radius,
                        },
                        options={
                            CONF_CATEGORIES: user_input[CONF_CATEGORIES],
                            CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                            CONF_PROVIDERS: [],
                            CONF_SHOW_ON_MAP: False,
                        },
                    )

        default_location = {
            CONF_LATITUDE: self.hass.config.latitude,
            CONF_LONGITUDE: self.hass.config.longitude,
            CONF_RADIUS: DEFAULT_RADIUS_M,
        }
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=self.hass.config.location_name or "Home"): TextSelector(),
                vol.Required(CONF_LOCATION, default=default_location): LocationSelector(
                    LocationSelectorConfig(radius=True)
                ),
                vol.Required(CONF_CATEGORIES, default=DEFAULT_CATEGORIES): _CATEGORY_SELECTOR,
                vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL_MIN): _INTERVAL_SELECTOR,
            }
        )
        return self.async_show_form(
            step_id="area",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
            errors=errors,
            description_placeholders={"min": str(MIN_RADIUS_M), "max": str(MAX_RADIUS_M)},
        )

    async def async_step_station(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            client = SharedMobilityClient(async_get_clientsession(self.hass))
            try:
                found = await client.async_find_stations(user_input[CONF_SEARCH].strip())
            except SharedMobilityError:
                errors["base"] = "cannot_connect"
            else:
                if not found:
                    errors["base"] = "no_results"
                else:
                    self._candidates = {o.id: o for o in found}
                    return await self.async_step_station_pick()
        schema = vol.Schema({vol.Required(CONF_SEARCH): TextSelector()})
        return self.async_show_form(step_id="station", data_schema=schema, errors=errors)

    async def async_step_station_pick(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            offer = self._candidates[user_input[CONF_STATION_ID]]
            await self.async_set_unique_id(f"station_{offer.id}")
            self._abort_if_unique_id_configured()
            name = offer.station_name or offer.id
            return self.async_create_entry(
                title=f"{name} ({offer.provider_name})",
                data={
                    CONF_ENTRY_TYPE: ENTRY_TYPE_STATION,
                    CONF_STATION_ID: offer.id,
                    CONF_STATION_NAME: name,
                    CONF_LATITUDE: offer.latitude,
                    CONF_LONGITUDE: offer.longitude,
                },
                options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_MIN},
            )
        options = [
            SelectOptionDict(value=o.id, label=f"{o.station_name or o.id} – {o.provider_name}")
            for o in sorted(self._candidates.values(), key=lambda o: (o.station_name or "", o.provider_name))
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_STATION_ID): SelectSelector(
                    SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
                )
            }
        )
        return self.async_show_form(step_id="station_pick", data_schema=schema)


class SwissSharedMobilityOptionsFlow(OptionsFlow):
    """Change filters and polling without re-adding the entry."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self.config_entry
        is_station = entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_STATION
        errors: dict[str, str] = {}

        if user_input is not None:
            if not is_station and not user_input.get(CONF_CATEGORIES):
                errors["base"] = "no_category"
            else:
                if CONF_SCAN_INTERVAL in user_input:
                    user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
                return self.async_create_entry(data=user_input)

        interval = entry_value(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN)
        if is_station:
            schema = vol.Schema({vol.Required(CONF_SCAN_INTERVAL, default=interval): _INTERVAL_SELECTOR})
            return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

        # Provider choices: whatever operates in this area right now, plus any
        # already selected provider that happens to have nothing available.
        selected = list(entry_value(entry, CONF_PROVIDERS, []))
        providers: dict[str, str] = {}
        coordinator = getattr(entry, "runtime_data", None)
        if coordinator is not None and coordinator.data is not None:
            for offer in coordinator.data.all_offers:
                providers.setdefault(offer.provider_id, offer.provider_name or offer.provider_id)
        for provider_id in selected:
            providers.setdefault(provider_id, provider_id)
        provider_options = [
            SelectOptionDict(value=pid, label=name) for pid, name in sorted(providers.items(), key=lambda kv: kv[1])
        ]

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CATEGORIES, default=list(entry_value(entry, CONF_CATEGORIES, DEFAULT_CATEGORIES))
                ): _CATEGORY_SELECTOR,
                vol.Optional(CONF_PROVIDERS, default=selected): SelectSelector(
                    SelectSelectorConfig(options=provider_options, multiple=True, mode=SelectSelectorMode.DROPDOWN)
                ),
                vol.Required(CONF_SCAN_INTERVAL, default=interval): _INTERVAL_SELECTOR,
                vol.Required(
                    CONF_SHOW_ON_MAP, default=bool(entry_value(entry, CONF_SHOW_ON_MAP, False))
                ): BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
