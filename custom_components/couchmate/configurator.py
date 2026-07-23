"""Graphical room, device and entity configurator for CouchMate."""
from __future__ import annotations

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er

from .const import DOMAIN, CONF_AREAS, CONF_DEVICES, CONF_ENTITIES, CONF_EXCLUDED_ENTITIES
from .storage import async_save_entities


def _name(entry, state, fallback):
    return entry.name or entry.original_name or (state.name if state else None) or fallback


class CouchMateConfiguratorView(HomeAssistantView):
    url = "/api/couchmate/configurator"
    name = "api:couchmate:configurator"
    # The shell contains no Home Assistant data. It must be reachable by a
    # normal browser navigation, which does not attach an Authorization header.
    # The data and save endpoints below remain authenticated.
    requires_auth = False

    async def get(self, request):
        return web.Response(text=HTML, content_type="text/html")


class CouchMateConfiguratorDataView(HomeAssistantView):
    url = "/api/couchmate/configurator/data"
    name = "api:couchmate:configurator:data"
    requires_auth = True

    async def get(self, request):
        hass = request.app["hass"]
        areas = ar.async_get(hass)
        devices = dr.async_get(hass)
        entities = er.async_get(hass)
        current = hass.data.get(DOMAIN, {})

        result_areas = []
        for area in sorted(areas.areas.values(), key=lambda x: x.name.casefold()):
            area_devices = []
            for device in devices.devices.values():
                if device.area_id != area.id:
                    continue
                device_entities = []
                for entity in entities.entities.values():
                    if entity.disabled or entity.device_id != device.id:
                        continue
                    state = hass.states.get(entity.entity_id)
                    device_entities.append({
                        "entity_id": entity.entity_id,
                        "name": _name(entity, state, entity.entity_id),
                        "domain": entity.entity_id.split(".", 1)[0],
                        "selected": entity.entity_id in current.get("explicit_entities", []),
                        "excluded": entity.entity_id in current.get("excluded_entities", []),
                    })
                area_devices.append({
                    "id": device.id,
                    "name": device.name_by_user or device.name or device.id,
                    "manufacturer": device.manufacturer or "",
                    "model": device.model or "",
                    "selected": device.id in current.get("devices", []),
                    "entities": sorted(device_entities, key=lambda x: x["name"].casefold()),
                })
            result_areas.append({
                "id": area.id,
                "name": area.name,
                "selected": area.id in current.get("areas", []),
                "devices": sorted(area_devices, key=lambda x: x["name"].casefold()),
            })
        return self.json({"areas": result_areas})


class CouchMateConfiguratorSaveView(HomeAssistantView):
    url = "/api/couchmate/configurator/save"
    name = "api:couchmate:configurator:save"
    requires_auth = True

    async def post(self, request):
        hass = request.app["hass"]
        payload = await request.json()
        data = {
            CONF_AREAS: list(dict.fromkeys(payload.get("areas", []))),
            CONF_DEVICES: list(dict.fromkeys(payload.get("devices", []))),
            CONF_ENTITIES: list(dict.fromkeys(payload.get("entities", []))),
            CONF_EXCLUDED_ENTITIES: list(dict.fromkeys(payload.get("excluded_entities", []))),
        }
        await async_save_entities(hass, data)
        from . import _resolve_filter
        resolved = sorted(_resolve_filter(hass, areas=data[CONF_AREAS], devices=data[CONF_DEVICES], entities=data[CONF_ENTITIES], excluded_entities=data[CONF_EXCLUDED_ENTITIES]))
        runtime = hass.data.setdefault(DOMAIN, {})
        runtime.update({
            "areas": data[CONF_AREAS], "devices": data[CONF_DEVICES],
            "explicit_entities": data[CONF_ENTITIES], "excluded_entities": data[CONF_EXCLUDED_ENTITIES],
            "entities": resolved,
        })
        entry = runtime.get("entry")
        if entry:
            hass.config_entries.async_update_entry(entry, data=data)
        return self.json({"success": True, "resolved_count": len(resolved)})


async def async_setup_configurator(hass):
    hass.http.register_view(CouchMateConfiguratorView())
    hass.http.register_view(CouchMateConfiguratorDataView())
    hass.http.register_view(CouchMateConfiguratorSaveView())


