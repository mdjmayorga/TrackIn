"""
Spike TG-11 - Fase 2: cobertura ADS-B de OpenSky sobre Costa Rica.

PREGUNTA DEL SPIKE QUE RESPONDE
    (2) "Que cobertura hay sobre Costa Rica (Juan Santamaria, Liberia)?"

LA PREGUNTA REAL DETRAS
    En la Fase 1 vimos 12 aeronaves en el bbox de CR. Ese numero por si solo
    no dice nada util para TrackIn. Lo que decide si esta fuente sirve es
    DONDE estan esas aeronaves:
      - Si todas van en crucero a 11.000 m sobrevolando el pais rumbo a
        Sudamerica, la cobertura NO sirve para saber si un embarque aterrizo
        en MROC.
      - Si hay trafico en aproximacion, salida y tierra en los aeropuertos,
        la fuente si permite seguir una llegada.
    Esta fase distingue esos dos escenarios.

METODO
    5 muestras espaciadas 30 s (no una sola foto: una consulta puntual no
    distingue cobertura real de casualidad). UNA sola request por muestra
    sobre el bbox de CR y segmentacion local del resultado, en vez de
    consultar tres bounding boxes por muestra. Con 4000 creditos/dia medidos
    en la Fase 1, gastar el triple de cuota para el mismo dato no se justifica.
    Costo total: 5 creditos.

TAMBIEN MIDE
    - Staleness: antiguedad de last_contact respecto de la hora del servidor.
      Indica cuan fresca es realmente la posicion que entrega la API.
    - Completitud de campos: porcentaje de registros con callsign, posicion,
      altitud y velocidad nulos. Alimenta la Fase 6 (casos borde).

USO
    python backend/scripts/spikes/opensky/02_coverage_cr.py --network personal

SALIDA
    Codigo 0 si se obtuvo al menos una muestra valida.
    Evidencia en backend/scripts/spikes/opensky/output/02_coverage_<red>.json
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import (  # noqa: E402
    SEP,
    SUB,
    describe_http_error,
    header,
    load_env,
    mask,
    network_arg,
    require,
    save_evidence,
    utc_now,
)

TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network"
    "/protocol/openid-connect/token"
)
STATES_URL = "https://opensky-network.org/api/states/all"

CR_BBOX = {"lamin": 8.0, "lomin": -86.0, "lamax": 11.3, "lomax": -82.5}

# Aeropuertos internacionales relevantes para importaciones de Gutis.
# El radio de 0.25 grados son ~28 km: cubre aproximacion final y patron de
# trafico sin invadir el area del otro aeropuerto.
AIRPORTS = {
    "MROC": {"name": "Juan Santamaria (SJO)", "lat": 9.9939, "lon": -84.2088, "radius_deg": 0.25},
    "MRLB": {"name": "Daniel Oduber, Liberia (LIR)", "lat": 10.5933, "lon": -85.5444, "radius_deg": 0.25},
}

SAMPLES = 5
INTERVAL_S = 30
TIMEOUT = 20.0

# Indices del array de estado que devuelve /states/all.
# La API entrega listas posicionales, no objetos: documentarlo aca evita
# errores de off-by-one al leer el codigo despues.
IDX = {
    "icao24": 0, "callsign": 1, "origin_country": 2, "time_position": 3,
    "last_contact": 4, "longitude": 5, "latitude": 6, "baro_altitude": 7,
    "on_ground": 8, "velocity": 9, "true_track": 10, "vertical_rate": 11,
    "sensors": 12, "geo_altitude": 13, "squawk": 14, "spi": 15,
    "position_source": 16,
}

# Umbral de altitud para separar aproximacion/salida de crucero.
# 3000 m es el orden de magnitud en que una aeronave ya esta configurada
# para aterrizar o acaba de despegar.
APPROACH_CEILING_M = 3000.0


def get_token(client_id: str, client_secret: str) -> str:
    """Obtiene el token OAuth2. Aborta con mensaje claro si falla."""
    import httpx

    try:
        response = httpx.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001
        category, explanation = describe_http_error(exc)
        sys.exit("[FATAL] No se pudo pedir el token (" + category + "): " + explanation)

    if response.status_code != 200:
        sys.exit(
            "[FATAL] Token HTTP " + str(response.status_code) + ": " + response.text[:200]
            + "\n        Correr primero 01_auth_test.py para diagnosticar."
        )
    token = response.json().get("access_token")
    if not token:
        sys.exit("[FATAL] La respuesta no contiene access_token.")
    return token


def fetch_sample(token: str, index: int) -> dict:
    """Una muestra de /states/all sobre el bbox de Costa Rica."""
    import httpx

    sample: dict = {"index": index, "requested_utc": utc_now()}
    try:
        response = httpx.get(
            STATES_URL,
            params=CR_BBOX,
            headers={"Authorization": "Bearer " + token},
            timeout=TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001
        category, explanation = describe_http_error(exc)
        sample.update(ok=False, error_category=category, error_detail=explanation)
        return sample

    sample["status_code"] = response.status_code
    remaining = response.headers.get("x-rate-limit-remaining")
    sample["credits_remaining"] = int(remaining) if remaining and remaining.isdigit() else None

    if response.status_code == 429:
        sample.update(ok=False, error_category="rate_limited",
                      error_detail="Cuota diaria agotada")
        return sample
    if response.status_code != 200:
        sample.update(ok=False, error_category="http_" + str(response.status_code),
                      error_detail=response.text[:200])
        return sample

    try:
        payload = response.json()
    except ValueError:
        sample.update(ok=False, error_category="invalid_json",
                      error_detail="200 sin JSON valido")
        return sample

    sample.update(ok=True, server_time=payload.get("time"), states=payload.get("states") or [])
    return sample


def distance_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Distancia euclidea en grados. Aproximacion deliberada.

    A la latitud de Costa Rica (~10 N) un grado de longitud son ~110 km y uno
    de latitud ~111 km, asi que la distorsion es despreciable para clasificar
    aeronaves en un radio de 28 km. No hace falta haversine para esto.
    """
    return ((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2) ** 0.5


def classify(state: list, server_time: int | None) -> dict:
    """Extrae y clasifica una aeronave a partir de su array de estado."""
    def field(name: str):
        idx = IDX[name]
        return state[idx] if len(state) > idx else None

    lat, lon = field("latitude"), field("longitude")
    altitude = field("baro_altitude")
    if altitude is None:
        altitude = field("geo_altitude")
    on_ground = bool(field("on_ground"))
    callsign = (field("callsign") or "").strip()
    last_contact = field("last_contact")

    zone = "en_ruta"
    if lat is not None and lon is not None:
        for code, airport in AIRPORTS.items():
            if distance_deg(lat, lon, airport["lat"], airport["lon"]) <= airport["radius_deg"]:
                zone = code
                break

    if on_ground:
        regime = "en_tierra"
    elif altitude is None:
        regime = "altitud_desconocida"
    elif altitude < APPROACH_CEILING_M:
        regime = "aproximacion_o_salida"
    else:
        regime = "crucero"

    staleness = None
    if isinstance(server_time, (int, float)) and isinstance(last_contact, (int, float)):
        staleness = server_time - last_contact

    return {
        "icao24": field("icao24"),
        "callsign": callsign or None,
        "origin_country": field("origin_country"),
        "latitude": lat,
        "longitude": lon,
        "altitude_m": altitude,
        "on_ground": on_ground,
        "velocity_ms": field("velocity"),
        "vertical_rate_ms": field("vertical_rate"),
        "squawk": field("squawk"),
        "position_source": field("position_source"),
        "last_contact": last_contact,
        "staleness_s": staleness,
        "zone": zone,
        "regime": regime,
    }


def main() -> int:
    args = network_arg("Spike TG-11 Fase 2: cobertura ADS-B sobre Costa Rica")
    env = load_env()
    client_id = require(env, "OPENSKY_CLIENT_ID")
    client_secret = require(env, "OPENSKY_CLIENT_SECRET")

    timestamp = header(
        "TrackIn - Spike TG-11 - Fase 2: cobertura sobre Costa Rica",
        args.network,
        {
            "client_id": mask(client_id),
            "bbox": json.dumps(CR_BBOX),
            "muestras": str(SAMPLES) + " cada " + str(INTERVAL_S) + " s (~"
                        + str(SAMPLES * INTERVAL_S // 60) + " min, " + str(SAMPLES) + " creditos)",
        },
    )

    token = get_token(client_id, client_secret)
    print("  Token       : obtenido")

    samples: list[dict] = []
    aircraft_by_sample: list[list[dict]] = []

    print(SUB)
    print("  MUESTREO")
    print(SUB)
    for i in range(1, SAMPLES + 1):
        sample = fetch_sample(token, i)
        if sample.get("ok"):
            aircraft = [classify(s, sample.get("server_time")) for s in sample["states"]]
            aircraft_by_sample.append(aircraft)
            zones: dict[str, int] = {}
            for entry in aircraft:
                zones[entry["zone"]] = zones.get(entry["zone"], 0) + 1
            zone_txt = ", ".join(k + "=" + str(v) for k, v in sorted(zones.items()))
            print("  Muestra {}/{}  [OK]   {:>3} aeronaves   creditos={}   {}".format(
                i, SAMPLES, len(aircraft), sample.get("credits_remaining"), zone_txt))
            sample["aircraft_count"] = len(aircraft)
            del sample["states"]  # se guardan clasificadas mas abajo
        else:
            aircraft_by_sample.append([])
            print("  Muestra {}/{}  [FALLO] {} - {}".format(
                i, SAMPLES, sample.get("error_category"), sample.get("error_detail")))
        samples.append(sample)

        if i < SAMPLES:
            time.sleep(INTERVAL_S)

    valid = [s for s in samples if s.get("ok")]
    if not valid:
        print(SEP)
        print("  Fase 2 NO superada: ninguna muestra valida.")
        print(SEP)
        save_evidence("opensky", "02_coverage_" + args.network + ".json", {
            "spike": "TG-11", "phase": "2-coverage-cr", "timestamp_utc": timestamp,
            "network_profile": args.network, "samples": samples, "passed": False,
        })
        return 1

    # --- Agregacion --------------------------------------------------------
    # Se consolida por icao24: la misma aeronave aparece en varias muestras y
    # contarla varias veces inflaria la cobertura aparente.
    unique: dict[str, dict] = {}
    for aircraft in aircraft_by_sample:
        for entry in aircraft:
            key = entry["icao24"]
            if key:
                unique.setdefault(key, entry)
                # conservamos el registro mas informativo (con posicion)
                if unique[key]["latitude"] is None and entry["latitude"] is not None:
                    unique[key] = entry

    counts = [s["aircraft_count"] for s in valid]
    zone_totals: dict[str, int] = {}
    regime_totals: dict[str, int] = {}
    for entry in unique.values():
        zone_totals[entry["zone"]] = zone_totals.get(entry["zone"], 0) + 1
        regime_totals[entry["regime"]] = regime_totals.get(entry["regime"], 0) + 1

    total_unique = len(unique)
    nulls = {
        "sin_callsign": sum(1 for e in unique.values() if not e["callsign"]),
        "sin_posicion": sum(1 for e in unique.values() if e["latitude"] is None),
        "sin_altitud": sum(1 for e in unique.values() if e["altitude_m"] is None),
        "sin_velocidad": sum(1 for e in unique.values() if e["velocity_ms"] is None),
    }
    staleness_values = [e["staleness_s"] for e in unique.values()
                        if isinstance(e["staleness_s"], (int, float))]

    print(SUB)
    print("  RESUMEN DE COBERTURA")
    print(SUB)
    print("  Muestras validas      : {}/{}".format(len(valid), SAMPLES))
    print("  Aeronaves por muestra : min={} max={} media={:.1f}".format(
        min(counts), max(counts), statistics.mean(counts)))
    print("  Aeronaves unicas      : {} (consolidadas por icao24)".format(total_unique))
    print()
    print("  Por zona:")
    for zone in ("MROC", "MRLB", "en_ruta"):
        count = zone_totals.get(zone, 0)
        label = AIRPORTS[zone]["name"] if zone in AIRPORTS else "En ruta / sobrevuelo"
        pct = (100.0 * count / total_unique) if total_unique else 0.0
        print("    {:<8} {:>3}  ({:>5.1f}%)  {}".format(zone, count, pct, label))
    print()
    print("  Por regimen de vuelo:")
    for regime in ("en_tierra", "aproximacion_o_salida", "crucero", "altitud_desconocida"):
        count = regime_totals.get(regime, 0)
        pct = (100.0 * count / total_unique) if total_unique else 0.0
        print("    {:<24} {:>3}  ({:>5.1f}%)".format(regime, count, pct))
    print()
    print("  Completitud de campos (sobre {} aeronaves):".format(total_unique))
    for field_name, count in nulls.items():
        pct = (100.0 * count / total_unique) if total_unique else 0.0
        print("    {:<16} {:>3}  ({:>5.1f}%)".format(field_name, count, pct))
    print()
    if staleness_values:
        print("  Frescura de la posicion (server_time - last_contact):")
        print("    min={:.0f}s  mediana={:.0f}s  max={:.0f}s".format(
            min(staleness_values), statistics.median(staleness_values), max(staleness_values)))
    else:
        print("  Frescura: no se pudo calcular (faltan last_contact o server_time)")

    # --- Lectura -----------------------------------------------------------
    airport_traffic = zone_totals.get("MROC", 0) + zone_totals.get("MRLB", 0)
    low_altitude = regime_totals.get("en_tierra", 0) + regime_totals.get("aproximacion_o_salida", 0)

    print(SEP)
    print("  LECTURA")
    print(SEP)
    if airport_traffic == 0 and low_altitude == 0:
        verdict = "solo_sobrevuelo"
        print("  Toda la cobertura observada es de crucero: no se vio una sola aeronave")
        print("  en tierra ni en aproximacion en MROC o MRLB.")
        print("  IMPLICACION: /states/all NO alcanza para saber si un embarque aterrizo.")
        print("  El modulo de Sprint 3 tendria que apoyarse en /flights/arrival por")
        print("  aeropuerto en vez de posiciones en vivo. Repetir esta fase en otro")
        print("  horario antes de concluir: puede ser una franja de bajo trafico.")
    elif airport_traffic == 0:
        verdict = "cobertura_parcial"
        print("  Hay trafico a baja altitud pero ninguna aeronave dentro del radio de")
        print("  MROC o MRLB en esta corrida. Cobertura util pero no confirmada en los")
        print("  aeropuertos objetivo. Repetir en franja de mayor trafico.")
    else:
        verdict = "cobertura_util"
        print("  Se observo trafico dentro del radio de los aeropuertos objetivo:")
        print("  la fuente permite seguir aeronaves en aproximacion, no solo sobrevuelos.")
        print("  IMPLICACION: /states/all es viable como fuente de posicion en vivo.")
    print(SEP)

    evidence = {
        "spike": "TG-11",
        "phase": "2-coverage-cr",
        "timestamp_utc": timestamp,
        "finished_utc": utc_now(),
        "network_profile": args.network,
        "bbox": CR_BBOX,
        "airports": AIRPORTS,
        "config": {"samples": SAMPLES, "interval_s": INTERVAL_S,
                   "approach_ceiling_m": APPROACH_CEILING_M},
        "samples": samples,
        "aircraft_per_sample": counts,
        "unique_aircraft_count": total_unique,
        "zone_totals": zone_totals,
        "regime_totals": regime_totals,
        "null_fields": nulls,
        "staleness_s": {
            "min": min(staleness_values) if staleness_values else None,
            "median": statistics.median(staleness_values) if staleness_values else None,
            "max": max(staleness_values) if staleness_values else None,
        },
        "unique_aircraft": list(unique.values()),
        "verdict": verdict,
        "passed": True,
    }
    save_evidence("opensky", "02_coverage_" + args.network + ".json", evidence)

    return 0


if __name__ == "__main__":
    sys.exit(main())
