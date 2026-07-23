"""Constants for CouchMate Core.

The technical domain matches the CouchMate product name.
"""

DOMAIN = "couchmate"
STORAGE_KEY = "couchmate"
STORAGE_VERSION = 1

CONF_ENTITIES = "entities"
CONF_EXCLUDED_ENTITIES = "excluded_entities"
CONF_AREAS = "areas"
CONF_DEVICES = "devices"
CONF_ROOM_TEMPERATURES = "room_temperatures"
CONF_FILTER_MODE = "filter_mode"

FILTER_MODE_INCLUDE = "include"
FILTER_MODE_EXCLUDE = "exclude"

WS_TYPE_SUBSCRIBE_FILTERED = f"{DOMAIN}/subscribe_filtered"
WS_TYPE_GET_ENTITIES = f"{DOMAIN}/get_entities"
WS_TYPE_UPDATE_ENTITIES = f"{DOMAIN}/update_entities"
# CouchMate pairing API
PAIRING_SESSION_LIFETIME_SECONDS = 300
PAIRING_CLIENT_STORAGE_VERSION = 1
PAIRING_CLIENT_STORAGE_KEY = "couchmate.paired_clients"
PAIRING_MANAGER = "pairing_manager"
