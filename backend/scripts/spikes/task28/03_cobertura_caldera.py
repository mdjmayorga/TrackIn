"""
Spike TASK-28 - Fase 3a: cobertura AIS en Puerto Caldera (Pacifico).

PREGUNTA DEL SPIKE QUE RESPONDE
    La pregunta 3 de "Lo que TASK-28 debe responder ahora":
    "Hay cobertura en Caldera? Esta en el Pacifico y el spike TG-10 solo
     evaluo el Caribe. Es la pregunta nueva del 04/09 y no tiene respuesta
     previa."

    No depende de ShipsGo ni de TrackingMore: se responde con la llave de
    AISStream que ya tenemos, y por eso se puede cerrar sin esperar una
    referencia real de Gutis.

POR QUE IMPORTA
    TG-10 probo que NO hay cobertura AIS gratuita en Moin, y de ahi salio que
    `US-14` (confirmacion manual del desembarco) sea el unico mecanismo que
    cierra el arribo. Caldera es el otro puerto maritimo del maestro
    (`CRCAL`, migracion 0002) y esta en la costa opuesta. Si Caldera SI tiene
    cobertura, los pedidos que entran por ahi pueden inferir el arribo por
    geocerca (`US-11` / RN-05) y no dependen de la confirmacion manual.
    Si no la tiene, queda confirmado que el arribo maritimo es manual en los
    dos puertos, y eso cierra la pregunta sin ambiguedad.

EL GRUPO DE CONTROL ES LA PARTE QUE HACE VALIDA LA PRUEBA
    "Cero buques en Caldera" no significa nada por si solo: puede ser un hueco
    de cobertura, o que la conexion no trajo datos. Por eso se suscribe una
    caja que incluye **Balboa / entrada pacifica del Canal de Panama**, una de
    las aguas mas transitadas del mundo, a 600 km de Caldera y en el mismo
    oceano.

      - Cero en Caldera Y cero en Balboa  -> la prueba NO vale, es la conexion
      - Cero en Caldera CON trafico en Balboa -> hueco real de cobertura
      - Trafico en Caldera -> hay cobertura, y cambia el plan

    Es el mismo razonamiento de la Fase 6 de TG-10, que llamo a su captura
    larga "la prueba decisiva" justamente por tener control.

COORDENADAS
    Caldera sale del maestro real (`0002_maestros_paises_destinos.py`):
    lat 9.9139, lon -84.7203, radio de geocerca 10 km.

USO
    python backend/scripts/spikes/task28/03_cobertura_caldera.py --network personal

SALIDA
    - output/03_caldera_<red>.json          resumen, metricas y veredicto
    - output/03_caldera_raw_<red>.jsonl     mensajes crudos (ignorado por git
      si se mueve a output/raw/; aca se conserva por volumen bajo)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import (
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

# AISStream espera [[lat, lon], [lat, lon]].
#
# CUIDADO CON EL ISTMO. La primera version de este script uso una sola caja
# [[5,-90],[15,-77]] "del Pacifico oriental", y metio dentro la costa CARIBE de
# Panama: seis de los siete buques capturados estaban en Bocas del Toro
# (lat 9.3, lon -82.2), que es Caribe. A estas latitudes el istmo corre en
# diagonal y una caja rectangular abarca los dos oceanos.
#
# Por eso van DOS cajas estrictamente pacificas, y ninguna pasa de lon -83.6 en
# la costa rica ni de lat 9.0 frente a Panama (Colon esta a 9.35 y es Caribe).
PACIFICO_BBOX = [
    [[5.0, -92.0], [11.5, -83.6]],   # costa pacifica de CR y Nicaragua
    [[6.5, -80.3], [9.0, -78.0]],    # Golfo de Panama / entrada pacifica del Canal
]

# El destino real, con el radio de geocerca del maestro (10 km ~ 0.09 grados).
CALDERA = {"lat": 9.9139, "lon": -84.7203, "radio_deg": 0.09}
# Golfo de Nicoya y fondeadero: donde esperaria un buque antes de atracar.
GOLFO_NICOYA = {"lat": 9.95, "lon": -84.85, "radio_deg": 0.60}
# GRUPO DE CONTROL: Balboa, entrada pacifica del Canal de Panama. Radio
# reducido a 0.45 para no rozar la latitud de Colon, que es del otro oceano.
BALBOA = {"lat": 8.70, "lon": -79.30, "radio_deg": 0.45}

# Linea base del MISMO dia: la caja del Caribe de TG-10 fase 2, que el 18/08
# rindio 161 mensajes en 180 s. Repetirla hoy separa "el Pacifico esta vacio"
# de "la cuenta dejo de entregar datos", que es la duda que TG-10 dejo abierta
# en "No es la red: es la cuenta".
CARIBE_BBOX = [[[7.0, -90.0], [25.0, -59.0]]]
BASELINE_TG10_MENSAJES = 161

SEGUNDOS_CAPTURA = 180
MAX_MENSAJES = 40000
TIMEOUT_CONEXION_S = 15


def distancia_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia euclidea en grados. Suficiente a esta latitud para clasificar."""
    return ((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2) ** 0.5


def clasificar_zona(lat: float | None, lon: float | None) -> str:
    """Ubica el mensaje en la zona mas especifica que lo contenga."""
    if lat is None or lon is None:
        return "sin_posicion"
    if distancia_deg(lat, lon, CALDERA["lat"], CALDERA["lon"]) <= CALDERA["radio_deg"]:
        return "caldera"
    if distancia_deg(lat, lon, GOLFO_NICOYA["lat"], GOLFO_NICOYA["lon"]) <= GOLFO_NICOYA["radio_deg"]:
        return "golfo_nicoya"
    if distancia_deg(lat, lon, BALBOA["lat"], BALBOA["lon"]) <= BALBOA["radio_deg"]:
        return "balboa_control"
    return "pacifico_abierto"


def clasificar_caribe(lat: float | None, lon: float | None) -> str:
    """Clasificador minimo para la linea base: solo interesa el volumen."""
    return "sin_posicion" if lat is None or lon is None else "caribe"


async def capturar(api_key: str, bbox: list, clasificar, ruta_cruda: Path, etiqueta: str) -> dict:
    """
    Captura SEGUNDOS_CAPTURA de mensajes y los escribe en JSONL.

    Los errores de conexion se devuelven como resultado, no como excepcion:
    para el spike importa saber que fallo, no que el script muera.
    """
    from websockets.asyncio.client import connect

    stats: dict = {
        "ok": False,
        "mensajes": 0,
        "bytes": 0,
        "tipos": Counter(),
        "zonas": Counter(),
        "mmsi_vistos": set(),
        "mmsi_por_zona": {},
        "errores_parseo": 0,
        "errores_servidor": [],
    }

    suscripcion = {"APIKey": api_key, "BoundingBoxes": bbox}
    websocket = None
    inicio = time.perf_counter()

    try:
        websocket = await asyncio.wait_for(
            connect(WS_URL, open_timeout=TIMEOUT_CONEXION_S,
                    close_timeout=2, ping_interval=None),
            timeout=TIMEOUT_CONEXION_S + 5,
        )
    except Exception as exc:
        stats["error"] = type(exc).__name__ + ": " + str(exc)[:200]
        return stats

    try:
        await websocket.send(json.dumps(suscripcion))
        print("  [" + etiqueta + "] suscripcion enviada. Capturando "
              + str(SEGUNDOS_CAPTURA) + " s...")

        limite = time.perf_counter() + SEGUNDOS_CAPTURA
        ultimo_reporte = time.perf_counter()

        with ruta_cruda.open("w", encoding="utf-8") as archivo:
            while time.perf_counter() < limite and stats["mensajes"] < MAX_MENSAJES:
                restante = limite - time.perf_counter()
                if restante <= 0:
                    break
                try:
                    trama = await asyncio.wait_for(websocket.recv(), timeout=restante)
                except TimeoutError:
                    break
                except Exception as exc:
                    stats["error"] = "durante recv: " + type(exc).__name__ + ": " + str(exc)[:150]
                    break

                texto = trama if isinstance(trama, str) else trama.decode("utf-8", "replace")
                stats["bytes"] += len(texto)

                try:
                    parsed = json.loads(texto)
                except (ValueError, TypeError):
                    stats["errores_parseo"] += 1
                    continue

                if isinstance(parsed, dict) and parsed.get("error"):
                    stats["errores_servidor"].append(str(parsed["error"])[:200])
                    continue

                stats["mensajes"] += 1
                archivo.write(texto + "\n")
                stats["tipos"][parsed.get("MessageType") or "(sin_tipo)"] += 1

                meta = parsed.get("MetaData") or {}
                lat, lon, mmsi = meta.get("latitude"), meta.get("longitude"), meta.get("MMSI")
                zona = clasificar(lat, lon)
                stats["zonas"][zona] += 1
                if mmsi:
                    stats["mmsi_vistos"].add(mmsi)
                    stats["mmsi_por_zona"].setdefault(zona, set()).add(mmsi)

                ahora = time.perf_counter()
                if ahora - ultimo_reporte >= 30:
                    print("    {:>3}s  {:>6} msg  {:>4} buques".format(
                        int(ahora - inicio), stats["mensajes"], len(stats["mmsi_vistos"])))
                    ultimo_reporte = ahora

        stats["ok"] = stats["mensajes"] > 0
        stats["segundos"] = round(time.perf_counter() - inicio, 1)

    finally:
        # Abortar, no negociar: con volumen alto el close() no completa nunca.
        with contextlib.suppress(AttributeError, OSError):
            websocket.transport.abort()

    return stats


def veredicto(stats: dict, base: dict) -> tuple[str, str]:
    """
    Traduce las metricas a un veredicto. Dos controles deciden la validez.

    Control 1 - Balboa, dentro de la MISMA captura: si no hay trafico en la
    entrada del Canal, la caja del Pacifico no esta entregando datos.
    Control 2 - el Caribe del MISMO dia contra los 161 mensajes que TG-10
    midio el 18/08: si hoy el Caribe tambien rinde una decima parte, lo que
    falla es la cuenta y no la cobertura de Caldera.

    Sin los dos, "cero buques en Caldera" no prueba nada.
    """
    buques = {z: len(s) for z, s in stats.get("mmsi_por_zona", {}).items()}
    caldera = buques.get("caldera", 0)
    nicoya = buques.get("golfo_nicoya", 0)
    control = buques.get("balboa_control", 0)
    msg_caribe = base.get("mensajes", 0)
    cuenta_viva = msg_caribe >= BASELINE_TG10_MENSAJES * 0.25

    if not stats.get("ok"):
        return "INVALIDA", "No llego ningun mensaje del Pacifico: el problema es la conexion."
    if not cuenta_viva:
        return ("CUENTA_DEGRADADA",
                "El Caribe rindio " + str(msg_caribe) + " mensajes hoy contra los "
                + str(BASELINE_TG10_MENSAJES) + " que TG-10 midio el 18/08 en la misma caja "
                "y el mismo tiempo. La cuenta de AISStream no esta entregando datos, asi que "
                "la captura del Pacifico no puede decidir nada sobre Caldera. Es exactamente "
                "el hallazgo que TG-10 dejo pendiente en 'No es la red: es la cuenta', y se "
                "cierra revisando el consumo del plan gratuito en aisstream.io.")
    if control == 0 and caldera == 0 and nicoya == 0:
        # Con la cuenta probada viva por la linea base, el cero en Balboa deja de
        # ser un fallo de la prueba y pasa a ser el hallazgo mas fuerte: si la
        # entrada del Canal esta muda, el hueco no es de Caldera sino regional.
        return ("SIN_COBERTURA_REGIONAL",
                "Cero buques en Caldera, en el Golfo de Nicoya y tambien en Balboa, la entrada "
                "pacifica del Canal de Panama, mientras el Caribe rendia " + str(msg_caribe)
                + " mensajes con la misma llave y en los mismos 3 minutos. No es que Caldera "
                "este oscuro: el feed gratuito de AISStream no cubre el Pacifico oriental. "
                "El arribo maritimo es manual en los dos puertos.")
    if control == 0:
        return ("INVALIDA",
                "Cero buques en el control de Balboa pero si en la zona de Caldera. "
                "Combinacion inesperada: revisar las cajas antes de concluir.")
    if caldera > 0:
        return ("HAY_COBERTURA",
                "Se vieron " + str(caldera) + " buques dentro de la geocerca de Caldera, con "
                + str(control) + " en el control. El arribo por geocerca (RN-05 / US-11) es "
                "viable en el Pacifico, a diferencia de Moin.")
    if nicoya > 0:
        return ("PARCIAL",
                "Cero buques en la geocerca de Caldera pero " + str(nicoya) + " en el Golfo de "
                "Nicoya, con " + str(control) + " en el control. Hay senal en la zona: hace "
                "falta una captura larga antes de concluir, porque 3 min pueden no cubrir un "
                "atraque.")
    return ("SIN_COBERTURA",
            "Cero buques en Caldera y en el Golfo de Nicoya, con " + str(control) + " en el "
            "control de Balboa y la cuenta entregando datos. Es un hueco real de cobertura, "
            "igual que Moin: el arribo maritimo es manual en los dos puertos.")


def main() -> int:
    args = network_arg("Spike TASK-28 Fase 3a: cobertura AIS en Caldera")
    env = load_env()
    api_key = require(env, "AISSTREAM_API_KEY")

    timestamp = header(
        "TrackIn - Spike TASK-28 - Fase 3a: cobertura AIS en Caldera",
        args.network,
        {"Llave": mask(api_key), "Captura": str(SEGUNDOS_CAPTURA) + " s",
         "Control": "Balboa (entrada pacifica del Canal)"},
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ruta_cruda = OUTPUT_DIR / ("03_caldera_raw_" + args.network + ".jsonl")

    print(SUB)
    print("  CAPTURA A - Pacifico (Caldera + control Balboa)")
    print(SUB)
    stats = asyncio.run(capturar(api_key, PACIFICO_BBOX, clasificar_zona,
                                 ruta_cruda, "pacifico"))

    print(SUB)
    print("  CAPTURA B - Caribe, linea base del mismo dia")
    print(SUB)
    print("  TG-10 midio " + str(BASELINE_TG10_MENSAJES) + " mensajes en "
          + str(SEGUNDOS_CAPTURA) + " s sobre esta misma caja el 18/08.")
    base = asyncio.run(capturar(api_key, CARIBE_BBOX, clasificar_caribe,
                                OUTPUT_DIR / ("03_caribe_base_raw_" + args.network + ".jsonl"),
                                "caribe-base"))
    print("  Hoy: " + str(base.get("mensajes", 0)) + " mensajes, "
          + str(len(base.get("mmsi_vistos", set()))) + " buques.")

    if stats.get("error"):
        print("  [!] " + stats["error"])

    buques_por_zona = {z: len(s) for z, s in stats.get("mmsi_por_zona", {}).items()}

    print(SUB)
    print("  RESULTADO POR ZONA")
    print(SUB)
    print("  {:<18} {:>9} {:>9}".format("zona", "mensajes", "buques"))
    for zona in ("caldera", "golfo_nicoya", "balboa_control", "pacifico_abierto", "sin_posicion"):
        print("  {:<18} {:>9} {:>9}".format(
            zona, stats["zonas"].get(zona, 0), buques_por_zona.get(zona, 0)))
    print()
    print("  Total: " + str(stats["mensajes"]) + " mensajes, "
          + str(len(stats["mmsi_vistos"])) + " buques unicos en "
          + str(stats.get("segundos", 0)) + " s")

    codigo, explicacion = veredicto(stats, base)
    print(SEP)
    print("  VEREDICTO: " + codigo)
    print(SEP)
    for linea in explicacion.split(". "):
        if linea.strip():
            print("  " + linea.strip().rstrip(".") + ".")
    print(SEP)

    evidencia = {
        "spike": "TASK-28",
        "fase": "3a-cobertura-caldera",
        "pregunta": "Hay cobertura AIS en Puerto Caldera (Pacifico)?",
        "timestamp_utc": timestamp,
        "network_profile": args.network,
        "bbox": PACIFICO_BBOX,
        "zonas": {"caldera": CALDERA, "golfo_nicoya": GOLFO_NICOYA, "balboa_control": BALBOA},
        "segundos_captura": SEGUNDOS_CAPTURA,
        "mensajes": stats["mensajes"],
        "bytes": stats["bytes"],
        "segundos_reales": stats.get("segundos"),
        "tipos_mensaje": dict(stats["tipos"]),
        "mensajes_por_zona": dict(stats["zonas"]),
        "buques_por_zona": buques_por_zona,
        "buques_unicos": len(stats["mmsi_vistos"]),
        "errores_parseo": stats["errores_parseo"],
        "errores_servidor": stats["errores_servidor"],
        "error": stats.get("error"),
        "linea_base_caribe": {
            "bbox": CARIBE_BBOX,
            "mensajes_hoy": base.get("mensajes", 0),
            "buques_hoy": len(base.get("mmsi_vistos", set())),
            "mensajes_tg10_18ago": BASELINE_TG10_MENSAJES,
            "cuenta_entregando_datos": base.get("mensajes", 0) >= BASELINE_TG10_MENSAJES * 0.25,
        },
        "veredicto": codigo,
        "explicacion": explicacion,
        "generado": utc_now(),
    }
    save_evidence("task28", "03_caldera_" + args.network + ".json", evidencia)
    print("  Crudo: " + str(ruta_cruda))

    return 0 if codigo != "INVALIDA" else 1


if __name__ == "__main__":
    sys.exit(main())
