"""
Spike TG-10 - Fase 5: resiliencia, reconexion y limites de conexion.

PREGUNTA DEL SPIKE QUE RESPONDE
    (6) "Disenar estrategia de reconexion y resiliencia para WebSocket."

PRUEBAS
    A. API key invalida        -> el servidor avisa o calla? Si calla, el
                                  modulo no puede distinguir credencial mala
                                  de "no hay trafico", y se queda colgado.
    B. Suscripcion malformada  -> hay error explicito o silencio?
    C. Dos conexiones a la vez -> el plan admite varias con la misma key?
                                  Si no, TODOS los bounding boxes tienen que
                                  ir multiplexados en una sola conexion. Es
                                  una restriccion de arquitectura, no un
                                  detalle de implementacion.
    D. Ciclo de reconexion x3  -> cuanto tarda en volver a recibir datos.
    E. Watchdog                -> gap maximo real entre mensajes, para fijar
                                  un umbral de socket zombi que no dispare
                                  falsos positivos.

ZONA USADA
    Cartagena / Santa Marta: la Fase 3 confirmo receptores activos ahi, asi
    que la ausencia de datos durante una prueba significa fallo de conexion,
    no falta de trafico.

USO
    python backend/scripts/spikes/aisstream/05_resilience.py --network personal

    Evidencia en backend/scripts/spikes/aisstream/output/05_resilience_<red>.json
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
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

# Zona con receptores confirmados en la Fase 3.
ACTIVE_BBOX = [[[9.0, -78.0], [12.5, -73.0]]]

CONNECT_TIMEOUT_S = 15
PROBE_WAIT_S = 25       # espera de datos en pruebas de error
RECONNECT_CYCLES = 3
WATCHDOG_SECONDS = 120  # ventana para medir gaps entre mensajes


async def open_ws():
    """Abre la conexion con los parametros que usara el modulo real."""
    from websockets.asyncio.client import connect

    return await asyncio.wait_for(
        connect(WS_URL, open_timeout=CONNECT_TIMEOUT_S,
                close_timeout=2, ping_interval=None),
        timeout=CONNECT_TIMEOUT_S + 5,
    )


def abort(websocket) -> None:
    """Cierre forzado. El negociado no completa con volumen alto (Fase 0)."""
    try:
        websocket.transport.abort()
    except (AttributeError, OSError):
        pass


async def probe_subscription(subscription: dict, label: str, wait_s: int) -> dict:
    """
    Envia una suscripcion y observa que hace el servidor.

    Distingue tres desenlaces: error explicito, cierre de la conexion, o
    silencio. Para el modulo real son casos muy distintos.
    """
    result: dict = {"label": label, "messages": 0, "server_error": None,
                    "closed_by_server": False, "waited_s": wait_s}
    websocket = None
    try:
        websocket = await open_ws()
    except Exception as exc:  # noqa: BLE001
        result["connect_error"] = type(exc).__name__ + ": " + str(exc)[:150]
        return result

    try:
        await websocket.send(json.dumps(subscription))
        deadline = time.perf_counter() + wait_s
        while time.perf_counter() < deadline:
            remaining = deadline - time.perf_counter()
            try:
                frame = await asyncio.wait_for(websocket.recv(), timeout=remaining)
            except asyncio.TimeoutError:
                break
            except Exception as exc:  # noqa: BLE001
                result["closed_by_server"] = True
                result["close_reason"] = type(exc).__name__ + ": " + str(exc)[:150]
                break

            text = frame if isinstance(frame, str) else frame.decode("utf-8", "replace")
            try:
                parsed = json.loads(text)
            except (ValueError, TypeError):
                result["messages"] += 1
                continue
            if isinstance(parsed, dict) and parsed.get("error"):
                result["server_error"] = str(parsed["error"])[:200]
                break
            result["messages"] += 1
            if result["messages"] >= 5:
                break
    finally:
        if websocket is not None:
            abort(websocket)

    if result["server_error"]:
        result["outcome"] = "error_explicito"
    elif result["closed_by_server"]:
        result["outcome"] = "cierre_del_servidor"
    elif result["messages"] > 0:
        result["outcome"] = "datos_recibidos"
    else:
        result["outcome"] = "silencio"
    return result


async def probe_concurrent(api_key: str) -> dict:
    """Dos conexiones simultaneas con la misma API key."""
    result: dict = {}
    subscription = {"APIKey": api_key, "BoundingBoxes": ACTIVE_BBOX}
    first = second = None
    try:
        first = await open_ws()
        await first.send(json.dumps(subscription))
        second = await open_ws()
        await second.send(json.dumps(subscription))
        result["both_opened"] = True

        async def count(websocket, seconds: int) -> int:
            total = 0
            deadline = time.perf_counter() + seconds
            while time.perf_counter() < deadline:
                remaining = deadline - time.perf_counter()
                try:
                    await asyncio.wait_for(websocket.recv(), timeout=remaining)
                except (asyncio.TimeoutError, Exception):
                    break
                total += 1
                if total >= 10:
                    break
            return total

        counts = await asyncio.gather(count(first, 25), count(second, 25),
                                      return_exceptions=True)
        result["messages_conn_1"] = counts[0] if isinstance(counts[0], int) else 0
        result["messages_conn_2"] = counts[1] if isinstance(counts[1], int) else 0
        result["both_received"] = result["messages_conn_1"] > 0 and result["messages_conn_2"] > 0
    except Exception as exc:  # noqa: BLE001
        result["error"] = type(exc).__name__ + ": " + str(exc)[:150]
        result["both_opened"] = False
    finally:
        for websocket in (first, second):
            if websocket is not None:
                abort(websocket)
    return result


async def probe_reconnect(api_key: str, cycles: int) -> dict:
    """Cierra a la fuerza y reconecta, midiendo el tiempo hasta el primer dato."""
    subscription = {"APIKey": api_key, "BoundingBoxes": ACTIVE_BBOX}
    attempts: list[dict] = []
    for cycle in range(1, cycles + 1):
        entry: dict = {"cycle": cycle}
        started = time.perf_counter()
        websocket = None
        try:
            websocket = await open_ws()
            entry["connect_ms"] = round((time.perf_counter() - started) * 1000, 1)
            await websocket.send(json.dumps(subscription))
            wait_started = time.perf_counter()
            try:
                await asyncio.wait_for(websocket.recv(), timeout=30)
                entry["first_message_ms"] = round((time.perf_counter() - wait_started) * 1000, 1)
                entry["ok"] = True
            except asyncio.TimeoutError:
                entry["ok"] = False
                entry["error"] = "sin datos en 30 s"
        except Exception as exc:  # noqa: BLE001
            entry["ok"] = False
            entry["error"] = type(exc).__name__ + ": " + str(exc)[:120]
        finally:
            if websocket is not None:
                abort(websocket)
        print("    ciclo {}: conexion {} ms, primer dato {} ms  {}".format(
            cycle, entry.get("connect_ms", "-"), entry.get("first_message_ms", "-"),
            "OK" if entry.get("ok") else "FALLO"))
        attempts.append(entry)
        await asyncio.sleep(2)
    return {"attempts": attempts}


async def probe_watchdog(api_key: str, seconds: int) -> dict:
    """Mide los intervalos entre mensajes para dimensionar el watchdog."""
    subscription = {"APIKey": api_key, "BoundingBoxes": ACTIVE_BBOX}
    gaps: list[float] = []
    total = 0
    websocket = None
    try:
        websocket = await open_ws()
        await websocket.send(json.dumps(subscription))
        deadline = time.perf_counter() + seconds
        last = time.perf_counter()
        while time.perf_counter() < deadline:
            remaining = deadline - time.perf_counter()
            try:
                await asyncio.wait_for(websocket.recv(), timeout=remaining)
            except asyncio.TimeoutError:
                break
            except Exception:  # noqa: BLE001
                break
            now = time.perf_counter()
            gaps.append(now - last)
            last = now
            total += 1
    except Exception as exc:  # noqa: BLE001
        return {"error": type(exc).__name__ + ": " + str(exc)[:150], "messages": total}
    finally:
        if websocket is not None:
            abort(websocket)

    return {
        "messages": total,
        "window_s": seconds,
        "median_gap_s": round(statistics.median(gaps), 2) if gaps else None,
        "p95_gap_s": round(sorted(gaps)[int(len(gaps) * 0.95)], 2) if len(gaps) >= 20 else None,
        "max_gap_s": round(max(gaps), 2) if gaps else None,
    }


def main() -> int:
    args = network_arg("Spike TG-10 Fase 5: resiliencia y reconexion")
    env = load_env()
    api_key = require(env, "AISSTREAM_API_KEY")

    timestamp = header(
        "TrackIn - Spike TG-10 - Fase 5: resiliencia y reconexion",
        args.network,
        {"api_key": mask(api_key), "zona": "Cartagena (receptores confirmados)"},
    )

    results: dict = {}

    print(SUB)
    print("  A. API KEY INVALIDA")
    print(SUB)
    results["a_invalid_key"] = asyncio.run(probe_subscription(
        {"APIKey": "0" * 40, "BoundingBoxes": ACTIVE_BBOX},
        "api_key_invalida", PROBE_WAIT_S))
    print("  Desenlace: {}".format(results["a_invalid_key"]["outcome"]))
    if results["a_invalid_key"].get("server_error"):
        print("  El servidor dijo: {}".format(results["a_invalid_key"]["server_error"]))
    if results["a_invalid_key"].get("close_reason"):
        print("  Cierre: {}".format(results["a_invalid_key"]["close_reason"]))

    print(SUB)
    print("  B. SUSCRIPCION MALFORMADA")
    print(SUB)
    results["b_malformed"] = asyncio.run(probe_subscription(
        {"APIKey": api_key, "BoundingBoxes": "esto-no-es-un-bbox"},
        "suscripcion_malformada", PROBE_WAIT_S))
    print("  Desenlace: {}".format(results["b_malformed"]["outcome"]))
    if results["b_malformed"].get("server_error"):
        print("  El servidor dijo: {}".format(results["b_malformed"]["server_error"]))
    if results["b_malformed"].get("close_reason"):
        print("  Cierre: {}".format(results["b_malformed"]["close_reason"]))

    print(SUB)
    print("  C. DOS CONEXIONES SIMULTANEAS CON LA MISMA KEY")
    print(SUB)
    results["c_concurrent"] = asyncio.run(probe_concurrent(api_key))
    concurrent = results["c_concurrent"]
    if concurrent.get("both_opened"):
        print("  Conexion 1: {} mensajes   Conexion 2: {} mensajes".format(
            concurrent.get("messages_conn_1"), concurrent.get("messages_conn_2")))
        print("  Ambas recibieron datos: {}".format(
            "SI" if concurrent.get("both_received") else "NO"))
    else:
        print("  No se pudieron abrir las dos: {}".format(concurrent.get("error")))

    print(SUB)
    print("  D. CICLOS DE RECONEXION")
    print(SUB)
    results["d_reconnect"] = asyncio.run(probe_reconnect(api_key, RECONNECT_CYCLES))

    print(SUB)
    print("  E. WATCHDOG - intervalos entre mensajes ({} s)".format(WATCHDOG_SECONDS))
    print(SUB)
    results["e_watchdog"] = asyncio.run(probe_watchdog(api_key, WATCHDOG_SECONDS))
    watchdog = results["e_watchdog"]
    if watchdog.get("messages"):
        print("  {} mensajes   mediana {} s   p95 {} s   maximo {} s".format(
            watchdog["messages"], watchdog.get("median_gap_s"),
            watchdog.get("p95_gap_s"), watchdog.get("max_gap_s")))
    else:
        print("  Sin mensajes: {}".format(watchdog.get("error", "silencio")))

    # --- Recomendaciones ---------------------------------------------------
    print(SEP)
    print("  ESTRATEGIA DE RECONEXION PARA SPRINT 3")
    print(SEP)

    key_outcome = results["a_invalid_key"]["outcome"]
    if key_outcome == "silencio":
        print("  1. Una API key invalida NO produce error: el servidor calla. El modulo")
        print("     no puede distinguirla de 'no hay trafico'. Hace falta un timeout de")
        print("     arranque: si no llega nada en los primeros N segundos tras conectar,")
        print("     tratarlo como fallo de credencial y alertar, no reintentar en bucle.")
    else:
        print("  1. Una API key invalida produce: {}. Se puede detectar y alertar".format(
            key_outcome))
        print("     sin ambiguedad, en vez de reintentar indefinidamente.")

    reconnects = results["d_reconnect"]["attempts"]
    successful = [a for a in reconnects if a.get("ok")]
    if successful:
        avg_recovery = statistics.mean(
            a["connect_ms"] + a["first_message_ms"] for a in successful)
        print("  2. La reconexion es fiable: {}/{} ciclos con datos, recuperacion media".format(
            len(successful), len(reconnects)))
        print("     de {:.0f} ms. Backoff exponencial arrancando en 1 s, techo 60 s.".format(
            avg_recovery))
    else:
        print("  2. Ningun ciclo de reconexion recupero datos: revisar antes de disenar.")

    max_gap = watchdog.get("max_gap_s")
    if max_gap:
        suggested = max(30, round(max_gap * 3))
        print("  3. Watchdog de socket zombi: el gap maximo real fue {} s.".format(max_gap))
        print("     Umbral sugerido {} s sin mensajes = conexion muerta -> reconectar.".format(
            suggested))
        print("     Un umbral menor daria falsos positivos en zonas de poco trafico.")
    else:
        print("  3. No se pudo medir el gap entre mensajes: no fijar watchdog a ciegas.")

    if concurrent.get("both_received"):
        print("  4. El plan admite conexiones simultaneas, pero conviene igual una sola")
        print("     conexion multiplexando bounding boxes: menos estado que reconciliar.")
    elif concurrent.get("both_opened"):
        print("  4. Se abrieron dos conexiones pero solo una recibio datos: el plan")
        print("     limita el streaming. OBLIGATORIO multiplexar todos los bounding")
        print("     boxes en UNA sola conexion.")
    else:
        print("  4. No se pudo abrir una segunda conexion: asumir limite de 1 y")
        print("     multiplexar todos los bounding boxes en una sola.")

    print("  5. Cierre: abortar el transporte, nunca esperar close() negociado (Fase 0).")
    print(SEP)

    evidence = {
        "spike": "TG-10",
        "phase": "5-resilience",
        "timestamp_utc": timestamp,
        "finished_utc": utc_now(),
        "network_profile": args.network,
        "active_bbox": ACTIVE_BBOX,
        "results": results,
        "passed": True,
    }
    save_evidence("aisstream", "05_resilience_" + args.network + ".json", evidence)
    return 0


if __name__ == "__main__":
    sys.exit(main())
