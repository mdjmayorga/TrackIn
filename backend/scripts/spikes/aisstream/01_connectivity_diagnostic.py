"""
Spike TG-10 - Fase 0: diagnostico de conectividad por capas con AISStream.

PREGUNTA DEL SPIKE QUE RESPONDE
    (1) "Confirmar si el problema de conectividad es firewall corporativo o
    cuenta."

POR QUE POR CAPAS
    El intento previo desde la laptop corporativa terminó en "el WebSocket
    conecta, la suscripcion no da error, pero no llegan mensajes". Ese
    sintoma es compatible con causas MUY distintas:
      - un proxy que completa el handshake y despues descarta los frames,
      - una API key rechazada en silencio,
      - un bounding box sin trafico,
      - un formato de suscripcion invalido que el servidor ignora.
    Un script que solo diga "no funciona" no distingue ninguna. Este prueba
    seis capas por separado y reporta en cual se rompe.

CAPAS
    1. DNS        - resolucion de stream.aisstream.io
    2. TCP:443    - apertura del socket
    3. TLS        - handshake Y EMISOR DEL CERTIFICADO. Este es el
                    diagnostico decisivo: si el certificado lo firmo una CA
                    corporativa en vez de una publica, hay inspeccion TLS
                    (MITM), que explica handshake exitoso con frames
                    descartados.
    4. HTTPS      - GET normal a aisstream.io: pasa el trafico web comun?
    5. WS         - handshake WebSocket: sobrevive el Upgrade al proxy?
    6. Datos      - suscripcion y espera del primer frame.

BOUNDING BOX GLOBAL A PROPOSITO
    Se suscribe al mundo entero. Asi, si no llegan mensajes, la causa NO
    puede ser haber elegido una zona sin trafico. Ese fue el punto ciego del
    intento anterior con el ejemplo de Japon.

USO
    python backend/scripts/spikes/aisstream/01_connectivity_diagnostic.py --network personal
    python backend/scripts/spikes/aisstream/01_connectivity_diagnostic.py --network gutis

    Correr en AMBAS redes: la comparacion es la evidencia que cierra TG-10.

    Evidencia en backend/scripts/spikes/aisstream/output/01_connectivity_<red>.json
"""

from __future__ import annotations

import asyncio
import json
import socket
import ssl
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

WS_HOST = "stream.aisstream.io"
WS_URL = "wss://stream.aisstream.io/v0/stream"
HTTPS_URL = "https://aisstream.io"
PORT = 443

# Mundo entero: si no llegan mensajes, no puede ser por falta de trafico.
GLOBAL_BBOX = [[[-90.0, -180.0], [90.0, 180.0]]]

WAIT_FIRST_MESSAGE_S = 30
CONNECT_TIMEOUT_S = 15

# Emisores publicos conocidos. Si el emisor NO contiene ninguno de estos,
# probablemente sea una CA corporativa haciendo inspeccion TLS.
PUBLIC_CA_HINTS = (
    "let's encrypt", "lets encrypt", "digicert", "sectigo", "globalsign",
    "amazon", "google trust", "cloudflare", "isrg", "comodo", "godaddy",
    "entrust", "baltimore", "starfield",
)


