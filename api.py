"""REST API for CouchMate Core."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import date, datetime
from enum import Enum
from typing import Any

from aiohttp import web
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, PAIRING_MANAGER
from .pairing import PairingManager, PairingStatus
from .storage import async_save_entities

_LOGGER = logging.getLogger(__name__)


def _manager(hass: HomeAssistant) -> PairingManager:
    return hass.data[DOMAIN][PAIRING_MANAGER]


def _json_safe(value: Any) -> Any:
    """Convert Home Assistant values into JSON-safe primitives."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return _json_safe(value.value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "as_dict"):
        try:
            return _json_safe(value.as_dict())
        except Exception:  # noqa: BLE001
            pass
    return str(value)


def _entity_payload(hass: HomeAssistant, entity_id: str) -> dict[str, Any] | None:
    """Build one robust client entity payload from current registries and state."""
    state = hass.states.get(entity_id)
    if state is None:
        return None

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)
    entry = ent_reg.async_get(entity_id)
    device = dev_reg.async_get(entry.device_id) if entry and entry.device_id else None
    area_id = (entry.area_id if entry else None) or (device.area_id if device else None)
    area = area_reg.async_get_area(area_id) if area_id else None

    name = None
    if entry:
        name = entry.name or entry.original_name
    if not name:
        name = state.attributes.get("friendly_name")

    return {
        "entity_id": entity_id,
        "state": state.state,
        "attributes": _json_safe(dict(state.attributes)),
        "last_changed": state.last_changed.isoformat(),
        "last_updated": state.last_updated.isoformat(),
        "area_id": area_id,
        "area_name": area.name if area else None,
        "device_id": entry.device_id if entry else None,
        "device_name": (device.name_by_user or device.name) if device else None,
        "name": name,
        "icon": (entry.icon or entry.original_icon) if entry else None,
        "device_class": entry.device_class if entry else None,
        "unit_of_measurement": entry.unit_of_measurement if entry else None,
    }


class CouchMateEntitiesView(HomeAssistantView):
    url = "/api/couchmate/entities"
    name = "api:couchmate:entities"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]
        if DOMAIN not in hass.data:
            return web.json_response({"error": "CouchMate Core not configured"}, status=400)
        selected = list(hass.data[DOMAIN].get("entities", []))
        detailed_entities: list[dict[str, Any]] = []
        skipped: list[str] = []
        for entity_id in selected:
            try:
                payload = _entity_payload(hass, entity_id)
                if payload is None:
                    skipped.append(entity_id)
                    continue
                detailed_entities.append(payload)
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Unable to serialize CouchMate entity %s", entity_id)
                skipped.append(f"{entity_id}: {err}")
        return web.json_response(
            {"entities": detailed_entities, "count": len(detailed_entities), "skipped": skipped},
            headers={"Cache-Control": "no-store"},
        )

    async def post(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]
        try:
            data = vol.Schema({vol.Required("entities"): [str]})(await request.json())
        except (ValueError, vol.Invalid) as err:
            return web.json_response({"error": f"Invalid data: {err}"}, status=400)
        valid = [entity_id for entity_id in data["entities"] if hass.states.get(entity_id)]
        hass.data[DOMAIN]["entities"] = valid
        await async_save_entities(hass, {"entities": valid})
        return web.json_response({"success": True, "entities": valid, "count": len(valid)})


class CouchMateInfoView(HomeAssistantView):
    url = "/api/couchmate/info"
    name = "api:couchmate:info"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]
        return web.json_response({
            "integration": "CouchMate Core",
            "version": "1.1.0-alpha.7",
            "domain": DOMAIN,
            "filtered_entities_count": len(hass.data.get(DOMAIN, {}).get("entities", [])),
            "pairing": True,
            "status": "active",
        })


