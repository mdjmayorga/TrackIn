"""
Spike TG-11 - Fase 4: como identificar un vuelo especifico.

PREGUNTA DEL SPIKE QUE RESPONDE
    (5) "Como identificar un vuelo especifico?"

LA CADENA QUE HAY QUE CERRAR
    Compras no tiene un icao24. Tiene una guia aerea (AWB) y, con suerte, un
    numero de vuelo comercial tipo "LH1234". OpenSky no conoce ni AWB ni
    numero de vuelo: trabaja con icao24 (hex de 24 bits, propio de la
    aeronave) y callsign (propio del vuelo, no de la aeronave).

        AWB  ->  numero de vuelo  ->  callsign  ->  icao24  ->  posicion
                 (courier)          (?)          (OpenSky)     (OpenSky)

    Este script prueba las vias disponibles para cerrar los dos ultimos
    saltos y mide cuanto cuesta cada una.

VIAS PROBADAS
    A. /states/all?icao24=...   consulta directa por identificador conocido.
       Se prueba con VARIOS icao24 a la vez para ver si el costo en creditos
       es por consulta o por aeronave: rastrear 10 embarques en 1 credito en
       vez de 10 cambia el presupuesto por completo.
    B. /flights/arrival?airport=MROC   llegadas a un aeropuerto en una
       ventana. Es la via mas prometedora para TrackIn: dado destino y fecha
       esperada, listar que aterrizo y cruzar por callsign.
       Se prueban DOS ventanas (ultimas 24 h y hace 3 dias) porque estos
       datos suelen publicarse con retraso y hay que medir cuanto.
    C. /flights/aircraft?icao24=...   historial de vuelos de una aeronave.
    D. /tracks/all?icao24=...   trayectoria completa. Marcado como
       experimental en la documentacion; se prueba para saber si se puede
       contar con el o hay que descartarlo.

COSTO
    ~6 consultas. El costo real de cada endpoint se mide leyendo
    x-rate-limit-remaining antes y despues, porque la documentacion no
    detalla la tarifa de los endpoints /flights/*.

USO
    python backend/scripts/spikes/opensky/04_flight_identification.py --network personal

    Evidencia en backend/scripts/spikes/opensky/output/04_identification_<red>.json
"""

from __future__ import annotations

import json
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

AIRPORT = "MROC"  # Juan Santamaria, destino de las importaciones aereas
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


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


def call(token: str, path: str, params: dict, label: str) -> dict:
    """
    Llama un endpoint y devuelve un diagnostico uniforme.

    Captura x-rate-limit-remaining para poder deducir el costo real del
    endpoint restando contra la llamada anterior.
    """
    import httpx

    url = BASE + path
    diag: dict = {"label": label, "endpoint": path, "params": params}
    started = time.perf_counter()
    try:
        response = httpx.get(
            url, params=params, headers={"Authorization": "Bearer " + token}, timeout=TIMEOUT
        )
    except Exception as exc:  # noqa: BLE001
        category, explanation = describe_http_error(exc)
        diag.update(ok=False, error_category=category, error_detail=explanation,
                    elapsed_ms=round((time.perf_counter() - started) * 1000, 1))
        return diag

    remaining = response.headers.get("x-rate-limit-remaining")
    diag.update(
        status_code=response.status_code,
        elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
        credits_remaining=int(remaining) if remaining and remaining.isdigit() else None,
    )

    # 404 en /flights/* significa "no hay datos para esa ventana", no un error
    # de programacion. Es un resultado valido y hay que documentarlo como tal.
    if response.status_code == 404:
        diag.update(ok=False, error_category="sin_datos",
                    error_detail="404: no hay vuelos registrados en esa ventana")
        return diag
    if response.status_code == 429:
        diag.update(ok=False, error_category="rate_limited", error_detail="Cuota agotada")
        return diag
    if response.status_code != 200:
        diag.update(ok=False, error_category="http_" + str(response.status_code),
                    error_detail=response.text[:200])
        return diag

    try:
        payload = response.json()
    except ValueError:
        diag.update(ok=False, error_category="invalid_json",
                    error_detail="200 sin JSON valido")
        return diag

    diag.update(ok=True, payload=payload, response_bytes=len(response.content))
    return diag


