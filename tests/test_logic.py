"""Pure logic: feature parsing, vehicle categories, provider labels and the
area summary."""
from __future__ import annotations

from custom_components.swiss_shared_mobility.api import Offer, category_of, distance_m, parse_feature, provider_label
from custom_components.swiss_shared_mobility.coordinator import summarize


def _feature(fid, vtypes, pickup="free_floating", **attrs):
    return {"id": fid, "geometry": {"x": 7.44, "y": 46.95},
            "attributes": {"id": fid, "provider_id": "publibike", "provider_name": "PubliBike", "vehicle_type": vtypes, "pickup_type": pickup, **attrs}}


def test_categories_and_labels():
    assert category_of("E-Bike") == "e_bike"
    assert category_of("E-CargoBike") == "cargo_bike"
    assert category_of("Taxi") == "car"
    assert category_of("Hoverboard") == "other"
    assert provider_label("lime", "Lime City partners from Partners::RegionFeedMediator") == "Lime"
    assert provider_label("mobility_ch", "") == "Mobility Ch"
    assert provider_label("x", "Nextbike") == "Nextbike"
    assert round(distance_m(46.95, 7.44, 46.95, 7.45)) == 759


def test_free_floating_vehicle():
    offer = parse_feature(_feature("v1", "E-Scooter"), 46.95, 7.43)
    assert offer.categories == ["e_scooter"] and offer.count == 1 and offer.by_category == {"e_scooter": 1}
    assert offer.pickup_type == "free_floating"
    assert 740 < offer.distance_m < 770
    assert parse_feature(_feature("v2", ["E-Scooter"], vehicle_status_reserved=True)).count == 0
    assert parse_feature(_feature("v3", ["E-Scooter"], available=False)).count == 0
    assert parse_feature({"attributes": {}, "geometry": {}}) is None


def test_station_counts_and_split():
    # one vehicle_type per available vehicle: a known split
    known = parse_feature(_feature("s1", ["Bike", "Bike", "E-Bike"], "station_based", station_status_num_vehicle_available=3, station_name="Bahnhof"))
    assert known.count == 3 and known.by_category == {"bike": 2, "e_bike": 1} and known.station_name == "Bahnhof"
    # only the accepted types listed: no split
    unknown = parse_feature(_feature("s2", ["Bike", "E-Bike"], "station_based", station_status_num_vehicle_available=5))
    assert unknown.count == 5 and unknown.by_category == {}
    closed = parse_feature(_feature("s3", ["Bike"], "station_based", station_status_num_vehicle_available=4, station_status_renting=False))
    assert closed.count == 0
    assert "station_status_renting" in closed.extra


def test_summary_counts_each_vehicle_once():
    offers = [
        parse_feature(_feature("s1", ["Bike", "Bike", "E-Bike"], "station_based", station_status_num_vehicle_available=3)),
        parse_feature(_feature("s2", ["Bike", "E-Bike"], "station_based", station_status_num_vehicle_available=5)),
        parse_feature(_feature("v1", "E-Scooter", provider_id="lime", provider_name="Lime")),
        parse_feature(_feature("v2", "E-Scooter", provider_id="lime", provider_name="Lime", available=False)),
        parse_feature(_feature("c1", "Car", provider_id="mobility", provider_name="Mobility")),
    ]
    data = summarize(offers, ["bike", "e_bike", "e_scooter"], [])
    assert data.total == 3 + 5 + 1  # the car is not a selected category, the reserved scooter not available
    assert data.by_category == {"bike": 2 + 5, "e_bike": 1 + 5, "e_scooter": 1}  # unknown split counts towards each type
    assert data.by_provider == {"PubliBike": 8, "Lime": 1}
    assert len(data.offers) == 3 and len(data.all_offers) == 5
    only_lime = summarize(offers, ["e_scooter", "bike"], ["lime"])
    assert only_lime.total == 1 and only_lime.by_provider == {"Lime": 1}
