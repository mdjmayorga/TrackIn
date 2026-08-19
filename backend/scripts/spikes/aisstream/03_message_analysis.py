"""
Spike TG-10 - Fase 3: analisis de mensajes AIS capturados.

PREGUNTAS DEL SPIKE QUE RESPONDE
    (3) Frecuencia de mensajes por embarcacion.
    (4) Como se relaciona una nave con su carga (MMSI, IMO, destination, ETA).
    (5) Que tipos de mensaje AIS son relevantes para TrackIn.
    (7) Volumen de mensajes para dimensionar el backend.

    Y ademas resuelve la anomalia detectada en la Fase 2: 133 buques con solo
    161 mensajes en 3 minutos (1.2 msg por buque) cuando un buque transmite
    cada 2-10 s. Dos explicaciones opuestas:
      a) AISStream limita el plan gratuito y entrega una muestra del flujo.
      b) El Caribe tiene poca cobertura de receptores (AIS terrestre es VHF,
         alcance 40-70 km desde costa).
    Se distinguen por la DISTRIBUCION GEOGRAFICA: si es limitacion del plan,
    los buques estan repartidos por todo el bbox; si es cobertura, aparecen
    apinados cerca de ciertas costas.

NO SE CONECTA A LA RED
    Trabaja sobre el JSONL que dejo 02_coverage_caribbean.py. Analizar es
    barato; capturar es lo caro. Se puede re-ejecutar sin consumir nada.

USO
    python backend/scripts/spikes/aisstream/03_message_analysis.py --network personal

    Evidencia en backend/scripts/spikes/aisstream/output/03_analysis_<red>.json
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import (  # noqa: E402
    SEP,
    SUB,
    header,
    network_arg,
    save_evidence,
    utc_now,
)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# Tipos que llevan la informacion que TrackIn necesita para ligar nave y carga.
STATIC_TYPES = {"ShipStaticData", "StaticDataReport"}
POSITION_TYPES = {"PositionReport", "StandardClassBPositionReport",
                  "ExtendedClassBPositionReport"}

# Celdas de 2 grados para el mapa de calor de cobertura.
GRID_DEG = 2.0


def parse_time(value: str | None) -> datetime | None:
    """
    Parsea el time_utc de AISStream, que viene como
    '2026-08-18 20:11:41.335667286 +0000 UTC' - no es ISO-8601.
    """
    if not value or not isinstance(value, str):
        return None
    cleaned = value.replace(" UTC", "").strip()
    parts = cleaned.split(" ")
    if len(parts) < 2:
        return None
    stamp = parts[0] + " " + parts[1]
    if "." in stamp:
        head, _, frac = stamp.partition(".")
        stamp = head + "." + frac[:6]  # microsegundos, no nanosegundos
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(stamp, fmt)
        except ValueError:
            continue
    return None


def first_present(payload: dict, *names):
    """Devuelve el primer campo no vacio de los nombres dados."""
    for name in names:
        value = payload.get(name)
        if value not in (None, "", 0):
            return value
    return None


def main() -> int:
    args = network_arg("Spike TG-10 Fase 3: analisis de mensajes AIS")
    raw_path = OUTPUT_DIR / ("02_caribbean_raw_" + args.network + ".jsonl")

    timestamp = header(
        "TrackIn - Spike TG-10 - Fase 3: analisis de mensajes AIS",
        args.network,
        {"dataset": raw_path.name},
    )

    if not raw_path.is_file():
        print("  [FATAL] No existe el dataset: " + str(raw_path))
        print("          Correr antes 02_coverage_caribbean.py --network " + args.network)
        return 1

    types = Counter()
    per_mmsi_times: dict[int, list[datetime]] = defaultdict(list)
    per_mmsi_types: dict[int, set] = defaultdict(set)
    ship_info: dict[int, dict] = {}
    grid = Counter()
    grid_ships: dict[tuple, set] = defaultdict(set)
    total = 0
    total_bytes = 0
    static_fields = Counter()

    with raw_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            total_bytes += len(line)
            try:
                parsed = json.loads(line)
            except ValueError:
                continue
            total += 1

            msg_type = parsed.get("MessageType") or "(sin_tipo)"
            types[msg_type] += 1

            meta = parsed.get("MetaData") or {}
            mmsi = meta.get("MMSI")
            lat, lon = meta.get("latitude"), meta.get("longitude")
            stamp = parse_time(meta.get("time_utc"))

            if mmsi:
                per_mmsi_types[mmsi].add(msg_type)
                if stamp:
                    per_mmsi_times[mmsi].append(stamp)
                entry = ship_info.setdefault(mmsi, {"mmsi": mmsi})
                if meta.get("ShipName") and not entry.get("name"):
                    entry["name"] = str(meta["ShipName"]).strip()

            if lat is not None and lon is not None:
                cell = (int(lat // GRID_DEG) * GRID_DEG, int(lon // GRID_DEG) * GRID_DEG)
                grid[cell] += 1
                if mmsi:
                    grid_ships[cell].add(mmsi)

            # Campos de identificacion de carga: solo viajan en los estaticos.
            if msg_type in STATIC_TYPES:
                body = parsed.get("Message", {}).get(msg_type) or {}
                for key in body:
                    static_fields[key] += 1
                if mmsi:
                    entry = ship_info.setdefault(mmsi, {"mmsi": mmsi})
                    imo = first_present(body, "ImoNumber", "IMONumber", "Imo")
                    if imo:
                        entry["imo"] = imo
                    dest = first_present(body, "Destination")
                    if dest:
                        entry["destination"] = str(dest).strip()
                    call = first_present(body, "CallSign")
                    if call:
                        entry["callsign"] = str(call).strip()
                    ship_type = first_present(body, "Type", "ShipType")
                    if ship_type:
                        entry["ship_type"] = ship_type
                    eta = body.get("Eta") or body.get("ETA")
                    if isinstance(eta, dict):
                        entry["eta"] = eta
                    name = first_present(body, "Name", "ShipName")
                    if name and not entry.get("name"):
                        entry["name"] = str(name).strip()

    if total == 0:
        print("  [FATAL] El dataset esta vacio.")
        return 1

    unique_ships = len(per_mmsi_types)

    # --- Tipos de mensaje --------------------------------------------------
    print(SUB)
    print("  TIPOS DE MENSAJE Y SU UTILIDAD PARA TrackIn")
    print(SUB)
    usefulness = {
        "PositionReport": "posicion de buque comercial (Clase A) - NUCLEO",
        "StandardClassBPositionReport": "posicion de embarcacion menor (Clase B)",
        "ExtendedClassBPositionReport": "posicion Clase B extendida",
        "ShipStaticData": "IMO, destino, ETA, nombre - LIGA NAVE Y CARGA",
        "StaticDataReport": "datos estaticos de Clase B (sin IMO ni destino)",
        "BaseStationReport": "estacion costera - ignorable",
        "AidsToNavigationReport": "boya o baliza - ignorable",
        "UnknownMessage": "no decodificado por AISStream",
    }
    for msg_type, count in types.most_common():
        print("  {:<32} {:>6} ({:>5.1f}%)  {}".format(
            msg_type, count, 100.0 * count / total,
            usefulness.get(msg_type, "")))

    # --- Identificacion nave-carga ----------------------------------------
    with_imo = [s for s in ship_info.values() if s.get("imo")]
    with_dest = [s for s in ship_info.values() if s.get("destination")]
    with_name = [s for s in ship_info.values() if s.get("name")]
    with_eta = [s for s in ship_info.values() if s.get("eta")]

    print()
    print(SUB)
    print("  IDENTIFICACION NAVE <-> CARGA  (sobre {} buques)".format(unique_ships))
    print(SUB)
    for label, subset in (("con MMSI", ship_info), ("con nombre", with_name),
                          ("con IMO", with_imo), ("con destino", with_dest),
                          ("con ETA", with_eta)):
        count = len(subset)
        print("  {:<16} {:>4} / {:<4} ({:>5.1f}%)".format(
            label, count, unique_ships, 100.0 * count / unique_ships if unique_ships else 0))

    if with_dest:
        print()
        print("  Ejemplos de destino declarado:")
        for ship in with_dest[:8]:
            eta = ship.get("eta")
            eta_txt = ""
            if isinstance(eta, dict):
                eta_txt = "  ETA {}-{} {}:{:02d}".format(
                    eta.get("Month"), eta.get("Day"), eta.get("Hour"), eta.get("Minute") or 0)
            print("    MMSI {}  {:<22} -> {:<20}{}".format(
                ship["mmsi"], (ship.get("name") or "?")[:22],
                ship["destination"][:20], eta_txt))

    # --- Frecuencia por buque ---------------------------------------------
    intervals: list[float] = []
    repeat_counts = []
    for mmsi, stamps in per_mmsi_times.items():
        repeat_counts.append(len(stamps))
        if len(stamps) >= 2:
            ordered = sorted(stamps)
            intervals.extend(
                (b - a).total_seconds() for a, b in zip(ordered, ordered[1:])
                if (b - a).total_seconds() > 0
            )

    print()
    print(SUB)
    print("  FRECUENCIA POR EMBARCACION")
    print(SUB)
    print("  Buques con 1 solo mensaje : {} / {}".format(
        sum(1 for c in repeat_counts if c == 1), unique_ships))
    print("  Buques con 2 o mas        : {}".format(sum(1 for c in repeat_counts if c > 1)))
    print("  Mensajes por buque        : media {:.1f}, max {}".format(
        statistics.mean(repeat_counts) if repeat_counts else 0,
        max(repeat_counts) if repeat_counts else 0))
    if intervals:
        print("  Intervalo entre mensajes  : mediana {:.0f}s  min {:.0f}s  max {:.0f}s".format(
            statistics.median(intervals), min(intervals), max(intervals)))
    else:
        print("  Intervalo entre mensajes  : no calculable (casi ningun buque repitio)")

    # --- Diagnostico de la anomalia ---------------------------------------
    print()
    print(SUB)
    print("  DISTRIBUCION GEOGRAFICA (celdas de {:.0f} grados)".format(GRID_DEG))
    print(SUB)
    occupied = len(grid)
    top_cells = grid.most_common(8)
    concentration = (sum(c for _, c in top_cells) / total * 100) if total else 0
    print("  Celdas con datos : {}".format(occupied))
    print("  Top 8 celdas concentran el {:.0f}% de los mensajes".format(concentration))
    print()
    print("  {:<18} {:>8} {:>8}".format("celda (lat,lon)", "msgs", "buques"))
    for (clat, clon), count in top_cells:
        print("  {:<18} {:>8} {:>8}".format(
            "{:+.0f}, {:+.0f}".format(clat, clon), count, len(grid_ships[(clat, clon)])))

    print()
    print(SEP)
    print("  LECTURA")
    print(SEP)

    single_ratio = (sum(1 for c in repeat_counts if c == 1) / unique_ships * 100
                    if unique_ships else 0)

    if single_ratio > 70 and concentration < 70:
        anomaly = "muestreo_del_plan"
        print("  El {:.0f}% de los buques aparece UNA sola vez y los mensajes estan".format(
            single_ratio))
        print("  repartidos entre {} celdas sin concentrarse en la costa.".format(occupied))
        print("  => Apunta a que el plan gratuito de AISStream ENTREGA UNA MUESTRA")
        print("     del flujo, no el stream completo. Hay que confirmarlo con el")
        print("     soporte o la documentacion del plan antes de dimensionar Sprint 3.")
    elif concentration >= 70:
        anomaly = "cobertura_costera"
        print("  Los mensajes se concentran en pocas celdas ({:.0f}% en 8 celdas).".format(
            concentration))
        print("  => Apunta a COBERTURA de receptores, no a limitacion del plan: el AIS")
        print("     terrestre es VHF y solo alcanza 40-70 km desde la costa. En mar")
        print("     abierto hace falta AIS satelital, que el plan gratuito no cubre.")
    else:
        anomaly = "indeterminado"
        print("  Los indicadores no son concluyentes: {:.0f}% de buques con un solo".format(
            single_ratio))
        print("  mensaje y {:.0f}% de concentracion. Repetir con captura mas larga.".format(
            concentration))

    print()
    print("  PARA TrackIn:")
    print("    - Los datos de carga (IMO, destino, ETA) SOLO viajan en ShipStaticData,")
    print("      que representa el {:.0f}% de los mensajes. Hay que persistirlos aparte".format(
        100.0 * types.get("ShipStaticData", 0) / total))
    print("      y no esperarlos en cada posicion.")
    print("    - El campo Destination es TEXTO LIBRE escrito por la tripulacion:")
    print("      no se puede parsear como codigo de puerto sin normalizar.")

    # --- Volumen para dimensionar -----------------------------------------
    print()
    print("  DIMENSIONAMIENTO (extrapolado de esta captura):")
    per_day_msgs = total / 180.0 * 86400
    per_day_mb = total_bytes / 180.0 * 86400 / 1024 / 1024
    print("    {:.0f} mensajes/dia  ~ {:.0f} MB/dia en bruto".format(per_day_msgs, per_day_mb))
    print("    Solo con submuestreo (1 posicion por buque cada N minutos) esto")
    print("    baja a un volumen razonable para PostgreSQL.")
    print(SEP)

    evidence = {
        "spike": "TG-10",
        "phase": "3-message-analysis",
        "timestamp_utc": timestamp,
        "finished_utc": utc_now(),
        "network_profile": args.network,
        "dataset": raw_path.name,
        "total_messages": total,
        "total_bytes": total_bytes,
        "unique_ships": unique_ships,
        "message_types": dict(types),
        "static_field_frequency": dict(static_fields.most_common(30)),
        "identification": {
            "with_name": len(with_name),
            "with_imo": len(with_imo),
            "with_destination": len(with_dest),
            "with_eta": len(with_eta),
        },
        "frequency": {
            "ships_with_single_message": sum(1 for c in repeat_counts if c == 1),
            "ships_with_multiple": sum(1 for c in repeat_counts if c > 1),
            "median_interval_s": statistics.median(intervals) if intervals else None,
            "min_interval_s": min(intervals) if intervals else None,
            "max_interval_s": max(intervals) if intervals else None,
        },
        "geography": {
            "occupied_cells": occupied,
            "top_cells_concentration_pct": round(concentration, 1),
            "top_cells": [
                {"lat": c[0], "lon": c[1], "messages": n, "ships": len(grid_ships[c])}
                for c, n in top_cells
            ],
        },
        "anomaly_diagnosis": anomaly,
        "extrapolated_daily_messages": round(per_day_msgs),
        "extrapolated_daily_mb": round(per_day_mb, 1),
        "ships_sample": list(ship_info.values())[:40],
        "passed": True,
    }
    save_evidence("aisstream", "03_analysis_" + args.network + ".json", evidence)
    return 0


if __name__ == "__main__":
    sys.exit(main())
