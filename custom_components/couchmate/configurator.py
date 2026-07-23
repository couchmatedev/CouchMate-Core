"""Graphical room, device and entity configurator for CouchMate."""
from __future__ import annotations

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er

from .const import (
    DOMAIN,
    CONF_AREAS,
    CONF_DEVICES,
    CONF_ENTITIES,
    CONF_EXCLUDED_ENTITIES,
    CONF_ROOM_TEMPERATURES,
)
from .storage import async_save_entities


def _name(entry, state, fallback):
    return entry.name or entry.original_name or (state.name if state else None) or fallback


def _is_temperature_entity(entity, state) -> bool:
    if entity.entity_id.startswith("sensor."):
        device_class = getattr(entity, "device_class", None) or (state.attributes.get("device_class") if state else None)
        unit = state.attributes.get("unit_of_measurement") if state else None
        return device_class == "temperature" or unit in ("°C", "°F")
    return False


class CouchMateConfiguratorView(HomeAssistantView):
    url = "/couchmate/configurator"
    name = "couchmate:configurator"
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
        device_area = {device.id: device.area_id for device in devices.devices.values()}
        room_temperatures = current.get("room_temperatures", {})

        result_areas = []
        for area in sorted(areas.areas.values(), key=lambda x: x.name.casefold()):
            area_devices = []
            temperature_candidates = []

            for entity in entities.entities.values():
                if entity.disabled:
                    continue
                entity_area = entity.area_id or (device_area.get(entity.device_id) if entity.device_id else None)
                if entity_area != area.id:
                    continue
                state = hass.states.get(entity.entity_id)
                if _is_temperature_entity(entity, state):
                    temperature_candidates.append({
                        "entity_id": entity.entity_id,
                        "name": _name(entity, state, entity.entity_id),
                    })

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
                "temperature_entity": room_temperatures.get(area.id),
                "temperature_candidates": sorted(temperature_candidates, key=lambda x: x["name"].casefold()),
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
        temperatures = {
            str(area_id): str(entity_id)
            for area_id, entity_id in dict(payload.get("room_temperatures", {})).items()
            if area_id and entity_id
        }
        data = {
            CONF_AREAS: list(dict.fromkeys(payload.get("areas", []))),
            CONF_DEVICES: list(dict.fromkeys(payload.get("devices", []))),
            CONF_ENTITIES: list(dict.fromkeys(payload.get("entities", []))),
            CONF_EXCLUDED_ENTITIES: list(dict.fromkeys(payload.get("excluded_entities", []))),
            CONF_ROOM_TEMPERATURES: temperatures,
        }
        await async_save_entities(hass, data)
        from . import _resolve_filter
        resolved = sorted(_resolve_filter(
            hass,
            areas=data[CONF_AREAS],
            devices=data[CONF_DEVICES],
            entities=data[CONF_ENTITIES],
            excluded_entities=data[CONF_EXCLUDED_ENTITIES],
        ))
        runtime = hass.data.setdefault(DOMAIN, {})
        runtime.update({
            "areas": data[CONF_AREAS],
            "devices": data[CONF_DEVICES],
            "explicit_entities": data[CONF_ENTITIES],
            "excluded_entities": data[CONF_EXCLUDED_ENTITIES],
            "room_temperatures": temperatures,
            "entities": resolved,
        })
        entry = runtime.get("entry")
        if entry:
            hass.config_entries.async_update_entry(entry, data=data)
        return self.json({
            "success": True,
            "resolved_count": len(resolved),
            "temperature_count": len(temperatures),
            "area_count": len(data[CONF_AREAS]),
            "device_count": len(data[CONF_DEVICES]),
            "entity_count": len(data[CONF_ENTITIES]),
        })


async def async_setup_configurator(hass):
    hass.http.register_view(CouchMateConfiguratorView())
    hass.http.register_view(CouchMateConfiguratorDataView())
    hass.http.register_view(CouchMateConfiguratorSaveView())


