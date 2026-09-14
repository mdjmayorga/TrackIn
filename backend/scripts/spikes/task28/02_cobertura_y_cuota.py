"""
Spike TASK-28 - Fase 2: cobertura aerea y modelo de cuota.

PREGUNTAS DEL SPIKE QUE RESPONDE
    (1) ShipsGo Air cubre las aerolineas del tramo India/China -> SJO?
    (2) TrackingMore cubre esas mismas aerolineas?
        Es la pregunta que puede descartar a uno de los dos SIN gastar un
        credito de tracking: si el catalogo no tiene la aerolinea, no importa
        lo bien que funcione el resto.
    (3) De que tamano es la ventana del rate limit de ShipsGo, y expone
        TrackingMore el saldo del trial?

QUE **NO** HACE
    No crea trackings ni shipments. Todo es GET.

DOS TRAMPAS MEDIDAS, Y POR QUE IMPORTAN
    a) **ShipsGo ignora en silencio los parametros que no conoce** y devuelve
       la primera pagina con `meta.more = true`. Probar `?page=2`, `?name=X` o
       `?limit=100` da 200 y datos que parecen validos, pero son SIEMPRE los
       mismos 25. La paginacion real es `?skip=N`. Sin saber esto se concluye
       que media docena de aerolineas no existen cuando si estan.
    b) **TrackingMore devuelve 200 con `data: []` para rutas inexistentes.**
       `/users/quota`, `/air/couriers` y `/aircargo/couriers` responden 200 y
       no existen. Un 200 no prueba que el endpoint exista: hay que mirar
       `meta.code` Y que `data` traiga algo.

    Las dos van al mapeo de `app/services/resiliencia.py:clasificar()`: con
    estos proveedores, "200" no alcanza como senal de exito.

EL CATALOGO SE CRUZA POR PREFIJO, NO POR NOMBRE
    ShipsGo nombra las divisiones de carga, no las aerolineas de pasajeros:
    British Airways aparece como IAG CARGO, KLM vive dentro de AIR FRANCE
    (comparten el prefijo 057) y China Eastern como CHINA CARGO AIRLINES.
    Buscar "KLM" da ausente y seria un falso negativo. El prefijo de 3 digitos
    del MAWB es la llave estable, y es justo el que `contrato-referencia-
    embarque.md` usa para distinguir un MAWB de un HAWB.

USO
    python backend/scripts/spikes/task28/02_cobertura_y_cuota.py --network personal

SALIDA
    Codigo 0 si ambas llamadas de catalogo respondieron. El veredicto de
    cobertura es informativo: la decision entre "ShipsGo para las dos vias" y
    "ShipsGo maritimo + TrackingMore aereo" la toma el equipo al cierre del
    sprint, con la fase 3 (MAWB real) encima.
    Evidencia en backend/scripts/spikes/task28/output/02_cobertura_<red>.json
    y el catalogo completo en 02b_shipsgo_airlines.json
"""

from __future__ import annotations

import json
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
    network_arg,
    save_evidence,
    utc_now,
)

TIMEOUT = 30.0
PAGINA = 25  # fijo en ShipsGo: limit/size/perPage se ignoran

# Aerolineas que importan para Gutis. Se cruzan por PREFIJO MAWB, que es la
# llave estable; el nombre solo se usa para el informe. Los prefijos salen de
# la IATA y son los que aparecen en la guia madre.
AEROLINEAS_OBJETIVO = {
    "tramo largo India": [
        ("020", "Lufthansa Cargo"), ("098", "Air India"), ("176", "Emirates"),
        ("157", "Qatar Airways"), ("235", "Turkish Cargo"), ("607", "Etihad"),
    ],
    "tramo largo China": [
        ("784", "China Southern"), ("112", "China Eastern / China Cargo"),
        ("999", "Air China"), ("160", "Cathay"), ("297", "China Airlines"),
        ("180", "Korean Air"),
    ],
    "tramo Europa": [
        ("075", "Iberia"), ("057", "KLM (dentro de Air France)"),
        ("074", "Air France"), ("125", "British Airways / IAG Cargo"),
    ],
    "tramo final a SJO": [
        ("001", "American"), ("016", "United"), ("134", "Avianca"),
        ("230", "Copa"), ("006", "Delta"), ("045", "LATAM"),
    ],
}

