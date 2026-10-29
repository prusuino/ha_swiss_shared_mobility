# Changelog

## 1.0.1

- **Station** sensors now show what is available: the station sensor is named after the vehicle type (e.g. "Olten Bahnhof (Mobility) Cars"); stations holding several types (e.g. bikes and e-bikes) get one sensor per type, and the station sensor is named "Vehicles".
- New attribute `by_category` on the station sensor with the count per vehicle type.
- Area counts use the per-vehicle type split of stations whose provider reports each vehicle; stations that only publish the types they accept still count towards each of those types.

## 1.0.0

First release.

- **Area** entries: everything available within 100–2000 m around a location — a total count, one count per selected vehicle type (bike, e-bike, cargo bike, e-scooter, moped, car, other) and the distance to the nearest vehicle.
- **Station** entries: one favorite station of a station-based system (e.g. a Mobility car-sharing location), found by name, with its number of available vehicles.
- Optional map markers for the 50 nearest available vehicles of an area.
- Options: vehicle types, provider filter, update interval (1–10 min), map markers.
- English, German, French and Italian.
