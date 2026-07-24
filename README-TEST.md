# CouchMate Core 1.2.0-alpha.9

## Auswahlmodell v2

- Ganze Geräte und einzelne Funktionen sind technisch getrennte Zustände.
- Eine einzelne Funktion überträgt ausschließlich ihre Entity-ID.
- Ganze Geräte werden nur über den Schalter „Ganzes Gerät verwenden“ aktiviert.
- Alte Bereichsauswahlen werden beim ersten Speichern mit dem grafischen Konfigurator entfernt.
- Enthält ein altes Gerät gleichzeitig eine Geräte- und eine explizite Entitätsauswahl, gewinnt die explizite Entitätsauswahl.
- Temperatur- und Luftfeuchtigkeitssensoren bleiben eigenständige Raum-Metadaten.

## Test

1. Integration aktualisieren und Home Assistant neu starten.
2. `/couchmate/configurator` öffnen.
3. Beim Türsensor prüfen: Gerätekarte zeigt „1 Funktion gewählt“, nicht „Alle Funktionen“.
4. Nur „Kontakt“ aktiv lassen und speichern.
5. tvOS neu laden. Batterie und Diagnose-Entities dürfen nicht mehr übertragen werden.
