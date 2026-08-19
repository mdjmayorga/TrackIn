"""
Spike TG-11 - Fase 1: autenticacion OAuth2 y conectividad con OpenSky Network.

PREGUNTA DEL SPIKE QUE RESPONDE
    (1) "Se puede consumir OpenSky desde la red corporativa de Gutis?"
    Y de paso deja medido el TTL del token, dato que define la estrategia de
    refresco del modulo real en Sprint 3.

QUE PRUEBA, EN ORDEN
    1. Obtencion de token via OAuth2 client_credentials contra el realm
       Keycloak de OpenSky. Mide latencia.
    2. Lectura de expires_in y de los claims del JWT (iat/exp) para conocer
       el TTL real, sin verificar firma y SIN imprimir el token.
    3. Llamada autenticada a /states/all con un bounding box chico sobre
       Costa Rica, para confirmar que el token efectivamente sirve.
    4. La MISMA llamada sin token (anonima), para comparar. Sirve para dos
       cosas: ver si la red deja pasar la API aunque el auth falle, y medir
       la diferencia de trato entre anonimo y autenticado.
    5. Captura de headers de rate limit que devuelva el servidor.

POR QUE ESTA SEPARADO DE LAS FASES SIGUIENTES
    Si mezclamos auth con analisis de cobertura y despues no llegan datos,
    no sabriamos si el problema es la credencial, la red o que no hay
    aviones. Cada fase aisla una variable.

MANEJO DE ERRORES
    Distingue explicitamente dns_error / connect_timeout / read_timeout /
    proxy_error / 401 / 403 / 429. En red corporativa cada uno apunta a una
    causa distinta, y confundirlos es lo que hace perder dias.

USO
    python backend/scripts/spikes/opensky/01_auth_test.py --network personal

SALIDA
    Codigo 0 si autentico y la llamada autenticada devolvio 200.
    Evidencia en backend/scripts/spikes/opensky/output/01_auth_<red>.json
"""

from __future__ import annotations

import base64
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import (  # noqa: E402
    SEP,
    SUB,
    describe_http_error,
    header,
    load_env,
    mask,
    network_arg,
    require,
    save_evidence,
    utc_now,
)

TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network"
    "/protocol/openid-connect/token"
)
STATES_URL = "https://opensky-network.org/api/states/all"

# Bounding box de Costa Rica y su espacio aereo inmediato.
# Area aproximada 3.3 x 3.5 = ~11.5 grados cuadrados -> tarifa de 1 credito
# segun el esquema de OpenSky (<25 grados cuadrados). En Fase 5 se verifica.
CR_BBOX = {"lamin": 8.0, "lomin": -86.0, "lamax": 11.3, "lomax": -82.5}

TIMEOUT = 20.0


