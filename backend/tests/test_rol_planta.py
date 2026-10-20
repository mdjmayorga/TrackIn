"""El rol `PLANTA` solo lee — `US-43`.

La pantalla de planta queda desatendida en un lugar común: nada de lo que se
haga desde ella puede escribir. La prueba no enumera los endpoints a mano:
recorre **todas** las rutas de escritura de la API, así que un endpoint nuevo
que olvide su `requiere_rol` hace fallar esta prueba en vez de quedar abierto.
"""

from __future__ import annotations

import re
from typing import get_args

import pytest
from fastapi.routing import APIRoute

from app.main import app
from app.models.enums import ROLES
from app.schemas.usuarios import Rol

#: Lo único que un usuario de planta puede escribir: su propia sesión.
_PROPIAS_DE_LA_SESION = {"/api/v1/auth/login", "/api/v1/auth/logout"}

_ESCRITURAS = sorted(
    (metodo, ruta.path)
    for ruta in app.routes
    if isinstance(ruta, APIRoute) and ruta.path.startswith("/api/v1")
    for metodo in ruta.methods - {"GET", "HEAD", "OPTIONS"}
    if ruta.path not in _PROPIAS_DE_LA_SESION
)


def test_el_contrato_de_la_api_conoce_el_rol() -> None:
    assert get_args(Rol) == ROLES
    assert "PLANTA" in ROLES


def test_hay_escrituras_que_revisar() -> None:
    """Si el recorrido no encontrara rutas, la prueba de abajo pasaría vacía."""
    # 13 al 20/10: intervenciones, referencia, cargas, destinos y usuarios.
    assert len(_ESCRITURAS) >= 10


@pytest.mark.parametrize(("metodo", "ruta"), _ESCRITURAS)
async def test_planta_no_puede_escribir_nada(client, como_rol, metodo, ruta) -> None:
    como_rol("PLANTA")
    url = re.sub(r"\{[^}]+\}", "1", ruta)

    respuesta = await client.request(metodo, url, json={})

    # El 403 sale antes de validar el cuerpo o buscar el pedido: no hace falta
    # que la petición sea válida para comprobar que el rol no pasa.
    assert respuesta.status_code == 403, respuesta.text
    assert "PLANTA" in respuesta.json()["detail"]


async def test_planta_si_lee_quien_es(client, como_rol) -> None:
    como_rol("PLANTA")

    respuesta = await client.get("/api/v1/auth/yo")

    assert respuesta.status_code == 200
    assert respuesta.json()["rol"] == "PLANTA"
