"""
Spike TASK-28 - Fase 3e: las dos altas que el trial anterior dejo sin cupo.

QUE QUEDO PENDIENTE Y POR QUE
    La fase 3c gasto los 3 creditos del primer trial —uno de ellos en
    comprobar que ShipsGo no valida el formato, cosa que resulto cierta y
    costo un credito— y las altas del MAWB y del BL de COSCO recibieron
    `402 NOT_ENOUGH_CREDITS`. Con la cuenta nueva se completan.

LAS DOS PREGUNTAS QUE CIERRAN
    1. **ShipsGo Air resuelve un MAWB real?** Es lo unico que falta para
       decidir entre "ShipsGo para las dos vias" y "ShipsGo maritimo +
       TrackingMore aereo". TrackingMore ya quedo descartado en la practica:
       con el mismo MAWB propuso `dachser` y se quedo en `pending` sin datos.
    2. **La cobertura maritima depende del carrier?** Los dos embarques que
       funcionaron eran Maersk. El BL de COSCO prueba una segunda naviera; si
       tambien responde, la cobertura no es de un solo carrier.

DISCIPLINA DE GASTO
    Dos altas, ni una mas. Nada de sondas con referencias inventadas: eso fue
    lo que quemo el credito la vez pasada. Las dos referencias vienen
    validadas por `04_validar_referencias.py`:
      - `02050685434`  MAWB, prefijo 020 = LUFTHANSA CARGO, digito de control OK
      - `TGBU4872990`  contenedor ISO 6346 correcto, con el BL `COSU6508789000`

MADURACION
    La fase 3d midio que el alta tarda ~90 s en pasar de `NEW` a datos
    completos. Aca se espera 150 s antes del primer poll, y el poll se repite
    si sigue en `NEW`: consultar es gratis, crear no.

USO
    python backend/scripts/spikes/task28/07_altas_pendientes.py --network personal

SALIDA
    Evidencia en backend/scripts/spikes/task28/output/07_pendientes_<red>.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import SEP, SUB, load_env, save_evidence, utc_now

BASE = "https://api.shipsgo.com/v2"
TIMEOUT = 40.0
ESPERA_INICIAL_S = 150
REINTENTOS_POLL = 4
ESPERA_ENTRE_POLL_S = 60

AEREA = {"etiqueta": "Lufthansa Cargo (MAWB)", "via": "air",
         "cuerpo": {"awb_number": "02050685434"}}
MARITIMA = {"etiqueta": "COSCO (BL + contenedor)", "via": "ocean",
            "cuerpo": {"booking_number": "COSU6508789000",
                       "container_number": "TGBU4872990"}}

# Campo -> quien lo exige en TrackIn. Igual que en la fase 3d, para poder
# comparar la via aerea contra la maritima en la misma tabla.
EXIGIDOS = {
    "posicion": "historial_tracking.posicion · RF-16",
    "trayecto": "US-29 / RF-22",
    "eta": "RN-01 fecha proyectada",
    "etd_atd": "US-43 vista completa",
    "hitos": "RN-02 a RN-06 etapas",
    "transporte": "elementos_rastreados (buque o vuelo)",
    "identificador": "elementos_rastreados.imo / icao24",
    "destino": "maestro_destinos",
}


def llamar(cliente, metodo: str, url: str, headers: dict, cuerpo=None) -> dict:
    """Llamada que nunca levanta: un fallo es un resultado del spike."""
    try:
        r = cliente.request(metodo, url, headers=headers, json=cuerpo, timeout=TIMEOUT)
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__ + ": " + str(exc)[:200]}
    salida = {"ok": 200 <= r.status_code < 300, "status": r.status_code}
    try:
        salida["json"] = r.json()
    except ValueError:
        salida["texto"] = r.text[:300]
    return salida


def extraer(envio: dict, geo: dict) -> dict:
    """
    Cruza el payload contra lo que TrackIn necesita, sea aereo o maritimo.

    Los dos comparten la forma general —`route` con origen y destino, y una
    lista de movimientos— aunque cambien los nombres de las piezas. Se busca
    por las dos variantes en vez de escribir dos extractores.
    """
    hallado: dict[str, dict] = {}
    ruta = envio.get("route") or {}

    # Los nombres reales, medidos: maritimo usa port_of_loading/discharge y
    # aereo usa origin/destination. La primera version los adivino y dio un
    # falso negativo en la via aerea, que si traia los datos.
    origen = ruta.get("port_of_loading") or ruta.get("origin") or {}
    destino = ruta.get("port_of_discharge") or ruta.get("destination") or {}

    for clave in ("date_of_loading", "date_of_dep"):
        if origen.get(clave):
            hallado["etd_atd"] = {"valor": origen[clave], "de": "route.origen." + clave}
            break
    # `date_of_rcf` es "Received from Flight": el hito de llegada en lo aereo.
    for clave in ("date_of_discharge_predicted", "date_of_discharge",
                  "date_of_rcf_initial", "date_of_rcf"):
        if destino.get(clave):
            hallado["eta"] = {"valor": destino[clave], "de": "route.destino." + clave}
            break
    loc = destino.get("location") or {}
    if loc.get("code") or loc.get("iata"):
        hallado["destino"] = {"valor": loc.get("code") or loc.get("iata"),
                              "de": "route.destino.location"}

    # En lo aereo el transportista vive arriba del todo, no en los movimientos.
    linea = envio.get("airline") or envio.get("carrier") or {}
    if linea.get("name"):
        hallado["identificador"] = {"valor": str(linea.get("iata") or linea.get("scac"))
                                    + " · " + linea["name"], "de": "airline/carrier"}

    unidades = envio.get("containers") or envio.get("packages") or envio.get("legs") or []
    movimientos = []
    for u in unidades:
        movimientos.extend(u.get("movements") or u.get("events") or [])
    movimientos = movimientos or envio.get("movements") or envio.get("events") or []
    if movimientos:
        act = [m for m in movimientos if m.get("status") == "ACT"]
        hallado["hitos"] = {"valor": str(len(movimientos)) + " eventos (" + str(len(act))
                            + " ACT / " + str(len(movimientos) - len(act)) + " EST)",
                            "de": "movements[]"}
        nombres = []
        for m in movimientos:
            v = m.get("vessel") or m.get("flight") or m.get("flight_number")
            n = v.get("name") if isinstance(v, dict) else v
            if n and n not in nombres:
                nombres.append(n)
        if nombres:
            hallado["transporte"] = {"valor": " -> ".join(str(n) for n in nombres),
                                     "de": "movements[].vessel/flight"}

    for f in (geo.get("features") or []):
        pr = f.get("properties") or {}
        act = pr.get("current")
        if act and act.get("coordinates"):
            hallado["posicion"] = {"valor": str(act["coordinates"]),
                                   "de": "geojson properties.current.coordinates"}
        v = pr.get("vessel") or pr.get("flight") or {}
        if isinstance(v, dict) and (v.get("imo") or v.get("icao24")):
            hallado.setdefault("identificador", {
                "valor": str(v.get("imo") or v.get("icao24")),
                "de": "geojson properties.vessel/flight"})
        if f.get("geometry", {}).get("type") == "LineString":
            hallado.setdefault("trayecto", {"valor": "LineString", "de": "geojson geometry"})
    return hallado


def main() -> int:
    import httpx

    parser = argparse.ArgumentParser(description="TASK-28 fase 3e: altas pendientes")
    parser.add_argument("--network", choices=["personal", "gutis"], required=True)
    parser.add_argument("--solo-poll", action="store_true",
                        help="no crea nada: re-analiza los embarques ya dados de alta")
    args = parser.parse_args()

    env = load_env()
    token = (env.get("SHIPSGO_API_TOKEN") or env.get("SHIPSGO_SECRET") or "").strip()
    h = {"X-Shipsgo-User-Token": token, "Content-Type": "application/json",
         "Accept": "application/json"}

    print(SEP)
    print(" TrackIn - TASK-28 Fase 3e: MAWB aereo y BL de COSCO")
    print(SEP)
    print("  Cuenta nueva. Dos altas, ni una mas.")

    evidencia: dict = {"spike": "TASK-28", "fase": "3e-altas-pendientes",
                       "timestamp_utc": utc_now(), "network_profile": args.network,
                       "embarques": []}
    creados = []

    with httpx.Client() as cliente:
        print(SUB)
        print("  A. ALTAS")
        print(SUB)
        if args.solo_poll:
            previo = json.loads((Path(__file__).resolve().parent / "output"
                                 / ("07_pendientes_" + args.network + ".json")
                                 ).read_text(encoding="utf-8"))
            for e in previo["embarques"]:
                if e.get("id"):
                    ref = AEREA if e["via"] == "air" else MARITIMA
                    creados.append((ref, e["id"]))
                    evidencia["embarques"].append({k: v for k, v in e.items()
                                                   if k in ("etiqueta", "via", "peticion",
                                                            "status", "id", "respuesta_alta")})
            print("  --solo-poll: reusando " + str(len(creados)) + " embarques ya creados.")

        for ref in ([] if args.solo_poll else (AEREA, MARITIMA)):
            r = llamar(cliente, "POST", BASE + "/" + ref["via"] + "/shipments", h, ref["cuerpo"])
            envio = ((r.get("json") or {}).get("shipment") or {})
            sid = envio.get("id")
            estado = "id=" + str(sid) if sid else json.dumps(r.get("json") or {})[:90]
            print("  {:<26} [{}] {}".format(ref["etiqueta"], r.get("status"), estado))
            if sid:
                creados.append((ref, sid))
            evidencia["embarques"].append({"etiqueta": ref["etiqueta"], "via": ref["via"],
                                           "peticion": ref["cuerpo"], "status": r.get("status"),
                                           "id": sid, "respuesta_alta": r.get("json")})

        if not creados:
            print("\n  Ninguna alta prospero. Revisar creditos de la cuenta nueva.")
            save_evidence("task28", "07_pendientes_" + args.network + ".json", evidencia)
            return 1

        print(SUB)
        print("  B. MADURACION Y POLL")
        print(SUB)
        if not args.solo_poll:
            print("  La fase 3d midio ~90 s de NEW a datos completos. Esperando "
                  + str(ESPERA_INICIAL_S) + " s...")
            time.sleep(ESPERA_INICIAL_S)

        for ref, sid in creados:
            url = BASE + "/" + ref["via"] + "/shipments/" + str(sid)
            envio, geo = {}, {}
            for intento in range(1, REINTENTOS_POLL + 1):
                envio = (llamar(cliente, "GET", url, h).get("json") or {}).get("shipment") or {}
                geo = (llamar(cliente, "GET", url + "/geojson", h).get("json") or {}).get(
                    "geojson") or {}
                estado = envio.get("status")
                print("  " + ref["etiqueta"] + "  intento " + str(intento)
                      + "  estado=" + str(estado))
                if estado and estado != "NEW":
                    break
                if intento < REINTENTOS_POLL:
                    time.sleep(ESPERA_ENTRE_POLL_S)

            campos = extraer(envio, geo)
            print(SUB)
            print("  " + ref["etiqueta"] + "  ·  estado final " + str(envio.get("status")))
            print(SUB)
            for campo, quien in EXIGIDOS.items():
                if campo in campos:
                    print("  [SI] {:<14} {}".format(campo, str(campos[campo]["valor"])[:70]))
                else:
                    print(f"  [no] {campo:<14} ausente · {quien}")
            for e in evidencia["embarques"]:
                if e.get("id") == sid:
                    e.update(estado_final=envio.get("status"), campos=campos,
                             payload_shipment=envio, payload_geojson=geo)

    print(SEP)
    print("  VEREDICTO")
    print(SEP)
    for e in evidencia["embarques"]:
        if not e.get("id"):
            print("  " + e["etiqueta"] + ": alta rechazada (" + str(e.get("status")) + ")")
            continue
        n = len(e.get("campos") or {})
        print("  {:<26} estado {:<10} {} de {} campos".format(
            e["etiqueta"], str(e.get("estado_final")), n, len(EXIGIDOS)))
    print(SEP)

    save_evidence("task28", "07_pendientes_" + args.network + ".json", evidencia)
    return 0


if __name__ == "__main__":
    sys.exit(main())