class PairingCreateView(HomeAssistantView):
    url = "/api/couchmate/pairing/create"
    name = "api:couchmate:pairing:create"
    requires_auth = False

    async def post(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]
        if DOMAIN not in hass.data:
            return web.json_response({"error": "not_configured"}, status=503)
        try:
            data = await request.json()
        except Exception:
            data = {}
        session = _manager(hass).create_session(str(data.get("device_name", "Apple TV")))
        persistent_notification.async_create(
            hass,
            f"Ein Apple TV namens **{session.device_name}** möchte sich mit CouchMate verbinden. "
            f"Kopplungscode: **{session.code}**. Bestätige ihn über den Dienst "
            f"`couchmate.approve_pairing`.",
            title="CouchMate Kopplungsanfrage",
            notification_id=f"{DOMAIN}_pairing_{session.session_id}",
        )
        return web.json_response(session.public_dict())


class PairingStatusView(HomeAssistantView):
    url = "/api/couchmate/pairing/status"
    name = "api:couchmate:pairing:status"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        session_id = request.query.get("session_id", "")
        session = _manager(request.app["hass"]).get_by_session_id(session_id)
        if not session:
            return web.json_response({"error": "session_not_found"}, status=404)
        payload = session.public_dict()
        if session.status == PairingStatus.APPROVED:
            payload["exchange_token"] = session.exchange_token
        return web.json_response(payload)


class PairingApproveView(HomeAssistantView):
    url = "/api/couchmate/pairing/approve"
    name = "api:couchmate:pairing:approve"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        data = await request.json()
        session = _manager(request.app["hass"]).approve(str(data.get("code", "")))
        if not session:
            return web.json_response({"error": "code_not_found"}, status=404)
        return web.json_response(session.public_dict())


class PairingExchangeView(HomeAssistantView):
    url = "/api/couchmate/pairing/exchange"
    name = "api:couchmate:pairing:exchange"
    requires_auth = False

    async def post(self, request: web.Request) -> web.Response:
        data = await request.json()
        credentials = await _manager(request.app["hass"]).async_exchange(
            str(data.get("session_id", "")), str(data.get("exchange_token", ""))
        )
        if not credentials:
            return web.json_response({"error": "exchange_denied"}, status=403)
        return web.json_response(credentials)


async def _client_id_from_request(request: web.Request) -> str | None:
    """Validate a CouchMate client bearer token."""
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return await _manager(request.app["hass"]).async_validate_client_token(token)


