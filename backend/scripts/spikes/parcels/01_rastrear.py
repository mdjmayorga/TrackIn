"""
Spike Parcels API - rastrear tres pedidos reales de Gutis contra lo que ya se sabe.

POR QUE
    En la reunion del 29/09/2026 los usuarios clave pidieron una alternativa a
    ShipsGo con licencia (cuota fija mensual) en vez de pago por embarque.
    Parcels vende planes mensuales con cuota (300 envios por US$19). Este spike
    responde si entrega lo que TrackIn usa hoy de ShipsGo.

PREGUNTAS DEL SPIKE
    (1) Resuelve un contenedor, un BL y una guia aerea reales de Gutis?
    (2) Entrega el puerto de descarga (toPort, UN/LOCODE)? `US-54` depende de el.
    (3) Entrega la ETA? El contrato no tiene campo propio: se busca en
        `attributes`, en los eventos y en `flight_legs`.
    (4) Entrega los hitos y la llegada real, y coinciden con ShipsGo y TICA?

GASTA CUOTA
    La cuenta gratuita trae 3 envios. La cuota cuenta numeros de rastreo
    **unicos por ciclo de facturacion**: reenviar el mismo numero en el mismo
    ciclo no cobra. Aun asi:
    - Sin --confirmar el script SOLO muestra el plan.
    - Con --solo ALIAS se envia uno por corrida.
    - Un 503 no consume cuota; un 402 corta la corrida y muestra lo disponible.
    - --mock usa el servidor de pruebas de Parcels: no pide token ni gasta nada.

VERDAD CONOCIDA (consultada gratis el 29/09/2026)
    arribado   MRSU8132490     ShipsGo: DISCHARGED el 18/09 en CRPMN (Moin)
    maritimo   COSU6508789000  ShipsGo: SAILING, ETA 05/10 a CRCAL (Caldera)
    aereo      020-25244995    TICA: arribo 10/09 desde Frankfurt (Lufthansa)
    Las dos guias aereas del WK38 ya llegaron: no hay una aerea en transito en
    el archivo. Ver el README del spike.

USO
    python backend/scripts/spikes/parcels/01_rastrear.py --network personal --mock
    python backend/scripts/spikes/parcels/01_rastrear.py --network personal
    python backend/scripts/spikes/parcels/01_rastrear.py --network personal --confirmar --solo maritimo

SALIDA
    Evidencia: parcels/output/01_<alias>_<red>.json (resumen y comparacion).
    Respuesta cruda: parcels/output/raw/ (ignorado por git).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from _common import (
    SPIKES_DIR,
    describe_http_error,
    header,
    load_env,
    mask,
    require,
    save_evidence,
    utc_now,
)

LIVE = "https://parcelsapp.com/api/v4"
MOCK = "https://parcelsapp.com/api-docs/mock/v4"
ESPERA_ENTRE_LECTURAS_S = 5
LECTURAS_MAXIMAS = 36  # tres minutos

#: Los tres pedidos del Excel WK38 y lo que ya se sabe de cada uno.
REFERENCIAS: dict[str, dict[str, Any]] = {
    "arribado": {
        "oc": "4500016171-90",
        "tipo": "CONTENEDOR",
        "numero": "MRSU8132490",
        "verdad": {
            "fuente": "ShipsGo",
            "estado": "DISCHARGED",
            "puerto": "CRPMN",
            "llegada": "2026-09-18",
            "eta": "2026-09-18",
        },
    },
    "maritimo": {
        "oc": "4500016185-10",
        "tipo": "BL",
        "numero": "COSU6508789000",
        "verdad": {
            "fuente": "ShipsGo",
            "estado": "SAILING",
            "puerto": "CRCAL",
            "llegada": None,
            "eta": "2026-10-05",
        },
    },
    "aereo": {
        "oc": "4500018062-10/20/30",
        "tipo": "MAWB",
        # Guion tras el prefijo de aerolinea: lo pide el contrato para detectar AWB.
        "numero": "020-25244995",
        "verdad": {
            "fuente": "TICA",
            "estado": "arribada",
            "puerto": "SJO",
            "llegada": "2026-09-10",
            "eta": None,
        },
    },
}


def _argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--network", choices=["personal", "gutis"], required=True)
    parser.add_argument("--mock", action="store_true", help="Servidor de pruebas: sin token.")
    parser.add_argument("--confirmar", action="store_true", help="Enviar de verdad.")
    parser.add_argument("--solo", choices=sorted(REFERENCIAS), help="Enviar solo uno.")
    parser.add_argument(
        "--pista",
        help=(
            "carrier_hint de GET /tracking-carriers (p. ej. maersk-line). Reenviar el "
            "mismo numero en el ciclo no consume cuota."
        ),
    )
    return parser.parse_args()


def _plan(elegidas: list[str], mock: bool) -> None:
    print("\n  Plan:")
    for alias in elegidas:
        ref = REFERENCIAS[alias]
        print(f"    {alias:<9} {ref['tipo']:<11} {ref['numero']:<16} OC {ref['oc']}")
    costo = "0 (mock)" if mock else f"hasta {len(elegidas)} de los 3 envíos gratuitos"
    print(f"  Costo     : {costo}")


def _atributos(shipment: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"l": a.get("l"), "val": a.get("val"), "code": a.get("code")}
        for a in shipment.get("attributes") or []
    ]


def _candidatos_eta(shipment: dict[str, Any]) -> list[str]:
    """Todo lo que parezca una fecha estimada de llegada, venga de donde venga."""
    hallados: list[str] = []
    for atributo in _atributos(shipment):
        texto = f"{atributo['l']} {atributo['code']}".lower()
        if any(p in texto for p in ("eta", "estimated", "arrival", "llegada")):
            hallados.append(f"attributes: {atributo['l']} = {atributo['val']}")
    for tramo in shipment.get("flight_legs") or []:
        if tramo.get("scheduled_arrival"):
            hallados.append(
                f"flight_legs: {tramo.get('origin')}->{tramo.get('destination')} "
                f"llegada programada {tramo['scheduled_arrival']}"
            )
    for evento in shipment.get("states") or []:
        if "estimat" in (evento.get("status") or evento.get("state") or "").lower():
            hallados.append(f"states: {evento.get('state')} ({evento.get('date')})")
    return hallados


def _resumen(alias: str, resultado: dict[str, Any]) -> dict[str, Any]:
    shipment = resultado.get("shipment") or {}
    eventos = shipment.get("states") or []
    verdad = REFERENCIAS[alias]["verdad"]
    detectado = shipment.get("detectedCarrier") or {}
    return {
        "estado_resultado": resultado.get("state"),
        "desde_cache": resultado.get("from_cache"),
        "error": shipment.get("error"),
        "transportista": detectado.get("name") or detectado.get("slug"),
        "modo": shipment.get("transportMode"),
        "estado": shipment.get("status"),
        "origen": shipment.get("origin"),
        "destino": shipment.get("destination"),
        "puerto_origen": shipment.get("fromPort") or shipment.get("fromAirport"),
        "puerto_destino": shipment.get("toPort") or shipment.get("toAirport"),
        "eventos": len(eventos),
        "primer_evento": eventos[-1] if eventos else None,
        "ultimo_evento": eventos[0] if eventos else None,
        "tramos_de_vuelo": len(shipment.get("flight_legs") or []),
        "eta_candidatos": _candidatos_eta(shipment),
        "atributos": _atributos(shipment),
        "verdad_conocida": verdad,
    }


def _imprimir(alias: str, resumen: dict[str, Any]) -> None:
    verdad = resumen["verdad_conocida"]
    print(f"\n  --- {alias} ---")
    for clave in (
        "estado_resultado",
        "error",
        "transportista",
        "modo",
        "estado",
        "origen",
        "destino",
        "puerto_origen",
        "puerto_destino",
        "eventos",
        "tramos_de_vuelo",
    ):
        print(f"    {clave:<17}: {resumen[clave]}")
    for nombre in ("primer_evento", "ultimo_evento"):
        evento = resumen[nombre] or {}
        # El contrato dice `state`; las respuestas reales traen `status`.
        texto = evento.get("status") or evento.get("state")
        print(f"    {nombre:<17}: {evento.get('date')} · {texto} · " f"{evento.get('location')}")
    print(f"    ETA encontrada   : {resumen['eta_candidatos'] or 'ninguna'}")
    print(
        f"    Según {verdad['fuente']:<9}: {verdad['estado']} · puerto {verdad['puerto']} · "
        f"llegada {verdad['llegada']} · ETA {verdad['eta']}"
    )


def _rastrear(
    cliente: httpx.Client, alias: str, pista: str | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    envio: dict[str, str] = {"tracking_number": REFERENCIAS[alias]["numero"]}
    if pista:
        envio["carrier_hint"] = pista
    respuesta = cliente.post("/trackings", json={"language": "es", "shipments": [envio]})
    crudo: dict[str, Any] = {"post": {"status": respuesta.status_code, "body": _json(respuesta)}}
    if respuesta.status_code != 200:
        return crudo, {"http": respuesta.status_code, "cuerpo": _json(respuesta)}

    cuerpo = respuesta.json()
    request_id = cuerpo["request_id"]
    lecturas = 0
    while not cuerpo.get("done") and lecturas < LECTURAS_MAXIMAS:
        time.sleep(ESPERA_ENTRE_LECTURAS_S)
        lecturas += 1
        leida = cliente.get(f"/trackings/{request_id}")
        if leida.status_code != 200:
            crudo["get_fallido"] = {"status": leida.status_code, "body": _json(leida)}
            break
        cuerpo = leida.json()
    crudo["final"] = cuerpo
    crudo["lecturas"] = lecturas
    print(f"    request_id {mask(request_id)} · done={cuerpo.get('done')} tras {lecturas} lecturas")
    for rechazo in cuerpo.get("rejected") or []:
        print(f"    [!] rechazado: {rechazo}")
    resultados = cuerpo.get("results") or []
    return crudo, _resumen(alias, resultados[0]) if resultados else {"sin_resultados": cuerpo}


def _json(respuesta: httpx.Response) -> Any:
    try:
        return respuesta.json()
    except ValueError:
        return respuesta.text[:500]


def _guardar_crudo(alias: str, red: str, crudo: dict[str, Any]) -> None:
    carpeta = SPIKES_DIR / "parcels" / "output" / "raw"
    carpeta.mkdir(parents=True, exist_ok=True)
    archivo = carpeta / f"01_{alias}_{red}_{utc_now().replace(':', '')}.json"
    archivo.write_text(json.dumps(crudo, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"    Crudo    : {archivo}")


def main() -> int:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    args = _argumentos()
    elegidas = [args.solo] if args.solo else list(REFERENCIAS)
    base = MOCK if args.mock else LIVE
    timestamp = header("Spike Parcels API — tres pedidos reales", args.network, {"Servidor": base})
    _plan(elegidas, args.mock)

    cabeceras = {"Accept": "application/json"}
    if not args.mock:
        cabeceras["Authorization"] = "Bearer " + require(load_env(), "PARCELS_API_KEY")
    if not (args.confirmar or args.mock):
        print("\n  Sin --confirmar no se envía nada. Revisar el plan y repetir con --confirmar.")
        return 0

    with httpx.Client(base_url=base, headers=cabeceras, timeout=30) as cliente:
        for alias in elegidas:
            print(f"\n  Enviando {alias} ({REFERENCIAS[alias]['numero']})...")
            try:
                crudo, resumen = _rastrear(cliente, alias, args.pista)
            except httpx.HTTPError as exc:
                categoria, explicacion = describe_http_error(exc)
                print(f"    [!] {categoria}: {explicacion}")
                return 1
            if not args.mock:
                _guardar_crudo(alias, args.network, crudo)
            if "http" in resumen:
                error = (
                    (resumen["cuerpo"] or {}).get("error", {})
                    if isinstance(resumen["cuerpo"], dict)
                    else {}
                )
                # El 403 UNCONFIRMED_ACCOUNT trae un enlace con un token de un
                # solo uso: se nombra, no se imprime.
                if error.get("confirmation_url"):
                    error = {
                        **error,
                        "confirmation_url": "<en el crudo; confirmar desde el correo>",
                    }
                print(f"    [!] HTTP {resumen['http']}: {error or resumen['cuerpo']}")
                if resumen["http"] in (401, 402, 403):
                    return 1
                continue
            if "sin_resultados" in resumen:
                print(f"    [!] Sin resultados: {resumen['sin_resultados']}")
                continue
            _imprimir(alias, resumen)
            if not args.mock:
                referencia = REFERENCIAS[alias]
                save_evidence(
                    "parcels",
                    f"01_{alias}{'_' + args.pista if args.pista else ''}_{args.network}.json",
                    {
                        "spike": "parcels",
                        "fase": "01-rastrear",
                        "timestamp_utc": timestamp,
                        "red": args.network,
                        "alias": alias,
                        "oc": referencia["oc"],
                        "tipo": referencia["tipo"],
                        "numero": referencia["numero"],
                        "carrier_hint": args.pista,
                        "resumen": resumen,
                    },
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
