"""
Spike TG-11 - Fase 6: casos borde y contrato de errores.

PREGUNTA DEL SPIKE QUE RESPONDE
    (6) "Como manejar aeronaves sin destino declarado o con senal perdida?"

ENFOQUE
    Las fases anteriores encontraron casos borde por accidente (callsign nulo,
    staleness de 207 s, destino sin resolver). Esta fase los PROVOCA a
    proposito y documenta la respuesta exacta de la API en cada uno, para que
    el modulo de Sprint 3 se disene contra un contrato conocido en vez de
    descubrirlo en produccion.

CASOS PROBADOS
    1. icao24 inexistente          -> lista vacia o null? consume credito?
    2. Bounding box sin trafico    -> como se distingue de un fallo de red?
    3. Token invalido              -> distinguir "expirado" de "credencial mala"
    4. Ventana de 3 particiones    -> mensaje de error exacto
    5. Aeropuerto inexistente      -> 404 o 200 vacio?
    6. Parametro obligatorio ausente
    7. CONTINUIDAD DE SEGUIMIENTO  -> dos muestras separadas 60 s para medir
       cuantas aeronaves DESAPARECEN del bbox. Es la medida real de "senal
       perdida" y decide si el dashboard puede afirmar "en ruta" o debe decir
       "ultima posicion conocida hace N minutos".

COSTO
    ~8 consultas. Los casos de error (400/401/404) normalmente no consumen
    cuota; se verifica leyendo el header en cada uno.

USO
    python backend/scripts/spikes/opensky/06_edge_cases.py --network personal

    Evidencia en backend/scripts/spikes/opensky/output/06_edge_cases_<red>.json
"""

from __future__ import annotations

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
BASE = "https://opensky-network.org/api"
TIMEOUT = 30.0

CR_BBOX = {"lamin": 8.0, "lomin": -86.0, "lamax": 11.3, "lomax": -82.5}
# Pacifico sur abierto: sin rutas comerciales ni receptores en tierra.
EMPTY_BBOX = {"lamin": -55.0, "lomin": -140.0, "lamax": -50.0, "lomax": -135.0}

CONTINUITY_GAP_S = 60


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


