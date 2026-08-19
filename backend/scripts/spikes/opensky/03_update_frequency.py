"""
Spike TG-11 - Fase 3: frecuencia real de actualizacion de posiciones.

PREGUNTA DEL SPIKE QUE RESPONDE
    (3) "Con que frecuencia se actualizan las posiciones?"

LA PREGUNTA REAL DETRAS
    La documentacion promete una resolucion de 5 s para usuarios autenticados.
    Eso es el limite del servicio, no necesariamente lo que ocurre. Para
    dimensionar Sprint 3 lo que importa es cada cuanto CAMBIA el dato:
    si el servidor refresca una aeronave cada 10 s, pollear cada 5 s gasta
    el doble de cuota para la misma informacion. Con 4000 creditos/dia
    medidos en la Fase 1, ese desperdicio se paga en cobertura horaria.

METODO
    30 muestras cada 6 s (3 min, 30 creditos ~ 0.75% de la cuota diaria).
    Para cada icao24 se registra la secuencia de time_position y se cuenta
    cuantas muestras consecutivas devuelven el MISMO valor. Ese conteo mide
    el refresco real del servidor, con independencia del intervalo de sondeo.

    Se usa time_position (instante de la posicion reportada) y no
    last_contact (ultimo contacto de cualquier tipo, que se actualiza aunque
    la posicion no cambie).

SALIDA UTIL
    Un intervalo de polling recomendado para el modulo real, justificado
    contra la cuota diaria.

USO
    python backend/scripts/spikes/opensky/03_update_frequency.py --network personal

    Evidencia en backend/scripts/spikes/opensky/output/03_frequency_<red>.json
"""

from __future__ import annotations

import json
import statistics
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
STATES_URL = "https://opensky-network.org/api/states/all"
CR_BBOX = {"lamin": 8.0, "lomin": -86.0, "lamax": 11.3, "lomax": -82.5}

SAMPLES = 30
INTERVAL_S = 6
TIMEOUT = 20.0
DAILY_CREDITS = 4000  # medido en la Fase 1
SECONDS_PER_DAY = 86400

# Fraccion de la cuota que NO se dedica al sondeo continuo de posiciones.
# Queda reservada para /flights/arrival, reintentos tras fallo y consultas
# puntuales. Sin esta reserva el polling agota la cuota y cualquier otra
# llamada del dia falla con 429.
RESERVE_RATIO = 0.30

IDX_ICAO24 = 0
IDX_CALLSIGN = 1
IDX_TIME_POSITION = 3
IDX_ON_GROUND = 8


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
        sys.exit("[FATAL] Token HTTP " + str(response.status_code) + ": " + response.text[:200])
    token = response.json().get("access_token")
    if not token:
        sys.exit("[FATAL] La respuesta no contiene access_token.")
    return token


