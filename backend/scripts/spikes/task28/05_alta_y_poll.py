"""
Spike TASK-28 - Fase 3c: alta de embarques reales y lectura del payload.

ES LA FASE QUE CUESTA
    Los dos proveedores son *create-then-poll*: dar de alta un embarque es lo
    que consume el trial. Por eso todo lo anterior —auth, cuota, catalogo,
    validacion local de las referencias— se hizo sin gastar, y aqui se gasta
    una sola vez por referencia.

QUE RESPONDE
    1. ShipsGo devuelve hitos, posicion y ETA con referencias reales de Gutis?
       Es el go/no-go de `US-45`.
    2. El payload trae los campos que TrackIn necesita? Concretamente los que
       `historial_tracking` y RN-16 exigen: posicion, velocidad, rumbo; y los
       que `US-43` pide para la vista completa: ETD y ATD.
    3. TrackingMore puede rastrear un MAWB? La fase 2 dejo la sospecha —su
       catalogo son 1505 couriers `express` y 173 `globalpost`, ninguna
       aerolinea— y esta fase la confirma o la desmiente gastando un credito.
    4. Se cierra el hueco que la fase 1 dejo abierto: un `200` con
       `shipments: []` era "no existe" o "la cuenta estaba vacia"? Con
       embarques dados de alta, la respuesta se ve directamente.

REFERENCIAS
    Reales, de Gutis, validadas en local por `04_validar_referencias.py` antes
    de gastar un solo credito. La quinta que llego —`6163512401`— NO se usa:
    el validador la clasifico como HAWB y ninguna API resuelve una guia hija.

    **ShipsGo no valida el formato.** Medido: un `POST` con el contenedor
    inventado `XXXX0000000` devolvio `200 SUCCESS` y creo el embarque (id
    6734880, borrado despues). Cobra igual por una referencia imposible, asi
    que la validacion local de `US-32` deja de ser una comodidad y pasa a ser
    lo que protege el presupuesto.

USO
    python backend/scripts/spikes/task28/05_alta_y_poll.py --network personal
    python backend/scripts/spikes/task28/05_alta_y_poll.py --network personal --limpiar

    `--limpiar` borra al final los embarques creados. Por defecto NO borra: se
    dejan vivos para poder volver a consultarlos y ver si maduran.

SALIDA
    Evidencia en backend/scripts/spikes/task28/output/05_alta_<red>.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import SEP, SUB, load_env, save_evidence, utc_now

BASE_SG = "https://api.shipsgo.com/v2"
BASE_TM = "https://api.trackingmore.com/v4"
TIMEOUT = 40.0
ESPERA_MADURACION_S = 45

# Referencias reales de Gutis, ya validadas en local.
MARITIMAS = [
    {"etiqueta": "Maersk 1", "container_number": "MRSU8507472", "booking_number": "271102440"},
    {"etiqueta": "Maersk 2", "container_number": "MRSU8132490", "booking_number": "271108898"},
    {"etiqueta": "COSCO", "container_number": "TGBU4872990", "booking_number": "COSU6508789000"},
]
AEREA = {"etiqueta": "Lufthansa Cargo", "awb_number": "02050685434"}

# Campos que TrackIn necesita, y quien los exige. Se buscan por nombre en
# cualquier nivel del payload: lo que importa es si el dato viene o no.
CAMPOS_TRACKIN = {
    "posicion": (["latitude", "lat", "longitude", "lon", "lng"],
                 "historial_tracking.posicion / mapa (RF-16)"),
    "velocidad": (["speed", "sog", "speed_over_ground"], "RN-16 y US-08 (ETA estimada)"),
    "rumbo": (["course", "cog", "heading"], "historial_tracking.rumbo"),
    "eta": (["eta", "estimated_arrival", "estimated_time_of_arrival"], "RN-01 fecha proyectada"),
    "etd": (["etd", "estimated_departure"], "US-43 vista completa"),
    "atd": (["atd", "actual_departure"], "US-43 vista completa"),
    "ata": (["ata", "actual_arrival"], "RN-14 / US-14"),
    "hitos": (["milestones", "events", "movements", "status_events"], "RN-02 a RN-06"),
    "buque": (["vessel", "vessel_name", "ship_name"], "elementos_rastreados"),
    "imo_mmsi": (["imo", "mmsi"], "elementos_rastreados"),
}


def buscar_campos(obj, encontrados: dict) -> dict:
    """
    Recorre el payload y marca que campos de TrackIn aparecen, con un ejemplo.

    Busca por nombre a cualquier profundidad: los proveedores anidan distinto y
    lo que interesa del spike es si el dato existe, no donde vive.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            kb = k.lower()
            for campo, (alias, _) in CAMPOS_TRACKIN.items():
                if kb in alias and campo not in encontrados and v not in (None, "", [], {}):
                    encontrados[campo] = {"clave": k, "muestra": str(v)[:120]}
            buscar_campos(v, encontrados)
    elif isinstance(obj, list):
        for v in obj[:20]:
            buscar_campos(v, encontrados)
    return encontrados


