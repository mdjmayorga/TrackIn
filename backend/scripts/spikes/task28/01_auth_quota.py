"""
Spike TASK-28 - Fase 1: autenticacion, forma del error y cuota.

PREGUNTAS DEL SPIKE QUE RESPONDE
    (1) La llave de prueba sirve? Que devuelve el proveedor con una llave
        valida y que devuelve con una deliberadamente invalida?
    (2) Una referencia inexistente es un 404 o un 200 con lista vacia?
    (3) Que headers de cuota / rate limit expone cada proveedor?

    Las tres alimentan codigo que YA existe:
      - `app/services/resiliencia.py:clasificar()` traduce un motivo a una
        ClaseFallo. Un fallo permanente (credencial mala, referencia que no
        existe) no debe entrar al bucle de reintentos; uno transitorio si.
        Hoy ese mapeo es generico. Esta fase produce el mapeo real.
      - `EstadoFuente.registrar_exito(con_datos=False)` existe para "respondio
        bien pero no traia nada". Saber si una referencia inexistente da 404 o
        200-vacio decide cual de los dos caminos se toma.

QUE **NO** HACE
    NO crea trackings ni shipments. Todas las llamadas son GET de lectura.
    En TrackingMore "create" es lo que consume cuota de la prueba gratuita, y
    en ShipsGo un shipment creado queda en la cuenta. Gastar el trial para
    responder "la llave sirve?" seria tirarlo.

    Tampoco usa referencias reales de Gutis: no las tenemos todavia, y esta
    fase esta disenada para no necesitarlas (criterio agregado a TASK-28 el
    14/09/2026).

ORDEN, DE MAS BARATO A MAS CARO
    0. Sonda sin credencial      -> confirma host, TLS y que la red deja pasar
    1. GET de lectura con llave  -> la llave sirve
    2. El MISMO GET con llave mala -> forma del error de credencial
    3. GET de referencia inexistente -> 404 contra 200-vacio

    Si el paso 1 falla, los siguientes igual corren: en red corporativa hace
    falta distinguir "la llave es mala" de "la red no deja salir", y eso solo
    se ve comparando.

CREDENCIALES
    Acepta los dos esquemas de nombres, igual que check_env.py:
      canonico -> SHIPSGO_API_TOKEN   / TRACKINGMORE_API_KEY
      alterno  -> SHIPSGO_SECRET      / TRACKINGMORE_SECRET
    Nunca imprime el token: solo la mascara de 4+4 de _common.mask().

USO
    python backend/scripts/spikes/task28/01_auth_quota.py --network personal

SALIDA
    Codigo 0 si AMBOS proveedores autenticaron; 1 si alguno no.
    Evidencia en backend/scripts/spikes/task28/output/01_auth_<red>.json
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import (
    SEP,
    SUB,
    describe_http_error,
    header,
    load_env,
    mask,
    network_arg,
    save_evidence,
    utc_now,
)

# Llave invalida pero con la MISMA forma que la buena, para que el proveedor
# la rechace por invalida y no por malformada. Son dos preguntas distintas.
LLAVE_FALSA = "00000000-0000-4000-8000-000000000000"

# Referencia sintacticamente valida pero que no le pertenece a nadie.
# Contenedor ISO 6346 con digito de control correcto y prefijo no asignado.
CONTENEDOR_INEXISTENTE = "ZZZU0000005"
AWB_INEXISTENTE = "999-99999999"

TIMEOUT = 20.0

# Cabeceras que interesan para la cuota. Se buscan en minusculas.
HEADERS_CUOTA = (
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
    "ratelimit-limit",
    "ratelimit-remaining",
    "ratelimit-reset",
    "retry-after",
    "x-quota-limit",
    "x-quota-remaining",
    "x-credits-remaining",
)


def credencial(env: dict[str, str], canonico: str, alterno: str) -> tuple[str | None, str]:
    """Devuelve (valor, nombre_usado) aceptando los dos esquemas de nombres."""
    for nombre in (canonico, alterno):
        valor = (env.get(nombre) or "").strip()
        if valor:
            return valor, nombre
    return None, canonico


def cuota(headers) -> dict[str, str]:
    """Extrae del response los headers de cuota que el proveedor haya puesto."""
    bajos = {k.lower(): v for k, v in headers.items()}
    return {k: bajos[k] for k in HEADERS_CUOTA if k in bajos}


def resumen_cuerpo(texto: str, limite: int = 400) -> str:
    """Recorta el cuerpo para la evidencia. Interesa la FORMA, no el volcado."""
    limpio = " ".join(texto.split())
    return limpio if len(limpio) <= limite else limpio[:limite] + " [...]"


def sondear(cliente, metodo: str, url: str, headers: dict, etiqueta: str) -> dict:
    """
    Ejecuta una llamada y devuelve su evidencia.

    Nunca levanta: un fallo de red es un resultado del spike, no un accidente.
    """
    import httpx

    registro: dict = {"etiqueta": etiqueta, "metodo": metodo, "url": url}
    inicio = time.perf_counter()
    try:
        resp = cliente.request(metodo, url, headers=headers, timeout=TIMEOUT)
    except Exception as exc:  # clasificar el fallo es justamente el punto
        categoria, explicacion = describe_http_error(exc)
        registro.update(
            ok=False,
            error_categoria=categoria,
            error_detalle=explicacion,
            latencia_ms=round((time.perf_counter() - inicio) * 1000),
        )
        print(f"  {etiqueta:<34} [RED] {categoria} - {explicacion}")
        return registro

    latencia = round((time.perf_counter() - inicio) * 1000)
    headers_cuota = cuota(resp.headers)
    try:
        cuerpo_json = resp.json()
        forma = type(cuerpo_json).__name__
        claves = sorted(cuerpo_json.keys())[:12] if isinstance(cuerpo_json, dict) else []
    except (ValueError, httpx.DecodingError):
        forma = "no-json"
        claves = []

    registro.update(
        ok=200 <= resp.status_code < 300,
        status=resp.status_code,
        latencia_ms=latencia,
        content_type=resp.headers.get("content-type", ""),
        cuerpo_forma=forma,
        cuerpo_claves=claves,
        cuerpo_muestra=resumen_cuerpo(resp.text),
        headers_cuota=headers_cuota,
    )
    marca = "OK " if registro["ok"] else "-- "
    print(f"  {etiqueta:<34} [{marca.strip()}] {resp.status_code} en {latencia} ms")
    if claves:
        print("  " + " " * 36 + "claves: " + ", ".join(claves))
    if headers_cuota:
        for k, v in headers_cuota.items():
            print("  " + " " * 36 + k + ": " + v)
    return registro


def probar_shipsgo(cliente, token: str | None, nombre_var: str) -> dict:
    """ShipsGo v2: header X-Shipsgo-User-Token. Solo GET."""
    print(SUB)
    print("  SHIPSGO  (variable: " + nombre_var + ")")
    print(SUB)
    if token is None:
        print("  Sin credencial. Se salta.")
        return {"credencial": None, "sondas": []}

    print("  Token: " + mask(token))
    base = "https://api.shipsgo.com/v2"
    h_ok = {"X-Shipsgo-User-Token": token, "Accept": "application/json"}
    h_mal = {"X-Shipsgo-User-Token": LLAVE_FALSA, "Accept": "application/json"}

    sondas = [
        sondear(cliente, "GET", base + "/ocean/shipments?limit=1", {"Accept": "application/json"},
                "0 sin credencial"),
        sondear(cliente, "GET", base + "/ocean/shipments?limit=1", h_ok,
                "1 listado oceano (llave buena)"),
        sondear(cliente, "GET", base + "/air/shipments?limit=1", h_ok,
                "2 listado aereo (llave buena)"),
        sondear(cliente, "GET", base + "/ocean/shipments?limit=1", h_mal,
                "3 listado oceano (llave mala)"),
        sondear(cliente, "GET", base + "/ocean/shipments?containerNumber=" + CONTENEDOR_INEXISTENTE,
                h_ok, "4 contenedor inexistente"),
    ]
    return {"credencial": nombre_var, "base_url": base, "sondas": sondas}


def probar_trackingmore(cliente, key: str | None, nombre_var: str) -> dict:
    """TrackingMore v4: header Tracking-Api-Key. Solo GET, nunca create."""
    print(SUB)
    print("  TRACKINGMORE  (variable: " + nombre_var + ")")
    print(SUB)
    if key is None:
        print("  Sin credencial. Se salta.")
        return {"credencial": None, "sondas": []}

    print("  Key: " + mask(key))
    base = "https://api.trackingmore.com/v4"
    h_ok = {"Tracking-Api-Key": key, "Content-Type": "application/json"}
    h_mal = {"Tracking-Api-Key": LLAVE_FALSA, "Content-Type": "application/json"}

    sondas = [
        sondear(cliente, "GET", base + "/couriers/all", {"Content-Type": "application/json"},
                "0 sin credencial"),
        # couriers/all es el sondeo barato: valida la llave sin crear nada.
        sondear(cliente, "GET", base + "/couriers/all", h_ok,
                "1 listado couriers (llave buena)"),
        sondear(cliente, "GET", base + "/couriers/all", h_mal,
                "2 listado couriers (llave mala)"),
        sondear(cliente, "GET", base + "/trackings/get?tracking_numbers=" + AWB_INEXISTENTE,
                h_ok, "3 AWB inexistente (lectura)"),
    ]
    return {"credencial": nombre_var, "base_url": base, "sondas": sondas}


def main() -> int:
    import httpx

    args = network_arg("Spike TASK-28 Fase 1: auth, forma del error y cuota")
    timestamp = header(
        "TrackIn - Spike TASK-28 - Fase 1: auth, error y cuota",
        args.network,
        {"Alcance": "solo GET - no crea trackings ni shipments"},
    )

    env = load_env()
    sg_token, sg_var = credencial(env, "SHIPSGO_API_TOKEN", "SHIPSGO_SECRET")
    tm_key, tm_var = credencial(env, "TRACKINGMORE_API_KEY", "TRACKINGMORE_SECRET")

    with httpx.Client(follow_redirects=True) as cliente:
        shipsgo = probar_shipsgo(cliente, sg_token, sg_var)
        trackingmore = probar_trackingmore(cliente, tm_key, tm_var)

    def autentico(bloque: dict) -> bool:
        for sonda in bloque["sondas"]:
            if "llave buena" in sonda["etiqueta"] and sonda.get("ok"):
                return True
        return False

    sg_ok = autentico(shipsgo)
    tm_ok = autentico(trackingmore)

    print(SEP)
    print("  RESULTADO")
    print(SEP)
    print("  ShipsGo      : " + ("autentico" if sg_ok else "NO autentico"))
    print("  TrackingMore : " + ("autentico" if tm_ok else "NO autentico"))
    print()
    print("  Lo que hay que leer en la evidencia:")
    print("    - status de la sonda 'llave mala'  -> mapeo de fallo PERMANENTE")
    print("    - status de la sonda 'inexistente' -> 404 o 200-vacio")
    print("    - headers_cuota                    -> cuanto queda del trial")
    print(SEP)

    evidencia = {
        "spike": "TASK-28",
        "fase": "1-auth-error-cuota",
        "timestamp_utc": timestamp,
        "network_profile": args.network,
        "solo_lectura": True,
        "referencias_reales_usadas": False,
        "shipsgo": shipsgo,
        "trackingmore": trackingmore,
        "autenticacion": {"shipsgo": sg_ok, "trackingmore": tm_ok},
        "generado": utc_now(),
    }
    save_evidence("task28", "01_auth_" + args.network + ".json", evidencia)

    return 0 if (sg_ok and tm_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