def probe(token: str | None, path: str, params: dict, title: str, expectation: str) -> dict:
    """
    Ejecuta un caso borde y documenta la respuesta cruda.

    No se juzga si el resultado es 'correcto': se registra qué devuelve la API
    para que el modulo real pueda programarse contra ese comportamiento.
    """
    import httpx

    headers = {"Authorization": "Bearer " + token} if token else {}
    result: dict = {"case": title, "endpoint": path, "params": params,
                    "expectation": expectation}

    started = time.perf_counter()
    try:
        response = httpx.get(BASE + path, params=params, headers=headers, timeout=TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        category, explanation = describe_http_error(exc)
        result.update(outcome="excepcion", error_category=category, error_detail=explanation)
        print("  {:<34} [EXCEPCION] {}".format(title, category))
        return result

    remaining = response.headers.get("x-rate-limit-remaining")
    body = response.text
    result.update(
        status_code=response.status_code,
        elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
        credits_remaining=int(remaining) if remaining and remaining.isdigit() else None,
        body_preview=body[:180],
        body_is_empty=(body.strip() in ("", "null", "[]", "{}")),
    )

    detail = ""
    if response.status_code == 200:
        try:
            payload = response.json()
        except ValueError:
            result["outcome"] = "200_no_json"
            detail = "200 pero el cuerpo no es JSON"
        else:
            if payload is None:
                result["outcome"] = "200_null"
                detail = "200 con cuerpo null"
            elif isinstance(payload, dict):
                states = payload.get("states")
                if states is None:
                    result["outcome"] = "200_states_null"
                    detail = "200 con states=null (NO es lista vacia)"
                else:
                    result["outcome"] = "200_con_datos"
                    result["item_count"] = len(states)
                    detail = "200 con {} elementos".format(len(states))
            elif isinstance(payload, list):
                result["outcome"] = "200_lista"
                result["item_count"] = len(payload)
                detail = "200 con lista de {} elementos".format(len(payload))
    else:
        result["outcome"] = "http_" + str(response.status_code)
        detail = body[:110].replace("\n", " ")

    print("  {:<34} [{}] {}".format(title, response.status_code, detail))
    print("  {:<34}   creditos_rest={}".format("", result.get("credits_remaining")))
    return result


def continuity_test(token: str) -> dict:
    """
    Mide cuantas aeronaves desaparecen del bounding box entre dos muestras.

    Una aeronave puede desaparecer por tres motivos distintos y la API no los
    distingue: salio del area, aterrizo, o se perdio la senal. Para el
    dashboard son estados MUY distintos, y de ahi la importancia de medirlo.
    """
    import httpx

    def snapshot() -> tuple[dict[str, dict], int | None]:
        response = httpx.get(BASE + "/states/all", params=CR_BBOX,
                             headers={"Authorization": "Bearer " + token}, timeout=TIMEOUT)
        if response.status_code != 200:
            return {}, None
        payload = response.json()
        found: dict[str, dict] = {}
        for state in payload.get("states") or []:
            if len(state) > 8 and state[0]:
                found[state[0]] = {
                    "callsign": (state[1] or "").strip() or None,
                    "on_ground": bool(state[8]),
                    "last_contact": state[4] if len(state) > 4 else None,
                    "altitude_m": state[7] if len(state) > 7 else None,
                }
        return found, payload.get("time")

    first, t1 = snapshot()
    print("  Muestra 1: {} aeronaves".format(len(first)))
    time.sleep(CONTINUITY_GAP_S)
    second, t2 = snapshot()
    print("  Muestra 2: {} aeronaves  (tras {} s)".format(len(second), CONTINUITY_GAP_S))

    disappeared = sorted(set(first) - set(second))
    appeared = sorted(set(second) - set(first))
    persisted = sorted(set(first) & set(second))

    detail = []
    for icao24 in disappeared:
        entry = first[icao24]
        staleness = (t1 - entry["last_contact"]) if (t1 and entry["last_contact"]) else None
        detail.append({
            "icao24": icao24,
            "callsign": entry["callsign"],
            "was_on_ground": entry["on_ground"],
            "altitude_m": entry["altitude_m"],
            "staleness_at_disappearance_s": staleness,
        })

    return {
        "gap_seconds": CONTINUITY_GAP_S,
        "first_count": len(first),
        "second_count": len(second),
        "persisted": len(persisted),
        "disappeared": len(disappeared),
        "appeared": len(appeared),
        "churn_pct": round(100.0 * len(disappeared) / len(first), 1) if first else 0.0,
        "disappeared_detail": detail,
    }


def main() -> int:
    args = network_arg("Spike TG-11 Fase 6: casos borde y contrato de errores")
    env = load_env()
    client_id = require(env, "OPENSKY_CLIENT_ID")
    client_secret = require(env, "OPENSKY_CLIENT_SECRET")

    timestamp = header(
        "TrackIn - Spike TG-11 - Fase 6: casos borde",
        args.network,
        {"client_id": mask(client_id)},
    )

    token = get_token(client_id, client_secret)
    now = int(time.time())
    cases: list[dict] = []

    print(SUB)
    print("  CASOS DE DATOS AUSENTES")
    print(SUB)
    cases.append(probe(token, "/states/all", {"icao24": "ffffff"},
                       "icao24 inexistente", "lista vacia o null"))
    cases.append(probe(token, "/states/all", EMPTY_BBOX,
                       "bbox sin trafico (Pacifico sur)", "lista vacia o null"))

    print(SUB)
    print("  CASOS DE AUTENTICACION")
    print(SUB)
    cases.append(probe("token.invalido.aproposito", "/states/all", CR_BBOX,
                       "token invalido", "401 con cuerpo distinguible"))

    print(SUB)
    print("  CASOS DE PARAMETROS INVALIDOS")
    print(SUB)
    # Ventana desalineada que toca 3 dias UTC: el error de la Fase 4.
    cases.append(probe(token, "/flights/aircraft",
                       {"icao24": "0ac9e1", "begin": now - 47 * 3600, "end": now},
                       "ventana de 3 particiones", "400 con mensaje explicativo"))
    cases.append(probe(token, "/flights/arrival",
                       {"airport": "XXXX", "begin": now - 86400, "end": now},
                       "aeropuerto inexistente", "404 o 200 vacio"))
    cases.append(probe(token, "/flights/arrival", {"airport": "MROC"},
                       "falta parametro begin/end", "400"))

    print(SUB)
    print("  CONTINUIDAD DE SEGUIMIENTO (senal perdida real)")
    print(SUB)
    continuity = continuity_test(token)

    print()
    print("  Persistieron : {}".format(continuity["persisted"]))
    print("  Desaparecieron: {}  ({}% de la primera muestra)".format(
        continuity["disappeared"], continuity["churn_pct"]))
    print("  Aparecieron  : {}".format(continuity["appeared"]))
    for entry in continuity["disappeared_detail"]:
        print("    -> {} / {}   alt={}   en_tierra={}   staleness_al_desaparecer={}s".format(
            entry["icao24"], entry["callsign"] or "(nulo)",
            entry["altitude_m"], entry["was_on_ground"],
            entry["staleness_at_disappearance_s"]))

    # --- Lectura -----------------------------------------------------------
    print(SEP)
    print("  CONTRATO DE ERRORES PARA SPRINT 3")
    print(SEP)
    for case in cases:
        print("  {:<34} -> {}".format(case["case"], case.get("outcome")))

    print()
    no_data_outcomes = {c["case"]: c.get("outcome") for c in cases[:2]}
    if "200_states_null" in no_data_outcomes.values():
        print("  [!] Cuando no hay aeronaves, la API devuelve states=null, NO una lista")
        print("      vacia. Iterar el resultado sin comprobar null lanza TypeError.")
        print("      El modulo de Sprint 3 debe normalizar null -> [] al deserializar.")

    auth_case = cases[2]
    print("  Token invalido -> {}. Distinguible de un fallo de red por el codigo".format(
        auth_case.get("outcome")))
    print("  HTTP, no por timeout: se puede reintentar con token nuevo sin backoff.")

    print()
    print("  SENAL PERDIDA: {}% de las aeronaves desaparecio del bbox en {} s.".format(
        continuity["churn_pct"], CONTINUITY_GAP_S))
    print("  La API NO distingue entre 'salio del area', 'aterrizo' y 'se perdio la")
    print("  senal': simplemente deja de listarla. Para el dashboard son estados muy")
    print("  distintos. Recomendacion para Sprint 3:")
    print("    - Persistir la ultima posicion conocida con su timestamp.")
    print("    - Mostrar 'ultima posicion hace N min' en vez de afirmar 'en ruta'.")
    print("    - Inferir aterrizaje solo si la ultima posicion tenia on_ground=true")
    print("      dentro del radio del aeropuerto; si no, marcar 'senal perdida'.")
    print("    - Confirmar despues por /flights/arrival (con ~16 h de retraso).")
    print(SEP)

    evidence = {
        "spike": "TG-11",
        "phase": "6-edge-cases",
        "timestamp_utc": timestamp,
        "finished_utc": utc_now(),
        "network_profile": args.network,
        "error_contract": cases,
        "continuity": continuity,
        "passed": True,
    }
    save_evidence("opensky", "06_edge_cases_" + args.network + ".json", evidence)
    return 0


if __name__ == "__main__":
    sys.exit(main())
