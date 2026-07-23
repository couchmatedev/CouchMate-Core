# Changelog

## 1.1.0-alpha.10

- Vollständiges Branding aus der neuen alleinigen Master-SVG erneuert.
- Home-Assistant-Icons und Logos für helle und dunkle Darstellung ersetzt.
- Keine älteren SVG- oder Branding-Dateien enthalten.

## 1.1.0-alpha.6

- Added authenticated client service endpoint for lights, switches, media players, climate devices, covers, scenes and scripts.
- Service calls are restricted to entities selected in CouchMate.

# Changelog

## 1.1.0-alpha.4

- Fixed HTTP 500 responses from the paired-client entities endpoint when entity attributes contain dates, sets, enums, or other non-JSON-native values.
- The client entities API now reads the current selection for every request and disables caching.
- Added robust handling for deleted or unavailable entities.
- Added resolved area and device names, including device-area fallback.
- Added `selected_count` and `skipped` diagnostics to the client payload.

## 1.1.0-alpha.3

- Added a CouchMate management menu under the integration options.
- Pairing requests can now be approved or rejected directly in the Home Assistant UI.
- Paired CouchMate clients can be revoked from the integration options.
- Added pairing cancellation endpoint.
- Added client-authenticated info and entity endpoints for the tvOS app.
- Pairing notifications are dismissed automatically after approval, rejection, or cancellation.
- Added `couchmate.reject_pairing` service.

## 1.1.0-alpha.2

- Renamed the technical integration domain from `couch_control` to `couchmate`.
- Updated REST paths, WebSocket commands, services, storage keys, translations, and documentation.

## 1.1.0-alpha.1

- Initial Apple TV pairing prototype.

## 1.1.0-alpha.7
- Send exact Home Assistant area metadata for all exposed entities.
- Individually selected entities now create their assigned room without exposing the whole area.
