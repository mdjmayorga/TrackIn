"""
Spike TASK-28 - ShipsGo - Fase 3: registrar las referencias reales.

PREGUNTAS DEL SPIKE QUE RESPONDE
    (1) ShipsGo acepta un contenedor, booking o BL real de Gutis?
    (2) Acepta un MAWB real de la ruta India/China -> SJO?
    Si los datos llegan hasta la descarga lo dice la Fase 4, que observa
    estos envios durante varios dias.

GASTA CREDITOS
    Cada envio nuevo cuesta 1 credito (la cuenta gratuita trae 3). Por eso:
    - Sin --confirmar, el script SOLO muestra el plan y lo que costaria.
    - Antes de gastar, verifica el digito de control del contenedor (ISO 6346)
      y del MAWB. Un numero mal copiado se descarta sin llamar a la API,
      salvo --forzar.
    - Un 409 ALREADY_EXISTS no cobra y devuelve el id: correr dos veces el
      script no gasta dos veces.
    - Un 402 NOT_ENOUGH_CREDITS corta la corrida.
    - Con --solo ALIAS se crea de a uno, para decidir en que gastar cada credito.

COMO SE ENVIA CADA TIPO
    CONTENEDOR -> container_number.
    BOOKING    -> booking_number.
    BL         -> booking_number. ShipsGo NO tiene campo para el BL: se prueba
                  si lo resuelve por ahi. Si no, es un hallazgo para TASK-30.
    MAWB       -> awb_number, en /air/shipments.
    HAWB       -> no se envia. ShipsGo pide MAWB; el HAWB se prueba en
                  TrackingMore (trackingmore/03_consultar_awb.py).

USO
    python backend/scripts/spikes/shipsgo/03_crear_envios.py --network personal
    python backend/scripts/spikes/shipsgo/03_crear_envios.py --network personal --confirmar --solo mar-moin-1

SALIDA
    Registro de envios en shipsgo/output/envios_creados.json (lo lee la Fase 4).
    Evidencia en shipsgo/output/03_creacion_<red>_<fecha>.json, con los numeros
    enmascarados. Las respuestas crudas van a shipsgo/output/raw/ (ignorado por git).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _comercial import (  # noqa: E402
    TIMEOUT,
    Referencia,
    cargar_referencias,
    cuerpo_json,
    filtrar_por_alias,
    guardar_crudo,
    imprimir_diag,
    llamar,
    mawb_con_guion,
    parser_base,
    problema_de_formato,
)
from _common import SEP, SPIKES_DIR, header, load_env, mask, require, save_evidence, utc_now  # noqa: E402

BASE = "https://api.shipsgo.com/v2"
REGISTRO = SPIKES_DIR / "shipsgo" / "output" / "envios_creados.json"
ETIQUETA = "trackin-spike"


def peticion(ref: Referencia) -> tuple[str, dict[str, Any]] | str:
    """
    (path, cuerpo) de la creacion, o el motivo por el que no se envia.

    El campo reference identifica el envio en el panel de ShipsGo; se arma
    con el alias, nunca con el numero, para que no aparezca en claro.
    """
    referencia_interna = ("TRACKIN-" + ref.alias.upper())[:128]
    if len(referencia_interna) < 5:
        referencia_interna = referencia_interna.ljust(5, "0")
    base: dict[str, Any] = {"reference": referencia_interna, "tags": [ETIQUETA]}

    if ref.tipo == "HAWB":
        return "ShipsGo exige MAWB; el HAWB se prueba en TrackingMore"
    if ref.tipo == "MAWB":
        return "/air/shipments", {**base, "awb_number": mawb_con_guion(ref.numero)}

    cuerpo = dict(base)
    if ref.tipo == "CONTENEDOR":
        cuerpo["container_number"] = ref.numero
    else:  # BOOKING o BL: ShipsGo solo tiene booking_number
        cuerpo["booking_number"] = ref.numero
    # El SCAC es opcional; si el dato no tiene forma de SCAC, que lo detecte ShipsGo.
    if ref.transportista and re.fullmatch(r"(SG_)?[A-Z0-9]{4}", ref.transportista):
        cuerpo["carrier"] = ref.transportista
    return "/ocean/shipments", cuerpo


def cargar_registro() -> dict[str, Any]:
    if REGISTRO.is_file():
        return json.loads(REGISTRO.read_text(encoding="utf-8"))
    return {"envios": {}}


def guardar_registro(registro: dict[str, Any]) -> None:
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    REGISTRO.write_text(json.dumps(registro, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    parser = parser_base("Spike TASK-28 ShipsGo Fase 3: registrar referencias reales")
    parser.add_argument("--confirmar", action="store_true", help="Crear los envios (gasta creditos).")
    parser.add_argument("--solo", action="append", metavar="ALIAS", help="Solo este alias (repetible).")
    parser.add_argument("--forzar", action="store_true", help="Enviar aunque falle el digito de control.")
    args = parser.parse_args()

    env = load_env()
    token = require(env, "SHIPSGO_API_TOKEN")
    referencias = filtrar_por_alias(cargar_referencias(), args.solo)

    timestamp = header(
        "TrackIn - Spike TASK-28 - ShipsGo - Fase 3: registrar referencias",
        args.network,
        {"token": mask(token), "modo": "CREAR" if args.confirmar else "solo plan (sin --confirmar)"},
    )

    registro = cargar_registro()
    plan: list[tuple[Referencia, str, dict[str, Any]]] = []
    omitidas: list[dict[str, Any]] = []

    print("  {:<16} {:<10} {:<11} {:<16} {}".format("Alias", "Via", "Tipo", "Numero", "Decision"))
    for ref in referencias:
        motivo = None
        if ref.alias in registro["envios"]:
            motivo = "ya registrado (id " + str(registro["envios"][ref.alias]["shipment_id"]) + ")"
        problema = problema_de_formato(ref)
        if motivo is None and problema and not args.forzar:
            motivo = "NO se envia: " + problema
        resultado = peticion(ref) if motivo is None else motivo
        if isinstance(resultado, str):
            omitidas.append({**ref.resumen(), "motivo": resultado})
            decision = resultado
        else:
            plan.append((ref, *resultado))
            decision = "crear en " + resultado[0] + (" (BL enviado como booking)" if ref.tipo == "BL" else "")
        print("  {:<16} {:<10} {:<11} {:<16} {}".format(ref.alias, ref.via, ref.tipo, ref.enmascarada, decision))

    print()
    print("  Costo maximo: " + str(len(plan)) + " credito(s). La cuenta gratuita trae 3.")
    if not args.confirmar:
        print("  Modo plan: no se llamo a la API. Repetir con --confirmar para crear.")
        print(SEP)
        return 0
    if not plan:
        print("  Nada que crear.")
        print(SEP)
        return 0

    resultados: list[dict[str, Any]] = []
    import httpx

    with httpx.Client(
        headers={"X-Shipsgo-User-Token": token, "Accept": "application/json"},
        timeout=TIMEOUT,
    ) as client:
        for ref, path, cuerpo_peticion in plan:
            response, diag = llamar(client, "POST", BASE + path, json=cuerpo_peticion)
            diag.update(ref.resumen())
            cuerpo = cuerpo_json(response) if response is not None else None
            if isinstance(cuerpo, dict):
                diag["mensaje"] = cuerpo.get("message")
                envio = cuerpo.get("shipment") or {}
                if envio.get("id") is not None:
                    registro["envios"][ref.alias] = {
                        **ref.resumen(),
                        "shipment_id": envio["id"],
                        "endpoint": path,
                        "registrado_utc": utc_now(),
                        "respuesta": cuerpo.get("message"),
                    }
                    guardar_registro(registro)
                guardar_crudo("shipsgo", "03_" + ref.alias + ".json", {"status": diag.get("status_code"), "cuerpo": cuerpo})
            elif response is not None:
                diag["mensaje"] = response.text[:300]

            imprimir_diag(diag, "CREAR - " + ref.alias + " (" + ref.tipo + " " + ref.enmascarada + ")")
            print("  Mensaje     : " + str(diag.get("mensaje")))
            resultados.append(diag)

            if diag.get("status_code") == 402:
                print("  [!] Sin creditos: se corta la corrida.")
                break

    print(SEP)
    print("  LECTURA")
    print(SEP)
    for r in resultados:
        costo = (r.get("saldo") or {}).get("X-Shipsgo-Credits-Cost", "?")
        restante = (r.get("saldo") or {}).get("X-Shipsgo-Credits-Remaining", "?")
        print("  {:<16} HTTP {:<5} {:<20} costo {} / restan {}".format(
            r["alias"], str(r.get("status_code")), str(r.get("mensaje"))[:20], costo, restante
        ))
    print()
    print("  Siguiente paso: shipsgo/04_observar.py, hoy y varias veces al dia durante la")
    print("  semana. Un envio recien creado puede tardar horas en traer movimientos.")
    print(SEP)

    evidencia = {
        "spike": "TASK-28",
        "proveedor": "shipsgo",
        "phase": "3-crear-envios",
        "timestamp_utc": timestamp,
        "finished_utc": utc_now(),
        "network_profile": args.network,
        "creaciones": resultados,
        "omitidas": omitidas,
    }
    sello = timestamp.replace(":", "").replace("-", "")[:15]
    save_evidence("shipsgo", "03_creacion_" + args.network + "_" + sello + ".json", evidencia)
    return 0 if all(r.get("status_code") in (200, 409) for r in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
