# Changelog

## 1.5.0 — 2026-11-09

- **Version on the service card.** The integration's version now appears on its service card under Settings → Devices & services, where the entities are listed.
- **Repair notices.** An unreachable sharedmobility.ch raises a notice under Settings → Repairs after three failed refreshes, a favorite station that is no longer reported after about an hour; both withdraw themselves. No change to entities or configuration.

## 1.4.0 — 2026-11-09

- **Quality scale Bronze.** The README gained removal instructions and a quality-scale section, and the manifest declares the **bronze** tier. A test suite (feature parsing, vehicle categories, station splits, area summary, config flow with area checks, station search, duplicate, unreachable service and reconfigure) runs on every push. No change to entities or configuration.

## 1.3.0 — 2026-11-08

- **New: reconfigure an entry in place.** The entry's menu under **Settings → Devices & services** now offers *Reconfigure*, which runs the same steps as the setup: a new name, location, radius, categories or interval for an area, another station for a station entry. The entry keeps its id and the user's options; entities of a selection that stays keep their ids and history, entities of one that is replaced are recreated. A change that would duplicate another entry is refused.
- **New: triggers and conditions in the automation editor** (Home Assistant 2026.10 / 2026.11 or newer). Triggers: *Vehicle count crossed a threshold* (available vehicles of an area or station, all or one category) and *Nearest vehicle crossed a distance*. Conditions: *Vehicles are available* (at least a minimum number) and *Nearest vehicle is within* (a distance in metres). In all four languages; on older versions the entries are simply not offered.

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