def llamar(cliente, metodo: str, url: str, headers: dict, cuerpo=None) -> dict:
    """Llamada que nunca levanta: un fallo es un resultado del spike."""
    try:
        resp = cliente.request(metodo, url, headers=headers, json=cuerpo, timeout=TIMEOUT)
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__ + ": " + str(exc)[:200]}
    salida = {"ok": 200 <= resp.status_code < 300, "status": resp.status_code}
    try:
        salida["json"] = resp.json()
    except ValueError:
        salida["texto"] = resp.text[:300]
    return salida


def main() -> int:
    import httpx

    parser = argparse.ArgumentParser(description="TASK-28 fase 3c: alta y poll")
    parser.add_argument("--network", choices=["personal", "gutis"], required=True)
    parser.add_argument("--limpiar", action="store_true",
                        help="borra los embarques creados al terminar")
    args = parser.parse_args()

    env = load_env()
    sg = (env.get("SHIPSGO_API_TOKEN") or env.get("SHIPSGO_SECRET") or "").strip()
    tm = (env.get("TRACKINGMORE_API_KEY") or env.get("TRACKINGMORE_SECRET") or "").strip()
    h_sg = {"X-Shipsgo-User-Token": sg, "Content-Type": "application/json",
            "Accept": "application/json"}
    h_tm = {"Tracking-Api-Key": tm, "Content-Type": "application/json"}

    print(SEP)
    print(" TrackIn - TASK-28 Fase 3c: alta de embarques reales y lectura")
    print(SEP)
    print("  Red: " + args.network + "  |  4 altas: 3 maritimas + 1 aerea")
    print("  Referencias validadas en local antes de gastar (fase 3b).")

    evidencia: dict = {"spike": "TASK-28", "fase": "3c-alta-y-poll",
                       "timestamp_utc": utc_now(), "network_profile": args.network,
                       "altas": [], "trackingmore": {}}
    creados: list[tuple[str, int]] = []

    with httpx.Client() as cliente:
        # --- A. Altas en ShipsGo -----------------------------------------
        print(SUB)
        print("  A. ALTA EN SHIPSGO")
        print(SUB)
        for ref in MARITIMAS:
            cuerpo = {k: v for k, v in ref.items() if k != "etiqueta"}
            r = llamar(cliente, "POST", BASE_SG + "/ocean/shipments", h_sg, cuerpo)
            envio = ((r.get("json") or {}).get("shipment") or {})
            sid = envio.get("id")
            if sid:
                creados.append(("ocean", sid))
            print("  {:<18} [{}] id={}".format(ref["etiqueta"], r.get("status"), sid))
            evidencia["altas"].append({"tipo": "ocean", "etiqueta": ref["etiqueta"],
                                       "peticion": cuerpo, "status": r.get("status"),
                                       "id": sid, "respuesta": r.get("json")})

        r = llamar(cliente, "POST", BASE_SG + "/air/shipments", h_sg,
                   {"awb_number": AEREA["awb_number"]})
        envio = ((r.get("json") or {}).get("shipment") or {})
        sid_aereo = envio.get("id")
        if sid_aereo:
            creados.append(("air", sid_aereo))
        print("  {:<18} [{}] id={}".format(AEREA["etiqueta"], r.get("status"), sid_aereo))
        evidencia["altas"].append({"tipo": "air", "etiqueta": AEREA["etiqueta"],
                                   "peticion": {"awb_number": AEREA["awb_number"]},
                                   "status": r.get("status"), "id": sid_aereo,
                                   "respuesta": r.get("json")})

        # --- B. Maduracion y poll ----------------------------------------
        print(SUB)
        print("  B. POLL (tras " + str(ESPERA_MADURACION_S) + " s de maduracion)")
        print(SUB)
        print("  El alta solo registra; el proveedor va a buscar los datos despues.")
        time.sleep(ESPERA_MADURACION_S)

        for tipo, sid in creados:
            r = llamar(cliente, "GET", BASE_SG + "/" + tipo + "/shipments/" + str(sid), h_sg)
            payload = r.get("json") or {}
            campos = buscar_campos(payload, {})
            print("  " + tipo + "/" + str(sid) + "  [" + str(r.get("status")) + "]  campos: "
                  + (", ".join(sorted(campos)) if campos else "NINGUNO de los de TrackIn"))
            for entrada in evidencia["altas"]:
                if entrada.get("id") == sid:
                    entrada["poll"] = {"status": r.get("status"),
                                       "campos_trackin": campos,
                                       "payload": payload}

        # --- C. TrackingMore con el MAWB ---------------------------------
        print(SUB)
        print("  C. TRACKINGMORE CON EL MISMO MAWB")
        print(SUB)
        det = llamar(cliente, "POST", BASE_TM + "/couriers/detect", h_tm,
                     {"tracking_number": AEREA["awb_number"]})
        propuestos = [c.get("courier_code") for c in ((det.get("json") or {}).get("data") or [])]
        print("  detect propone: " + (", ".join(propuestos[:5]) if propuestos else "nada"))

        alta_tm = None
        if propuestos:
            alta_tm = llamar(cliente, "POST", BASE_TM + "/trackings/create", h_tm,
                             {"tracking_number": AEREA["awb_number"],
                              "courier_code": propuestos[0]})
            print("  create con '" + propuestos[0] + "' -> [" + str(alta_tm.get("status"))
                  + "] " + json.dumps((alta_tm.get("json") or {}).get("meta") or {})[:160])
            if alta_tm.get("ok"):
                time.sleep(10)
                lec = llamar(cliente, "GET", BASE_TM + "/trackings/get?tracking_numbers="
                             + AEREA["awb_number"], h_tm)
                campos = buscar_campos(lec.get("json") or {}, {})
                print("  poll -> [" + str(lec.get("status")) + "]  campos: "
                      + (", ".join(sorted(campos)) if campos else "NINGUNO"))
                evidencia["trackingmore"]["poll"] = {"status": lec.get("status"),
                                                     "campos_trackin": campos,
                                                     "payload": lec.get("json")}
        evidencia["trackingmore"].update({"detect_propuestos": propuestos, "create": alta_tm})

        # --- D. Limpieza opcional ----------------------------------------
        if args.limpiar:
            print(SUB)
            print("  D. LIMPIEZA")
            print(SUB)
            for tipo, sid in creados:
                r = llamar(cliente, "DELETE", BASE_SG + "/" + tipo + "/shipments/" + str(sid), h_sg)
                print("  borrado " + tipo + "/" + str(sid) + " -> " + str(r.get("status")))
            evidencia["limpiado"] = True

    # --- Resumen ---------------------------------------------------------
    print(SEP)
    print("  QUE CAMPOS DE TRACKIN LLEGARON")
    print(SEP)
    union: dict[str, str] = {}
    for entrada in evidencia["altas"]:
        for campo in (entrada.get("poll", {}).get("campos_trackin") or {}):
            union[campo] = entrada["etiqueta"]
    for campo, (_, quien) in CAMPOS_TRACKIN.items():
        marca = "SI " if campo in union else "no "
        print("  [" + marca + f"] {campo:<10} {quien}")
    evidencia["campos_presentes"] = sorted(union)
    print(SEP)

    save_evidence("task28", "05_alta_" + args.network + ".json", evidencia)
    return 0


if __name__ == "__main__":
    sys.exit(main())
