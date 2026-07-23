# CouchMate Core 1.2.0-alpha.3

Grafischer CouchMate-Konfigurator.

Nach Installation und vollständigem Home-Assistant-Neustart öffnen:

`http://DEINE-HA-IP:8123/couchmate/configurator`

Wichtig: Der alte Pfad `/api/couchmate/configurator` ist nicht mehr gültig.


## 1.2.0-alpha.5
- Preferred room-temperature sensors are always included in the tvOS client payload.
- `/api/couchmate/client/entities` now exposes `room_temperature_entity_ids` and resolved `room_temperatures` per area.