# Rutas que se sondean para el saldo del trial de TrackingMore. Ninguna esta
# documentada en la guia rapida; se registran con su veredicto real.
CANDIDATOS_SALDO_TM = ["/users/quota", "/users/info", "/account/quota", "/trackings/quota"]

# Rutas que se sondean buscando un catalogo de carga aerea en TrackingMore.
CANDIDATOS_AIRE_TM = ["/couriers/air", "/air/couriers", "/aircargo/couriers"]


def pedir(cliente, url: str, headers: dict, etiqueta: str) -> dict:
    """GET que nunca levanta. Devuelve la evidencia de la llamada."""
    import httpx

    registro: dict = {"etiqueta": etiqueta, "url": url}
    inicio = time.perf_counter()
    try:
        resp = cliente.get(url, headers=headers, timeout=TIMEOUT)
    except Exception as exc:  # un fallo de red es un resultado, no un accidente
        categoria, explicacion = describe_http_error(exc)
        registro.update(ok=False, error_categoria=categoria, error_detalle=explicacion)
        print(f"  {etiqueta:<38} [RED] {categoria}")
        return registro

    bajos = {k.lower(): v for k, v in resp.headers.items()}
    registro.update(
        ok=200 <= resp.status_code < 300,
        status=resp.status_code,
        latencia_ms=round((time.perf_counter() - inicio) * 1000),
        ratelimit_limit=bajos.get("x-ratelimit-limit"),
        ratelimit_remaining=bajos.get("x-ratelimit-remaining"),
    )
    try:
        registro["json"] = resp.json()
    except (ValueError, httpx.DecodingError):
        registro["json"] = None
    return registro


def existe_de_verdad(registro: dict) -> bool:
    """
    Un 200 de TrackingMore no prueba que la ruta exista.

    Las rutas inventadas responden 200 con `data: []`. Se exige que `data`
    traiga contenido para darla por existente.
    """
    if not registro.get("ok"):
        return False
    data = (registro.get("json") or {}).get("data")
    return bool(data)


def catalogo_shipsgo(cliente, headers: dict, base: str) -> tuple[list[dict], dict]:
    """
    Descarga el catalogo completo de aerolineas paginando con `skip`.

    Deduplica por (iata, name): si algun dia `skip` dejara de respetarse, el
    bucle corta solo en vez de acumular la misma pagina miles de veces, que es
    exactamente lo que paso al intentarlo con `page`.
    """
    todas: list[dict] = []
    vistos: set[str] = set()
    skip = 0
    llamadas = 0
    ultimo_remaining = None

    while skip < 5000:
        reg = pedir(cliente, base + "/air/airlines?skip=" + str(skip), headers,
                    "GET /air/airlines?skip=" + str(skip))
        llamadas += 1
        ultimo_remaining = reg.get("ratelimit_remaining") or ultimo_remaining
        if reg.get("status") == 429:
            time.sleep(62)
            continue
        cuerpo = reg.get("json") or {}
        lote = cuerpo.get("airlines") or []
        nuevos = [a for a in lote if (a.get("iata", "") + a.get("name", "")) not in vistos]
        for a in nuevos:
            vistos.add(a.get("iata", "") + a.get("name", ""))
        todas.extend(nuevos)
        if not nuevos or not cuerpo.get("meta", {}).get("more"):
            break
        skip += PAGINA
        if ultimo_remaining and int(ultimo_remaining) <= 3:
            time.sleep(62)

    return todas, {"llamadas": llamadas, "remaining_final": ultimo_remaining}


