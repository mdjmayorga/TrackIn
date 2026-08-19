"""
Spike TG-10 - Fase 2: cobertura AIS en el Caribe y rutas hacia Puerto Moin.

PREGUNTA DEL SPIKE QUE RESPONDE
    (2) "Medir cobertura en Caribe y rutas hacia puerto Moin (Costa Rica)."

POR QUE ADEMAS GUARDA TODO EN CRUDO
    Las preguntas 3, 4, 5 y 7 del spike (tipos de mensaje, relacion nave-carga,
    frecuencia por embarcacion y volumen para dimensionar el backend) se
    responden sobre LOS MISMOS datos. Abrir tres conexiones largas separadas
    seria desperdiciar tiempo de captura. Este script captura una sola vez y
    escribe un JSONL que 03_message_analysis.py analiza despues sin volver a
    conectarse.

ZONAS
    - Caribe occidental completo, que cubre las rutas de aproximacion a Moin
      desde el Canal de Panama, el Golfo de Mexico y el Atlantico.
    - Radio cercano a Puerto Moin / Limon, el destino real de las
      importaciones maritimas de Gutis.

CIERRE DEL SOCKET
    Se aborta el transporte en vez de negociar el cierre. Con volumen alto el
    close() negociado no completa nunca (hallazgo de la Fase 0).

USO
    python backend/scripts/spikes/aisstream/02_coverage_caribbean.py --network personal

SALIDA
    - output/02_coverage_<red>.json    resumen y metricas
    - output/02_caribbean_raw_<red>.jsonl   todos los mensajes crudos
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
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

# AISStream espera [[lat, lon], [lat, lon]] por cada bounding box.
# Caribe occidental: del norte de Sudamerica al Golfo, y de Centroamerica
# hasta las Antillas Menores. Cubre toda aproximacion posible a Moin.
CARIBBEAN_BBOX = [[[7.0, -90.0], [25.0, -59.0]]]

# Puerto Moin / Limon: destino maritimo de las importaciones de Gutis.
MOIN = {"lat": 10.00, "lon": -83.08, "radius_deg": 0.45}   # ~50 km
# Aproximacion amplia: corredor de espera y fondeo frente a la costa caribe.
LIMON_APPROACH = {"lat": 10.0, "lon": -83.0, "radius_deg": 1.5}  # ~165 km

CAPTURE_SECONDS = 180
MAX_MESSAGES = 40000  # tope de seguridad para no llenar disco
CONNECT_TIMEOUT_S = 15


def distance_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia euclidea en grados. Suficiente a esta latitud para clasificar."""
    return ((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2) ** 0.5


def classify_zone(lat: float | None, lon: float | None) -> str:
    """Ubica un mensaje en la zona de interes mas especifica que lo contenga."""
    if lat is None or lon is None:
        return "sin_posicion"
    if distance_deg(lat, lon, MOIN["lat"], MOIN["lon"]) <= MOIN["radius_deg"]:
        return "moin"
    if distance_deg(lat, lon, LIMON_APPROACH["lat"], LIMON_APPROACH["lon"]) <= LIMON_APPROACH["radius_deg"]:
        return "aproximacion_limon"
    return "caribe"


async def capture(api_key: str, raw_path: Path) -> dict:
    """
    Captura mensajes durante CAPTURE_SECONDS y los escribe en JSONL.

    Devuelve las metricas agregadas. Los errores de conexion se reportan como
    resultado, no como excepcion: para el spike importa saber que fallo.
    """
    from websockets.asyncio.client import connect

    stats: dict = {
        "ok": False,
        "messages": 0,
        "bytes": 0,
        "message_types": Counter(),
        "zones": Counter(),
        "mmsi_seen": set(),
        "mmsi_by_zone": {},
        "parse_errors": 0,
        "server_errors": [],
    }

    subscription = {"APIKey": api_key, "BoundingBoxes": CARIBBEAN_BBOX}
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
        print("  Suscripcion enviada. Capturando {} s...".format(CAPTURE_SECONDS))

        deadline = time.perf_counter() + CAPTURE_SECONDS
        last_report = time.perf_counter()

        with raw_path.open("w", encoding="utf-8") as raw_file:
            while time.perf_counter() < deadline and stats["messages"] < MAX_MESSAGES:
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    break
                try:
                    frame = await asyncio.wait_for(websocket.recv(), timeout=remaining)
                except asyncio.TimeoutError:
                    break
                except Exception as exc:  # noqa: BLE001
                    stats["error"] = "durante recv: " + type(exc).__name__ + ": " + str(exc)[:150]
                    break

                text = frame if isinstance(frame, str) else frame.decode("utf-8", "replace")
                stats["bytes"] += len(text)

                try:
                    parsed = json.loads(text)
                except (ValueError, TypeError):
                    stats["parse_errors"] += 1
                    continue

                if isinstance(parsed, dict) and parsed.get("error"):
                    stats["server_errors"].append(str(parsed["error"])[:200])
                    continue

                stats["messages"] += 1
                raw_file.write(text + "\n")

                msg_type = parsed.get("MessageType") or "(sin_tipo)"
                stats["message_types"][msg_type] += 1

                meta = parsed.get("MetaData") or {}
                lat = meta.get("latitude")
                lon = meta.get("longitude")
                mmsi = meta.get("MMSI")

                zone = classify_zone(lat, lon)
                stats["zones"][zone] += 1
                if mmsi:
                    stats["mmsi_seen"].add(mmsi)
                    stats["mmsi_by_zone"].setdefault(zone, set()).add(mmsi)

                now = time.perf_counter()
                if now - last_report >= 30:
                    elapsed = int(now - started)
                    print("    {:>3}s  {:>6} mensajes  {:>5} buques  moin={} aprox={}".format(
                        elapsed, stats["messages"], len(stats["mmsi_seen"]),
                        stats["zones"].get("moin", 0),
                        stats["zones"].get("aproximacion_limon", 0)))
                    last_report = now

        stats["ok"] = stats["messages"] > 0
        stats["elapsed_s"] = round(time.perf_counter() - started, 1)

    finally:
        # Abortar, no negociar: hallazgo de la Fase 0.
        try:
            websocket.transport.abort()
        except (AttributeError, OSError):
            pass

    return stats


def main() -> int:
    args = network_arg("Spike TG-10 Fase 2: cobertura Caribe y Puerto Moin")
    env = load_env()
    api_key = require(env, "AISSTREAM_API_KEY")

    timestamp = header(
        "TrackIn - Spike TG-10 - Fase 2: cobertura Caribe / Puerto Moin",
        args.network,
        {
            "api_key": mask(api_key),
            "bbox": str(CARIBBEAN_BBOX[0]),
            "captura": str(CAPTURE_SECONDS) + " s",
        },
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = OUTPUT_DIR / ("02_caribbean_raw_" + args.network + ".jsonl")

    print(SUB)
    print("  CAPTURA")
    print(SUB)
    stats = asyncio.run(capture(api_key, raw_path))

    if not stats["ok"]:
        print()
        print("  [FALLO] No se capturo ningun mensaje.")
        if stats.get("error"):
            print("  Error: " + stats["error"])
        for err in stats["server_errors"][:3]:
            print("  El servidor respondio: " + err)
        print(SEP)
        save_evidence("aisstream", "02_coverage_" + args.network + ".json", {
            "spike": "TG-10", "phase": "2-coverage-caribbean",
            "timestamp_utc": timestamp, "network_profile": args.network,
            "error": stats.get("error"), "server_errors": stats["server_errors"],
            "passed": False,
        })
        return 1

    # --- Resumen -----------------------------------------------------------
    elapsed = stats["elapsed_s"]
    total = stats["messages"]
    unique_mmsi = len(stats["mmsi_seen"])

    print()
    print(SUB)
    print("  VOLUMEN")
    print(SUB)
    print("  Mensajes capturados  : {}".format(total))
    print("  Duracion             : {} s".format(elapsed))
    print("  Tasa                 : {:.1f} msg/s".format(total / elapsed if elapsed else 0))
    print("  Volumen              : {:.1f} KB  ({:.2f} KB/s)".format(
        stats["bytes"] / 1024, stats["bytes"] / 1024 / elapsed if elapsed else 0))
    print("  Buques unicos (MMSI) : {}".format(unique_mmsi))
    if unique_mmsi:
        print("  Mensajes por buque   : {:.1f} en {} s".format(total / unique_mmsi, elapsed))

    print()
    print(SUB)
    print("  COBERTURA POR ZONA")
    print(SUB)
    zone_labels = {
        "moin": "Puerto Moin (radio 50 km)",
        "aproximacion_limon": "Aproximacion Limon (165 km)",
        "caribe": "Caribe occidental",
        "sin_posicion": "Mensajes sin posicion",
    }
    for zone in ("moin", "aproximacion_limon", "caribe", "sin_posicion"):
        count = stats["zones"].get(zone, 0)
        ships = len(stats["mmsi_by_zone"].get(zone, set()))
        pct = 100.0 * count / total if total else 0.0
        print("  {:<32} {:>6} msg ({:>5.1f}%)  {:>4} buques".format(
            zone_labels[zone], count, pct, ships))

    print()
    print(SUB)
    print("  TIPOS DE MENSAJE")
    print(SUB)
    for msg_type, count in stats["message_types"].most_common(12):
        pct = 100.0 * count / total if total else 0.0
        print("  {:<34} {:>6} ({:>5.1f}%)".format(msg_type, count, pct))

    # --- Lectura -----------------------------------------------------------
    moin_ships = len(stats["mmsi_by_zone"].get("moin", set()))
    approach_ships = len(stats["mmsi_by_zone"].get("aproximacion_limon", set()))

    print(SEP)
    print("  LECTURA")
    print(SEP)
    if moin_ships == 0 and approach_ships == 0:
        verdict = "sin_cobertura_moin"
        print("  Ningun buque detectado en Moin ni en su aproximacion durante la")
        print("  captura. El Caribe si tiene cobertura, pero la costa caribe de")
        print("  Costa Rica no aparece. Repetir en otra franja antes de concluir:")
        print("  Moin recibe pocos buques por dia, no es trafico continuo.")
    elif moin_ships == 0:
        verdict = "cobertura_aproximacion"
        print("  Hay {} buques en la aproximacion a Limon pero ninguno dentro del".format(
            approach_ships))
        print("  radio de Moin. Coherente con un puerto de bajo trafico: los buques")
        print("  se detectan en ruta, no necesariamente atracados.")
    else:
        verdict = "cobertura_util"
        print("  {} buques dentro del radio de Puerto Moin y {} en aproximacion.".format(
            moin_ships, approach_ships))
        print("  La cobertura AIS sirve para seguir un embarque hasta el destino.")

    print()
    print("  Dataset crudo guardado en:")
    print("    " + str(raw_path))
    print("  Lo analiza 03_message_analysis.py sin volver a conectarse.")
    print(SEP)

    evidence = {
        "spike": "TG-10",
        "phase": "2-coverage-caribbean",
        "timestamp_utc": timestamp,
        "finished_utc": utc_now(),
        "network_profile": args.network,
        "bbox": CARIBBEAN_BBOX,
        "zones": {"moin": MOIN, "aproximacion_limon": LIMON_APPROACH},
        "capture_seconds": CAPTURE_SECONDS,
        "elapsed_s": elapsed,
        "messages": total,
        "bytes": stats["bytes"],
        "messages_per_second": round(total / elapsed, 2) if elapsed else None,
        "unique_mmsi": unique_mmsi,
        "message_types": dict(stats["message_types"]),
        "zone_message_counts": dict(stats["zones"]),
        "zone_ship_counts": {z: len(s) for z, s in stats["mmsi_by_zone"].items()},
        "parse_errors": stats["parse_errors"],
        "server_errors": stats["server_errors"],
        "raw_dataset": str(raw_path.name),
        "verdict": verdict,
        "passed": True,
    }
    save_evidence("aisstream", "02_coverage_" + args.network + ".json", evidence)
    return 0


if __name__ == "__main__":
    sys.exit(main())
