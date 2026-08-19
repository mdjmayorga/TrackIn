"""
Spike TG-10 - Fase 6: captura larga para decidir si hay cobertura en CR.

POR QUE ESTA FASE EXISTE
    Las fases 2 y 4 observaron la costa caribe de Costa Rica un total de ~11
    minutos y no vieron un solo buque. Eso NO alcanza para concluir que no hay
    cobertura: Moin mueve pocos buques al dia y once minutos es una ventana
    demasiado corta.

    El argumento a favor de "no hay receptores" es que un buque Clase A
    ATRACADO O FONDEADO sigue transmitiendo cada ~3 minutos, y en Moin opera
    la terminal de contenedores de APM, donde es raro que no haya ninguno.
    Pero eso supone que habia un buque en muelle, cosa que no se verifico.

    Esta fase observa 45 minutos: suficiente para que cualquier buque estatico
    en la zona emita ~15 veces. Si tras 45 minutos no aparece NADA mientras el
    control sigue recibiendo, la conclusion pasa de plausible a solida.

DIFERENCIAS CON LA FASE 4
    - El bounding box de interes EXCLUYE Panama (lon <= -82.6), para que el
      trafico de Bocas del Toro no contamine el resultado como paso antes.
    - Cubre tambien la costa caribe de Nicaragua: si tampoco hay nada ahi, se
      confirma un vacio regional de receptores, no un hueco puntual.
    - 45 minutos en vez de 8.

USO
    python backend/scripts/spikes/aisstream/06_coverage_longrun.py --network personal

    Evidencia en backend/scripts/spikes/aisstream/output/06_longrun_<red>.json
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import (  # noqa: E402
    SEP,
    SUB,
    header,
    load_env,
    mask,
    network_arg,
    require,
    save_evidence,
    utc_now,
)

WS_URL = "wss://stream.aisstream.io/v0/stream"

# Costa caribe de Costa Rica y Nicaragua. Excluye Panama a proposito:
# la frontera caribe cae en Sixaola, ~82.56 W.
ZONE_TARGET = {
    "name": "Caribe de Costa Rica y Nicaragua (sin Panama)",
    "bbox": [[9.5, -84.5], [15.0, -82.6]],
}
ZONE_CONTROL = {
    "name": "Cartagena / Santa Marta (control)",
    "bbox": [[9.0, -78.0], [12.5, -73.0]],
}

MOIN_POINT = {"lat": 10.00, "lon": -83.08}
CAPTURE_SECONDS = 2700  # 45 min
CONNECT_TIMEOUT_S = 15
REPORT_EVERY_S = 300


def in_bbox(lat: float, lon: float, bbox: list) -> bool:
    (lat1, lon1), (lat2, lon2) = bbox
    return min(lat1, lat2) <= lat <= max(lat1, lat2) and min(lon1, lon2) <= lon <= max(lon1, lon2)


async def capture(api_key: str) -> dict:
    from websockets.asyncio.client import connect

    stats: dict = {
        "ok": False, "messages": 0, "bytes": 0,
        "target_messages": 0, "control_messages": 0, "other_messages": 0,
        "target_ships": set(), "control_ships": set(),
        "target_types": Counter(), "target_detail": [],
        "min_km_to_moin": float("inf"),
        "server_errors": [], "reconnects": 0,
    }

    subscription = {
        "APIKey": api_key,
        "BoundingBoxes": [ZONE_TARGET["bbox"], ZONE_CONTROL["bbox"]],
    }

    deadline = time.perf_counter() + CAPTURE_SECONDS
    last_report = time.perf_counter()
    started = time.perf_counter()

    # Reconexion automatica: 45 minutos es tiempo suficiente para que la
    # conexion se caiga al menos una vez.
    while time.perf_counter() < deadline:
        websocket = None
        try:
            websocket = await asyncio.wait_for(
                connect(WS_URL, open_timeout=CONNECT_TIMEOUT_S,
                        close_timeout=2, ping_interval=20, ping_timeout=20),
                timeout=CONNECT_TIMEOUT_S + 5,
            )
        except Exception as exc:  # noqa: BLE001
            stats.setdefault("connect_errors", []).append(type(exc).__name__)
            await asyncio.sleep(5)
            continue

        try:
            await websocket.send(json.dumps(subscription))
            while time.perf_counter() < deadline:
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    break
                try:
                    frame = await asyncio.wait_for(websocket.recv(), timeout=min(remaining, 90))
                except asyncio.TimeoutError:
                    if time.perf_counter() >= deadline:
                        break
                    continue  # silencio momentaneo, no es fallo
                except Exception:  # noqa: BLE001
                    stats["reconnects"] += 1
                    break  # conexion caida -> reconectar

                text = frame if isinstance(frame, str) else frame.decode("utf-8", "replace")
                stats["bytes"] += len(text)
                try:
                    parsed = json.loads(text)
                except (ValueError, TypeError):
                    continue
                if isinstance(parsed, dict) and parsed.get("error"):
                    stats["server_errors"].append(str(parsed["error"])[:200])
                    continue

                stats["messages"] += 1
                meta = parsed.get("MetaData") or {}
                lat, lon = meta.get("latitude"), meta.get("longitude")
                mmsi = meta.get("MMSI")
                if lat is None or lon is None:
                    stats["other_messages"] += 1
                    continue

                if in_bbox(lat, lon, ZONE_TARGET["bbox"]):
                    stats["target_messages"] += 1
                    stats["target_types"][parsed.get("MessageType") or "?"] += 1
                    if mmsi:
                        stats["target_ships"].add(mmsi)
                    km = (((lat - MOIN_POINT["lat"]) ** 2
                           + (lon - MOIN_POINT["lon"]) ** 2) ** 0.5) * 111.0
                    stats["min_km_to_moin"] = min(stats["min_km_to_moin"], km)
                    if len(stats["target_detail"]) < 25:
                        stats["target_detail"].append({
                            "mmsi": mmsi,
                            "name": (meta.get("ShipName") or "").strip() or None,
                            "lat": lat, "lon": lon, "km_to_moin": round(km),
                            "type": parsed.get("MessageType"),
                        })
                elif in_bbox(lat, lon, ZONE_CONTROL["bbox"]):
                    stats["control_messages"] += 1
                    if mmsi:
                        stats["control_ships"].add(mmsi)
                else:
                    stats["other_messages"] += 1

                now = time.perf_counter()
                if now - last_report >= REPORT_EVERY_S:
                    print("    {:>4.0f} min   CR+NI: {:>3} msg / {:>2} buques   "
                          "control: {:>4} msg / {:>3} buques".format(
                              (now - started) / 60, stats["target_messages"],
                              len(stats["target_ships"]), stats["control_messages"],
                              len(stats["control_ships"])))
                    last_report = now
        finally:
            try:
                websocket.transport.abort()
            except (AttributeError, OSError):
                pass

    stats["ok"] = True
    stats["elapsed_s"] = round(time.perf_counter() - started, 1)
    return stats


def main() -> int:
    args = network_arg("Spike TG-10 Fase 6: captura larga de cobertura en CR")
    env = load_env()
    api_key = require(env, "AISSTREAM_API_KEY")

    timestamp = header(
        "TrackIn - Spike TG-10 - Fase 6: captura larga (45 min)",
        args.network,
        {"api_key": mask(api_key), "captura": str(CAPTURE_SECONDS // 60) + " min"},
    )
    print("  Zona interes: {}".format(ZONE_TARGET["name"]))
    print("                {}".format(ZONE_TARGET["bbox"]))
    print("  Zona control: {}".format(ZONE_CONTROL["name"]))

    print(SUB)
    print("  CAPTURA")
    print(SUB)
    stats = asyncio.run(capture(api_key))

    target_ships = len(stats["target_ships"])
    control_ships = len(stats["control_ships"])
    elapsed = stats["elapsed_s"]
    nearest = stats["min_km_to_moin"]
    nearest_txt = "{:.0f} km".format(nearest) if nearest != float("inf") else "ninguno"

    print()
    print(SUB)
    print("  RESULTADO tras {:.0f} minutos".format(elapsed / 60))
    print(SUB)
    print("  {:<40} {:>6} msg   {:>4} buques".format(
        "CR + Nicaragua (sin Panama)", stats["target_messages"], target_ships))
    print("  {:<40} {:>6} msg   {:>4} buques".format(
        "Control - Cartagena", stats["control_messages"], control_ships))
    print("  {:<40} {:>6} msg".format("Fuera de ambas / sin posicion",
                                      stats["other_messages"]))
    print("  Buque mas cercano a Puerto Moin: {}".format(nearest_txt))
    print("  Reconexiones durante la captura : {}".format(stats["reconnects"]))

    if stats["target_detail"]:
        print()
        print("  Detecciones en la zona de interes:")
        for entry in stats["target_detail"]:
            print("    MMSI {}  {:<22} {:.3f}, {:.3f}  a {} km de Moin  {}".format(
                entry["mmsi"], (entry["name"] or "?")[:22], entry["lat"], entry["lon"],
                entry["km_to_moin"], entry["type"]))

    # --- Lectura -----------------------------------------------------------
    print(SEP)
    print("  LECTURA")
    print(SEP)
    expected_static_emissions = int(elapsed / 180)

    if control_ships == 0:
        verdict = "test_invalido"
        print("  El control no recibio datos: el test no es concluyente. Repetir.")
    elif target_ships == 0:
        verdict = "sin_cobertura_confirmado"
        print("  En {:.0f} minutos, el control detecto {} buques y la costa caribe de".format(
            elapsed / 60, control_ships))
        print("  Costa Rica y Nicaragua CERO.")
        print()
        print("  Un buque Clase A atracado o fondeado transmite cada ~3 min: en esta")
        print("  ventana habria emitido ~{} veces. No aparecio ni uno en {} km de".format(
            expected_static_emissions, "cientos de"))
        print("  costa, incluyendo dos puertos activos (Moin y Limon).")
        print()
        print("  => Conclusion SOLIDA: no hay receptores AIS cubriendo la costa caribe")
        print("     de Costa Rica en el plan gratuito de AISStream.")
    else:
        verdict = "cobertura_detectada"
        print("  Se detectaron {} buques en la zona en {:.0f} minutos.".format(
            target_ships, elapsed / 60))
        print("  El mas cercano a Moin quedo a {}.".format(nearest_txt))
        print("  La conclusion de las fases 2 y 4 era PREMATURA: hay cobertura, aunque")
        print("  escasa. Revisar el detalle de arriba para ver de que tipo de")
        print("  embarcaciones se trata y a que distancia del puerto.")
    print(SEP)

    evidence = {
        "spike": "TG-10",
        "phase": "6-coverage-longrun",
        "timestamp_utc": timestamp,
        "finished_utc": utc_now(),
        "network_profile": args.network,
        "purpose": (
            "Decidir si la ausencia de datos en CR se debe a falta de receptores "
            "o a bajo trafico. Las fases 2 y 4 solo observaron ~11 minutos."
        ),
        "zone_target": ZONE_TARGET,
        "zone_control": ZONE_CONTROL,
        "capture_seconds": CAPTURE_SECONDS,
        "elapsed_s": elapsed,
        "target_messages": stats["target_messages"],
        "target_ships": target_ships,
        "target_types": dict(stats["target_types"]),
        "target_detail": stats["target_detail"],
        "control_messages": stats["control_messages"],
        "control_ships": control_ships,
        "other_messages": stats["other_messages"],
        "nearest_km_to_moin": round(nearest) if nearest != float("inf") else None,
        "reconnects": stats["reconnects"],
        "expected_static_emissions_in_window": expected_static_emissions,
        "server_errors": stats["server_errors"],
        "verdict": verdict,
        "passed": verdict != "test_invalido",
    }
    save_evidence("aisstream", "06_longrun_" + args.network + ".json", evidence)
    return 0


if __name__ == "__main__":
    sys.exit(main())