class PairingCancelView(HomeAssistantView):
    url = "/api/couchmate/pairing/cancel"
    name = "api:couchmate:pairing:cancel"
    requires_auth = False

    async def post(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            data = {}
        session = _manager(request.app["hass"]).cancel(
            str(data.get("session_id", ""))
        )
        if not session:
            return web.json_response({"error": "session_not_found"}, status=404)
        persistent_notification.async_dismiss(
            request.app["hass"], f"{DOMAIN}_pairing_{session.session_id}"
        )
        return web.json_response(session.public_dict())


class CouchMateClientInfoView(HomeAssistantView):
    url = "/api/couchmate/client/info"
    name = "api:couchmate:client:info"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        client_id = await _client_id_from_request(request)
        if client_id is None:
            return web.json_response({"error": "unauthorized"}, status=401)
        hass = request.app["hass"]
        return web.json_response({
            "client_id": client_id,
            "integration": "CouchMate Core",
            "version": "1.1.0-alpha.7",
            "status": "active",
            "entities_count": len(hass.data.get(DOMAIN, {}).get("entities", [])),
        })


class CouchMateClientEntitiesView(HomeAssistantView):
    url = "/api/couchmate/client/entities"
    name = "api:couchmate:client:entities"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        client_id = await _client_id_from_request(request)
        if client_id is None:
            return web.json_response({"error": "unauthorized"}, status=401)
        hass = request.app["hass"]
        selected = list(hass.data.get(DOMAIN, {}).get("entities", []))
        entities: list[dict[str, Any]] = []
        skipped: list[str] = []

        for entity_id in selected:
            try:
                payload = _entity_payload(hass, entity_id)
                if payload is None:
                    skipped.append(entity_id)
                    continue
                entities.append(payload)
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Unable to serialize CouchMate client entity %s", entity_id)
                skipped.append(f"{entity_id}: {err}")

        # Send the exact Home Assistant areas that belong to the exposed
        # entities. This guarantees that an individually selected entity
        # creates its room in CouchMate without exposing every other entity
        # from that area.
        areas_by_id: dict[str, dict[str, str]] = {}
        for entity in entities:
            area_id = entity.get("area_id")
            area_name = entity.get("area_name")
            if area_id and area_name:
                areas_by_id[area_id] = {"id": area_id, "name": area_name}

        return web.json_response(
            {
                "client_id": client_id,
                "entities": entities,
                "areas": sorted(areas_by_id.values(), key=lambda item: item["name"].casefold()),
                "count": len(entities),
                "selected_count": len(selected),
                "skipped": skipped,
            },
            headers={"Cache-Control": "no-store"},
        )


_ALLOWED_SERVICES: dict[str, set[str]] = {
    "light": {"turn_on", "turn_off", "toggle"},
    "switch": {"turn_on", "turn_off", "toggle"},
    "media_player": {"media_play_pause", "media_play", "media_pause", "turn_on", "turn_off", "volume_up", "volume_down"},
    "climate": {"turn_on", "turn_off", "set_temperature", "set_hvac_mode"},
    "cover": {"open_cover", "close_cover", "stop_cover", "set_cover_position"},
    "scene": {"turn_on"},
    "script": {"turn_on"},
}


class CouchMateClientServiceView(HomeAssistantView):
    url = "/api/couchmate/client/service"
    name = "api:couchmate:client:service"
    requires_auth = False

    async def post(self, request: web.Request) -> web.Response:
        client_id = await _client_id_from_request(request)
        if client_id is None:
            return web.json_response({"error": "unauthorized"}, status=401)

        hass = request.app["hass"]
        try:
            payload = await request.json()
            domain = str(payload.get("domain", "")).strip()
            service = str(payload.get("service", "")).strip()
            entity_ids = [str(item) for item in payload.get("entity_ids", [])]
            service_data = dict(payload.get("data", {}) or {})
        except (ValueError, TypeError):
            return web.json_response({"error": "invalid_json"}, status=400)

        if service not in _ALLOWED_SERVICES.get(domain, set()):
            return web.json_response({"error": "service_not_allowed"}, status=403)
        if not entity_ids:
            return web.json_response({"error": "missing_entity_ids"}, status=400)

        selected = set(hass.data.get(DOMAIN, {}).get("entities", []))
        denied = [entity_id for entity_id in entity_ids if entity_id not in selected]
        if denied:
            return web.json_response({"error": "entity_not_selected", "entities": denied}, status=403)

        wrong_domain = [entity_id for entity_id in entity_ids if entity_id.split(".", 1)[0] != domain]
        if wrong_domain:
            return web.json_response({"error": "domain_mismatch", "entities": wrong_domain}, status=400)

        existing = [entity_id for entity_id in entity_ids if hass.states.get(entity_id) is not None]
        if len(existing) != len(entity_ids):
            missing = sorted(set(entity_ids) - set(existing))
            return web.json_response({"error": "entity_not_found", "entities": missing}, status=404)

        try:
            await hass.services.async_call(
                domain,
                service,
                service_data,
                blocking=True,
                target={"entity_id": entity_ids},
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("CouchMate service call failed for client %s", client_id)
            return web.json_response({"error": "service_call_failed", "message": str(err)}, status=500)

        return web.json_response({
            "success": True,
            "client_id": client_id,
            "domain": domain,
            "service": service,
            "entity_ids": entity_ids,
        })


async def async_setup_api(hass: HomeAssistant) -> None:
    for view in (
        CouchMateEntitiesView(),
        CouchMateInfoView(),
        PairingCreateView(),
        PairingStatusView(),
        PairingApproveView(),
        PairingExchangeView(),
        PairingCancelView(),
        CouchMateClientInfoView(),
        CouchMateClientEntitiesView(),
        CouchMateClientServiceView(),
    ):
        hass.http.register_view(view)
    _LOGGER.info("CouchMate Core REST and pairing API endpoints registered")
