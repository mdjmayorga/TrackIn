"""
Spike TASK-28 - Fase 3b: validacion local de las referencias, antes de gastar.

POR QUE ESTO VA ANTES DE LA PRIMERA LLAMADA
    Los dos proveedores son *create-then-poll*: dar de alta un embarque es lo
    que consume el trial. Una referencia mal formada gasta el credito igual y
    devuelve vacio, y despues no se sabe si el problema fue la referencia o la
    cobertura. Validar primero separa esas dos cosas.

    Es ademas lo que `US-32` tendra que hacer en la carga del Z-tracking, y lo
    que `TASK-30` dejo especificado: contenedor ISO 6346 (4 letras + 7 digitos
    con digito de control) y MAWB de 11 digitos con prefijo de aerolinea.

QUE VALIDA
    1. **Contenedor ISO 6346.** Cuatro letras, la cuarta siempre U/J/Z, seis
       digitos de serie y un digito de control calculado sobre los diez
       primeros caracteres. Un contenedor con digito malo es un error de
       transcripcion, no una referencia que el proveedor no conozca.
    2. **MAWB.** Once digitos: prefijo de 3 de la aerolinea + serie de 7 +
       digito de control, que es la serie modulo 7. El prefijo se cruza contra
       el catalogo real descargado de ShipsGo en la fase 2
       (`02b_shipsgo_airlines.json`), asi que ademas dice **que aerolinea es**.
    3. **La trampa del HAWB.** `contrato-referencia-embarque.md` avisa que el
       agente de carga suele entregar la guia hija, que ningun API resuelve.
       La senal es justamente no tener forma de MAWB: si no son 11 digitos con
       prefijo valido, se marca como probable HAWB.
    4. **Ceros a la izquierda comidos por Excel.** Un MAWB que empieza por cero
       guardado como numero pierde el cero y queda en 10 digitos. Antes de
       declarar invalida una guia corta, se prueba rellenando por la izquierda.

QUE **NO** HACE
    No llama a ningun API. Es aritmetica local y cero costo.

USO
    python backend/scripts/spikes/task28/04_validar_referencias.py REF [REF ...]
    python backend/scripts/spikes/task28/04_validar_referencias.py --archivo refs.txt

    Acepta pares "booking/contenedor" separados por barra, y los parte.

SALIDA
    Codigo 0 si toda referencia quedo clasificada sin errores de formato.
    Evidencia en backend/scripts/spikes/task28/output/04_referencias.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import SEP, SUB, save_evidence, utc_now

CATALOGO = Path(__file__).resolve().parent / "output" / "02b_shipsgo_airlines.json"

# ISO 6346: cada letra vale un numero, saltando los multiplos de 11.
VALOR_LETRA = {}
_n = 10
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    while _n % 11 == 0:
        _n += 1
    VALOR_LETRA[_c] = _n
    _n += 1

RE_CONTENEDOR = re.compile(r"^([A-Z]{3})([UJZ])(\d{6})(\d)$")
RE_SOLO_DIGITOS = re.compile(r"^\d+$")
# Prefijos SCAC de linea naviera que aparecen en BL y booking.
RE_BL_SCAC = re.compile(r"^([A-Z]{4})(\d{6,12})$")


def digito_iso6346(codigo: str) -> int:
    """Calcula el digito de control de un contenedor a partir de sus 10 primeros."""
    total = 0
    for i, ch in enumerate(codigo[:10]):
        valor = VALOR_LETRA[ch] if ch.isalpha() else int(ch)
        total += valor * (2 ** i)
    return total % 11 % 10


def digito_mawb(serie: str) -> int:
    """El digito de control de un MAWB es la serie de 7 digitos modulo 7."""
    return int(serie) % 7


def cargar_aerolineas() -> dict[str, dict]:
    """Indexa el catalogo de ShipsGo por prefijo MAWB. Vacio si no se descargo."""
    if not CATALOGO.is_file():
        return {}
    indice: dict[str, dict] = {}
    for a in json.loads(CATALOGO.read_text(encoding="utf-8")):
        for p in a.get("prefixes") or []:
            indice.setdefault(p, a)
    return indice


def clasificar(ref: str, aerolineas: dict[str, dict], con_contenedor: bool = False) -> dict:
    """
    Clasifica una referencia y explica por que.

    `con_contenedor` dice si venia emparejada con un contenedor en la misma
    celda. Es informacion decisiva: una serie numerica suelta puede ser un
    booking maritimo o una guia aerea, y sin el contexto un booking de Maersk
    de 9 digitos se clasifica como HAWB, que es absurdo en un envio maritimo.
    """
    ref = ref.strip().upper().replace("-", "").replace(" ", "")
    res: dict = {"referencia": ref, "tipo": None, "valido": False, "notas": []}

    m = RE_CONTENEDOR.match(ref)
    if m:
        esperado = digito_iso6346(ref)
        real = int(m.group(4))
        res["tipo"] = "CONTENEDOR"
        res["propietario"] = m.group(1)
        res["valido"] = esperado == real
        if res["valido"]:
            res["notas"].append("ISO 6346 correcto (digito de control " + str(real) + ")")
        else:
            res["notas"].append("digito de control " + str(real) + ", deberia ser "
                                + str(esperado) + " - error de transcripcion")
        return res

    if RE_SOLO_DIGITOS.match(ref):
        if con_contenedor:
            # Venia junto a un contenedor: es el booking de la naviera, no una guia.
            res["tipo"] = "BOOKING"
            res["valido"] = True
            res["notas"].append("serie de " + str(len(ref)) + " digitos emparejada con un "
                                "contenedor: es el booking maritimo. No lleva digito de "
                                "control verificable en local")
            return res

        # Un MAWB son 11 digitos. Con 10, hay dos hipotesis que probar.
        candidatos = [ref] if len(ref) == 11 else ([ref.zfill(11)] if len(ref) == 10 else [])
        for cand in candidatos:
            prefijo, serie, control = cand[:3], cand[3:10], int(cand[10])
            aerolinea = aerolineas.get(prefijo)
            if aerolinea and digito_mawb(serie) == control:
                res["tipo"] = "MAWB"
                res["valido"] = True
                res["prefijo"] = prefijo
                res["aerolinea"] = aerolinea.get("name")
                res["iata"] = aerolinea.get("iata")
                if cand != ref:
                    res["notas"].append("se restauro un cero a la izquierda que Excel "
                                        "se habia comido: " + ref + " -> " + cand)
                    res["referencia_corregida"] = cand
                res["notas"].append("prefijo " + prefijo + " = " + str(aerolinea.get("name"))
                                    + "; digito de control " + str(control) + " correcto")
                return res

        # No cuadra como MAWB. Decir QUE se probo y por que fallo cada cosa:
        # es lo unico accionable para ir a pedirle el numero bueno al agente.
        res["tipo"] = "PROBABLE_HAWB"
        res["notas"].append("tiene " + str(len(ref)) + " digitos; un MAWB son 11")

        if len(ref) == 10:
            cero = ref.zfill(11)
            duenno = aerolineas.get(cero[:3])
            if duenno:
                res["notas"].append("probado con un cero delante (" + cero + "): prefijo "
                                    + cero[:3] + " = " + str(duenno.get("name")) + ", pero el "
                                    "digito de control seria " + str(digito_mawb(cero[3:10]))
                                    + " y trae " + cero[10])
            else:
                res["notas"].append("probado con un cero delante (" + cero + "): el prefijo "
                                    + cero[:3] + " no esta en el catalogo")
            falta = aerolineas.get(ref[:3])
            if falta:
                res["notas"].append("probado como MAWB sin su digito de control: prefijo "
                                    + ref[:3] + " = " + str(falta.get("name"))
                                    + ", quedaria " + ref + str(digito_mawb(ref[3:10])))
            else:
                res["notas"].append("probado como MAWB sin su digito de control: el prefijo "
                                    + ref[:3] + " tampoco esta en el catalogo")

        if len(ref) == 11:
            if ref[:3] not in aerolineas:
                res["notas"].append("el prefijo " + ref[:3] + " no esta en el catalogo")
            else:
                serie, control = ref[3:10], int(ref[10])
                res["notas"].append("el prefijo " + ref[:3] + " si existe, pero el digito de "
                                    "control es " + str(control) + " y deberia ser "
                                    + str(digito_mawb(serie)))

        res["notas"].append("ninguna hipotesis cuadra: es un HAWB del agente de carga. "
                            "Pedirle el MAWB o la correspondencia HAWB/MAWB (TASK-30)")
        return res

    m = RE_BL_SCAC.match(ref)
    if m:
        res["tipo"] = "BL_O_BOOKING"
        res["scac"] = m.group(1)
        res["valido"] = True
        res["notas"].append("cuatro letras de naviera (" + m.group(1) + ") mas serie; "
                            "no lleva digito de control verificable en local")
        return res

    res["tipo"] = "BOOKING"
    res["valido"] = True
    res["notas"].append("serie numerica sin prefijo de naviera: booking. No hay nada "
                        "que validar en local; lo confirma el proveedor")
    return res


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida referencias de embarque en local")
    parser.add_argument("referencias", nargs="*", help="referencias; acepta 'booking/contenedor'")
    parser.add_argument("--archivo", type=Path, help="archivo con una referencia por linea")
    args = parser.parse_args()

    crudas: list[str] = list(args.referencias)
    if args.archivo:
        crudas += [ln for ln in args.archivo.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not crudas:
        parser.error("hay que pasar al menos una referencia")

    # Los pares "booking/contenedor" vienen juntos: se parten y se validan aparte.
    # Se conserva el emparejamiento: si en la misma celda hay un contenedor,
    # la otra parte es el booking de esa naviera y no una guia aerea.
    sueltas: list[tuple[str, bool]] = []
    for c in crudas:
        partes = [p.strip() for p in re.split(r"[/,;]", c) if p.strip()]
        hay_contenedor = any(RE_CONTENEDOR.match(p.upper().replace("-", "")) for p in partes)
        sueltas.extend((p, hay_contenedor) for p in partes)

    aerolineas = cargar_aerolineas()
    print(SEP)
    print(" TrackIn - TASK-28 Fase 3b: validacion local de referencias")
    print(SEP)
    print("  Catalogo de aerolineas: "
          + (str(len(aerolineas)) + " prefijos" if aerolineas
             else "NO disponible - correr antes la fase 2"))
    print("  Referencias a validar : " + str(len(sueltas)))
    print(SUB)

    resultados = [clasificar(r, aerolineas, emparejada) for r, emparejada in sueltas]
    for r in resultados:
        marca = "OK  " if r["valido"] else "REV "
        print("  [" + marca + "] " + r["referencia"].ljust(16) + r["tipo"])
        for n in r["notas"]:
            print("           " + n)

    revisar = [r for r in resultados if not r["valido"]]
    print(SEP)
    print("  RESUMEN")
    print(SEP)
    tipos: dict[str, int] = {}
    for r in resultados:
        tipos[r["tipo"]] = tipos.get(r["tipo"], 0) + 1
    for t, n in sorted(tipos.items()):
        print("  " + t.ljust(18) + str(n))
    print()
    print("  Utilizables para el spike : " + str(len(resultados) - len(revisar)))
    print("  Para revision             : " + str(len(revisar)))
    print(SEP)

    save_evidence("task28", "04_referencias.json", {
        "spike": "TASK-28",
        "fase": "3b-validacion-local",
        "sin_llamadas_externas": True,
        "prefijos_en_catalogo": len(aerolineas),
        "resultados": resultados,
        "generado": utc_now(),
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
