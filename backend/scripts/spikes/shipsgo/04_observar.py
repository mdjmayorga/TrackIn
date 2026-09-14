"""
Spike TASK-28 - ShipsGo - Fase 4: observar los envios durante varios dias.

PREGUNTAS DEL SPIKE QUE RESPONDE
    (1) Los datos llegan hasta la descarga en Moin/Limon/Caldera, o se cortan?
    (2) Con que frescura? checked_at y los cambios entre corridas dicen cada
        cuanto actualiza de verdad, contra las "5 veces al dia" que promete.
    (3) Como se traduce su estado a las etapas de TrackIn (RN-02 a RN-06)?
    (4) Cubre lo que piden los criterios de US-45 y US-46: buque con IMO,
        ETA predicha, ETD/ATD, envio aereo partido (status_split)?

NO GASTA CREDITOS
    Solo lee el detalle de envios ya creados. Correrlo tantas veces como se
    quiera: manana, mediodia y tarde, de aqui al cierre del spike.

QUE HACE
    Por cada envio de output/envios_creados.json (lo escribe la Fase 3):
    1. GET del detalle y respuesta cruda a output/raw/ (ignorado por git).
    2. Resumen con lo que importa a TrackIn, sin el numero de referencia.
    3. Comparacion contra la observacion anterior de ese envio: que cambio.
    4. Una linea mas en output/04_observaciones.jsonl, la serie de tiempo.

EL MAPEO DE ETAPAS ES UNA PROPUESTA
    ETAPA_MARITIMA y ETAPA_AEREA son hipotesis para validar con estos datos,
    no una decision. Dos cosas ya decididas las condicionan: el paso a
    EN_PROCESO_ADUANAL es manual (reunion del 04/09), asi que ningun estado
    del proveedor lleva ahi; y DELIVERED en aereo es entrega al agente en
    destino, no llegada a planta.

USO
    python backend/scripts/spikes/shipsgo/04_observar.py --network personal
    python backend/scripts/spikes/shipsgo/04_observar.py --network personal --solo mar-moin-1

SALIDA
    Codigo 0 si todos los envios respondieron.
    Serie en backend/scripts/spikes/shipsgo/output/04_observaciones.jsonl
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _comercial import TIMEOUT, cuerpo_json, guardar_crudo, llamar, parser_base  # noqa: E402
from _common import SEP, SPIKES_DIR, SUB, header, load_env, mask, require, utc_now  # noqa: E402

BASE = "https://api.shipsgo.com/v2"
REGISTRO = SPIKES_DIR / "shipsgo" / "output" / "envios_creados.json"
SERIE = SPIKES_DIR / "shipsgo" / "output" / "04_observaciones.jsonl"

#: Propuesta de mapeo estado ShipsGo -> etapa TrackIn. A validar.
ETAPA_MARITIMA = {
    "NEW": "EN_ORIGEN",
    "INPROGRESS": "EN_ORIGEN",
    "BOOKED": "EN_ORIGEN",
    "LOADED": "EN_ORIGEN",  # cargado pero sin zarpar
    "SAILING": "EN_TRANSITO",
    "ARRIVED": "EN_DESTINO",
    "DISCHARGED": "EN_DESTINO",  # EN_PROCESO_ADUANAL lo decide una persona
    "UNTRACKED": "SIN_TRACKING",
}
ETAPA_AEREA = {
    "NEW": "EN_ORIGEN",
    "INPROGRESS": "EN_ORIGEN",
    "BOOKED": "EN_ORIGEN",
    "EN_ROUTE": "EN_TRANSITO",
    "LANDED": "EN_DESTINO",
    "DELIVERED": "EN_DESTINO",  # entrega al agente en destino, no a planta
    "UNTRACKED": "SIN_TRACKING",
}

#: Codigos UN/LOCODE e IATA de los cuatro destinos de maestro_destinos.
DESTINOS_GUTIS = {"CRMOB", "CRLIO", "CRCAL", "SJO"}


def horas_desde(instante: Any) -> float | None:
    """
    Horas entre un timestamp del proveedor y ahora. None si no parsea.

    ShipsGo manda los instantes SIN zona horaria ("2025-04-14 10:31:02") y
    cada movimiento trae aparte el timezone de su lugar. Aca se asume UTC;
    verificarlo contra un evento real es un pendiente del spike, porque el
    adaptador de US-45 necesita saber si tiene que convertir.
    """
    if not isinstance(instante, str) or not instante:
        return None
    try:
        dt = datetime.fromisoformat(instante.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return round((datetime.now(timezone.utc) - dt).total_seconds() / 3600, 1)


def ultimo_real(movimientos: list[dict[str, Any]]) -> dict[str, Any] | None:
    """El movimiento ACT mas reciente: lo ultimo que de verdad ocurrio."""
    reales = [m for m in movimientos if m.get("status") == "ACT" and m.get("timestamp")]
    return max(reales, key=lambda m: m["timestamp"]) if reales else None


def resumir_maritimo(envio: dict[str, Any]) -> dict[str, Any]:
    ruta = envio.get("route") or {}
    pol = ruta.get("port_of_loading") or {}
    pod = ruta.get("port_of_discharge") or {}
    pod_codigo = (pod.get("location") or {}).get("code")
    movimientos = [m for c in envio.get("containers") or [] for m in c.get("movements") or []]
    ultimo = ultimo_real(movimientos)
    buques = sorted({
        (m.get("vessel") or {}).get("name", "") + " / IMO " + str((m.get("vessel") or {}).get("imo"))
        for m in movimientos
        if m.get("vessel")
    })
    return {
        "status": envio.get("status"),
        "etapa_propuesta": ETAPA_MARITIMA.get(str(envio.get("status")), "?"),
        "naviera": (envio.get("carrier") or {}).get("scac"),
        "pol": (pol.get("location") or {}).get("code"),
        "fecha_carga": pol.get("date_of_loading"),
        "pod": pod_codigo,
        "pod_es_destino_gutis": pod_codigo in DESTINOS_GUTIS if pod_codigo else None,
        "fecha_descarga": pod.get("date_of_discharge"),
        "fecha_descarga_inicial": pod.get("date_of_discharge_initial"),
        "fecha_descarga_predicha": pod.get("date_of_discharge_predicted"),
        "transbordos": ruta.get("ts_count"),
        "avance_pct": ruta.get("transit_percentage"),
        "contenedores": envio.get("container_count"),
        "estados_contenedor": sorted({str(c.get("status")) for c in envio.get("containers") or []}),
        "movimientos_act": sum(1 for m in movimientos if m.get("status") == "ACT"),
        "movimientos_est": sum(1 for m in movimientos if m.get("status") == "EST"),
        "ultimo_evento": (
            {"evento": ultimo.get("event"), "lugar": (ultimo.get("location") or {}).get("code"),
             "instante": ultimo.get("timestamp")}
            if ultimo else None
        ),
        "buques": buques,
        "checked_at": envio.get("checked_at"),
        "horas_desde_checked": horas_desde(envio.get("checked_at")),
        "updated_at": envio.get("updated_at"),
    }


def resumir_aereo(envio: dict[str, Any]) -> dict[str, Any]:
    ruta = envio.get("route") or {}
    origen = ruta.get("origin") or {}
    destino = ruta.get("destination") or {}
    destino_iata = (destino.get("location") or {}).get("iata")
    movimientos = envio.get("movements") or []
    ultimo = ultimo_real(movimientos)
    return {
        "status": envio.get("status"),
        "etapa_propuesta": ETAPA_AEREA.get(str(envio.get("status")), "?"),
        "envio_partido": envio.get("status_split"),
        "aerolinea": (envio.get("airline") or {}).get("iata"),
        "origen": (origen.get("location") or {}).get("iata"),
        "fecha_salida": origen.get("date_of_dep"),
        "fecha_salida_inicial": origen.get("date_of_dep_initial"),
        "destino": destino_iata,
        "destino_es_sjo": destino_iata == "SJO" if destino_iata else None,
        "fecha_rcf": destino.get("date_of_rcf"),
        "fecha_rcf_inicial": destino.get("date_of_rcf_initial"),
        "transbordos": ruta.get("ts_count"),
        "avance_pct": ruta.get("transit_percentage"),
        "piezas": (envio.get("cargo") or {}).get("pieces"),
        "movimientos_act": sum(1 for m in movimientos if m.get("status") == "ACT"),
        "movimientos_est": sum(1 for m in movimientos if m.get("status") == "EST"),
        "eventos_reales": [m.get("event") for m in movimientos if m.get("status") == "ACT"],
        "ultimo_evento": (
            {"evento": ultimo.get("event"), "lugar": (ultimo.get("location") or {}).get("iata"),
             "vuelo": ultimo.get("flight"), "instante": ultimo.get("timestamp")}
            if ultimo else None
        ),
        "vuelos": sorted({str(m.get("flight")) for m in movimientos if m.get("flight")}),
        "checked_at": envio.get("checked_at"),
        "horas_desde_checked": horas_desde(envio.get("checked_at")),
        "updated_at": envio.get("updated_at"),
    }


def observacion_anterior(alias: str) -> dict[str, Any] | None:
    if not SERIE.is_file():
        return None
    anterior = None
    for linea in SERIE.read_text(encoding="utf-8").splitlines():
        if linea.strip():
            registro = json.loads(linea)
            if registro.get("alias") == alias and registro.get("resumen"):
                anterior = registro
    return anterior


def cambios(antes: dict[str, Any], ahora: dict[str, Any]) -> dict[str, list[Any]]:
    """Campos que cambiaron, sin contar la antiguedad, que cambia siempre."""
    ignorar = {"horas_desde_checked"}
    return {
        k: [antes.get(k), v]
        for k, v in ahora.items()
        if k not in ignorar and antes.get(k) != v
    }


def main() -> int:
    parser = parser_base("Spike TASK-28 ShipsGo Fase 4: observar envios")
    parser.add_argument("--solo", action="append", metavar="ALIAS", help="Solo este alias (repetible).")
    args = parser.parse_args()

    if not REGISTRO.is_file():
        sys.exit("[FATAL] No hay envios registrados. Correr antes shipsgo/03_crear_envios.py --confirmar")
    envios = json.loads(REGISTRO.read_text(encoding="utf-8"))["envios"]
    if args.solo:
        envios = {a: e for a, e in envios.items() if a in args.solo}

    env = load_env()
    token = require(env, "SHIPSGO_API_TOKEN")
    header(
        "TrackIn - Spike TASK-28 - ShipsGo - Fase 4: observacion",
        args.network,
        {"token": mask(token), "envios": str(len(envios))},
    )

    import httpx

    fallidos = 0
    SERIE.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(
        headers={"X-Shipsgo-User-Token": token, "Accept": "application/json"},
        timeout=TIMEOUT,
    ) as client, SERIE.open("a", encoding="utf-8") as serie:
        for alias, envio in envios.items():
            path = envio["endpoint"] + "/" + str(envio["shipment_id"])
            response, diag = llamar(client, "GET", BASE + path)
            observado = utc_now()
            print(SUB)
            print("  " + alias + "  (" + envio["tipo"] + " " + envio["numero_enmascarado"] + ")")
            print(SUB)

            cuerpo = cuerpo_json(response) if response is not None else None
            if not diag.get("ok") or not isinstance(cuerpo, dict) or not cuerpo.get("shipment"):
                fallidos += 1
                print("  [FALLO] " + str(diag.get("status_code") or diag.get("error_category")))
                serie.write(json.dumps({"observado_utc": observado, "alias": alias,
                                        "network": args.network, "diag": diag}) + "\n")
                continue

            guardar_crudo("shipsgo", "04_" + alias + "_" + observado.replace(":", "")[:15] + ".json", cuerpo)
            detalle = cuerpo["shipment"]
            resumen = (resumir_aereo if envio["via"] == "AEREO" else resumir_maritimo)(detalle)

            for clave, valor in resumen.items():
                print("  {:<24}: {}".format(clave, valor))

            anterior = observacion_anterior(alias)
            diferencias = cambios(anterior["resumen"], resumen) if anterior else None
            print()
            if anterior is None:
                print("  Primera observacion de este envio.")
            elif diferencias:
                print("  Cambios desde " + anterior["observado_utc"] + ":")
                for campo, (antes, ahora) in diferencias.items():
                    print("    " + campo + ": " + str(antes) + " -> " + str(ahora))
            else:
                print("  Sin cambios desde " + anterior["observado_utc"] + ".")

            serie.write(json.dumps({
                "observado_utc": observado,
                "alias": alias,
                "via": envio["via"],
                "network": args.network,
                "latencia_ms": diag.get("elapsed_ms"),
                "resumen": resumen,
                "cambios": diferencias,
            }, ensure_ascii=False) + "\n")

    print(SEP)
    print("  " + str(len(envios) - fallidos) + " de " + str(len(envios)) + " envios observados.")
    print("  Serie: " + str(SERIE))
    print(SEP)
    return 0 if fallidos == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
