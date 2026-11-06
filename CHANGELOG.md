# Changelog

## 1.2.1 — 2026-11-06

- **Fixed: the diagnostics download could contain private values.** The entry's unique id went out unredacted: depending on the integration it holds the coordinates of the entry or, for a VKF entry of Swiss Hail Protection, the device serial. The text of the last error could also repeat a request URL. The unique id, the entry title and the entry's name and location fields are now redacted, and only the type of the last error is reported. If you have shared a diagnostics file from the previous version, consider it exposed.

## 1.2.0 — 2026-11-06

- **New: diagnostics download.** The entry menu under **Settings → Devices & services** offers *Download diagnostics*: the entry's configuration, what was last fetched and the current state of its entities, with coordinates, credentials and other personal values redacted and long lists cut. Attach it to an issue report.

## 1.1.1 — 2026-11-06

- Fixed: the manifest now declares the dependency on Home Assistant's `http` component, which serves the dashboard strategy file. Nothing changes at runtime (`http` is always loaded); it is what Home Assistant's manifest validation (hassfest) requires.

## 1.1.0 — 2026-11-06

- **New: a dashboard strategy.** The integration now serves `/swiss_shared_mobility_files/swiss-shared-mobility-dashboard.js`, a recipe Home Assistant renders in the browser: a map of the vehicles around your areas, one section per area (total, nearest vehicle, one tile per vehicle type) and one per favourite station — generated live from your config entries, nothing is written into your dashboard configuration. Register the file once as a Lovelace resource (JavaScript module), then pick *Swiss Shared Mobility* under **Settings → Dashboards → + Add dashboard**, or fill a single view of your own dashboard with `custom:swiss-shared-mobility`; `title`, `max_columns` and `map: false` can be set under `strategy:`. The README has the details.

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