def decode_jwt_claims(token: str) -> dict:
    """
    Decodifica el payload de un JWT SIN verificar la firma.

    Solo interesa leer iat/exp/azp para medir el TTL. No se valida nada
    criptograficamente porque no estamos autenticando a nadie: el token ya
    nos lo dio el servidor por un canal TLS.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {"error": "el token no tiene 3 segmentos, no parece un JWT"}
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)  # padding base64url
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except (ValueError, json.JSONDecodeError) as exc:
        return {"error": "no se pudo decodificar el payload: " + str(exc)}


def fetch_token(client_id: str, client_secret: str) -> tuple[str | None, dict]:
    """Pide el token OAuth2. Devuelve (token, diagnostico)."""
    import httpx

    diag: dict = {"url": TOKEN_URL, "grant_type": "client_credentials"}
    started = time.perf_counter()
    try:
        response = httpx.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001 - queremos clasificar cualquier fallo
        category, explanation = describe_http_error(exc)
        diag.update(
            ok=False,
            error_category=category,
            error_detail=explanation,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return None, diag

    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    diag.update(status_code=response.status_code, elapsed_ms=elapsed_ms)

    if response.status_code == 401:
        diag.update(ok=False, error_category="unauthorized",
                    error_detail="client_id o client_secret invalidos")
        return None, diag
    if response.status_code == 400:
        diag.update(ok=False, error_category="bad_request",
                    error_detail="Peticion mal formada o grant_type no habilitado: "
                                 + response.text[:200])
        return None, diag
    if response.status_code != 200:
        diag.update(ok=False, error_category="http_" + str(response.status_code),
                    error_detail=response.text[:200])
        return None, diag

    try:
        payload = response.json()
    except ValueError:
        diag.update(ok=False, error_category="invalid_json",
                    error_detail="La respuesta 200 no era JSON. "
                                 "Sintoma tipico de portal cautivo o proxy corporativo.")
        return None, diag

    token = payload.get("access_token")
    if not token:
        diag.update(ok=False, error_category="no_token",
                    error_detail="JSON sin access_token: " + str(list(payload.keys())))
        return None, diag

    diag.update(
        ok=True,
        token_type=payload.get("token_type"),
        expires_in_s=payload.get("expires_in"),
        scope=payload.get("scope"),
        token_masked=mask(token),
        token_length=len(token),
    )
    return token, diag


def call_states(token: str | None, label: str) -> dict:
    """
    Llama /states/all sobre el bbox de Costa Rica.

    Con token si se pasa, anonima si no. La comparacion entre ambas es lo
    que revela si la red deja pasar la API con independencia del auth.
    """
    import httpx

    headers = {"Authorization": "Bearer " + token} if token else {}
    diag: dict = {"label": label, "authenticated": token is not None, "bbox": CR_BBOX}

    started = time.perf_counter()
    try:
        response = httpx.get(STATES_URL, params=CR_BBOX, headers=headers, timeout=TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        category, explanation = describe_http_error(exc)
        diag.update(
            ok=False,
            error_category=category,
            error_detail=explanation,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return diag

    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    diag.update(status_code=response.status_code, elapsed_ms=elapsed_ms)

    # Headers de cuota: los nombres varian segun despliegue, capturamos todo
    # lo que suene a limite para no perder el dato en Fase 5.
    quota_headers = {
        k: v for k, v in response.headers.items()
        if "rate" in k.lower() or "limit" in k.lower() or "remaining" in k.lower()
    }
    diag["quota_headers"] = quota_headers

    if response.status_code == 401:
        diag.update(ok=False, error_category="unauthorized",
                    error_detail="Token rechazado por la API de estados")
        return diag
    if response.status_code == 403:
        diag.update(ok=False, error_category="forbidden",
                    error_detail="Cuenta sin permiso para esta consulta")
        return diag
    if response.status_code == 429:
        diag.update(ok=False, error_category="rate_limited",
                    error_detail="Cuota agotada: " + response.text[:200])
        return diag
    if response.status_code != 200:
        diag.update(ok=False, error_category="http_" + str(response.status_code),
                    error_detail=response.text[:200])
        return diag

    try:
        payload = response.json()
    except ValueError:
        diag.update(ok=False, error_category="invalid_json",
                    error_detail="200 sin JSON valido. Posible proxy interceptando.")
        return diag

    states = payload.get("states") or []
    server_time = payload.get("time")
    diag.update(
        ok=True,
        aircraft_count=len(states),
        server_time=server_time,
        server_time_utc=(
            datetime.fromtimestamp(server_time, tz=timezone.utc).isoformat(timespec="seconds")
            if isinstance(server_time, (int, float)) else None
        ),
        response_bytes=len(response.content),
    )
    return diag


def print_result(diag: dict, title: str) -> None:
    print(SUB)
    print("  " + title)
    print(SUB)
    if diag.get("ok"):
        print("  Estado      : [OK] HTTP " + str(diag.get("status_code", "-")))
    else:
        print("  Estado      : [FALLO] " + str(diag.get("error_category", "desconocido")))
        print("  Detalle     : " + str(diag.get("error_detail", "-")))
    print("  Latencia    : " + str(diag.get("elapsed_ms", "-")) + " ms")


def main() -> int:
    args = network_arg("Spike TG-11 Fase 1: auth OAuth2 y conectividad OpenSky")
    env = load_env()
    client_id = require(env, "OPENSKY_CLIENT_ID")
    client_secret = require(env, "OPENSKY_CLIENT_SECRET")

    timestamp = header(
        "TrackIn - Spike TG-11 - Fase 1: auth OAuth2 + conectividad OpenSky",
        args.network,
        {"client_id": mask(client_id), "secret": mask(client_secret)},
    )

    # --- Paso 1: token -----------------------------------------------------
    token, token_diag = fetch_token(client_id, client_secret)
    print_result(token_diag, "PASO 1 - Token OAuth2 (client_credentials)")

    claims: dict = {}
    ttl_info: dict = {}
    if token:
        print("  Tipo        : " + str(token_diag.get("token_type")))
        print("  expires_in  : " + str(token_diag.get("expires_in_s")) + " s")
        print("  Token       : " + str(token_diag.get("token_masked"))
              + "  (" + str(token_diag.get("token_length")) + " chars)")
        claims = decode_jwt_claims(token)
        if "error" not in claims:
            iat, exp = claims.get("iat"), claims.get("exp")
            if isinstance(iat, int) and isinstance(exp, int):
                ttl_info = {
                    "iat_utc": datetime.fromtimestamp(iat, tz=timezone.utc).isoformat(timespec="seconds"),
                    "exp_utc": datetime.fromtimestamp(exp, tz=timezone.utc).isoformat(timespec="seconds"),
                    "ttl_seconds": exp - iat,
                    "ttl_minutes": round((exp - iat) / 60, 1),
                }
                print("  TTL real    : " + str(ttl_info["ttl_minutes"]) + " min"
                      + "  (expira " + ttl_info["exp_utc"] + ")")
            print("  Cliente     : " + str(claims.get("azp") or claims.get("clientId") or "-"))
        else:
            print("  [!] " + str(claims["error"]))

    # --- Paso 2: llamada autenticada --------------------------------------
    auth_call = call_states(token, "autenticada") if token else {
        "label": "autenticada", "ok": False, "skipped": True,
        "error_category": "sin_token", "error_detail": "No se obtuvo token en el paso 1",
    }
    if not auth_call.get("skipped"):
        print_result(auth_call, "PASO 2 - GET /states/all sobre Costa Rica (autenticada)")
        if auth_call.get("ok"):
            print("  Aeronaves   : " + str(auth_call["aircraft_count"]) + " en el bbox de CR")
            print("  Hora server : " + str(auth_call.get("server_time_utc")))
            print("  Payload     : " + str(auth_call["response_bytes"]) + " bytes")
        if auth_call.get("quota_headers"):
            print("  Cuota       : " + json.dumps(auth_call["quota_headers"]))
    else:
        print_result(auth_call, "PASO 2 - GET /states/all (autenticada) [OMITIDO]")

    # --- Paso 3: llamada anonima, para comparar ---------------------------
    anon_call = call_states(None, "anonima")
    print_result(anon_call, "PASO 3 - GET /states/all sobre Costa Rica (anonima)")
    if anon_call.get("ok"):
        print("  Aeronaves   : " + str(anon_call["aircraft_count"]) + " en el bbox de CR")
    if anon_call.get("quota_headers"):
        print("  Cuota       : " + json.dumps(anon_call["quota_headers"]))

    # --- Lectura del resultado --------------------------------------------
    print(SEP)
    print("  LECTURA")
    print(SEP)
    passed = bool(token) and bool(auth_call.get("ok"))

    if passed:
        print("  Fase 1 SUPERADA: OAuth2 autentica y la API responde desde red "
              + args.network + ".")
        count = auth_call.get("aircraft_count", 0)
        if count == 0:
            print("  [!] 0 aeronaves en el bbox de Costa Rica en este instante.")
            print("      No invalida la fase 1 (el auth funciono), pero es la primera")
            print("      senal sobre la pregunta de cobertura. Se mide en serio en Fase 2.")
    elif not token:
        print("  Fase 1 NO superada: fallo la obtencion del token.")
        print("  Categoria: " + str(token_diag.get("error_category")))
        if anon_call.get("ok"):
            print("  Dato clave: la llamada ANONIMA si funciono. La red deja pasar la API,")
            print("              asi que el problema esta en las credenciales, no en el firewall.")
        else:
            print("  Dato clave: la llamada anonima TAMBIEN fallo. Apunta a red/firewall,")
            print("              no a las credenciales. Comparar con la corrida en la otra red.")
    else:
        print("  Fase 1 NO superada: hubo token pero la llamada autenticada fallo.")
        print("  Categoria: " + str(auth_call.get("error_category")))
    print(SEP)

    evidence = {
        "spike": "TG-11",
        "phase": "1-auth-connectivity",
        "timestamp_utc": timestamp,
        "finished_utc": utc_now(),
        "network_profile": args.network,
        "token_request": token_diag,
        "jwt_claims": {k: v for k, v in claims.items()
                       if k in ("iat", "exp", "azp", "clientId", "scope", "typ")},
        "token_ttl": ttl_info,
        "authenticated_call": auth_call,
        "anonymous_call": anon_call,
        "passed": passed,
    }
    save_evidence("opensky", "01_auth_" + args.network + ".json", evidence)

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
