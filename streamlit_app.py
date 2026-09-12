"""
Cuadro de novedades SGAMET — app Streamlit.

Por defecto lee data/novedades.json (lo genera el cron diario, coste 0 por visita).
El boton "Actualizar ahora" fuerza una busqueda en vivo si hay clave de API.

La restriccion de acceso (lista de personas) se configura en Streamlit Community
Cloud (app privada + lista de viewers). El bloque OPCIONAL de abajo anade una
lista blanca por correo como defensa extra si despliegas con autenticacion propia
(p. ej. Entra ID en Azure).
"""
import json
import pathlib
from datetime import datetime

import streamlit as st
from sgamet_feed import CATS, cat_by_id, fetch_all

DATA = pathlib.Path(__file__).parent / "data" / "novedades.json"

st.set_page_config(page_title="Novedades SGAMET", page_icon="📡", layout="wide")

# --- (OPCIONAL) Lista blanca por correo --------------------------------------
# Solo actua si defines allowed_viewers en secrets Y hay identidad autenticada.
# En Community Cloud la lista de viewers ya restringe; esto es defensa en capas.
_allowed = st.secrets.get("allowed_viewers", None)
if _allowed:
    email = getattr(getattr(st, "user", None), "email", None)
    if email and email.lower() not in [a.lower() for a in _allowed]:
        st.error("No tienes acceso a este cuadro de mando.")
        st.stop()

# --- Estilos -----------------------------------------------------------------
st.markdown("""
<style>
  .block-container{max-width:1080px}
  .masthead h1{font-family:Georgia,serif;font-weight:600;font-size:26px;margin:0 0 2px}
  .kick{color:#0b474e;font-weight:600;font-size:12.5px;margin:0}
  .lead{color:#5b6472;font-size:13.5px;margin:2px 0 0;max-width:62ch}
  .stamp{color:#5b6472;font-size:12.5px}
  .card{background:#fff;border:1px solid #e3e7ec;border-left:4px solid var(--c,#0e5a63);
        border-radius:10px;padding:14px 16px;margin-bottom:11px;
        box-shadow:0 1px 2px rgba(20,25,32,.05),0 6px 16px rgba(20,25,32,.05)}
  .cat{font-size:11.5px;font-weight:700;letter-spacing:.2px;color:var(--ci,#0b474e)}
  .owned{font-size:10px;font-weight:700;color:#8a5a00;background:#fbf1dd;
         border:1px solid #efd9a8;border-radius:5px;padding:1px 6px;margin-left:8px}
  .card h3{margin:6px 0 5px;font-size:16px;line-height:1.35}
  .card h3 a{color:#141920;text-decoration:none}
  .card h3 a:hover{text-decoration:underline}
  .card p{margin:0 0 8px;color:#2c333d;font-size:14px}
  .meta{font-size:12px;color:#5b6472}
  .meta .src{font-family:ui-monospace,Menlo,monospace}
</style>
""", unsafe_allow_html=True)


def load_file() -> dict:
    if DATA.exists():
        try:
            return json.loads(DATA.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"generated_at": None, "items": [], "errors": []}


@st.cache_data(ttl=1800, show_spinner=False)
def live_fetch() -> dict:
    """Refresco en vivo, cacheado 30 min para no repetir llamadas entre visitas."""
    return fetch_all(api_key=st.secrets.get("ANTHROPIC_API_KEY"),
                     model=st.secrets.get("MODEL"))


if "data" not in st.session_state:
    st.session_state.data = load_file()

# --- Cabecera + controles ----------------------------------------------------
c1, c2 = st.columns([3, 1])
with c1:
    st.markdown('<div class="masthead">'
                '<p class="kick">Ministerio para la Transformacion Digital · SETID</p>'
                '<h1>Cuadro de novedades SGAMET</h1>'
                '<p class="lead">Seguimiento diario de las secciones web a cargo de '
                'SGAMET y de los portales del area de Telecomunicaciones e '
                'Infraestructuras Digitales.</p></div>', unsafe_allow_html=True)
with c2:
    has_key = bool(st.secrets.get("ANTHROPIC_API_KEY"))
    if st.button("↻ Actualizar ahora", type="primary", use_container_width=True,
                 disabled=not has_key,
                 help=None if has_key else "Configura ANTHROPIC_API_KEY para refrescar en vivo"):
        live_fetch.clear()
        with st.spinner("Consultando fuentes oficiales…"):
            st.session_state.data = live_fetch()
    gen = st.session_state.data.get("generated_at")
    if gen:
        try:
            dt = datetime.fromisoformat(gen)
            gen = dt.strftime("%d %b · %H:%M")
        except Exception:
            pass
    st.markdown(f'<div class="stamp">Ultima actualizacion:<br><b>{gen or "sin datos"}</b></div>',
                unsafe_allow_html=True)

data = st.session_state.data
items = data.get("items", [])
errors = data.get("errors", [])

m1, m2, m3, m4 = st.columns(4)
m1.metric("Secciones mapeadas", "119")
m2.metric("A cargo de SGAMET", "5")
m3.metric("Portales fuente", "4")
m4.metric("Novedades", len(items))

if errors:
    st.warning("No se pudieron consultar: " + ", ".join(errors) + ". Vuelve a actualizar.")

# --- Filtro ------------------------------------------------------------------
labels = ["Todas"] + [c["label"] for c in CATS]
choice = st.radio("Bloque", labels, horizontal=True, label_visibility="collapsed")
active = None if choice == "Todas" else next(c["id"] for c in CATS if c["label"] == choice)

shown = items if active is None else [i for i in items if i.get("cat") == active]

st.divider()

# --- Feed --------------------------------------------------------------------
if not items:
    st.info("Aun no hay novedades cargadas. Pulsa «Actualizar ahora» "
            "(si tienes clave de API) o espera al refresco diario automatico.")
elif not shown:
    st.info("Sin novedades recientes en este bloque. Prueba con «Todas».")
else:
    for it in shown:
        c = cat_by_id(it.get("cat", ""))
        src = str(it.get("fuente", "")).replace("https://", "").replace("http://", "").split("/")[0]
        url = it.get("url", "")
        title = it.get("titulo", "(sin titulo)")
        title_html = f'<a href="{url}" target="_blank" rel="noopener">{title}</a>' \
            if str(url).startswith("http") else title
        owned = '<span class="owned">SGAMET</span>' if it.get("owned") else ""
        st.markdown(
            f'<div class="card" style="--c:{c["color"]};--ci:{c["color"]}">'
            f'<span class="cat">{c["label"].upper()}</span>{owned}'
            f'<h3>{title_html}</h3>'
            f'<p>{it.get("resumen","")}</p>'
            f'<div class="meta"><span class="src">{src}</span>'
            + (f' &nbsp;·&nbsp; {it.get("fecha")}' if it.get("fecha") else "")
            + '</div></div>',
            unsafe_allow_html=True,
        )

st.caption("Las novedades se obtienen mediante busqueda web sobre fuentes publicas; "
           "es una vista de apoyo, no un canal oficial. Verifica en el portal original "
           "antes de citar. Los bloques SGAMET son las secciones de las que la unidad "
           "es responsable segun el mapa de organizacion.")
