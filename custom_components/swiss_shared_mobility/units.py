"""Distance in metres from a sensor state, whatever display unit the user
picked for the nearest-vehicle sensor (km, ft, mi ...). The trigger and the
condition take their distance option in metres, so the state is converted
before it is compared."""
from __future__ import annotations

from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfLength
from homeassistant.core import State
from homeassistant.util.unit_conversion import DistanceConverter


def state_in_metres(state: State) -> float | None:
    """The state as metres; None if it is not a number or not a distance."""
    try:
        value = float(state.state)
    except (TypeError, ValueError):
        return None
    unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) or UnitOfLength.METERS
    if unit == UnitOfLength.METERS:
        return value
    if unit not in DistanceConverter.VALID_UNITS:
        return None
    return DistanceConverter.convert(value, unit, UnitOfLength.METERS)