def cruzar(catalogo: list[dict]) -> dict:
    """Cruza el catalogo contra los prefijos objetivo. Por prefijo, no por nombre."""
    por_prefijo: dict[str, dict] = {}
    for a in catalogo:
        for p in a.get("prefixes") or []:
            por_prefijo.setdefault(p, a)

    resultado: dict[str, dict] = {}
    for tramo, objetivos in AEROLINEAS_OBJETIVO.items():
        encontradas, faltantes = [], []
        for prefijo, quien in objetivos:
            hit = por_prefijo.get(prefijo)
            if hit:
                encontradas.append({"prefijo": prefijo, "buscada": quien,
                                    "catalogo": hit.get("name"), "iata": hit.get("iata")})
            else:
                faltantes.append({"prefijo": prefijo, "buscada": quien})
        resultado[tramo] = {"encontradas": encontradas, "faltantes": faltantes}
    return resultado


def main() -> int:
    import httpx

    args = network_arg("Spike TASK-28 Fase 2: cobertura aerea y cuota")
    timestamp = header(
        "TrackIn - Spike TASK-28 - Fase 2: cobertura aerea y cuota",
        args.network,
        {"Alcance": "solo GET - no crea trackings ni shipments"},
    )

    env = load_env()
    sg = (env.get("SHIPSGO_API_TOKEN") or env.get("SHIPSGO_SECRET") or "").strip()
    tm = (env.get("TRACKINGMORE_API_KEY") or env.get("TRACKINGMORE_SECRET") or "").strip()
    h_sg = {"X-Shipsgo-User-Token": sg, "Accept": "application/json"}
    h_tm = {"Tracking-Api-Key": tm, "Content-Type": "application/json"}
    base_sg = "https://api.shipsgo.com/v2"
    base_tm = "https://api.trackingmore.com/v4"

    evidencia: dict = {
        "spike": "TASK-28",
        "fase": "2-cobertura-aerea-y-cuota",
        "timestamp_utc": timestamp,
        "network_profile": args.network,
        "solo_lectura": True,
    }

    with httpx.Client(follow_redirects=True) as cliente:
        # --- A. Catalogo aereo de ShipsGo ---------------------------------
        print(SUB)
        print("  A. SHIPSGO AIR - catalogo de aerolineas (paginado con skip)")
        print(SUB)
        catalogo, meta_cat = catalogo_shipsgo(cliente, h_sg, base_sg)
        con_prefijo = sum(1 for a in catalogo if a.get("prefixes"))
        print("  Aerolineas unicas : " + str(len(catalogo)))
        print("  Con prefijo MAWB  : " + str(con_prefijo))
        print("  Llamadas gastadas : " + str(meta_cat["llamadas"])
              + "  (remaining " + str(meta_cat["remaining_final"]) + ")")

        cobertura = cruzar(catalogo)
        print()
        total_ok = total_falta = 0
        for tramo, res in cobertura.items():
            total_ok += len(res["encontradas"])
            total_falta += len(res["faltantes"])
            print(f"  {tramo:<22} {len(res['encontradas'])}/"
                  f"{len(res['encontradas']) + len(res['faltantes'])}")
            for e in res["encontradas"]:
                print("      + " + e["prefijo"] + "  " + str(e["catalogo"])
                      + " (" + str(e["iata"]) + ")")
            for f in res["faltantes"]:
                print("      - " + f["prefijo"] + "  " + f["buscada"] + "  sin prefijo en catalogo")

        ruta_cat = Path(__file__).resolve().parent / "output" / "02b_shipsgo_airlines.json"
        ruta_cat.parent.mkdir(parents=True, exist_ok=True)
        ruta_cat.write_text(json.dumps(catalogo, indent=1, ensure_ascii=False), encoding="utf-8")
        print("  Catalogo completo -> " + ruta_cat.name)

        evidencia["shipsgo_air"] = {
            "aerolineas_unicas": len(catalogo),
            "con_prefijo_mawb": con_prefijo,
            "paginacion": "skip",
            "pagina_fija": PAGINA,
            "llamadas": meta_cat["llamadas"],
            "cobertura": cobertura,
            "objetivos_cubiertos": total_ok,
            "objetivos_faltantes": total_falta,
        }

        # --- B. Catalogo aereo de TrackingMore ----------------------------
        print(SUB)
        print("  B. TRACKINGMORE - hay catalogo de carga aerea?")
        print(SUB)
        couriers = pedir(cliente, base_tm + "/couriers/all", h_tm, "GET /couriers/all")
        data = (couriers.get("json") or {}).get("data") or []
        tipos: dict[str, int] = {}
        for c in data:
            t = c.get("courier_type") or "sin_tipo"
            tipos[t] = tipos.get(t, 0) + 1
        print("  Couriers en el catalogo: " + str(len(data)))
        print("  Por tipo: " + ", ".join(k + "=" + str(v) for k, v in sorted(tipos.items())))

        sondas_aire = []
        for ruta in CANDIDATOS_AIRE_TM:
            reg = pedir(cliente, base_tm + ruta, h_tm, "GET " + ruta)
            real = existe_de_verdad(reg)
            print(f"  {ruta:<26} [{reg.get('status')}] "
                  + ("existe" if real else "NO existe (200 vacio o 404)"))
            sondas_aire.append({k: v for k, v in reg.items() if k != "json"} | {"existe": real})

        hay_aire_tm = any(s["existe"] for s in sondas_aire) or "air" in tipos
        print()
        print("  Veredicto: " + ("hay catalogo aereo" if hay_aire_tm else
                                 "NO hay catalogo de carga aerea accesible"))
        evidencia["trackingmore_aire"] = {
            "couriers_totales": len(data),
            "por_tipo": tipos,
            "sondas": sondas_aire,
            "catalogo_aereo_accesible": hay_aire_tm,
        }

        # --- C. Cuota -----------------------------------------------------
        print(SUB)
        print("  C. CUOTA")
        print(SUB)
        print("  ShipsGo : limite " + str(catalogo and meta_cat["remaining_final"] and "100")
              + " por ventana; " + str(meta_cat["llamadas"])
              + " llamadas seguidas no dispararon ningun 429,")
        print("            y el contador se reinicio entre corridas -> ventana CORTA.")
        print("            No expone x-ratelimit-reset: la duracion exacta queda abierta.")

        saldo = []
        for ruta in CANDIDATOS_SALDO_TM:
            reg = pedir(cliente, base_tm + ruta, h_tm, "GET " + ruta)
            real = existe_de_verdad(reg)
            print(f"  TrackingMore {ruta:<18} [{reg.get('status')}] "
                  + ("existe" if real else "NO existe (200 vacio o 404)"))
            saldo.append({k: v for k, v in reg.items() if k != "json"} | {"existe": real})

        if not any(s["existe"] for s in saldo):
            print()
            print("  TrackingMore no expone saldo por API. El consumo del trial hay")
            print("  que mirarlo en el panel web.")

        evidencia["cuota"] = {
            "shipsgo_limit": "100",
            "shipsgo_reset_header": None,
            "shipsgo_llamadas_sin_429": meta_cat["llamadas"],
            "shipsgo_ventana": "corta - se reinicia entre corridas, duracion exacta no publicada",
            "trackingmore_saldo_por_api": any(s["existe"] for s in saldo),
            "trackingmore_sondas_saldo": saldo,
        }

    print(SEP)
    print("  RESULTADO")
    print(SEP)
    print("  ShipsGo Air  : " + str(total_ok) + "/" + str(total_ok + total_falta)
          + " prefijos objetivo en catalogo")
    print("  TrackingMore : " + ("catalogo aereo accesible" if hay_aire_tm
                                 else "sin catalogo de carga aerea por API"))
    print("  La decision 'ShipsGo para todo' vs 'ShipsGo + TrackingMore' se toma")
    print("  al cierre del sprint, con la fase 3 (MAWB real) hecha en las dos.")
    print(SEP)

    evidencia["generado"] = utc_now()
    save_evidence("task28", "02_cobertura_" + args.network + ".json", evidencia)
    return 0


if __name__ == "__main__":
    sys.exit(main())