def layer_dns() -> dict:
    """Capa 1: resolucion DNS."""
    started = time.perf_counter()
    try:
        infos = socket.getaddrinfo(WS_HOST, PORT, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        return {"ok": False, "error": "gaierror: " + str(exc),
                "diagnosis": "DNS bloqueado o sin resolucion. El firewall filtra por dominio."}
    addresses = sorted({info[4][0] for info in infos})
    return {
        "ok": True,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "addresses": addresses,
    }


def layer_tcp(address: str) -> dict:
    """Capa 2: apertura del socket TCP al 443."""
    started = time.perf_counter()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(CONNECT_TIMEOUT_S)
    try:
        sock.connect((address, PORT))
    except socket.timeout:
        return {"ok": False, "error": "timeout",
                "diagnosis": "El firewall descarta los SYN en silencio (no hay RST)."}
    except OSError as exc:
        return {"ok": False, "error": str(exc),
                "diagnosis": "Conexion rechazada activamente."}
    finally:
        sock.close()
    return {"ok": True, "elapsed_ms": round((time.perf_counter() - started) * 1000, 1)}


def layer_tls() -> dict:
    """
    Capa 3: handshake TLS y, sobre todo, EMISOR DEL CERTIFICADO.

    Si el certificado presentado no lo firmo una CA publica conocida, hay un
    intermediario reescribiendo el TLS. Ese es el hallazgo que explicaria el
    sintoma del intento anterior.
    """
    context = ssl.create_default_context()
    started = time.perf_counter()
    try:
        with socket.create_connection((WS_HOST, PORT), timeout=CONNECT_TIMEOUT_S) as raw:
            with context.wrap_socket(raw, server_hostname=WS_HOST) as tls:
                cert = tls.getpeercert()
                version = tls.version()
                cipher = tls.cipher()
    except ssl.SSLCertVerificationError as exc:
        return {"ok": False, "error": "cert_verification: " + str(exc),
                "diagnosis": "El certificado no valida contra las CA del sistema. "
                             "Sintoma tipico de inspeccion TLS corporativa."}
    except (ssl.SSLError, socket.timeout, OSError) as exc:
        return {"ok": False, "error": type(exc).__name__ + ": " + str(exc),
                "diagnosis": "Fallo el handshake TLS."}

    issuer_parts = []
    for entry in cert.get("issuer", ()):
        for key, value in entry:
            if key in ("organizationName", "commonName"):
                issuer_parts.append(str(value))
    issuer = " / ".join(issuer_parts)
    subject_parts = []
    for entry in cert.get("subject", ()):
        for key, value in entry:
            if key == "commonName":
                subject_parts.append(str(value))

    is_public = any(hint in issuer.lower() for hint in PUBLIC_CA_HINTS)
    return {
        "ok": True,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "tls_version": version,
        "cipher": cipher[0] if cipher else None,
        "issuer": issuer,
        "subject_cn": subject_parts[0] if subject_parts else None,
        "valid_until": cert.get("notAfter"),
        "issuer_is_public_ca": is_public,
        "diagnosis": (
            "Certificado de CA publica: NO hay inspeccion TLS en el camino."
            if is_public else
            "[!] El emisor NO parece una CA publica. Hay un intermediario "
            "reescribiendo el TLS (proxy corporativo con inspeccion)."
        ),
    }


def layer_https() -> dict:
    """Capa 4: HTTPS normal, para separar 'web bloqueada' de 'WebSocket bloqueado'."""
    import httpx

    started = time.perf_counter()
    try:
        response = httpx.get(HTTPS_URL, timeout=CONNECT_TIMEOUT_S, follow_redirects=True)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__ + ": " + str(exc)[:150],
                "diagnosis": "Ni el HTTPS normal pasa: el bloqueo es del dominio entero."}
    return {
        "ok": True,
        "status_code": response.status_code,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "server": response.headers.get("server"),
    }


