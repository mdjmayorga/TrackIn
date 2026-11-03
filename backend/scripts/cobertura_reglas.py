"""Cobertura de las reglas de negocio de la §7 del SRS — `TASK-06`, RNF-18.

    pytest                                # deja los datos en .coverage
    python scripts/cobertura_reglas.py    # el informe por regla; falla bajo el 70 %

RNF-18 pide que las pruebas de las reglas de cálculo cubran más del 70 %. La
cobertura global del backend (~97 %) lo dice de sobra, pero mezcla todo: este
informe mide **solo los módulos que implementan cada regla** (RN-01 a RN-14) y
dice qué pruebas la ejercitan, para poder mostrarlo regla por regla.

Lo corre el CI después de `pytest`.
"""

from __future__ import annotations

import sys
from pathlib import Path

from coverage import Coverage
from coverage.exceptions import NoDataError

BACKEND_DIR = Path(__file__).resolve().parents[1]

#: El mínimo de RNF-18.
MINIMO = 70.0

#: Regla → (qué dice, módulos que la implementan, pruebas que la ejercitan).
REGLAS: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "RN-01": (
        "Fecha proyectada = ETA o ATA + lead time + ajuste",
        ("services/proyeccion.py", "services/recalculo.py"),
        ("test_proyeccion", "test_recalculo", "test_intervenciones", "test_flujo_completo"),
    ),
    "RN-02": (
        "Sin tracking",
        ("services/estado.py", "services/asociacion.py"),
        ("test_estado", "test_asociacion", "test_flujo_completo"),
    ),
    "RN-03": (
        "En origen",
        ("services/estado.py", "services/asociacion.py"),
        ("test_estado", "test_asociacion", "test_flujo_completo"),
    ),
    "RN-04": (
        "En tránsito",
        ("services/estado.py", "services/rastreo/shipsgo.py"),
        ("test_estado", "test_shipsgo", "test_flujo_completo"),
    ),
    "RN-05": (
        "En destino: llegada reportada por la fuente o inferida",
        (
            "services/arribo.py",
            "services/rastreo/colector_shipsgo.py",
            "services/rastreo/colector_tica.py",
        ),
        ("test_arribo", "test_colector_shipsgo", "test_colector_tica", "test_flujo_completo"),
    ),
    "RN-06": (
        "En proceso aduanal",
        ("services/estado.py", "services/intervenciones.py"),
        ("test_estado", "test_intervenciones", "test_flujo_completo"),
    ),
    "RN-07": (
        "A tiempo",
        ("services/estado.py",),
        ("test_estado", "test_recalculo", "test_flujo_completo"),
    ),
    "RN-08": (
        "En riesgo",
        ("services/estado.py",),
        ("test_estado", "test_recalculo"),
    ),
    "RN-09": (
        "Retrasado",
        ("services/estado.py",),
        ("test_estado", "test_recalculo", "test_intervenciones"),
    ),
    "RN-10": (
        "Cerrado: recibido y liberado por Calidad",
        ("services/intervenciones.py",),
        ("test_intervenciones", "test_flujo_completo"),
    ),
    "RN-11": (
        "Umbral de En riesgo configurable",
        ("services/parametros.py", "services/estado.py"),
        ("test_parametros", "test_estado", "test_recalculo"),
    ),
    "RN-12": (
        "Lead time por destino (uno solo, decisión del 25/08)",
        ("services/destinos.py",),
        ("test_destinos", "test_recalculo"),
    ),
    "RN-13": (
        "Estados terminales: no se recalculan ni se consultan",
        ("services/estado.py", "services/planificador.py", "services/intervenciones.py"),
        ("test_estado", "test_planificador", "test_intervenciones", "test_flujo_completo"),
    ),
    "RN-14": (
        "Lo manual y lo ocurrido mandan sobre lo estimado",
        ("services/proyeccion.py", "services/eta_estimada.py", "services/intervenciones.py"),
        ("test_proyeccion", "test_eta_estimada", "test_eta_manual", "test_intervenciones"),
    ),
}


def _medir(cobertura: Coverage, modulo: str) -> tuple[int, int]:
    """(líneas ejecutables, líneas sin cubrir) de un módulo de `app/`."""
    _, ejecutables, _, faltan, _ = cobertura.analysis2(str(BACKEND_DIR / "app" / modulo))
    return len(ejecutables), len(faltan)


def principal() -> int:
    cobertura = Coverage(data_file=str(BACKEND_DIR / ".coverage"))
    cobertura.load()
    medidos: dict[str, tuple[int, int]] = {}
    try:
        for _, modulos, _ in REGLAS.values():
            for modulo in modulos:
                if modulo not in medidos:
                    medidos[modulo] = _medir(cobertura, modulo)
    except NoDataError:
        print("No hay datos de cobertura: corra `pytest` antes.", file=sys.stderr)
        return 1

    print(f"{'Regla':<6} {'Cobertura':>9}  Qué dice · pruebas")
    for regla, (texto, modulos, pruebas) in REGLAS.items():
        total = sum(medidos[m][0] for m in modulos)
        faltan = sum(medidos[m][1] for m in modulos)
        porcentaje = 100.0 * (total - faltan) / total if total else 100.0
        print(f"{regla:<6} {porcentaje:>8.1f}%  {texto} · {', '.join(pruebas)}")

    total = sum(t for t, _ in medidos.values())
    faltan = sum(f for _, f in medidos.values())
    global_ = 100.0 * (total - faltan) / total
    print(
        f"\nMódulos de la §7: {len(medidos)}, {total} líneas, {global_:.1f}% cubiertas "
        f"(RNF-18 pide más de {MINIMO:.0f}%)."
    )
    if global_ <= MINIMO:
        print("Por debajo del mínimo de RNF-18.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(principal())
