"""Constants for the Swiss Shared Mobility integration."""
DOMAIN = "swiss_shared_mobility"

ATTRIBUTION = "Data: sharedmobility.ch (Swiss Federal Office of Energy SFOE)"

API_BASE = "https://api.sharedmobility.ch/v1/sharedmobility"
FETCH_TIMEOUT_SECONDS = 30

# The identify endpoint returns 50 features per page. A dense city centre can
# exceed 150 vehicles within 300 m (measured at Zurich HB, 2026-10-29), so the
# fetch pages through the results — capped, so a large radius in a big city
# can never turn into an unbounded number of requests per poll.
PAGE_SIZE = 50
MAX_PAGES = 30
PAGE_BATCH = 4

CONF_ENTRY_TYPE = "entry_type"
ENTRY_TYPE_AREA = "area"
ENTRY_TYPE_STATION = "station"

CONF_NAME = "name"
CONF_LOCATION = "location"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_RADIUS = "radius"
CONF_CATEGORIES = "categories"
CONF_PROVIDERS = "providers"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_SHOW_ON_MAP = "show_on_map"

CONF_STATION_ID = "station_id"
CONF_STATION_NAME = "station_name"
CONF_SEARCH = "search"

DEFAULT_RADIUS_M = 500
MIN_RADIUS_M = 100
MAX_RADIUS_M = 2000
DEFAULT_SCAN_INTERVAL_MIN = 2
MIN_SCAN_INTERVAL_MIN = 1
MAX_SCAN_INTERVAL_MIN = 10

# Station favorites are re-read with a small identify query around the
# station's own coordinates.
STATION_TOLERANCE_M = 25

# Map markers per area entry: the nearest vehicles win, the count sensors
# still reflect everything in the radius.
MAX_MAP_MARKERS = 50

# sharedmobility.ch vehicle types (see SFOE "Additions to GBFS") grouped into
# the categories a user actually thinks in.
CATEGORY_VEHICLE_TYPES: dict[str, tuple[str, ...]] = {
    "bike": ("Bike",),
    "e_bike": ("E-Bike",),
    "cargo_bike": ("CargoBike", "E-CargoBike"),
    "e_scooter": ("Scooter", "E-Scooter"),
    "moped": ("Moped", "E-Moped"),
    "car": ("Car", "E-Car", "Taxi", "E-Taxi"),
    "other": ("Other", "E-Other"),
}
CATEGORIES = list(CATEGORY_VEHICLE_TYPES)
DEFAULT_CATEGORIES = ["bike", "e_bike", "e_scooter", "car"]

CATEGORY_ICONS = {
    "bike": "mdi:bicycle",
    "e_bike": "mdi:bicycle-electric",
    "cargo_bike": "mdi:bicycle-cargo",
    "e_scooter": "mdi:scooter-electric",
    "moped": "mdi:moped-electric",
    "car": "mdi:car",
    "other": "mdi:help-circle-outline",
}

GEO_SOURCE = DOMAIN
