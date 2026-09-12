"""
Refresco desatendido. Lo ejecuta el cron de GitHub Actions cada manana:
recoge las novedades y las escribe en data/novedades.json, que la app lee
sin coste de API por visita.

Uso local:  ANTHROPIC_API_KEY=sk-ant-... MODEL=claude-sonnet-5 python refresh.py
"""
import json
import pathlib
import sys
from sgamet_feed import fetch_all

OUT = pathlib.Path(__file__).parent / "data" / "novedades.json"


def main() -> int:
    try:
        data = fetch_all()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {len(data['items'])} novedades escritas en {OUT} "
          f"(errores: {data['errors'] or 'ninguno'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