async def layers_ws_and_data(api_key: str) -> tuple[dict, dict]:
    """
    Capas 5 y 6: handshake WebSocket y llegada del primer frame.

    Se separan a proposito: un handshake exitoso sin frames es justamente el
    sintoma que hay que poder distinguir.
    """
    from websockets.asyncio.client import connect

    ws_result: dict = {}
    data_result: dict = {"messages": [], "message_count": 0}

    started = time.perf_counter()
    try:
        # close_timeout corto y ping_interval desactivado a proposito.
        # Con bounding box global el servidor emite miles de mensajes por
        # segundo; un cierre "limpio" nunca completa porque no se alcanza a
        # drenar el backlog mientras el servidor sigue enviando. La primera
        # version de este script se colgaba justo aca, no en la recepcion.
        async with connect(
            WS_URL,
            open_timeout=CONNECT_TIMEOUT_S,
            close_timeout=3,
            ping_interval=None,
        ) as websocket:
            ws_result = {
                "ok": True,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                "diagnosis": "El Upgrade a WebSocket se completo.",
            }
            print("  Capa 5 WS handshake        [OK]   {} ms".format(ws_result["elapsed_ms"]))

            # AISStream exige el mensaje de suscripcion en los primeros
            # segundos; si no, cierra la conexion sin explicacion.
            subscription = {"APIKey": api_key, "BoundingBoxes": GLOBAL_BBOX}
            await websocket.send(json.dumps(subscription))
            data_result["subscription_sent"] = {
                "BoundingBoxes": GLOBAL_BBOX, "APIKey": "(enmascarada)"
            }
            print("  Capa 6 suscripcion enviada  ...  esperando frames hasta {} s".format(
                WAIT_FIRST_MESSAGE_S))

            wait_started = time.perf_counter()
            deadline = wait_started + WAIT_FIRST_MESSAGE_S
            first_latency = None

            while time.perf_counter() < deadline:
                remaining = deadline - time.perf_counter()
                try:
                    raw = await asyncio.wait_for(websocket.recv(), timeout=remaining)
                except asyncio.TimeoutError:
                    break

                if first_latency is None:
                    first_latency = round((time.perf_counter() - wait_started) * 1000, 1)
                    data_result["first_message_latency_ms"] = first_latency

                data_result["message_count"] += 1
                if len(data_result["messages"]) < 5:
                    try:
                        parsed = json.loads(raw)
                    except (ValueError, TypeError):
                        data_result["messages"].append({"raw_preview": str(raw)[:200]})
                    else:
                        # Un "error" del servidor llega como frame normal:
                        # hay que detectarlo, no contarlo como dato valido.
                        if isinstance(parsed, dict) and parsed.get("error"):
                            data_result["server_error"] = parsed["error"]
                        data_result["messages"].append({
                            "MessageType": parsed.get("MessageType") if isinstance(parsed, dict) else None,
                            "keys": sorted(parsed.keys())[:12] if isinstance(parsed, dict) else None,
                        })

                if data_result["message_count"] >= 25:
                    break

            data_result["ok"] = data_result["message_count"] > 0
            data_result["waited_s"] = round(time.perf_counter() - wait_started, 1)

            # HALLAZGO: con bounding box global el servidor emite miles de
            # mensajes por segundo. El cierre negociado del WebSocket NO
            # completa nunca, porque no se alcanza a drenar el backlog
            # mientras el servidor sigue enviando. Hay que ABORTAR el
            # transporte. Esto vale tal cual para la estrategia de
            # reconexion del modulo real: no depender de close() limpio.
            try:
                websocket.transport.abort()
                data_result["closed_by"] = "transport.abort()"
            except (AttributeError, OSError) as exc:
                data_result["closed_by"] = "fallo el abort: " + type(exc).__name__

    except asyncio.TimeoutError:
        # Solo es fallo de handshake si el handshake no habia completado ya.
        if not ws_result.get("ok"):
            ws_result = {"ok": False, "error": "open_timeout",
                         "diagnosis": "El handshake WebSocket no completo a tiempo. "
                                      "Proxy que no soporta o no permite el Upgrade."}
        else:
            data_result.setdefault("note", "Timeout despues de un handshake exitoso.")
    except Exception as exc:  # noqa: BLE001
        if not ws_result.get("ok"):
            ws_result = {"ok": False, "error": type(exc).__name__ + ": " + str(exc)[:200],
                         "diagnosis": "Fallo la conexion WebSocket."}
        else:
            data_result.setdefault(
                "note", "Excepcion tras el handshake: " + type(exc).__name__)

    return ws_result, data_result


