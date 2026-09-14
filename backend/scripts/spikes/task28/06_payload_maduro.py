"""
Spike TASK-28 - Fase 3d: el payload ya maduro, y que campos de TrackIn trae.

POR QUE ESTE SCRIPT EXISTE APARTE DEL 05
    El 05 da de alta y consulta a los 45 s. A esa altura ShipsGo devuelve
    `status: NEW`, `route: null` y `containers: []`: **registro el embarque pero
    todavia no habia ido a buscarlo**. Concluir ahi que "no trae ningun campo"
    era un falso negativo, y por eso la lectura de verdad va separada.

    Medido: a los ~90 s los dos embarques pasaron a `SAILING` con ruta y
    contenedor completos. Para `US-07` eso significa que el planificador tiene
    que contemplar un estado **"dado de alta pero sin datos todavia"**, que no
    es un fallo ni una respuesta vacia definitiva.

QUE HACE
    Consulta los embarques ya creados y cruza el payload contra los campos que
    TrackIn necesita, diciendo de donde sale cada uno. Solo GET: no gasta
    creditos, solo roza el rate limit.

    Consulta DOS endpoints, porque los datos estan repartidos:
      - `/ocean/shipments/{id}`          ruta, hitos, ETA, buque por tramo
      - `/ocean/shipments/{id}/geojson`  **posicion actual** y trayecto

    El segundo no estaba documentado en la guia y es el que alimenta el mapa:
    sin el, la conclusion habria sido que ShipsGo no da posicion.

USO
    python backend/scripts/spikes/task28/06_payload_maduro.py --network personal
    python backend/scripts/spikes/task28/06_payload_maduro.py --network personal --id 6734886

SALIDA
    Evidencia en backend/scripts/spikes/task28/output/06_payload_<red>.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import SEP, SUB, load_env, save_evidence, utc_now

BASE_SG = "https://api.shipsgo.com/v2"
TIMEOUT = 40.0

# Los embarques creados en la fase 3c con referencias reales de Gutis.
EMBARQUES = [6734886, 6734887]


def extraer(envio: dict, geo: dict) -> dict:
    """
    Saca de los dos payloads exactamente lo que TrackIn necesita.

    Devuelve un dict campo -> (valor, de donde salio). Lo que no aparece se
    omite: la ausencia se reporta despues comparando contra la lista completa.
    """
    hallado: dict[str, dict] = {}
    ruta = envio.get("route") or {}
    contenedores = envio.get("containers") or []
    movimientos = (contenedores[0].get("movements") if contenedores else []) or []

    carga = ruta.get("port_of_loading") or {}
    descarga = ruta.get("port_of_discharge") or {}

    if carga.get("date_of_loading"):
        hallado["etd_atd"] = {"valor": carga["date_of_loading"],
                              "de": "route.port_of_loading.date_of_loading"}
    if descarga.get("date_of_discharge_predicted"):
        hallado["eta"] = {"valor": descarga["date_of_discharge_predicted"],
                          "de": "route.port_of_discharge.date_of_discharge_predicted"}
    if descarga.get("location", {}).get("code"):
        hallado["puerto_destino"] = {"valor": descarga["location"]["code"],
                                     "de": "route.port_of_discharge.location.code"}
    if ruta.get("transit_time") is not None:
        hallado["transito"] = {"valor": str(ruta["transit_time"]) + " dias, "
                               + str(ruta.get("transit_percentage")) + "%",
                               "de": "route.transit_time"}
    if movimientos:
        actuales = [m for m in movimientos if m.get("status") == "ACT"]
        hallado["hitos"] = {"valor": str(len(movimientos)) + " eventos ("
                            + str(len(actuales)) + " ACT / "
                            + str(len(movimientos) - len(actuales)) + " EST)",
                            "de": "containers[].movements[]"}
        # El cambio de buque entre tramos ES el transbordo de US-30.
        buques = []
        for m in movimientos:
            v = m.get("vessel")
            nombre = v.get("name") if isinstance(v, dict) else v
            if nombre and nombre not in buques:
                buques.append(nombre)
        if buques:
            hallado["buque"] = {"valor": " -> ".join(buques),
                                "de": "containers[].movements[].vessel.name"}
            if len(buques) > 1:
                hallado["transbordo"] = {"valor": str(len(buques) - 1) + " cambio(s) de nave",
                                         "de": "cambio de vessel entre movements (US-30)"}

    for f in (geo.get("features") or []):
        props = f.get("properties") or {}
        actual = props.get("current")
        if actual and actual.get("coordinates"):
            hallado["posicion"] = {"valor": str(actual["coordinates"]),
                                   "de": "geojson features[].properties.current.coordinates"}
        vessel = props.get("vessel")
        if isinstance(vessel, dict) and vessel.get("imo") and "imo" not in hallado:
            hallado["imo"] = {"valor": str(vessel["imo"]),
                              "de": "geojson features[].properties.vessel.imo"}
        if f.get("geometry", {}).get("type") == "LineString" and "trayecto" not in hallado:
            hallado["trayecto"] = {"valor": "LineString(s) PAST/CURRENT/FUTURE",
                                   "de": "geojson features[].geometry"}
    return hallado


# Campo -> quien lo exige en TrackIn.
EXIGIDOS = {
    "posicion": "historial_tracking.posicion · RF-16 mapa",
    "trayecto": "US-29 / RF-22 dibujar el trayecto",
    "velocidad": "RN-16 y US-08 (ETA estimada)",
    "rumbo": "historial_tracking.rumbo",
    "eta": "RN-01 fecha proyectada",
    "etd_atd": "US-43 vista completa",
    "hitos": "RN-02 a RN-06 etapas",
    "buque": "elementos_rastreados.nombre",
    "imo": "elementos_rastreados.imo",
    "transbordo": "US-30 / RF-26",
    "puerto_destino": "maestro_destinos",
    "transito": "informativo",
}


def main() -> int:
    import httpx

    parser = argparse.ArgumentParser(description="TASK-28 fase 3d: payload maduro")
    parser.add_argument("--network", choices=["personal", "gutis"], required=True)
    parser.add_argument("--id", type=int, action="append", help="id de embarque; repetible")
    args = parser.parse_args()

    env = load_env()
    token = (env.get("SHIPSGO_API_TOKEN") or env.get("SHIPSGO_SECRET") or "").strip()
    h = {"X-Shipsgo-User-Token": token, "Accept": "application/json"}
    ids = args.id or EMBARQUES

    print(SEP)
    print(" TrackIn - TASK-28 Fase 3d: payload maduro de ShipsGo")
    print(SEP)
    print("  Solo GET: no gasta creditos de alta.")

    resultados = []
    with httpx.Client() as cliente:
        for sid in ids:
            base = BASE_SG + "/ocean/shipments/" + str(sid)
            envio = cliente.get(base, headers=h, timeout=TIMEOUT).json().get("shipment") or {}
            geo = cliente.get(base + "/geojson", headers=h,
                              timeout=TIMEOUT).json().get("geojson") or {}

            print(SUB)
            print("  Embarque " + str(sid) + "  ·  " + str(envio.get("container_number"))
                  + "  ·  estado " + str(envio.get("status")))
            print(SUB)
            campos = extraer(envio, geo)
            for campo in EXIGIDOS:
                if campo in campos:
                    print("  [SI] {:<15} {}".format(campo, campos[campo]["valor"]))
                    print("       {:<15} <- {}".format("", campos[campo]["de"]))
                else:
                    print("  [no] {:<15} {}".format(campo, "ausente · " + EXIGIDOS[campo]))
            resultados.append({"id": sid, "contenedor": envio.get("container_number"),
                               "estado": envio.get("status"), "campos": campos,
                               "payload_shipment": envio, "payload_geojson": geo})

    presentes = sorted({c for r in resultados for c in r["campos"]})
    ausentes = [c for c in EXIGIDOS if c not in presentes]

    print(SEP)
    print("  VEREDICTO PARA US-45")
    print(SEP)
    print("  Presentes: " + ", ".join(presentes))
    print("  Ausentes : " + (", ".join(ausentes) if ausentes else "ninguno"))
    print()
    print("  velocidad y rumbo no llegan, pero ShipsGo entrega la ETA ya calculada,")
    print("  que es justo para lo que RN-16 las necesitaba. US-08 se mantiene Could.")
    print(SEP)

    save_evidence("task28", "06_payload_" + args.network + ".json", {
        "spike": "TASK-28", "fase": "3d-payload-maduro",
        "solo_lectura": True, "embarques": resultados,
        "campos_presentes": presentes, "campos_ausentes": ausentes,
        "generado": utc_now(),
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
