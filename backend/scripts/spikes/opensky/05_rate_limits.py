"""
Spike TG-11 - Fase 5: tarifa de creditos por tamano de area y por endpoint.

PREGUNTA DEL SPIKE QUE RESPONDE
    (4) "Cuales son los rate limits reales?" - los huecos que quedaron tras
    las fases 1, 3, 4 y 6.

QUE YA SE SABIA ANTES DE ESTA FASE
    - Cuota de 4000 creditos/dia por familia de endpoints, con contadores
      INDEPENDIENTES entre /states/*, /flights/* y /tracks/*.
    - Bounding box chico de Costa Rica (~11.6 grados cuadrados): 1 credito.
    - Consulta global por icao24 (sin bbox): 4 creditos.
    - /flights/*: 30 creditos por consulta.

QUE FALTABA Y MIDE ESTA FASE
    1. La tarifa de areas INTERMEDIAS. Solo se habian medido los dos extremos.
       La hipotesis a contrastar es el esquema escalonado por area:
         <25 grados^2 -> 1 | <400 -> 2 | <2500 -> 3 | resto -> 4
    2. El costo de /tracks/all, que en la Fase 4 se llamo una sola vez y por
       lo tanto no tenia par consecutivo con el cual restar.

QUE **NO** MIDE Y POR QUE
    El comportamiento exacto al recibir 429. Provocarlo exige agotar 4000
    creditos a proposito: el costo no justifica el dato. El manejo de 429 se
    programa defensivamente leyendo x-rate-limit-remaining, que viene en
    todas las respuestas.

METODO
    Llamadas CONSECUTIVAS al mismo endpoint, restando el header entre una y
    la siguiente. Es la unica resta valida: el contador no es comparable
    entre familias de endpoints (ver Fase 4).

COSTO
    ~15 creditos de /states/* y ~2 llamadas de /tracks/*.

USO
    python backend/scripts/spikes/opensky/05_rate_limits.py --network personal

    Evidencia en backend/scripts/spikes/opensky/output/05_rate_limits_<red>.json
"""

from __future__ import annotations

import sys
import time
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
BASE = "https://opensky-network.org/api"
TIMEOUT = 30.0

# Bounding boxes de area creciente. La columna "esperado" es la hipotesis del
# esquema escalonado; el script la confirma o la refuta.
BOXES = [
    ("costa_rica", {"lamin": 8.0, "lomin": -86.0, "lamax": 11.3, "lomax": -82.5}, 1),
    ("centroamerica", {"lamin": 7.0, "lomin": -93.0, "lamax": 18.0, "lomax": -77.0}, 2),
    ("caribe_amplio", {"lamin": 5.0, "lomin": -100.0, "lamax": 30.0, "lomax": -60.0}, 3),
    ("americas", {"lamin": -30.0, "lomin": -120.0, "lamax": 45.0, "lomax": -35.0}, 4),
    ("global", {"lamin": -90.0, "lomin": -180.0, "lamax": 90.0, "lomax": 180.0}, 4),
]

TRACKS_ICAO24 = "0ac9e1"  # AVA072, usado en la Fase 4


def area_deg2(box: dict) -> float:
    """Area del bounding box en grados cuadrados."""
    return (box["lamax"] - box["lamin"]) * (box["lomax"] - box["lomin"])


def get_token(client_id: str, client_secret: str) -> str:
    """Obtiene el token OAuth2. Aborta con mensaje claro si falla."""
    import httpx

    try:
        response = httpx.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials",
                  "client_id": client_id, "client_secret": client_secret},
            timeout=TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001
        category, explanation = describe_http_error(exc)
        sys.exit("[FATAL] No se pudo pedir el token (" + category + "): " + explanation)
    if response.status_code != 200:
        sys.exit("[FATAL] Token HTTP " + str(response.status_code))
    token = response.json().get("access_token")
    if not token:
        sys.exit("[FATAL] La respuesta no contiene access_token.")
    return token