def fetch(token: str) -> dict:
    """Una consulta a /states/all. Devuelve dict con ok/estados o el fallo."""
    import httpx

    try:
        response = httpx.get(
            STATES_URL,
            params=CR_BBOX,
            headers={"Authorization": "Bearer " + token},
            timeout=TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001
        category, explanation = describe_http_error(exc)
        return {"ok": False, "error_category": category, "error_detail": explanation}

    remaining = response.headers.get("x-rate-limit-remaining")
    credits_remaining = int(remaining) if remaining and remaining.isdigit() else None

    if response.status_code == 429:
        return {"ok": False, "error_category": "rate_limited",
                "error_detail": "Cuota agotada", "credits_remaining": credits_remaining}
    if response.status_code != 200:
        return {"ok": False, "error_category": "http_" + str(response.status_code),
                "error_detail": response.text[:200], "credits_remaining": credits_remaining}
    try:
        payload = response.json()
    except ValueError:
        return {"ok": False, "error_category": "invalid_json",
                "error_detail": "200 sin JSON valido"}

    return {
        "ok": True,
        "server_time": payload.get("time"),
        "states": payload.get("states") or [],
        "credits_remaining": credits_remaining,
    }


def main() -> int:
    args = network_arg("Spike TG-11 Fase 3: frecuencia real de actualizacion")
    env = load_env()
    client_id = require(env, "OPENSKY_CLIENT_ID")
    client_secret = require(env, "OPENSKY_CLIENT_SECRET")

    duration_min = round(SAMPLES * INTERVAL_S / 60.0, 1)
    timestamp = header(
        "TrackIn - Spike TG-11 - Fase 3: frecuencia de actualizacion",
        args.network,
        {
            "client_id": mask(client_id),
            "muestreo": str(SAMPLES) + " muestras cada " + str(INTERVAL_S)
                        + " s (~" + str(duration_min) + " min, " + str(SAMPLES) + " creditos)",
        },
    )

    token = get_token(client_id, client_secret)
    print("  Token       : obtenido")

    # historial[icao24] = lista de (indice_muestra, time_position)
    history: dict[str, list[tuple[int, int]]] = {}
    callsigns: dict[str, str] = {}
    server_times: list[int] = []
    failures: list[dict] = []
    credits_start = None
    credits_end = None

    print(SUB)
    print("  MUESTREO (un punto por muestra)")
    print(SUB)
    progress = ""
    for i in range(1, SAMPLES + 1):
        result = fetch(token)
        if result.get("ok"):
            if credits_start is None:
                credits_start = result.get("credits_remaining")
            credits_end = result.get("credits_remaining")
            if result.get("server_time"):
                server_times.append(result["server_time"])
            for state in result["states"]:
                icao24 = state[IDX_ICAO24] if len(state) > IDX_ICAO24 else None
                time_position = state[IDX_TIME_POSITION] if len(state) > IDX_TIME_POSITION else None
                if not icao24 or time_position is None:
                    continue
                history.setdefault(icao24, []).append((i, time_position))
                callsign = (state[IDX_CALLSIGN] or "").strip() if len(state) > IDX_CALLSIGN else ""
                if callsign:
                    callsigns[icao24] = callsign
            progress += "."
        else:
            failures.append({"sample": i, **result})
            progress += "x"

        print("\r  [{}{}] {}/{}".format(progress, " " * (SAMPLES - i), i, SAMPLES), end="", flush=True)
        if i < SAMPLES:
            time.sleep(INTERVAL_S)
    print()

    if not history:
        print(SEP)
        print("  Fase 3 NO superada: no se registro ninguna aeronave.")
        print(SEP)
        save_evidence("opensky", "03_frequency_" + args.network + ".json", {
            "spike": "TG-11", "phase": "3-update-frequency", "timestamp_utc": timestamp,
            "network_profile": args.network, "failures": failures, "passed": False,
        })
        return 1

    # --- Analisis por aeronave --------------------------------------------
    per_aircraft: list[dict] = []
    all_deltas: list[float] = []

    for icao24, entries in history.items():
        positions = [tp for _, tp in entries]
        distinct = sorted(set(positions))
        # Deltas entre actualizaciones efectivas de la posicion.
        deltas = [b - a for a, b in zip(distinct, distinct[1:]) if b - a > 0]
        all_deltas.extend(deltas)

        # Cuantas muestras consecutivas repitieron el mismo time_position.
        repeats = len(positions) - len(distinct)

        per_aircraft.append({
            "icao24": icao24,
            "callsign": callsigns.get(icao24),
            "samples_seen": len(positions),
            "distinct_positions": len(distinct),
            "repeated_samples": repeats,
            "median_delta_s": statistics.median(deltas) if deltas else None,
            "min_delta_s": min(deltas) if deltas else None,
            "max_delta_s": max(deltas) if deltas else None,
        })

    per_aircraft.sort(key=lambda a: -a["samples_seen"])

    print(SUB)
    print("  ACTUALIZACION POR AERONAVE (top 12 por presencia)")
    print(SUB)
    row = "  {:<8} {:<9} {:>8} {:>10} {:>10} {:>9} {:>9}"
    print(row.format("icao24", "callsign", "muestras", "posic.dist", "repetidas",
                     "delta_med", "delta_max"))
    for entry in per_aircraft[:12]:
        print(row.format(
            entry["icao24"],
            (entry["callsign"] or "(nulo)")[:9],
            entry["samples_seen"],
            entry["distinct_positions"],
            entry["repeated_samples"],
            "{:.0f}s".format(entry["median_delta_s"]) if entry["median_delta_s"] is not None else "-",
            "{:.0f}s".format(entry["max_delta_s"]) if entry["max_delta_s"] is not None else "-",
        ))

    # --- Agregados globales ------------------------------------------------
    tracked = [a for a in per_aircraft if a["samples_seen"] >= SAMPLES // 2]
    global_median = statistics.median(all_deltas) if all_deltas else None
    total_samples = sum(a["samples_seen"] for a in per_aircraft)
    total_repeats = sum(a["repeated_samples"] for a in per_aircraft)
    repeat_ratio = (100.0 * total_repeats / total_samples) if total_samples else 0.0

    print()
    print(SUB)
    print("  AGREGADOS")
    print(SUB)
    print("  Muestras validas       : {}/{}".format(SAMPLES - len(failures), SAMPLES))
    print("  Aeronaves observadas   : {}".format(len(per_aircraft)))
    print("  Seguidas >50% del test : {}".format(len(tracked)))
    print("  Creditos consumidos    : {}".format(
        (credits_start - credits_end + 1) if (credits_start and credits_end) else "-"))
    if global_median is not None:
        print("  Delta entre posiciones : mediana={:.0f}s  min={:.0f}s  max={:.0f}s".format(
            global_median, min(all_deltas), max(all_deltas)))
    print("  Muestras redundantes   : {}/{} ({:.1f}%) devolvieron una posicion ya vista".format(
        total_repeats, total_samples, repeat_ratio))

    # --- Recomendacion de polling -----------------------------------------
    print(SEP)
    print("  LECTURA Y RECOMENDACION PARA SPRINT 3")
    print(SEP)

    floor_interval = SECONDS_PER_DAY / DAILY_CREDITS
    polling_budget = DAILY_CREDITS * (1.0 - RESERVE_RATIO)
    sustainable_interval = SECONDS_PER_DAY / polling_budget

    print("  Cuota diaria medida        : {} creditos".format(DAILY_CREDITS))
    print("  Piso teorico (100% cuota)  : 1 consulta cada {:.1f}s".format(floor_interval))
    print("  [!] Ese piso NO es utilizable: consume la cuota completa y no deja")
    print("      credito para /flights/*, reintentos ni un segundo bounding box.")
    print()
    print("  Reserva para otras llamadas: {:.0f}% ({:.0f} creditos)".format(
        RESERVE_RATIO * 100, DAILY_CREDITS * RESERVE_RATIO))
    print("  Presupuesto de polling     : {:.0f} consultas/dia".format(polling_budget))
    print("  => intervalo sostenible 24/7: {:.0f}s".format(sustainable_interval))
    print()

    if global_median is None:
        recommended = None
        print("  No hubo suficientes cambios de posicion para recomendar un intervalo.")
    else:
        # El intervalo util no puede ser menor que el refresco del servidor
        # (seria dato repetido) ni menor que lo que la cuota permite sostener.
        recommended = max(global_median, sustainable_interval)
        print("  Refresco real del servidor : ~{:.0f}s (mediana)".format(global_median))
        print("  INTERVALO RECOMENDADO      : {:.0f}s en operacion continua".format(recommended))
        print()
        if repeat_ratio > 35:
            print("  El {:.0f}% de las consultas de esta prueba devolvio una posicion ya".format(
                repeat_ratio))
            print("  conocida: sondear cada {}s es mas rapido de lo que el servidor".format(
                INTERVAL_S))
            print("  actualiza. El limite real lo pone la cuota, no la frescura del dato.")
        else:
            print("  La redundancia es baja: el servidor actualiza a un ritmo cercano al")
            print("  intervalo de sondeo usado en esta prueba.")
        print()
        # Alternativa por ventanas: los embarques llegan en horarios acotados,
        # no hace falta sondear de madrugada si no hay vuelo en curso.
        for window_h in (8, 12):
            window_interval = (window_h * 3600) / polling_budget
            print("  Alternativa: sondear solo {}h/dia (ventana de vuelos activos)".format(window_h))
            print("               => se puede bajar a {:.0f}s sin exceder el presupuesto.".format(
                max(global_median, window_interval)))
    print(SEP)

    evidence = {
        "spike": "TG-11",
        "phase": "3-update-frequency",
        "timestamp_utc": timestamp,
        "finished_utc": utc_now(),
        "network_profile": args.network,
        "config": {"samples": SAMPLES, "interval_s": INTERVAL_S, "bbox": CR_BBOX},
        "credits": {"start_remaining": credits_start, "end_remaining": credits_end},
        "failures": failures,
        "aircraft_count": len(per_aircraft),
        "tracked_more_than_half": len(tracked),
        "global_median_delta_s": global_median,
        "min_delta_s": min(all_deltas) if all_deltas else None,
        "max_delta_s": max(all_deltas) if all_deltas else None,
        "redundant_sample_ratio_pct": round(repeat_ratio, 1),
        "quota_floor_interval_s": round(floor_interval, 1),
        "reserve_ratio": RESERVE_RATIO,
        "polling_budget_per_day": round(polling_budget),
        "sustainable_interval_s": round(sustainable_interval, 1),
        "recommended_poll_interval_s": round(recommended) if recommended else None,
        "per_aircraft": per_aircraft,
        "passed": True,
    }
    save_evidence("opensky", "03_frequency_" + args.network + ".json", evidence)

    return 0


if __name__ == "__main__":
    sys.exit(main())
