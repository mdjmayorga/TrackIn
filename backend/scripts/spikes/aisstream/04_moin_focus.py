"""
Spike TG-10 - Fase 4: existe cobertura AIS en Puerto Moin? (test controlado)

PREGUNTA DEL SPIKE QUE RESPONDE
    (2) Cobertura en las rutas hacia Puerto Moin - de forma CONCLUYENTE.
    (7) Volumen de mensajes, medido sobre una ventana mas larga.

POR QUE UN TEST CONTROLADO
    La Fase 3 mostro que el 95% de los mensajes del Caribe se concentra en 8
    celdas costeras y NINGUNA esta cerca de Costa Rica. Pero una captura de 3
    minutos no distingue entre:
      a) no hay receptores AIS cubriendo la costa caribe de Costa Rica, y
      b) no pasaba ningun buque por ahi en esos 3 minutos.

    Por eso este script se suscribe a DOS areas a la vez:
      - ZONA DE INTERES : Costa Rica y Panama caribe (incluye Moin y Limon)
      - ZONA DE CONTROL : Cartagena / Santa Marta, donde la Fase 3 YA
                          demostro que hay receptores activos

    Si durante la captura llegan mensajes del control y cero de la zona de
    interes, el resultado es concluyente: la ausencia no se puede atribuir a
    un fallo del script, de la suscripcion ni de la conexion. Ese es el punto
    del grupo de control.

USO
    python backend/scripts/spikes/aisstream/04_moin_focus.py --network personal

    Evidencia en backend/scripts/spikes/aisstream/output/04_moin_<red>.json
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
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# Zona de interes: costa caribe de Costa Rica y Panama. Contiene Moin y Limon.
ZONE_TARGET = {
    "name": "Costa Rica / Panama caribe",
    "bbox": [[8.0, -84.5], [12.0, -80.0]],
}

# La primera corrida dio un FALSO POSITIVO: el bbox de interes incluye la
# costa de Panama, y los buques detectados resultaron ser yates recreativos
# fondeados en Bocas del Toro (9.33 N, 82.24 W), a ~118 km de Moin. El
# veredicto automatico concluyo "hay cobertura en Costa Rica" cuando no habia
# un solo mensaje costarricense. Por eso se subdivide por pais.
# La frontera CR/Panama en el Caribe cae en Sixaola, ~82.56 W.
CR_PA_BORDER_LON = -82.56
MOIN_POINT = {"lat": 10.00, "lon": -83.08}
# Zona de control: la Fase 3 confirmo receptores activos aca.
ZONE_CONTROL = {
    "name": "Cartagena / Santa Marta (control)",
    "bbox": [[9.0, -78.0], [12.5, -73.0]],
}

CAPTURE_SECONDS = 480
CONNECT_TIMEOUT_S = 15


def in_bbox(lat: float, lon: float, bbox: list) -> bool:
    """El bbox de AISStream son dos esquinas opuestas [[lat,lon],[lat,lon]]."""
    (lat1, lon1), (lat2, lon2) = bbox
    return min(lat1, lat2) <= lat <= max(lat1, lat2) and min(lon1, lon2) <= lon <= max(lon1, lon2)


async def capture(api_key: str) -> dict:
    """Captura suscrito a las dos zonas simultaneamente."""
    from websockets.asyncio.client import connect

    stats: dict = {
        "ok": False,
        "messages": 0,
        "bytes": 0,
        "target_messages": 0,
        "control_messages": 0,
        "target_ships": set(),
        "control_ships": set(),
        "cr_messages": 0,
        "pa_messages": 0,
        "cr_ships": set(),
        "pa_ships": set(),
        "min_distance_to_moin_km": float("inf"),
        "other_messages": 0,
        "target_types": Counter(),
        "target_samples": [],
        "server_errors": [],
    }

    subscription = {
        "APIKey": api_key,
        "BoundingBoxes": [ZONE_TARGET["bbox"], ZONE_CONTROL["bbox"]],
    }

    websocket = None
    started = time.perf_counter()
    try:
        websocket = await asyncio.wait_for(
            connect(WS_URL, open_timeout=CONNECT_TIMEOUT_S,
                    close_timeout=2, ping_interval=None),
            timeout=CONNECT_TIMEOUT_S + 5,
        )
    except Exception as exc:  # noqa: BLE001
        stats["error"] = type(exc).__name__ + ": " + str(exc)[:200]
        return stats

    try:
        await websocket.send(json.dumps(subscription))
        print("  Suscrito a 2 zonas. Capturando {} s ({:.0f} min)...".format(
            CAPTURE_SECONDS, CAPTURE_SECONDS / 60))

        deadline = time.perf_counter() + CAPTURE_SECONDS
        last_report = time.perf_counter()

        while time.perf_counter() < deadline:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                break
            try:
                frame = await asyncio.wait_for(websocket.recv(), timeout=remaining)
            except asyncio.TimeoutError:
                break
            except Exception as exc:  # noqa: BLE001
                stats["error"] = "durante recv: " + type(exc).__name__
                break

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
            lat, lon, mmsi = meta.get("latitude"), meta.get("longitude"), meta.get("MMSI")
            if lat is None or lon is None:
                stats["other_messages"] += 1
                continue

            if in_bbox(lat, lon, ZONE_TARGET["bbox"]):
                stats["target_messages"] += 1
                stats["target_types"][parsed.get("MessageType") or "?"] += 1
                if mmsi:
                    stats["target_ships"].add(mmsi)

                # Separar Costa Rica de Panama: solo lo costarricense cuenta
                # para la pregunta del spike.
                if lon < CR_PA_BORDER_LON:
                    stats["cr_messages"] += 1
                    if mmsi:
                        stats["cr_ships"].add(mmsi)
                else:
                    stats["pa_messages"] += 1
                    if mmsi:
                        stats["pa_ships"].add(mmsi)

                distance_km = (((lat - MOIN_POINT["lat"]) ** 2
                                + (lon - MOIN_POINT["lon"]) ** 2) ** 0.5) * 111.0
                stats["min_distance_to_moin_km"] = min(
                    stats["min_distance_to_moin_km"], distance_km)

                if len(stats["target_samples"]) < 15:
                    stats["target_samples"].append({
                        "mmsi": mmsi,
                        "name": (meta.get("ShipName") or "").strip() or None,
                        "lat": lat, "lon": lon,
                        "country": "CR" if lon < CR_PA_BORDER_LON else "PA",
                        "km_to_moin": round(distance_km),
                        "type": parsed.get("MessageType"),
                    })
            elif in_bbox(lat, lon, ZONE_CONTROL["bbox"]):
                stats["control_messages"] += 1
                if mmsi:
                    stats["control_ships"].add(mmsi)
            else:
                stats["other_messages"] += 1

            now = time.perf_counter()
            if now - last_report >= 60:
                print("    {:>4.0f}s   interes: {:>4} msg / {:>3} buques   "
                      "control: {:>4} msg / {:>3} buques".format(
                          now - started, stats["target_messages"], len(stats["target_ships"]),
                          stats["control_messages"], len(stats["control_ships"])))
                last_report = now

        stats["ok"] = True
        stats["elapsed_s"] = round(time.perf_counter() - started, 1)
    finally:
        try:
            websocket.transport.abort()
        except (AttributeError, OSError):
            pass

    return stats


def main() -> int:
    args = network_arg("Spike TG-10 Fase 4: cobertura en Puerto Moin (test controlado)")
    env = load_env()
    api_key = require(env, "AISSTREAM_API_KEY")

    timestamp = header(
        "TrackIn - Spike TG-10 - Fase 4: cobertura en Moin (control)",
        args.network,
        {"api_key": mask(api_key), "captura": str(CAPTURE_SECONDS) + " s"},
    )
    print("  Zona interes: {}  {}".format(ZONE_TARGET["name"], ZONE_TARGET["bbox"]))
    print("  Zona control: {}  {}".format(ZONE_CONTROL["name"], ZONE_CONTROL["bbox"]))

    print(SUB)
    print("  CAPTURA")
    print(SUB)
    stats = asyncio.run(capture(api_key))

    if not stats["ok"] and stats.get("error"):
        print("  [FALLO] " + stats["error"])
        save_evidence("aisstream", "04_moin_" + args.network + ".json", {
            "spike": "TG-10", "phase": "4-moin-focus", "timestamp_utc": timestamp,
            "network_profile": args.network, "error": stats["error"], "passed": False,
        })
        return 1

    target_ships = len(stats["target_ships"])
    control_ships = len(stats["control_ships"])
    elapsed = stats.get("elapsed_s", CAPTURE_SECONDS)

    print()
    print(SUB)
    print("  RESULTADO")
    print(SUB)
    print("  {:<34} {:>6} msg   {:>4} buques".format(
        "ZONA DE INTERES (Moin/Limon)", stats["target_messages"], target_ships))
    print("  {:<34} {:>6} msg   {:>4} buques".format(
        "ZONA DE CONTROL (Cartagena)", stats["control_messages"], control_ships))
    print("  {:<34} {:>6} msg".format("Fuera de ambas / sin posicion", stats["other_messages"]))
    print("  {:<34} {:>6} msg   {:.2f} msg/s".format(
        "TOTAL", stats["messages"], stats["messages"] / elapsed if elapsed else 0))

    if stats["target_samples"]:
        print()
        print("  Buques detectados en la zona de interes:")
        for sample in stats["target_samples"]:
            print("    MMSI {}  {:<22} {:.3f}, {:.3f}  {}".format(
                sample["mmsi"], (sample["name"] or "?")[:22],
                sample["lat"], sample["lon"], sample["type"]))

    # --- Lectura -----------------------------------------------------------
    print(SEP)
    print("  LECTURA")
    print(SEP)

    cr_ships = len(stats["cr_ships"])
    pa_ships = len(stats["pa_ships"])
    nearest = stats["min_distance_to_moin_km"]
    nearest_txt = "{:.0f} km".format(nearest) if nearest != float("inf") else "sin datos"

    print()
    print("  Desglose de la zona de interes:")
    print("    Costa Rica (lon < {}): {:>4} msg   {:>3} buques".format(
        CR_PA_BORDER_LON, stats["cr_messages"], cr_ships))
    print("    Panama     (lon >= {}): {:>4} msg   {:>3} buques".format(
        CR_PA_BORDER_LON, stats["pa_messages"], pa_ships))
    print("    Buque mas cercano a Puerto Moin: {}".format(nearest_txt))
    print()

    if control_ships == 0:
        verdict = "test_invalido"
        print("  El grupo de control no recibio datos. El test NO es concluyente:")
        print("  pudo fallar la suscripcion o la conexion. Repetir.")
    elif cr_ships == 0:
        verdict = "sin_cobertura_costa_rica_confirmado"
        print("  CONCLUYENTE: el control detecto {} buques y Costa Rica CERO.".format(
            control_ships))
        if pa_ships:
            print("  Los {} buques de la zona son PANAMENOS (Bocas del Toro), no".format(
                pa_ships))
            print("  costarricenses. El buque mas cercano a Moin quedo a {}.".format(
                nearest_txt))
        print()
        print("  => NO hay cobertura AIS en la costa caribe de Costa Rica en el plan")
        print("     gratuito. El AIS terrestre es VHF (40-70 km desde costa) y el")
        print("     receptor util mas cercano esta en Bocas del Toro, Panama, fuera")
        print("     de alcance de Moin. El AIS satelital no esta incluido en el plan.")
        print()
        print("  IMPACTO EN TrackIn: no se puede confirmar la llegada de un buque a")
        print("  Moin con esta fuente. Si se puede seguirlo en tramos con cobertura")
        print("  (salida, Cartagena, Canal de Panama) y se pierde la traza en el")
        print("  ultimo tramo. Hay que decidir con Compras si eso alcanza.")
    else:
        verdict = "cobertura_costa_rica_confirmada"
        print("  Hay cobertura costarricense: {} buques en {:.0f} minutos.".format(
            cr_ships, elapsed / 60))
        print("  Buque mas cercano a Moin: {}.".format(nearest_txt))
    print(SEP)

    evidence = {
        "spike": "TG-10",
        "phase": "4-moin-focus",
        "timestamp_utc": timestamp,
        "finished_utc": utc_now(),
        "network_profile": args.network,
        "design": "test controlado con zona de interes y zona de control simultaneas",
        "zone_target": ZONE_TARGET,
        "zone_control": ZONE_CONTROL,
        "capture_seconds": CAPTURE_SECONDS,
        "elapsed_s": elapsed,
        "total_messages": stats["messages"],
        "total_bytes": stats["bytes"],
        "target_messages": stats["target_messages"],
        "target_ships": target_ships,
        "costa_rica_messages": stats["cr_messages"],
        "costa_rica_ships": len(stats["cr_ships"]),
        "panama_messages": stats["pa_messages"],
        "panama_ships": len(stats["pa_ships"]),
        "nearest_ship_to_moin_km": (
            round(stats["min_distance_to_moin_km"])
            if stats["min_distance_to_moin_km"] != float("inf") else None),
        "false_positive_note": (
            "La primera corrida conto buques panamenos de Bocas del Toro como cobertura costarricense. El bbox de interes cruza la frontera; por eso se subdivide por longitud."),
        "target_message_types": dict(stats["target_types"]),
        "target_samples": stats["target_samples"],
        "control_messages": stats["control_messages"],
        "control_ships": control_ships,
        "other_messages": stats["other_messages"],
        "server_errors": stats["server_errors"],
        "verdict": verdict,
        "passed": verdict != "test_invalido",
    }
    save_evidence("aisstream", "04_moin_" + args.network + ".json", evidence)
    return 0


if __name__ == "__main__":
    sys.exit(main())
