"""Diagnostics carry no distances: a handful of distances to public points
is enough to work out the place they were measured from."""
from __future__ import annotations

from homeassistant.core import State

from custom_components.swiss_shared_mobility.diagnostics import REDACTED, _compact, _entity_state


def test_distances_are_redacted_in_data_and_attributes() -> None:
    data = {"name": "A", "distance_km": 1.2, "nearest_distance_m": 80, "items": [{"distance": 5, "free": 3}], "latitude": 47.0}
    assert _compact(data) == {
        "name": "A",
        "distance_km": REDACTED,
        "nearest_distance_m": REDACTED,
        "items": [{"distance": REDACTED, "free": 3}],
        "latitude": REDACTED,
    }
    assert _compact({"distance_km": None}) == {"distance_km": None}


def test_distance_states_are_redacted() -> None:
    assert _entity_state("geo_location.marker", State("geo_location.marker", "2.4")) == REDACTED
    assert _entity_state("sensor.nearest", State("sensor.nearest", "120", {"device_class": "distance"})) == REDACTED
    assert _entity_state("sensor.nearest", State("sensor.nearest", "unavailable", {"device_class": "distance"})) == "unavailable"
    assert _entity_state("sensor.free", State("sensor.free", "12")) == "12"
    assert _entity_state("sensor.gone", None) is None
