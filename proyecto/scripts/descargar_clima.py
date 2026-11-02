"""Descarga un snapshot meteorológico de Open-Meteo (guía G07).

Crea ``data/weather/<descarga>_<api>/`` con ``forecast.json`` (respuesta de la
API) y ``metadata.json`` (fuente, modelo, fecha de descarga, coordenadas, zona
horaria, variables y unidades). Nunca sobrescribe un snapshot existente: un
pronóstico descargado otro día es otro dato.

Uso:
    python scripts/descargar_clima.py --lat -33.45 --lon -70.66 --inicio 2026-11-27 --fin 2026-12-11
    python scripts/descargar_clima.py --api historico --lat ... --lon ... --inicio 2025-11-27 --fin 2025-12-11

APIs: pronostico (forecast), historico (archive ERA5, observación/reanálisis),
pronostico_historico (historical-forecast). Después, en el YAML:

    simulacion: {inicio: "2026-11-27T04:00"}
    clima: {snapshot: ../data/weather/<carpeta>, completar: error}
"""

from __future__ import annotations

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
APIS = {
    "pronostico": ("https://api.open-meteo.com/v1/forecast", "forecast determinista"),
    "historico": ("https://archive-api.open-meteo.com/v1/archive", "observación / reanálisis"),
    "pronostico_historico": ("https://historical-forecast-api.open-meteo.com/v1/forecast", "forecast histórico"),
}
VARIABLES = ("temperature_2m", "wind_speed_10m", "shortwave_radiation")


def construir_url(api: str, lat: float, lon: float, inicio: date, fin: date, modelo: str | None) -> str:
    base, _ = APIS[api]
    parametros = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "hourly": ",".join(VARIABLES),
        "wind_speed_unit": "ms",
        "timezone": "auto",
        "start_date": inicio.isoformat(),
        "end_date": fin.isoformat(),
    }
    if modelo:
        parametros["models"] = modelo
    return f"{base}?{urllib.parse.urlencode(parametros)}"


def guardar_snapshot(respuesta: dict, url: str, api: str, modelo: str | None, lat: float, lon: float,
                     destino: Path, descargado: datetime) -> Path:
    carpeta = destino / f"{descargado:%Y-%m-%dT%H%M}_{api}"
    if carpeta.exists():
        raise FileExistsError(f"Ya existe {carpeta}: un snapshot no se sobrescribe.")
    unidades = respuesta.get("hourly_units", {})
    faltan = [v for v in VARIABLES if v not in respuesta.get("hourly", {})]
    if faltan:
        raise ValueError(f"La respuesta no trae {faltan}.")
    meta = {
        "source": f"Open-Meteo {api}",
        "kind": APIS[api][1],
        "model": modelo or "best_match",
        "retrieved_at": descargado.isoformat(timespec="seconds"),
        "latitude": lat,
        "longitude": lon,
        "latitude_grid": respuesta.get("latitude"),
        "longitude_grid": respuesta.get("longitude"),
        "timezone": respuesta.get("timezone"),
        "variables": list(VARIABLES),
        "units": {v: unidades.get(v) for v in VARIABLES},
        "url": url,
    }
    carpeta.mkdir(parents=True)
    (carpeta / "forecast.json").write_text(json.dumps(respuesta, indent=1), encoding="utf-8")
    (carpeta / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return carpeta


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--lat", type=float, required=True)
    p.add_argument("--lon", type=float, required=True)
    p.add_argument("--inicio", type=date.fromisoformat, required=True, help="AAAA-MM-DD")
    p.add_argument("--fin", type=date.fromisoformat, required=True, help="AAAA-MM-DD")
    p.add_argument("--api", choices=sorted(APIS), default="pronostico")
    p.add_argument("--modelo", help="Modelo meteorológico de Open-Meteo (por defecto best_match).")
    p.add_argument("--destino", type=Path, default=RAIZ / "data" / "weather")
    a = p.parse_args(argv)
    if not (-90 <= a.lat <= 90 and -180 <= a.lon <= 180) or a.fin < a.inicio:
        p.error("Coordenadas fuera de rango o --fin anterior a --inicio.")
    url = construir_url(a.api, a.lat, a.lon, a.inicio, a.fin, a.modelo)
    print(f"Descargando {url}")
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            respuesta = json.load(r)
    except OSError as exc:
        print(f"Error de descarga: {exc}", file=sys.stderr)
        return 2
    if respuesta.get("error"):
        print(f"Open-Meteo: {respuesta.get('reason')}", file=sys.stderr)
        return 2
    carpeta = guardar_snapshot(respuesta, url, a.api, a.modelo, a.lat, a.lon, a.destino,
                               datetime.now(timezone.utc))
    tiempos = respuesta["hourly"]["time"]
    print(f"Snapshot: {carpeta}\n  {len(tiempos)} horas, {tiempos[0]} -> {tiempos[-1]} ({respuesta.get('timezone')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