def query(token: str, path: str, params: dict) -> dict:
    """Una consulta. Devuelve status, creditos restantes y tamano de respuesta."""
    import httpx

    started = time.perf_counter()
    try:
        response = httpx.get(BASE + path, params=params,
                             headers={"Authorization": "Bearer " + token}, timeout=TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        category, explanation = describe_http_error(exc)
        return {"ok": False, "error_category": category, "error_detail": explanation}

    remaining = response.headers.get("x-rate-limit-remaining")
    result = {
        "ok": response.status_code == 200,
        "status_code": response.status_code,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "credits_remaining": int(remaining) if remaining and remaining.isdigit() else None,
        "response_bytes": len(response.content),
    }
    if response.status_code == 200:
        try:
            payload = response.json()
        except ValueError:
            result["ok"] = False
            result["error_detail"] = "200 sin JSON valido"
        else:
            if isinstance(payload, dict):
                states = payload.get("states")
                result["item_count"] = len(states) if states else 0
            elif isinstance(payload, list):
                result["item_count"] = len(payload)
    else:
        result["error_detail"] = response.text[:150]
    return result


def main() -> int:
    args = network_arg("Spike TG-11 Fase 5: tarifa por area y por endpoint")
    env = load_env()
    client_id = require(env, "OPENSKY_CLIENT_ID")
    client_secret = require(env, "OPENSKY_CLIENT_SECRET")

    timestamp = header(
        "TrackIn - Spike TG-11 - Fase 5: tarifa de creditos",
        args.network,
        {"client_id": mask(client_id)},
    )
    token = get_token(client_id, client_secret)

    # --- Tarifa por area ---------------------------------------------------
    print(SUB)
    print("  TARIFA POR TAMANO DE BOUNDING BOX (/states/all)")
    print(SUB)
    print("  {:<15} {:>12} {:>9} {:>9} {:>10} {:>8}".format(
        "zona", "area_deg2", "aeronaves", "costo", "esperado", "coincide"))

    # Llamada de calibracion: fija la linea base del contador. Su propio costo
    # no se puede medir porque no hay lectura anterior con la cual restar.
    baseline = query(token, "/states/all", BOXES[0][1])
    if not baseline.get("ok"):
        print("  [FATAL] La llamada de calibracion fallo: " + str(baseline.get("error_detail")))
        return 1
    previous = baseline["credits_remaining"]

    measurements: list[dict] = []
    matches = 0
    for name, box, expected in BOXES:
        result = query(token, "/states/all", box)
        if not result.get("ok"):
            print("  {:<15} [FALLO] {}".format(name, result.get("error_detail")))
            measurements.append({"zone": name, "bbox": box, "ok": False, **result})
            continue
        remaining = result["credits_remaining"]
        cost = (previous - remaining) if (previous and remaining) else None
        previous = remaining
        area = area_deg2(box)
        coincide = "si" if cost == expected else "NO"
        if cost == expected:
            matches += 1
        print("  {:<15} {:>12.0f} {:>9} {:>9} {:>10} {:>8}".format(
            name, area, result.get("item_count", 0),
            cost if cost is not None else "-", expected, coincide))
        measurements.append({
            "zone": name, "bbox": box, "ok": True,
            "area_deg2": round(area, 1),
            "aircraft": result.get("item_count", 0),
            "measured_cost": cost,
            "expected_cost": expected,
            "matches_hypothesis": cost == expected,
            "credits_remaining": remaining,
            "response_bytes": result.get("response_bytes"),
            "elapsed_ms": result.get("elapsed_ms"),
        })

    # --- Costo de /tracks/all ---------------------------------------------
    print(SUB)
    print("  COSTO DE /tracks/all")
    print(SUB)
    t_base = query(token, "/tracks/all", {"icao24": TRACKS_ICAO24, "time": 0})
    t_second = query(token, "/tracks/all", {"icao24": TRACKS_ICAO24, "time": 0})
    tracks_cost = None
    if t_base.get("ok") and t_second.get("ok"):
        if t_base["credits_remaining"] and t_second["credits_remaining"]:
            tracks_cost = t_base["credits_remaining"] - t_second["credits_remaining"]
        print("  calibracion    creditos_rest={}".format(t_base["credits_remaining"]))
        print("  medicion       creditos_rest={}   costo={}".format(
            t_second["credits_remaining"], tracks_cost))
    else:
        failed = t_base if not t_base.get("ok") else t_second
        print("  [FALLO] {} - {}".format(
            failed.get("status_code"), failed.get("error_detail")))

    # --- Lectura -----------------------------------------------------------
    print(SEP)
    print("  LECTURA")
    print(SEP)
    valid = [m for m in measurements if m.get("ok") and m.get("measured_cost") is not None]
    if len(valid) == matches and valid:
        print("  El esquema escalonado por area se CONFIRMA en los {} tramos medidos:".format(
            len(valid)))
        print("    <25 grados^2 -> 1 | <400 -> 2 | <2500 -> 3 | resto -> 4")
    elif valid:
        print("  El esquema escalonado NO se confirma del todo: {}/{} tramos coinciden.".format(
            matches, len(valid)))
        print("  Los costos reales medidos son los de la tabla de arriba; usar esos.")
    else:
        print("  No se pudo medir ningun tramo.")

    print()
    if tracks_cost is not None:
        print("  /tracks/all cuesta {} credito(s) por consulta.".format(tracks_cost))
    else:
        print("  /tracks/all: costo no medido en esta corrida.")

    print()
    print("  PARA SPRINT 3: el bounding box de Costa Rica es el tramo mas barato")
    print("  (1 credito). Ampliar el area para cubrir la ruta completa de un vuelo")
    print("  multiplica el costo por 2, 3 o 4. Conviene sondear el area de destino")
    print("  y no la ruta entera.")
    print(SEP)

    evidence = {
        "spike": "TG-11",
        "phase": "5-rate-limits",
        "timestamp_utc": timestamp,
        "finished_utc": utc_now(),
        "network_profile": args.network,
        "note": (
            "Completa los huecos que dejaron las fases 1, 3, 4 y 6. NO se prueba "
            "el comportamiento ante 429: exigiria agotar 4000 creditos a proposito."
        ),
        "area_tariff": measurements,
        "hypothesis_matches": matches,
        "hypothesis_total": len(valid),
        "tracks_all_cost_credits": tracks_cost,
        "passed": bool(valid),
    }
    save_evidence("opensky", "05_rate_limits_" + args.network + ".json", evidence)
    return 0


if __name__ == "__main__":
    sys.exit(main())
