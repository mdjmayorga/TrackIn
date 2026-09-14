"""
Spike TASK-28 - TrackingMore - Fase 3: consultar guias aereas reales.

PREGUNTAS DEL SPIKE QUE RESPONDE
    (1) TrackingMore devuelve los hitos de un MAWB real de la ruta a SJO?
        Es la comparacion directa contra ShipsGo Air, con el mismo numero.
    (2) El HAWB del agente de carga resuelve, o hay que exigir el MAWB?
        Es el tercer criterio de aceptacion de TASK-28.

GASTA CREDITOS: 50 POR CONSULTA
    - Sin --confirmar, SOLO muestra el plan.
    - El MAWB se valida antes (11 digitos y digito de control del serial).
    - Un HAWB sin forma de guia aerea NO se envia: que /v4/awb ni siquiera
      lo pueda recibir ya responde la pregunta (2), gratis.
    - Una guia ya consultada no se repite salvo --repetir: no sabemos si
      volver a consultarla cobra otra vez.

USO
    python backend/scripts/spikes/trackingmore/03_consultar_awb.py --network personal
    python backend/scripts/spikes/trackingmore/03_consultar_awb.py --network personal --confirmar --solo aereo-sjo-1

SALIDA
    Evidencia en trackingmore/output/03_awb_<red>_<fecha>.json, enmascarada.
    Respuestas crudas en trackingmore/output/raw/ (ignorado por git): el
    esquema de la respuesta no esta documentado en detalle y hay que leerlo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _comercial import (  # noqa: E402
    TIMEOUT,
    cargar_referencias,
    cuerpo_json,
    filtrar_por_alias,
    guardar_crudo,
    imprimir_diag,
    llamar,
    mawb_con_guion,
    parser_base,
    problema_mawb,
)
from _common import SEP, SPIKES_DIR, header, load_env, mask, require, save_evidence, utc_now  # noqa: E402

BASE = "https://api.trackingmore.com/v4"
REGISTRO = SPIKES_DIR / "trackingmore" / "output" / "awb_consultadas.json"
COSTO_AWB = 50


def claves_de(valor: Any, profundidad: int = 0) -> Any:
    """Estructura de la respuesta sin sus valores: sirve para diseñar el adaptador."""
    if profundidad > 4:
        return "..."
    if isinstance(valor, dict):
        return {k: claves_de(v, profundidad + 1) for k, v in valor.items()}
    if isinstance(valor, list):
        return [claves_de(valor[0], profundidad + 1)] if valor else []
    return type(valor).__name__


def main() -> int:
    parser = parser_base("Spike TASK-28 TrackingMore Fase 3: consultar AWB reales")
    parser.add_argument("--confirmar", action="store_true", help="Consultar (50 creditos cada una).")
    parser.add_argument("--solo", action="append", metavar="ALIAS", help="Solo este alias (repetible).")
    parser.add_argument("--repetir", action="store_true", help="Consultar aunque ya se haya consultado.")
    args = parser.parse_args()

    env = load_env()
    clave = require(env, "TRACKINGMORE_API_KEY")
    referencias = [
        r for r in filtrar_por_alias(cargar_referencias(), args.solo) if r.via == "AEREO"
    ]
    registro: dict[str, Any] = (
        json.loads(REGISTRO.read_text(encoding="utf-8")) if REGISTRO.is_file() else {}
    )

    timestamp = header(
        "TrackIn - Spike TASK-28 - TrackingMore - Fase 3: consultar AWB",
        args.network,
        {"api_key": mask(clave), "modo": "CONSULTAR" if args.confirmar else "solo plan (sin --confirmar)"},
    )

    plan = []
    omitidas: list[dict[str, Any]] = []
    for ref in referencias:
        problema = problema_mawb(ref.numero)
        if ref.alias in registro and not args.repetir:
            motivo = "ya consultada el " + registro[ref.alias]["consultado_utc"]
        elif ref.tipo == "MAWB" and problema:
            motivo = "NO se envia: " + problema
        elif ref.tipo == "HAWB" and problema:
            # Hallazgo gratuito: la guia hija no tiene forma de guia aerea.
            motivo = "HAWB sin forma de guia aerea -> /v4/awb no la admite. Confirma que hace falta el MAWB"
        else:
            motivo = None
        if motivo:
            omitidas.append({**ref.resumen(), "motivo": motivo})
        else:
            plan.append(ref)
        print("  {:<16} {:<6} {:<16} {}".format(
            ref.alias, ref.tipo, ref.enmascarada, motivo or "consultar en /v4/awb"
        ))

    print()
    print("  Costo maximo: " + str(len(plan) * COSTO_AWB) + " creditos (" + str(COSTO_AWB) + " por guia).")
    print("  Revisar en el panel de TrackingMore cuantos trae la prueba antes de confirmar.")
    if not args.confirmar or not plan:
        print("  " + ("Modo plan: no se llamo a la API." if not args.confirmar else "Nada que consultar."))
        print(SEP)
        save_evidence("trackingmore", "03_awb_plan_" + args.network + ".json", {
            "spike": "TASK-28", "proveedor": "trackingmore", "phase": "3-consultar-awb-plan",
            "timestamp_utc": timestamp, "network_profile": args.network,
            "plan": [r.resumen() for r in plan], "omitidas": omitidas,
        })
        return 0

    resultados: list[dict[str, Any]] = []
    import httpx

    with httpx.Client(
        headers={
            "Tracking-Api-Key": clave,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        timeout=TIMEOUT,
    ) as client:
        for ref in plan:
            response, diag = llamar(
                client, "POST", BASE + "/awb", json={"awb_number": mawb_con_guion(ref.numero)}
            )
            diag.update(ref.resumen())
            cuerpo = cuerpo_json(response) if response is not None else None
            if isinstance(cuerpo, dict):
                diag["meta"] = cuerpo.get("meta")
                diag["estructura_data"] = claves_de(cuerpo.get("data"))
                guardar_crudo("trackingmore", "03_" + ref.alias + ".json", cuerpo)
                registro[ref.alias] = {**ref.resumen(), "consultado_utc": utc_now(), "meta": cuerpo.get("meta")}
                REGISTRO.parent.mkdir(parents=True, exist_ok=True)
                REGISTRO.write_text(json.dumps(registro, indent=2, ensure_ascii=False), encoding="utf-8")
            elif response is not None:
                diag["cuerpo_texto"] = response.text[:300]
            imprimir_diag(diag, "AWB - " + ref.alias + " (" + ref.tipo + " " + ref.enmascarada + ")")
            print("  Meta        : " + str(diag.get("meta") or diag.get("cuerpo_texto")))
            if diag.get("estructura_data"):
                print("  Estructura  : " + json.dumps(diag["estructura_data"])[:400])
            resultados.append(diag)

    print(SEP)
    print("  Leer las respuestas completas en trackingmore/output/raw/ y compararlas")
    print("  con shipsgo/04_observar.py para el mismo alias.")
    print(SEP)

    sello = timestamp.replace(":", "").replace("-", "")[:15]
    save_evidence("trackingmore", "03_awb_" + args.network + "_" + sello + ".json", {
        "spike": "TASK-28",
        "proveedor": "trackingmore",
        "phase": "3-consultar-awb",
        "timestamp_utc": timestamp,
        "finished_utc": utc_now(),
        "network_profile": args.network,
        "consultas": resultados,
        "omitidas": omitidas,
    })
    return 0 if all(r.get("ok") for r in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