def main() -> int:
    args = network_arg("Spike TG-10 Fase 0: diagnostico de conectividad por capas")
    env = load_env()
    api_key = require(env, "AISSTREAM_API_KEY")

    timestamp = header(
        "TrackIn - Spike TG-10 - Fase 0: conectividad por capas (AISStream)",
        args.network,
        {"api_key": mask(api_key), "host": WS_HOST},
    )

    layers: dict[str, dict] = {}

    print(SUB)
    print("  DIAGNOSTICO POR CAPAS")
    print(SUB)

    # Capa 1
    dns = layer_dns()
    layers["1_dns"] = dns
    if dns["ok"]:
        print("  Capa 1 DNS                 [OK]   {} -> {}".format(
            WS_HOST, ", ".join(dns["addresses"])))
    else:
        print("  Capa 1 DNS                 [FALLO] {}".format(dns["error"]))
        print("         {}".format(dns["diagnosis"]))

    # Capa 2
    if dns["ok"]:
        tcp = layer_tcp(dns["addresses"][0])
        layers["2_tcp"] = tcp
        if tcp["ok"]:
            print("  Capa 2 TCP:443             [OK]   {} ms".format(tcp["elapsed_ms"]))
        else:
            print("  Capa 2 TCP:443             [FALLO] {}".format(tcp["error"]))
            print("         {}".format(tcp["diagnosis"]))

    # Capa 3 - la decisiva
    tls = layer_tls()
    layers["3_tls"] = tls
    if tls["ok"]:
        print("  Capa 3 TLS                 [OK]   {} / {}".format(
            tls["tls_version"], tls["cipher"]))
        print("         Emisor : {}".format(tls["issuer"]))
        print("         {}".format(tls["diagnosis"]))
    else:
        print("  Capa 3 TLS                 [FALLO] {}".format(tls["error"][:110]))
        print("         {}".format(tls["diagnosis"]))

    # Capa 4
    https = layer_https()
    layers["4_https"] = https
    if https["ok"]:
        print("  Capa 4 HTTPS a aisstream.io [OK]   HTTP {}".format(https["status_code"]))
    else:
        print("  Capa 4 HTTPS a aisstream.io [FALLO] {}".format(https["error"][:110]))

    # Capas 5 y 6, con cortafuegos duro EXTERNO al bucle: la primera version
    # se colgo indefinidamente pese a tener su propio deadline interno.
    async def guarded() -> tuple[dict, dict]:
        try:
            async with asyncio.timeout(CONNECT_TIMEOUT_S + WAIT_FIRST_MESSAGE_S + 10):
                return await layers_ws_and_data(api_key)
        except TimeoutError:
            return (
                {"ok": False, "error": "hard_timeout",
                 "diagnosis": "La conexion no completo dentro del limite duro."},
                {"ok": False, "message_count": 0, "messages": [],
                 "note": "Cortado por el limite duro externo."},
            )

    ws_result, data_result = asyncio.run(guarded())
    layers["5_websocket"] = ws_result
    layers["6_data"] = data_result

    if not ws_result.get("ok"):
        print("  Capa 5 WS handshake        [FALLO] {}".format(
            str(ws_result.get("error"))[:110]))
        print("         {}".format(ws_result.get("diagnosis")))
    elif data_result.get("ok"):
        print("  Capa 6 primer frame        [OK]   {} mensajes en {} s "
              "(primero a los {} ms)".format(
                  data_result["message_count"], data_result["waited_s"],
                  data_result.get("first_message_latency_ms")))
    else:
        print("  Capa 6 primer frame        [FALLO] 0 mensajes en {} s".format(
            data_result.get("waited_s")))
        if data_result.get("server_error"):
            print("         El servidor respondio con error: {}".format(
                data_result["server_error"]))

    # --- Veredicto ---------------------------------------------------------
    print(SEP)
    print("  VEREDICTO (red: {})".format(args.network))
    print(SEP)

    if not dns.get("ok"):
        verdict = "dns_bloqueado"
        print("  Se rompe en DNS. El firewall filtra el dominio. No es la cuenta.")
    elif not layers.get("2_tcp", {}).get("ok"):
        verdict = "tcp_bloqueado"
        print("  DNS resuelve pero el TCP:443 no abre. Firewall a nivel de red.")
    elif not tls.get("ok"):
        verdict = "tls_bloqueado"
        print("  El TLS falla. Ver el detalle: si es error de verificacion de")
        print("  certificado, hay inspeccion corporativa en el camino.")
    elif tls.get("ok") and not tls.get("issuer_is_public_ca"):
        verdict = "tls_interceptado"
        print("  [!] HAY INSPECCION TLS: el certificado no viene de una CA publica.")
        print("      Un proxy esta terminando y reescribiendo la conexion. Eso")
        print("      explica un handshake exitoso con frames que nunca llegan.")
    elif not ws_result.get("ok"):
        verdict = "websocket_bloqueado"
        print("  TLS limpio pero el Upgrade a WebSocket falla: el proxy permite")
        print("  HTTPS y no WebSocket. Es un bloqueo de protocolo, no de dominio.")
    elif not data_result.get("ok"):
        verdict = "conecta_sin_datos"
        print("  Conecta, suscribe y NO llegan mensajes, con bounding box GLOBAL.")
        print("  Descartada la falta de trafico. Las causas que quedan son:")
        print("    - API key rechazada en silencio (revisar cuenta en aisstream.io)")
        print("    - proxy que deja pasar el handshake y descarta los frames")
        if data_result.get("server_error"):
            print("  El servidor devolvio un error explicito: revisar arriba.")
    else:
        verdict = "operativo"
        print("  TODO OPERATIVO desde la red {}: llegan datos AIS.".format(args.network))
        print("  Si en la red de Gutis falla, la causa es el firewall corporativo,")
        print("  no la cuenta ni la API key. Esa comparacion cierra TG-10.")
    print(SEP)

    evidence = {
        "spike": "TG-10",
        "phase": "0-connectivity-diagnostic",
        "timestamp_utc": timestamp,
        "finished_utc": utc_now(),
        "network_profile": args.network,
        "target": {"ws_url": WS_URL, "https_url": HTTPS_URL, "bbox": "global"},
        "layers": layers,
        "verdict": verdict,
        "passed": verdict == "operativo",
    }
    save_evidence("aisstream", "01_connectivity_" + args.network + ".json", evidence)
    return 0 if verdict == "operativo" else 1


if __name__ == "__main__":
    sys.exit(main())
