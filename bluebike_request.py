import sys
import requests
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

GBFS_URL = "https://gbfs.lyft.com/gbfs/1.1/bos/gbfs.json"
OUTPUT_DIR = Path("data_raw")

# Grupos de feeds: edítalos cuando decidas cuál va en cuál
FEEDS_FRECUENTES = [
    "station_status",
    "free_bike_status",
    "ebikes_at_stations",
    "system_alerts",
]

FEEDS_ESTATICOS = [
    "gbfs",
    "system_information",
    "station_information",
    "system_hours",
    "system_calendar",
    "system_regions",
    "system_pricing_plans",
    "gbfs_versions",
]

GRUPOS = {
    "frecuentes": FEEDS_FRECUENTES,
    "estaticos": FEEDS_ESTATICOS,
    "todos": FEEDS_FRECUENTES + FEEDS_ESTATICOS,
}


def get_json(url):
    """Descarga una URL y devuelve el JSON."""
    response = requests.get(url, timeout=30)
    response.raise_for_status()  # lanza error si la petición falló
    return response.json()


def feed_to_dataframe(payload):
    """Convierte la respuesta de un feed en una tabla (DataFrame)."""
    data = payload["data"]

    # Buscamos si dentro de "data" hay una lista (estaciones, bicis, alertas...)
    lista = None
    for value in data.values():
        if isinstance(value, list):
            lista = value
            break

    if lista is not None:
        df = pd.json_normalize(lista)   # una fila por elemento de la lista
    else:
        df = pd.json_normalize(data)    # un objeto único -> una fila

    # Columnas de control, útiles después en dbt
    df["feed_last_updated"] = payload.get("last_updated")
    df["feed_ttl"] = payload.get("ttl")
    df["extracted_at"] = datetime.now(timezone.utc).isoformat()
    return df


def main():
    # El grupo se pasa al ejecutar: python extract_gbfs.py frecuentes
    grupo = sys.argv[1] if len(sys.argv) > 1 else "todos"
    if grupo not in GRUPOS:
        print(f"Grupo inválido. Usa: {list(GRUPOS)}")
        return
    feeds_a_extraer = GRUPOS[grupo]

    OUTPUT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    gbfs = get_json(GBFS_URL)
    feeds = gbfs["data"]["en"]["feeds"]

    for feed in feeds:
        name = feed["name"]
        if name not in feeds_a_extraer:   # saltamos los que no son del grupo
            continue
        try:
            payload = get_json(feed["url"])
            df = feed_to_dataframe(payload)
            file_path = OUTPUT_DIR / f"{name}_{timestamp}.csv"
            df.to_csv(file_path, index=False)
            print(f"OK    {name}: {len(df)} filas -> {file_path}")
        except Exception as e:
            print(f"ERROR {name}: {e}")


if __name__ == "__main__":
    main()