HTML = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CouchMate</title><style>
:root{color-scheme:light dark;--bg:#101416;--card:#1a2023;--muted:#9aa7ad;--accent:#71d6c5;--line:#344047}*{box-sizing:border-box}body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:#f5f7f7}.wrap{max-width:1180px;margin:auto;padding:28px}.top{display:flex;justify-content:space-between;align-items:center;gap:16px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:14px}.tile{border:1px solid var(--line);border-radius:22px;background:var(--card);padding:18px;cursor:pointer;text-align:left;color:inherit;min-height:145px}.tile.active{outline:3px solid var(--accent);background:#17312e}.icon{font-size:40px}.sub{color:var(--muted);font-size:14px}.section{margin-top:30px}.entities{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}.entity{display:flex;gap:12px;align-items:center;border:1px solid var(--line);border-radius:16px;padding:13px;background:var(--card)}button.primary{background:var(--accent);color:#061411;border:0;border-radius:14px;padding:13px 18px;font-weight:700;cursor:pointer}.hidden{display:none}.crumb{color:var(--muted);margin:8px 0 20px}.back{background:none;border:0;color:var(--accent);font-size:16px;cursor:pointer;padding:0}.status{margin-top:14px;color:var(--accent)}h1,h2{font-weight:650}</style></head><body><main class="wrap"><div class="top"><div><h1>CouchMate Konfigurator</h1><div class="sub">Raum → Gerät → benötigte Funktionen</div></div><button id="save" class="primary">Auswahl speichern</button></div><div id="status" class="status"></div><section id="areas" class="section"><h2>Räume</h2><div id="areaGrid" class="grid"></div></section><section id="devices" class="section hidden"><button class="back" id="backAreas">← Räume</button><div class="crumb" id="areaName"></div><h2>Geräte</h2><div id="deviceGrid" class="grid"></div></section><section id="entities" class="section hidden"><button class="back" id="backDevices">← Geräte</button><div class="crumb" id="deviceName"></div><h2>Funktionen</h2><div id="entityGrid" class="entities"></div></section></main><script>
let data,area,device;const selected={areas:new Set(),devices:new Set(),entities:new Set(),excluded:new Set()};const icons={light:'💡',switch:'🔌',media_player:'📺',climate:'🌡️',cover:'🪟',fan:'🌀',sensor:'📟',binary_sensor:'◉',default:'⬡'};
const auth=()=>{try{const t=JSON.parse(localStorage.getItem('hassTokens')||'{}');return t.access_token?{'Authorization':'Bearer '+t.access_token}:{} }catch(e){return {}}};
async function api(url,options={}){options.headers={...(options.headers||{}),...auth()};const r=await fetch(url,options);if(r.status===401){throw new Error('AUTH')}if(!r.ok)throw new Error('HTTP '+r.status);return r}
api('/api/couchmate/configurator/data').then(r=>r.json()).then(j=>{data=j;for(const a of data.areas){if(a.selected)selected.areas.add(a.id);for(const d of a.devices){if(d.selected)selected.devices.add(d.id);for(const e of d.entities){if(e.selected)selected.entities.add(e.entity_id);if(e.excluded)selected.excluded.add(e.entity_id)}}}renderAreas()}).catch(e=>{status.textContent=e.message==='AUTH'?'Nicht autorisiert. Öffne CouchMate im selben Browser, in dem du bei Home Assistant angemeldet bist, und lade die Seite neu.':'Konfigurator konnte nicht geladen werden: '+e.message});
function tile(title,sub,icon,active,fn){const b=document.createElement('button');b.className='tile'+(active?' active':'');b.innerHTML=`<div class="icon">${icon}</div><h3>${title}</h3><div class="sub">${sub}</div>`;b.onclick=fn;return b}
function renderAreas(){areas.classList.remove('hidden');devices.classList.add('hidden');entities.classList.add('hidden');areaGrid.innerHTML='';for(const a of data.areas)areaGrid.append(tile(a.name,`${a.devices.length} Geräte`,'🏠',selected.areas.has(a.id),()=>{area=a;renderDevices()}))}
function renderDevices(){areas.classList.add('hidden');devices.classList.remove('hidden');entities.classList.add('hidden');areaName.textContent=area.name;deviceGrid.innerHTML='';for(const d of area.devices){const domain=d.entities[0]?.domain||'default';deviceGrid.append(tile(d.name,[d.manufacturer,d.model].filter(Boolean).join(' · ')||`${d.entities.length} Funktionen`,icons[domain]||icons.default,selected.devices.has(d.id),()=>{device=d;renderEntities()}))}}
function renderEntities(){devices.classList.add('hidden');entities.classList.remove('hidden');deviceName.textContent=`${area.name} · ${device.name}`;entityGrid.innerHTML='';for(const e of device.entities){const row=document.createElement('label');row.className='entity';row.innerHTML=`<input type="checkbox" ${selected.entities.has(e.entity_id)?'checked':''}><span><b>${e.name}</b><br><span class="sub">${e.entity_id}</span></span>`;const c=row.querySelector('input');c.onchange=()=>c.checked?selected.entities.add(e.entity_id):selected.entities.delete(e.entity_id);entityGrid.append(row)}}
backAreas.onclick=renderAreas;backDevices.onclick=renderDevices;save.onclick=async()=>{status.textContent='Speichere …';try{const r=await api('/api/couchmate/configurator/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({areas:[...selected.areas],devices:[...selected.devices],entities:[...selected.entities],excluded_entities:[...selected.excluded]})});const j=await r.json();status.textContent=j.success?`Gespeichert · ${j.resolved_count} Entitäten freigegeben`:'Fehler beim Speichern'}catch(e){status.textContent=e.message==='AUTH'?'Anmeldung abgelaufen. Home Assistant neu laden und erneut speichern.':'Fehler beim Speichern: '+e.message}};
</script></body></html>'''
