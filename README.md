# Cuadro de novedades SGAMET

App Streamlit que vigila las secciones web a cargo de SGAMET y los portales del
área de Telecomunicaciones e Infraestructuras Digitales. Un cron diario recoge
las novedades (búsqueda web + resumen en español) y las publica; la app las
muestra en tarjetas con filtro por bloque. La clave de API vive en el servidor,
nunca en el navegador.

## Piezas

| Fichero | Qué hace |
|---|---|
| `streamlit_app.py` | La app: lee `data/novedades.json` y muestra las tarjetas. Botón de refresco en vivo. |
| `sgamet_feed.py` | Lógica de recogida: bloques a vigilar + llamadas a la API con búsqueda web. |
| `refresh.py` | Refresco desatendido; escribe `data/novedades.json`. Lo llama el cron. |
| `.github/workflows/daily.yml` | Cron de GitHub Actions: cada mañana ejecuta `refresh.py` y sube el JSON. |

## Despliegue en Streamlit Community Cloud (rápido)

1. Sube esta carpeta a un **repositorio privado** de GitHub (el repo privado hace
   que la app pueda ser privada).
2. En https://share.streamlit.io → **Create app** → elige el repo y
   `streamlit_app.py`.
3. En **Advanced settings → Secrets**, pega el contenido de
   `.streamlit/secrets.toml.example` con tu clave y modelo reales.
4. Deploy.

### Restringir a una lista de personas
En la app desplegada: **Share → desactiva "Make this app public"** para dejarla
privada, y **añade a cada persona como viewer** (por correo). Solo esos
podrán entrar. (Community Cloud permite una app privada a la vez.)

### Refresco diario automático
En el repo de GitHub: **Settings → Secrets and variables → Actions** y crea los
secretos `ANTHROPIC_API_KEY` y `MODEL`. El workflow ya corre laborables a las
06:00 UTC y hace commit de `data/novedades.json`. Puedes lanzarlo a mano desde la
pestaña **Actions → Refresco diario → Run workflow**.

El botón **↻ Actualizar ahora** de la app fuerza una búsqueda en vivo (requiere
que `ANTHROPIC_API_KEY` esté en los secrets de Streamlit).

## Prueba en local

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # y edítalo
ANTHROPIC_API_KEY=sk-ant-... MODEL=claude-sonnet-5 python refresh.py
streamlit run streamlit_app.py
```

## Migrar a Azure (versión gobernada)

El mismo código corre en **Azure App Service** (contenedor o `pip` + `streamlit
run`). Cambios: la clave va en **Key Vault**, la restricción de acceso se hace
con **Entra ID (Easy Auth)** restringido a un grupo, y el cron pasa a ser una
**Azure Function con temporizador** que ejecuta `refresh.py`. No hay que tocar
`streamlit_app.py` ni `sgamet_feed.py`.

## Ajustes

- **Modelo**: `MODEL` en secrets. Sonnet equilibra coste/calidad; Haiku abarata.
- **Bloques y fuentes**: edita la lista `CATS` en `sgamet_feed.py`.
- **Versión de la herramienta de búsqueda**: constante `WEB_SEARCH_TOOL` en
  `sgamet_feed.py`, por si Anthropic publica una posterior.