HTML = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CouchMate</title><style>
:root{color-scheme:dark;--bg:#0f1416;--card:#1a2023;--card2:#20282c;--muted:#a7b1b6;--accent:#71d6c5;--line:#39464c;--ok:#75d6a2;--danger:#ff8a8a}*{box-sizing:border-box}body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:#f5f7f7}.wrap{max-width:1500px;margin:auto;padding:42px 52px 80px}.top{display:flex;justify-content:space-between;align-items:flex-start;gap:28px;position:sticky;top:0;background:linear-gradient(var(--bg) 82%,transparent);padding:10px 0 28px;z-index:5}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:20px}.tile{border:1px solid var(--line);border-radius:26px;background:var(--card);padding:26px;cursor:pointer;text-align:left;color:inherit;min-height:190px;transition:.16s ease}.tile:hover{border-color:#607078;background:var(--card2);transform:translateY(-1px)}.tile.active{outline:3px solid var(--accent);background:#17312e}.icon{width:48px;height:48px;color:var(--accent);margin-bottom:26px}.icon svg{width:100%;height:100%;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}.sub{color:var(--muted);font-size:17px;line-height:1.35}.section{margin-top:38px}.entities,.temperatures{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px}.entity,.temperature{display:flex;gap:16px;align-items:center;border:1px solid var(--line);border-radius:20px;padding:21px 22px;background:var(--card);min-height:104px;cursor:pointer;overflow:hidden}.entity:hover,.temperature:hover{background:var(--card2)}.entity input,.temperature input{width:22px;height:22px;accent-color:var(--accent);flex:0 0 auto}.entity b,.temperature b{font-size:19px}.entity .sub,.temperature .sub{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block;max-width:100%}button.primary{background:var(--accent);color:#061411;border:0;border-radius:18px;padding:17px 26px;font-size:16px;font-weight:750;cursor:pointer;min-width:190px}button.primary:disabled{opacity:.65;cursor:wait}.hidden{display:none!important}.crumb{color:var(--muted);margin:10px 0 28px;font-size:19px}.back{background:none;border:0;color:var(--accent);font-size:18px;cursor:pointer;padding:0}.temperature-panel{border:1px solid var(--line);border-radius:26px;padding:24px;background:#141a1d;margin:0 0 32px}.temperature-panel h3{margin:0 0 6px;font-size:21px}.temperature-panel p{margin:0 0 20px}.toast{position:fixed;right:28px;bottom:28px;max-width:520px;border:1px solid var(--line);border-radius:20px;padding:18px 22px;background:#20282c;box-shadow:0 18px 50px rgba(0,0,0,.35);z-index:20}.toast.ok{border-color:var(--ok)}.toast.error{border-color:var(--danger)}.toast strong{display:block;font-size:18px;margin-bottom:5px}h1{font-size:40px;margin:0 0 18px}h2{font-size:30px;margin:0 0 24px}h3{font-size:19px;margin:0 0 12px;font-weight:700}@media(max-width:700px){.wrap{padding:24px 18px 70px}.top{position:static;display:block}.top button{width:100%;margin-top:20px}.grid{grid-template-columns:1fr}.entities,.temperatures{grid-template-columns:1fr}.toast{left:18px;right:18px;bottom:18px}h1{font-size:31px}}
</style></head><body><main class="wrap"><div class="top"><div><h1>CouchMate Konfigurator</h1><div class="sub">Raum → Gerät → benötigte Funktionen</div></div><button id="save" class="primary">Auswahl speichern</button></div><section id="areas" class="section"><h2>Räume</h2><div id="areaGrid" class="grid"></div></section><section id="devices" class="section hidden"><button class="back" id="backAreas">← Räume</button><div class="crumb" id="areaName"></div><div id="temperaturePanel" class="temperature-panel"><h3>Raumtemperatur</h3><p class="sub">Wähle den Sensor, der in CouchMate als Temperatur dieses Raums verwendet werden soll.</p><div id="temperatureGrid" class="temperatures"></div></div><h2>Geräte</h2><div id="deviceGrid" class="grid"></div></section><section id="entities" class="section hidden"><button class="back" id="backDevices">← Geräte</button><div class="crumb" id="deviceName"></div><h2>Funktionen</h2><div id="entityGrid" class="entities"></div></section></main><div id="toast" class="toast hidden" role="status" aria-live="polite"></div><script>
let data,area,device;const selected={areas:new Set(),devices:new Set(),entities:new Set(),excluded:new Set(),temperatures:{}};
const paths={room:'<path d="M4 10.5 12 4l8 6.5V20H4z"/><path d="M9 20v-6h6v6"/>',light:'<path d="M9 18h6"/><path d="M10 22h4"/><path d="M8.5 14.5A6 6 0 1 1 15.5 14.5c-1 .8-1.5 1.8-1.5 3h-4c0-1.2-.5-2.2-1.5-3Z"/>',switch:'<path d="M7 2v5M17 2v5"/><path d="M5 7h14v7a7 7 0 0 1-14 0Z"/><path d="M9 21h6"/>',media_player:'<rect x="3" y="5" width="18" height="13" rx="2"/><path d="m10 9 5 2.5-5 2.5Z"/><path d="M8 22h8"/>',climate:'<path d="M14 14.8V5a2 2 0 0 0-4 0v9.8a4 4 0 1 0 4 0Z"/><path d="M12 11v6"/>',cover:'<rect x="4" y="3" width="16" height="18" rx="1"/><path d="M4 8h16M4 13h16M4 18h16"/>',fan:'<circle cx="12" cy="12" r="2"/><path d="M12 10c-1-4 1-7 4-7 2 3 1 6-2 8M14 12c4-1 7 1 7 4-3 2-6 1-8-2M12 14c1 4-1 7-4 7-2-3-1-6 2-8M10 12c-4 1-7-1-7-4 3-2 6-1 8 2"/>',sensor:'<path d="M4 19V5M4 19h16"/><path d="m7 15 3-4 3 2 5-7"/>',binary_sensor:'<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2"/>',default:'<rect x="4" y="4" width="16" height="16" rx="4"/><path d="M9 9h6v6H9z"/>'};
function icon(kind){return `<svg viewBox="0 0 24 24" aria-hidden="true">${paths[kind]||paths.default}</svg>`}
function roomKind(name){const n=name.toLowerCase();if(n.includes('wohn'))return 'media_player';if(n.includes('küche')||n.includes('kueche'))return 'switch';if(n.includes('schlaf'))return 'light';if(n.includes('bad')||n.includes('wc'))return 'climate';if(n.includes('garten'))return 'sensor';if(n.includes('garage'))return 'cover';return 'room'}
const auth=()=>{try{const t=JSON.parse(localStorage.getItem('hassTokens')||'{}');return t.access_token?{'Authorization':'Bearer '+t.access_token}:{} }catch(e){return {}}};
async function api(url,options={}){options.headers={...(options.headers||{}),...auth()};const r=await fetch(url,options);if(r.status===401)throw new Error('AUTH');if(!r.ok)throw new Error('HTTP '+r.status);return r}
function showToast(type,title,text){toast.className='toast '+type;toast.innerHTML=`<strong>${title}</strong><span>${text}</span>`;clearTimeout(showToast.timer);showToast.timer=setTimeout(()=>toast.classList.add('hidden'),6000)}
api('/api/couchmate/configurator/data').then(r=>r.json()).then(j=>{data=j;for(const a of data.areas){if(a.selected)selected.areas.add(a.id);if(a.temperature_entity)selected.temperatures[a.id]=a.temperature_entity;for(const d of a.devices){if(d.selected)selected.devices.add(d.id);for(const e of d.entities){if(e.selected)selected.entities.add(e.entity_id);if(e.excluded)selected.excluded.add(e.entity_id)}}}renderAreas()}).catch(e=>showToast('error','Konfigurator konnte nicht geladen werden',e.message==='AUTH'?'Öffne die Seite im selben Browser, in dem du bei Home Assistant angemeldet bist.':e.message));
function tile(title,sub,kind,active,fn){const b=document.createElement('button');b.className='tile'+(active?' active':'');b.innerHTML=`<div class="icon">${icon(kind)}</div><h3>${title}</h3><div class="sub">${sub}</div>`;b.onclick=fn;return b}
function renderAreas(){areas.classList.remove('hidden');devices.classList.add('hidden');entities.classList.add('hidden');areaGrid.innerHTML='';for(const a of data.areas)areaGrid.append(tile(a.name,`${a.devices.length} Geräte`,roomKind(a.name),selected.areas.has(a.id)||!!selected.temperatures[a.id],()=>{area=a;renderDevices()}))}
function renderDevices(){areas.classList.add('hidden');devices.classList.remove('hidden');entities.classList.add('hidden');areaName.textContent=area.name;deviceGrid.innerHTML='';temperatureGrid.innerHTML='';if(!area.temperature_candidates.length){temperaturePanel.classList.add('hidden')}else{temperaturePanel.classList.remove('hidden');const none=document.createElement('label');none.className='temperature';none.innerHTML=`<input type="radio" name="roomTemp"><span><b>Keine Raumtemperatur</b><span class="sub">Für diesen Raum nicht anzeigen</span></span>`;none.querySelector('input').checked=!selected.temperatures[area.id];none.querySelector('input').onchange=()=>delete selected.temperatures[area.id];temperatureGrid.append(none);for(const t of area.temperature_candidates){const row=document.createElement('label');row.className='temperature';row.innerHTML=`<input type="radio" name="roomTemp"><span><b>${t.name}</b><span class="sub">${t.entity_id}</span></span>`;const input=row.querySelector('input');input.checked=selected.temperatures[area.id]===t.entity_id;input.onchange=()=>{selected.temperatures[area.id]=t.entity_id;selected.areas.add(area.id)};temperatureGrid.append(row)}}for(const d of area.devices){const domain=d.entities[0]?.domain||'default';deviceGrid.append(tile(d.name,[d.manufacturer,d.model].filter(Boolean).join(' · ')||`${d.entities.length} Funktionen`,domain,selected.devices.has(d.id),()=>{device=d;renderEntities()}))}}
function renderEntities(){devices.classList.add('hidden');entities.classList.remove('hidden');deviceName.textContent=`${area.name} · ${device.name}`;entityGrid.innerHTML='';for(const e of device.entities){const row=document.createElement('label');row.className='entity';row.innerHTML=`<input type="checkbox" ${selected.entities.has(e.entity_id)?'checked':''}><span><b>${e.name}</b><span class="sub">${e.entity_id}</span></span>`;const c=row.querySelector('input');c.onchange=()=>{if(c.checked){selected.entities.add(e.entity_id);selected.devices.add(device.id);selected.areas.add(area.id)}else selected.entities.delete(e.entity_id)};entityGrid.append(row)}}
backAreas.onclick=renderAreas;backDevices.onclick=renderDevices;save.onclick=async()=>{save.disabled=true;save.textContent='Speichert …';showToast('', 'Auswahl wird gespeichert','Bitte einen Moment warten.');try{const r=await api('/api/couchmate/configurator/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({areas:[...selected.areas],devices:[...selected.devices],entities:[...selected.entities],excluded_entities:[...selected.excluded],room_temperatures:selected.temperatures})});const j=await r.json();if(!j.success)throw new Error('Unbekannter Speicherfehler');showToast('ok','Auswahl erfolgreich gespeichert',`${j.area_count} Räume · ${j.device_count} Geräte · ${j.entity_count} Funktionen · ${j.temperature_count} Raumtemperaturen`)}catch(e){showToast('error','Speichern fehlgeschlagen',e.message==='AUTH'?'Die Home-Assistant-Anmeldung ist abgelaufen. Bitte Home Assistant neu laden.':e.message)}finally{save.disabled=false;save.textContent='Auswahl speichern'}};
</script></body></html>'''
