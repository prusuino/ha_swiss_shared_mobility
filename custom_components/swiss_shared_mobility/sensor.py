"""Sensors for Swiss Shared Mobility."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    ATTRIBUTION,
    CATEGORY_ICONS,
    CONF_ENTRY_TYPE,
    CONF_RADIUS,
    CONF_STATION_NAME,
    DOMAIN,
    ENTRY_TYPE_STATION,
)
from .coordinator import AreaCoordinator, StationCoordinator


def device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="sharedmobility.ch",
        model="Station" if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_STATION else "Area",
        entry_type=DeviceEntryType.SERVICE,
        configuration_url="https://sharedmobility.ch",
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_STATION:
        entities: list[SensorEntity] = [StationAvailableSensor(coordinator, entry)]
        if len(coordinator.categories) > 1 and coordinator.split_known:
            entities += [StationCategorySensor(coordinator, entry, c) for c in coordinator.categories]
        async_add_entities(entities)
        return
    entities: list[SensorEntity] = [AreaTotalSensor(coordinator, entry), NearestSensor(coordinator, entry)]
    entities += [CategorySensor(coordinator, entry, category) for category in coordinator.categories]
    async_add_entities(entities)


class _Base(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = device_info(entry)
        # Entity IDs stay English whatever the UI language is.
        self.entity_id = f"sensor.shared_mobility_{slugify(entry.title)}_{key}"


class AreaTotalSensor(_Base):
    _attr_translation_key = "available"
    _attr_icon = "mdi:map-marker-radius"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: AreaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "available")
        self._radius = entry.data[CONF_RADIUS]

    @property
    def native_value(self) -> int:
        return self.coordinator.data.total

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        return {
            "radius_m": self._radius,
            "by_category": data.by_category,
            "by_provider": data.by_provider,
            "stations": sum(1 for o in data.offers if o.pickup_type == "station_based"),
        }


class CategorySensor(_Base):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: AreaCoordinator, entry: ConfigEntry, category: str) -> None:
        super().__init__(coordinator, entry, f"{category}_available")
        self._category = category
        self._attr_translation_key = f"{category}_available"
        self._attr_icon = CATEGORY_ICONS.get(category)

    @property
    def native_value(self) -> int:
        return self.coordinator.data.by_category.get(self._category, 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        nearest = next((o for o in self.coordinator.data.offers if self._category in o.categories), None)
        if nearest is None:
            return {}
        return {
            "nearest_distance_m": round(nearest.distance_m),
            "nearest_provider": nearest.provider_name,
        }


class NearestSensor(_Base):
    _attr_translation_key = "nearest"
    _attr_icon = "mdi:map-marker-distance"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.METERS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: AreaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "nearest")

    @property
    def native_value(self) -> float | None:
        offers = self.coordinator.data.offers
        return round(offers[0].distance_m) if offers else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        offers = self.coordinator.data.offers
        if not offers:
            return {}
        o = offers[0]
        attrs = {
            "provider": o.provider_name,
            "category": o.categories[0] if len(o.categories) == 1 else o.categories,
            "pickup_type": o.pickup_type,
            "latitude": o.latitude,
            "longitude": o.longitude,
        }
        if o.station_name:
            attrs["station"] = o.station_name
        return attrs


class StationAvailableSensor(_Base):
    """Vehicles at the station, named after the vehicle type it holds."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: StationCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "available")
        self._station_name = entry.data[CONF_STATION_NAME]
        categories = coordinator.categories
        if len(categories) == 1:
            self._attr_translation_key = f"station_{categories[0]}"
            self._attr_icon = CATEGORY_ICONS.get(categories[0])
        else:
            self._attr_translation_key = "station_vehicles"
            self._attr_icon = "mdi:map-marker-check"

    @property
    def available(self) -> bool:
        # The station only drops out of the feed when its provider stops
        # reporting it; show that as unavailable rather than as 0.
        return super().available and self.coordinator.data is not None

    @property
    def native_value(self) -> int | None:
        offer = self.coordinator.data
        return offer.count if offer else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        offer = self.coordinator.data
        attrs: dict[str, Any] = {"station": self._station_name}
        if offer is None:
            return attrs
        attrs.update(
            {
                "provider": offer.provider_name,
                "categories": offer.categories,
                "by_category": offer.by_category if offer.count else {c: 0 for c in self.coordinator.categories},
                "renting": offer.extra.get("station_status_renting", True),
                "returning": offer.extra.get("station_status_returning", True),
            }
        )
        if "station_address" in offer.extra:
            attrs["address"] = offer.extra["station_address"]
        return attrs


class StationCategorySensor(_Base):
    """Vehicles of one category at a station holding several categories."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: StationCoordinator, entry: ConfigEntry, category: str) -> None:
        super().__init__(coordinator, entry, f"{category}_available")
        self._category = category
        self._attr_translation_key = f"{category}_available"
        self._attr_icon = CATEGORY_ICONS.get(category)

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data is not None

    @property
    def native_value(self) -> int | None:
        offer = self.coordinator.data
        if offer is None:
            return None
        return offer.by_category.get(self._category, 0)
