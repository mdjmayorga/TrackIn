#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verifica que el diccionario de datos sea consistente con el modelo ER.

El diccionario (`docs/data-dictionary.md`) es una transcripcion del modelo
(`docs/data-model.md`). Cada vez que el modelo cambia, el diccionario puede
quedar desfasado sin que nada avise. Este script compara ambos y falla si
divergen.

Comprueba, para cada tabla que ya tenga diccionario:

  1. Que no falte ningun campo del ER en el diccionario.
  2. Que el diccionario no invente campos que el ER no tiene.
  3. Que el orden de los campos coincida, para que ambos documentos se lean
     en paralelo.
  4. Que el tipo declarado en el diccionario concuerde con el del ER.

Uso:  python scripts/check_docs_model.py
Salida: 0 si todo cuadra, 1 si hay divergencias.
"""

from __future__ import annotations

import io
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELO = os.path.join(RAIZ, "docs", "data-model.md")
DICCIONARIO = os.path.join(RAIZ, "docs", "data-dictionary.md")

# El ER usa nombres de tipo cortos; el diccionario, el tipo PostgreSQL completo.
EQUIVALENCIAS = {
    "bigserial": ["bigserial"],
    "bigint": ["bigint"],
    "integer": ["integer"],
    "varchar": ["varchar"],
    "char": ["char"],
    "text": ["text"],
    "date": ["date"],
    "timestamptz": ["timestamptz"],
    "numeric": ["numeric"],
    "boolean": ["boolean"],
    "jsonb": ["jsonb"],
    "geography": ["geography"],
}


def leer(ruta: str) -> str:
    return io.open(ruta, encoding="utf-8").read()


def campos_del_er(texto: str) -> dict[str, list[tuple[str, str]]]:
    """Extrae {ENTIDAD: [(tipo, campo), ...]} del bloque mermaid erDiagram."""
    bloque = re.search(r"```mermaid\n(.*?)```", texto, re.S)
    if not bloque:
        sys.exit("ERROR: no hay bloque mermaid en el modelo")
    entidades: dict[str, list[tuple[str, str]]] = {}
    actual = None
    for linea in bloque.group(1).split("\n"):
        s = linea.strip()
        if not s or s == "erDiagram":
            continue
        if s == "}":
            actual = None
            continue
        apertura = re.match(r"^([A-Z_][A-Z0-9_]*)\s*\{$", s)
        if apertura:
            actual = apertura.group(1)
            entidades[actual] = []
            continue
        if actual:
            m = re.match(r"^([A-Za-z][\w\[\]()]*)\s+([A-Za-z_]\w*)", s)
            if m:
                entidades[actual].append((m.group(1).lower(), m.group(2)))
    return entidades


def campos_del_diccionario(texto: str) -> dict[str, list[tuple[str, str]]]:
    """Extrae {tabla: [(tipo, campo), ...]} de las tablas de campos."""
    tablas: dict[str, list[tuple[str, str]]] = {}
    actual = None
    for linea in texto.split("\n"):
        cabecera = re.match(r"^##\s+\d+\.\s+`([a-z_]+)`\s*$", linea)
        if cabecera:
            actual = cabecera.group(1)
            tablas[actual] = []
            continue
        if actual is None:
            continue
        # | 7 | `campo` | `TIPO(...)` | nulo | clave | dominio | descripcion |
        fila = re.match(
            r"^\|\s*\d+\s*\|\s*`([a-z_]+)`\s*\|\s*`([A-Za-z]+)[^`]*`", linea
        )
        if fila:
            tablas[actual].append((fila.group(2).lower(), fila.group(1)))
    return {t: c for t, c in tablas.items() if c}


def comparar(tabla, er, dicc, problemas):
    campos_er = [c for _, c in er]
    campos_dc = [c for _, c in dicc]

    faltan = [c for c in campos_er if c not in campos_dc]
    sobran = [c for c in campos_dc if c not in campos_er]
    for c in faltan:
        problemas.append("%s: el campo `%s` esta en el ER y no en el diccionario" % (tabla, c))
    for c in sobran:
        problemas.append("%s: el campo `%s` esta en el diccionario y no en el ER" % (tabla, c))
    if faltan or sobran:
        return

    if campos_er != campos_dc:
        problemas.append(
            "%s: el orden de los campos difiere\n      ER  : %s\n      dicc: %s"
            % (tabla, ", ".join(campos_er), ", ".join(campos_dc))
        )

    tipos_er = dict((c, t) for t, c in er)
    for tipo_dc, campo in dicc:
        tipo_er = tipos_er.get(campo)
        if tipo_er is None:
            continue
        admitidos = EQUIVALENCIAS.get(tipo_er, [tipo_er])
        if tipo_dc not in admitidos:
            problemas.append(
                "%s.%s: tipo `%s` en el diccionario contra `%s` en el ER"
                % (tabla, campo, tipo_dc, tipo_er)
            )


def main() -> int:
    er = campos_del_er(leer(MODELO))
    dicc = campos_del_diccionario(leer(DICCIONARIO))

    problemas: list[str] = []
    revisadas = 0
    for tabla, campos in sorted(dicc.items()):
        clave = tabla.upper()
        if clave not in er:
            problemas.append("%s: tiene diccionario pero no aparece en el ER" % tabla)
            continue
        revisadas += 1
        comparar(tabla, er[clave], campos, problemas)

    sin_diccionario = sorted(e.lower() for e in er if e.lower() not in dicc)

    print("Tablas en el ER          : %d" % len(er))
    print("Tablas con diccionario   : %d  (%s)" % (revisadas, ", ".join(sorted(dicc))))
    if sin_diccionario:
        print("Pendientes de diccionario: %s" % ", ".join(sin_diccionario))

    if problemas:
        print("\nDIVERGENCIAS (%d):" % len(problemas))
        for p in problemas:
            print("  - %s" % p)
        return 1

    print("\nOK: el diccionario concuerda con el ER en las tablas revisadas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