def load_candidates() -> list[dict]:
    """
    Toma icao24 reales de la evidencia de fases anteriores, en vez de
    hardcodearlos. Prioriza jets comerciales internacionales: son el caso de
    uso de TrackIn, no las avionetas locales.
    """
    candidates: list[dict] = []
    path = OUTPUT_DIR / "02_coverage_personal.json"
    if not path.is_file():
        return candidates
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return candidates

    for entry in data.get("unique_aircraft", []):
        if entry.get("icao24") and entry.get("callsign"):
            candidates.append({
                "icao24": entry["icao24"],
                "callsign": entry["callsign"],
                "origin_country": entry.get("origin_country"),
                "regime": entry.get("regime"),
            })
    # Los de crucero y de bandera extranjera son los comerciales de largo
    # alcance; van primero.
    candidates.sort(key=lambda c: (
        c["regime"] != "crucero",
        c["origin_country"] == "Costa Rica",
    ))
    return candidates


def main() -> int:
    args = network_arg("Spike TG-11 Fase 4: identificacion de un vuelo especifico")
    env = load_env()
    client_id = require(env, "OPENSKY_CLIENT_ID")
    client_secret = require(env, "OPENSKY_CLIENT_SECRET")

    timestamp = header(
        "TrackIn - Spike TG-11 - Fase 4: identificacion de un vuelo",
        args.network,
        {"client_id": mask(client_id), "aeropuerto": AIRPORT},
    )

    candidates = load_candidates()
    if not candidates:
        print("  [!] No hay evidencia previa en output/02_coverage_personal.json")
        print("      Correr antes la Fase 2. Sin icao24 reales esta fase no aplica.")
        return 1

    print("  Candidatos  : {} aeronaves tomadas de la evidencia de la Fase 2".format(len(candidates)))
    primary = candidates[0]
    print("  Principal   : {} / {} ({}, {})".format(
        primary["icao24"], primary["callsign"], primary["origin_country"], primary["regime"]))

    token = get_token(client_id, client_secret)
    results: dict[str, dict] = {}
    now = int(time.time())

    # --- VIA A: consulta directa por icao24, varios a la vez --------------
    print(SUB)
    print("  VIA A - /states/all?icao24=  (consulta directa)")
    print(SUB)
    # El costo solo se puede deducir restando el header entre llamadas
    # CONSECUTIVAS AL MISMO ENDPOINT. Restar contra otro endpoint da valores
    # incoherentes (ver nota sobre no-monotonia en la lectura final), asi que
    # se hace una serie de 4 llamadas seguidas a /states/all:
    #   bbox, bbox, 1 icao24, N icao24
    # La primera solo fija la linea base; las siguientes dan el costo real.
    multi = [c["icao24"] for c in candidates[:5]]
    cr_bbox = {"lamin": 8.0, "lomin": -86.0, "lamax": 11.3, "lomax": -82.5}

    series = [
        ("baseline_bbox", call(token, "/states/all", cr_bbox, "states_bbox_baseline")),
        ("bbox_cr", call(token, "/states/all", cr_bbox, "states_bbox_cr")),
        ("un_icao24", call(token, "/states/all", {"icao24": primary["icao24"]}, "states_un_icao24")),
        ("varios_icao24", call(token, "/states/all", {"icao24": multi}, "states_varios_icao24")),
    ]

    costs: dict[str, int | None] = {}
    previous_remaining = None
    for name, diag in series:
        results["via_a_" + name] = diag
        if diag.get("ok"):
            states = diag["payload"].get("states") or []
            diag["aircraft_returned"] = len(states)
            diag.pop("payload", None)
            remaining = diag.get("credits_remaining")
            cost = (previous_remaining - remaining) if (previous_remaining and remaining) else None
            costs[name] = cost
            diag["measured_cost_credits"] = cost
            print("  {:<15} [OK]   {} aeronaves   creditos_rest={}   costo={}   {} ms".format(
                name, len(states), remaining,
                cost if cost is not None else "(base)", diag.get("elapsed_ms")))
            previous_remaining = remaining
        else:
            costs[name] = None
            print("  {:<15} [FALLO] {} - {}".format(
                name, diag.get("error_category"), diag.get("error_detail")))

    a_one = dict(series[2][1])
    cost_bbox = costs.get("bbox_cr")
    cost_one = costs.get("un_icao24")
    cost_multi = costs.get("varios_icao24")

    print()
    if cost_one is not None and cost_multi is not None:
        print("  Costo por 1 icao24: {}   |   por {} icao24: {}".format(
            cost_one, len(multi), cost_multi))
        if cost_multi <= cost_one:
            print("  => El costo NO escala con la cantidad de aeronaves. Filtrar por icao24")
            print("     sin bounding box es una consulta GLOBAL y paga la tarifa maxima,")
            print("     se pida 1 aeronave o 50. Agrupar embarques es gratis.")
        else:
            print("  => El costo escala con la cantidad de aeronaves consultadas.")
    if cost_bbox is not None and cost_one is not None:
        print("  Costo por bounding box de CR: {}  vs  consulta global por icao24: {}".format(
            cost_bbox, cost_one))

    # --- VIA B: llegadas al aeropuerto ------------------------------------
    print(SUB)
    print("  VIA B - /flights/arrival?airport={}  (la mas relevante para TrackIn)".format(AIRPORT))
    print(SUB)
    windows = {
        "ultimas_24h": (now - 86400, now),
        "hace_3_dias": (now - 3 * 86400, now - 2 * 86400),
    }
    arrival_previous_remaining = None
    arrival_cost = None
    for name, (begin, end) in windows.items():
        diag = call(token, "/flights/arrival",
                    {"airport": AIRPORT, "begin": begin, "end": end},
                    "arrival_" + name)
        results["via_b_" + name] = diag
        # Costo valido: ambas llamadas son al MISMO endpoint y consecutivas.
        remaining = diag.get("credits_remaining")
        if arrival_previous_remaining and remaining:
            arrival_cost = arrival_previous_remaining - remaining
            diag["measured_cost_credits"] = arrival_cost
        arrival_previous_remaining = remaining
        begin_utc = datetime.fromtimestamp(begin, tz=timezone.utc).isoformat(timespec="minutes")
        end_utc = datetime.fromtimestamp(end, tz=timezone.utc).isoformat(timespec="minutes")
        if diag.get("ok"):
            flights = diag["payload"] if isinstance(diag["payload"], list) else []
            print("  {:<14} [OK]   {} llegadas   ({} -> {})   creditos_rest={}".format(
                name, len(flights), begin_utc, end_utc, diag.get("credits_remaining")))
            diag["flight_count"] = len(flights)
            # Se conserva una muestra acotada: el listado completo puede ser largo.
            diag["sample_flights"] = flights[:8]
            diag.pop("payload", None)

            # Latencia de publicacion: cuanto hace que aterrizo el vuelo mas
            # reciente que la API conoce. Es LA metrica que decide si este
            # endpoint sirve para deteccion en vivo o solo para conciliacion.
            last_seen = [f.get("lastSeen") for f in flights
                         if isinstance(f.get("lastSeen"), (int, float))]
            if last_seen:
                latest = max(last_seen)
                lag_h = (now - latest) / 3600.0
                diag["latest_arrival_epoch"] = latest
                diag["publication_lag_hours"] = round(lag_h, 1)
                print("      -> vuelo mas reciente conocido: {}  (retraso de publicacion: {:.1f} h)".format(
                    datetime.fromtimestamp(latest, tz=timezone.utc).isoformat(timespec="minutes"),
                    lag_h))
            for flight in flights[:5]:
                callsign = (flight.get("callsign") or "").strip() or "(nulo)"
                arrival = flight.get("lastSeen")
                arrival_utc = (
                    datetime.fromtimestamp(arrival, tz=timezone.utc).isoformat(timespec="minutes")
                    if isinstance(arrival, (int, float)) else "-"
                )
                print("      {:<9} icao24={}  desde={}  aterrizo={}".format(
                    callsign, flight.get("icao24"),
                    flight.get("estDepartureAirport") or "(desconocido)", arrival_utc))
        else:
            print("  {:<14} [{}] {}   ({} -> {})".format(
                name, diag.get("error_category"), diag.get("error_detail"), begin_utc, end_utc))

    # --- VIA C: historial de la aeronave ----------------------------------
    print(SUB)
    print("  VIA C - /flights/aircraft?icao24=  (historial de la aeronave)")
    print(SUB)
    # La API rechaza ventanas que crucen mas de 2 particiones diarias:
    #   400 "You can only query across 2 partitions (days)"
    # El limite NO es de duracion sino de DIAS UTC CALENDARIO tocados: una
    # ventana de 47 h desde media tarde toca tres dias y falla igual. Hay que
    # alinear el inicio a la medianoche UTC de ayer para tocar exactamente dos.
    midnight_today = int(
        datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    )
    begin_c = midnight_today - 86400  # medianoche UTC de ayer
    c_diag = call(token, "/flights/aircraft",
                  {"icao24": primary["icao24"], "begin": begin_c, "end": now},
                  "flights_aircraft")
    print("  Ventana     : {} -> {} (2 dias UTC)".format(
        datetime.fromtimestamp(begin_c, tz=timezone.utc).isoformat(timespec="minutes"),
        datetime.fromtimestamp(now, tz=timezone.utc).isoformat(timespec="minutes")))
    results["via_c_historial"] = c_diag
    if c_diag.get("ok"):
        flights = c_diag["payload"] if isinstance(c_diag["payload"], list) else []
        print("  [OK]   {} vuelos de {} en los ultimos 5 dias   creditos_rest={}".format(
            len(flights), primary["icao24"], c_diag.get("credits_remaining")))
        c_diag["flight_count"] = len(flights)
        c_diag["sample_flights"] = flights[:8]
        c_diag.pop("payload", None)
        for flight in flights[:5]:
            print("      {:<9} {} -> {}".format(
                (flight.get("callsign") or "").strip() or "(nulo)",
                flight.get("estDepartureAirport") or "?",
                flight.get("estArrivalAirport") or "?"))
    else:
        print("  [{}] {}".format(c_diag.get("error_category"), c_diag.get("error_detail")))

    # --- VIA D: trayectoria (experimental) --------------------------------
    print(SUB)
    print("  VIA D - /tracks/all  (marcado como experimental)")
    print(SUB)
    d_diag = call(token, "/tracks/all", {"icao24": primary["icao24"], "time": 0}, "tracks_all")
    results["via_d_tracks"] = d_diag
    if d_diag.get("ok"):
        payload = d_diag["payload"] or {}
        path_points = payload.get("path") or []
        print("  [OK]   trayectoria con {} puntos   creditos_rest={}".format(
            len(path_points), d_diag.get("credits_remaining")))
        d_diag["path_points"] = len(path_points)
        d_diag["sample_path"] = path_points[:5]
        d_diag.pop("payload", None)
    else:
        print("  [{}] {}".format(d_diag.get("error_category"), d_diag.get("error_detail")))

    # --- Lectura -----------------------------------------------------------
    print(SEP)
    print("  LECTURA Y RECOMENDACION PARA SPRINT 3")
    print(SEP)

    arrivals_ok = any(
        results.get("via_b_" + name, {}).get("ok") for name in windows
    )
    recent_ok = results.get("via_b_ultimas_24h", {}).get("ok", False)
    old_ok = results.get("via_b_hace_3_dias", {}).get("ok", False)

    print("  [!] ADVERTENCIA SOBRE LA MEDICION DE CREDITOS")
    print("      El header x-rate-limit-remaining NO es monotono entre endpoints")
    print("      distintos: sube y baja segun cual se consulte. Lo mas plausible es")
    print("      que haya cuotas separadas por endpoint. Por eso los costos de arriba")
    print("      solo se midieron entre llamadas consecutivas al MISMO endpoint.")
    print("      El costo de /flights/* y /tracks/* queda como pregunta ABIERTA.")
    print()

    if a_one.get("ok"):
        print("  VIA A operativa: con el icao24 se consulta la posicion directamente.")
        if cost_multi is not None and cost_one is not None and cost_multi <= cost_one:
            print("  Costo plano: pedir {} aeronaves cuesta lo mismo que pedir 1 ({} creditos).".format(
                len(multi), cost_multi))
            print("  Filtrar por icao24 sin bbox es una consulta global y paga tarifa maxima.")
            print("  => Rastrear TODOS los embarques activos en una sola consulta agrupada.")
            if cost_bbox is not None and cost_bbox < cost_one:
                print("  Alternativa mas barata: bounding box de CR cuesta {} vs {}.".format(
                    cost_bbox, cost_one))
                print("  Conviene si todos los embarques convergen al mismo destino.")
    else:
        print("  VIA A NO operativa: revisar antes de disenar el modulo.")

    print()
    if arrivals_ok:
        print("  VIA B operativa: /flights/arrival lista que aterrizo en " + AIRPORT + ".")
        # La latencia de publicacion decide el uso: en vivo o conciliacion.
        lags = [results["via_b_" + name].get("publication_lag_hours")
                for name in windows if results.get("via_b_" + name, {}).get("ok")]
        lags = [x for x in lags if isinstance(x, (int, float))]
        min_lag = min(lags) if lags else None
        if min_lag is not None:
            print("  Retraso de publicacion medido: {:.1f} h.".format(min_lag))
            if min_lag > 2:
                print("  [!] NO sirve para deteccion de aterrizaje en vivo: el dato llega")
                print("      con {:.0f} h de atraso. Sirve para CONCILIACION posterior.".format(min_lag))
                print("      La deteccion en tiempo real debe hacerse por posicion:")
                print("      on_ground = true dentro del radio del aeropuerto (validado en Fase 2).")
            else:
                print("  El retraso es bajo: se puede usar tambien para el corto plazo.")
        if arrival_cost is not None:
            print("  Costo medido: {} creditos por consulta de 24 h.".format(arrival_cost))
            if cost_bbox:
                print("  Es {:.0f}x mas caro que una consulta de posicion por bounding box.".format(
                    arrival_cost / cost_bbox))
        print("  Para cerrar la cadena AWB -> vuelo -> icao24: buscar por aeropuerto y")
        print("  fecha esperada, y cruzar por callsign.")
    else:
        print("  VIA B NO devolvio datos en ninguna ventana. Si se confirma en otra corrida,")
        print("  la deteccion de aterrizaje debe hacerse por posicion (on_ground dentro del")
        print("  radio del aeropuerto), que es lo que ya validamos en la Fase 2.")

    print()
    print("  IDENTIFICADOR ESTABLE: icao24. El callsign puede venir nulo o aparecer")
    print("  tarde (visto en las Fases 2 y 3), y ademas cambia entre vuelos de la misma")
    print("  aeronave. El modelo de Sprint 3 debe guardar icao24 como clave y el")
    print("  callsign como atributo mutable del tramo.")
    print(SEP)

    evidence = {
        "spike": "TG-11",
        "phase": "4-flight-identification",
        "timestamp_utc": timestamp,
        "finished_utc": utc_now(),
        "network_profile": args.network,
        "airport": AIRPORT,
        "candidates": candidates[:5],
        "primary_candidate": primary,
        "measured_costs_states_all": {
            "bbox_cr_credits": cost_bbox,
            "un_icao24_credits": cost_one,
            "varios_icao24_credits": cost_multi,
            "icao24_count_in_multi": len(multi),
        },
        "measured_cost_flights_arrival_credits": arrival_cost,
        "credits_header_caveat": (
            "x-rate-limit-remaining no es monotono entre endpoints distintos "
            "(serie observada: 3960, 3956, 3970, 3940, 3996). Probablemente hay "
            "cuotas separadas por endpoint. Los costos solo son validos entre "
            "llamadas consecutivas al mismo endpoint. Costo de /flights/* y "
            "/tracks/*: PREGUNTA ABIERTA."
        ),
        "results": results,
        "passed": bool(a_one.get("ok")),
    }
    save_evidence("opensky", "04_identification_" + args.network + ".json", evidence)

    return 0 if a_one.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
