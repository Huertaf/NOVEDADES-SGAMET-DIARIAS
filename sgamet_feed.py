"""
Núcleo de recogida de novedades para el Cuadro de novedades SGAMET.

Lo usan tanto la app de Streamlit (refresco en vivo) como refresh.py (cron diario).
La clave de API y el modelo se leen de variables de entorno o de st.secrets;
NUNCA se codifican aquí.

La llamada usa la API de Anthropic con la herramienta de búsqueda web, del lado
servidor: la clave no llega jamás al navegador.
"""
from __future__ import annotations
import os
import re
import json
import concurrent.futures as cf
from datetime import datetime, timezone

# --- Configuración ajustable -------------------------------------------------
# Modelo: pon uno al que tu clave tenga acceso. Sonnet es buen equilibrio
# coste/calidad para esta tarea; Haiku abarata, Opus afina.
DEFAULT_MODEL = os.environ.get("MODEL", "claude-sonnet-5")

# Tipo de la herramienta de búsqueda web. Si Anthropic publica una versión más
# reciente, cámbiala aquí en un solo sitio.
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 4}

MAX_TOKENS = 1500
MAX_ITEMS_PER_BLOCK = 5

# --- Bloques a vigilar (derivados del Excel de organización de secciones) -----
# owned=True  -> sección de la que SGAMET es responsable segun el mapa.
CATS = [
    {"id": "prensa", "label": "Notas de prensa", "owned": False,
     "color": "#0e5a63",
     "q": "novedades y notas de prensa recientes del Ministerio para la "
          "Transformacion Digital, area de telecomunicaciones e infraestructuras "
          "digitales, digital.gob.es"},
    {"id": "legis", "label": "Legislacion", "owned": True,
     "color": "#8a5a00",
     "q": "normativa y legislacion reciente de telecomunicaciones y espectro en "
          "Espana, BOE, Ministerio Transformacion Digital, ultimos dias"},
    {"id": "estad", "label": "Estadisticas e informes", "owned": True,
     "color": "#8a5a00",
     "q": "estadisticas e informes recientes del sector de telecomunicaciones en "
          "Espana, digital.gob.es y CNMC, publicaciones nuevas"},
    {"id": "espectro", "label": "Espectro y numeracion", "owned": True,
     "color": "#8a5a00",
     "q": "novedades sobre espectro radioelectrico, registro publico de "
          "concesiones y numeracion y direccionamiento en Espana, Ministerio "
          "Transformacion Digital"},
    {"id": "banda", "label": "Banda ancha y cobertura", "owned": True,
     "color": "#8a5a00",
     "q": "novedades de banda ancha e informacion de cobertura en Espana, "
          "despliegue de redes y programa UNICO, digital.gob.es"},
    {"id": "ayudas", "label": "Ayudas y convocatorias", "owned": False,
     "color": "#0e5a63",
     "q": "convocatorias y ayudas recientes en telecomunicaciones e "
          "infraestructuras digitales, portal de ayudas digital.gob.es"},
]

_PROMPT = (
    "Eres un asistente de vigilancia documental para una unidad reguladora "
    "espanola (SGAMET). Busca en la web las NOVEDADES MAS RECIENTES (ultimos 7 "
    "dias si es posible) sobre: {q}. Prioriza fuentes oficiales (digital.gob.es, "
    "sede electronica, portal de ayudas, BOE, CNMC). Devuelve EXCLUSIVAMENTE un "
    "array JSON valido, sin texto ni markdown, con hasta {n} objetos con las "
    "claves: titulo, resumen (maximo 2 frases en espanol), fuente (dominio), "
    "url (https), fecha (YYYY-MM-DD o texto). Si no encuentras nada reciente y "
    "fiable, devuelve []."
)


def _parse_json_array(text: str) -> list:
    """Extrae el primer array JSON de la respuesta del modelo, tolerante a ruido."""
    if not text:
        return []
    t = text.replace("```json", "").replace("```", "").strip()
    i, j = t.find("["), t.rfind("]")
    if i != -1 and j > i:
        t = t[i:j + 1]
    try:
        v = json.loads(t)
        return v if isinstance(v, list) else []
    except Exception:
        return []


def fetch_category(cat: dict, api_key: str, model: str) -> list:
    """Devuelve la lista de novedades de un bloque. Nunca lanza: ante error, []."""
    import anthropic  # import perezoso: solo se necesita al buscar de verdad
    client = anthropic.Anthropic(api_key=api_key)
    prompt = _PROMPT.format(q=cat["q"], n=MAX_ITEMS_PER_BLOCK)
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            tools=[WEB_SEARCH_TOOL],
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            getattr(b, "text", "") for b in resp.content
            if getattr(b, "type", "") == "text"
        )
        items = _parse_json_array(text)
    except Exception as e:  # red, modelo no disponible, cuota, etc.
        print(f"[sgamet_feed] error en bloque {cat['id']}: {e}")
        return []
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        it["cat"] = cat["id"]
        it["owned"] = cat["owned"]
        out.append(it)
    return out


def fetch_all(api_key: str | None = None, model: str | None = None) -> dict:
    """Recoge todos los bloques en paralelo. Devuelve {generated_at, items, errors}."""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    model = model or DEFAULT_MODEL
    if not api_key:
        raise RuntimeError(
            "Falta ANTHROPIC_API_KEY (variable de entorno o st.secrets)."
        )
    items, errors = [], []
    with cf.ThreadPoolExecutor(max_workers=len(CATS)) as ex:
        futs = {ex.submit(fetch_category, c, api_key, model): c for c in CATS}
        for fut in cf.as_completed(futs):
            c = futs[fut]
            try:
                items.extend(fut.result())
            except Exception as e:
                errors.append(c["label"])
                print(f"[sgamet_feed] fallo bloque {c['id']}: {e}")

    def _key(it):
        try:
            return datetime.fromisoformat(str(it.get("fecha", "")))
        except Exception:
            return datetime.min
    items.sort(key=_key, reverse=True)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "items": items,
        "errors": errors,
    }


def cat_by_id(cid: str) -> dict:
    for c in CATS:
        if c["id"] == cid:
            return c
    return CATS[0]
