"""Client for the sharedmobility.ch REST API (identify + find endpoints).

The API is open, needs no key and returns ESRI-JSON features. Station-based
systems come back as one feature per station (with the number of available
vehicles), free-floating systems as one feature per vehicle.
"""
from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from .const import (
    API_BASE,
    CATEGORY_VEHICLE_TYPES,
    FETCH_TIMEOUT_SECONDS,
    MAX_PAGES,
    PAGE_BATCH,
    PAGE_SIZE,
)

_TYPE_TO_CATEGORY = {
    vtype: category for category, vtypes in CATEGORY_VEHICLE_TYPES.items() for vtype in vtypes
}


class SharedMobilityError(Exception):
    """Raised when the API cannot be reached or returns garbage."""


@dataclass
class Offer:
    """One available offer: a free-floating vehicle or a station with vehicles."""

    id: str
    provider_id: str
    provider_name: str
    pickup_type: str
    latitude: float
    longitude: float
    categories: list[str]
    count: int
    station_name: str | None = None
    distance_m: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


def provider_label(provider_id: str, provider_name: str) -> str:
    """Readable provider name; some feeds publish internal names like
    'Lime City partners from Partners::RegionFeedMediator'."""
    if provider_name and "::" not in provider_name:
        return provider_name
    return provider_id.replace("_", " ").replace("-", " ").title() or provider_name


def category_of(vehicle_type: str) -> str:
    return _TYPE_TO_CATEGORY.get(vehicle_type, "other")


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def parse_feature(feature: dict[str, Any], lat: float | None = None, lon: float | None = None) -> Offer | None:
    """Turn one API feature into an Offer; None if it is not usable."""
    attrs = feature.get("attributes") or {}
    geom = feature.get("geometry") or {}
    try:
        f_lon = float(geom["x"])
        f_lat = float(geom["y"])
    except (KeyError, TypeError, ValueError):
        return None

    vtypes = attrs.get("vehicle_type") or []
    if isinstance(vtypes, str):
        vtypes = [vtypes]
    categories = sorted({category_of(v) for v in vtypes}) or ["other"]

    pickup_type = attrs.get("pickup_type") or "free_floating"
    if pickup_type == "station_based":
        renting = attrs.get("station_status_renting", True) is not False
        count = int(attrs.get("station_status_num_vehicle_available") or 0) if renting else 0
    else:
        usable = (
            attrs.get("available", True) is not False
            and not attrs.get("vehicle_status_disabled")
            and not attrs.get("vehicle_status_reserved")
        )
        count = 1 if usable else 0

    offer = Offer(
        id=str(attrs.get("id") or feature.get("id") or ""),
        provider_id=str(attrs.get("provider_id") or ""),
        provider_name=provider_label(str(attrs.get("provider_id") or ""), str(attrs.get("provider_name") or "")),
        pickup_type=pickup_type,
        latitude=f_lat,
        longitude=f_lon,
        categories=categories,
        count=count,
        station_name=attrs.get("station_name"),
        extra={
            k: attrs[k]
            for k in (
                "station_address",
                "station_status_renting",
                "station_status_returning",
                "provider_apps_ios_store_uri",
                "provider_apps_android_store_uri",
            )
            if k in attrs
        },
    )
    if lat is not None and lon is not None:
        offer.distance_m = distance_m(lat, lon, f_lat, f_lon)
    return offer


class SharedMobilityClient:
    """Thin async wrapper around the two endpoints the integration needs."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _get(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            async with asyncio.timeout(FETCH_TIMEOUT_SECONDS):
                resp = await self._session.get(f"{API_BASE}/{path}", params=params)
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SharedMobilityError(f"sharedmobility.ch request failed: {err}") from err
        except ValueError as err:
            raise SharedMobilityError("sharedmobility.ch returned invalid JSON") from err
        if not isinstance(data, list):
            raise SharedMobilityError("sharedmobility.ch returned an unexpected payload")
        return data

    async def async_identify(
        self, lat: float, lon: float, radius_m: int, max_pages: int = MAX_PAGES
    ) -> list[Offer]:
        """All offers within radius_m of the point, nearest first.

        One page takes the API 3-8 s (measured 2026-10-29), so pages are
        requested in small parallel batches until a short page shows the end.
        """
        params = {"Geometry": f"{lon},{lat}", "Tolerance": int(radius_m), "geometryFormat": "esrijson"}
        offers: list[Offer] = []
        seen: set[str] = set()
        page = 0
        done = False
        while not done and page < max_pages:
            batch = range(page, min(page + PAGE_BATCH, max_pages))
            results = await asyncio.gather(
                *(self._get("identify", {**params, "offset": p * PAGE_SIZE}) for p in batch)
            )
            for features in results:
                for feature in features:
                    offer = parse_feature(feature, lat, lon)
                    if offer is None or offer.id in seen:
                        continue
                    # The API's tolerance is a box-like search; keep the circle.
                    if offer.distance_m > radius_m:
                        continue
                    seen.add(offer.id)
                    offers.append(offer)
                if len(features) < PAGE_SIZE:
                    done = True
                    break
            page += len(batch)
        offers.sort(key=lambda o: o.distance_m)
        return offers

    async def async_find_stations(self, text: str) -> list[Offer]:
        """Full-text search on station names (station-based systems only)."""
        features = await self._get(
            "find",
            {
                "searchText": text,
                "searchField": "ch.bfe.sharedmobility.station.name",
                "offset": 0,
                "geometryFormat": "esrijson",
            },
        )
        result = []
        for feature in features:
            offer = parse_feature(feature)
            if offer is not None and offer.pickup_type == "station_based":
                result.append(offer)
        return result
