"""Configuración de la aplicación, leída del entorno / archivo .env."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Final, Literal

from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# app/core/config.py -> app/core -> app -> backend/
BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent

#: La clave de desarrollo. Sirve en local; en producción es un secreto conocido.
SECRET_KEY_DE_DESARROLLO: Final = "dev-only-insecure-key-change-me"
#: La contraseña de la base que trae el código. Mismo razonamiento.
PASSWORD_DE_DESARROLLO: Final = "trackin"
#: Un valor copiado tal cual de `.env.example`: `<placeholder>`, `<generar-...>`.
_MARCADOR_DE_PLANTILLA = re.compile(r"^<[^<>]+>$")
#: Credenciales que solo sirven completas. Media pareja no autentica, y sin
#: esta comprobación el fallo aparecería en la primera llamada, no al arrancar.
_PAREJAS: Final = (("OPENSKY_CLIENT_ID", "OPENSKY_CLIENT_SECRET"),)


class Settings(BaseSettings):
    """Settings de TrackIn.

    Precedencia (de menor a mayor): backend/.env  <  .env de la raíz  <
    variables de entorno reales. En Docker no hay archivos .env dentro de la
    imagen: todo llega por `environment:` de docker-compose.
    """

    model_config = SettingsConfigDict(
        # El último archivo de la tupla gana sobre los anteriores.
        env_file=(BACKEND_DIR / ".env", REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # Sin esto, el error de arranque copia la configuración entera
        # —credenciales incluidas— en `input_value`, y termina en un log.
        hide_input_in_errors=True,
    )

    # --- Metadatos de la app ------------------------------------------------
    PROJECT_NAME: str = "TrackIn API"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = (
        "API de tracking logístico para compras internacionales de Laboratorios Gutis."
    )
    API_V1_PREFIX: str = "/api/v1"

    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False

    # --- Seguridad ----------------------------------------------------------
    # Sin uso todavía (no hay autenticación en Sprint 0), pero se valida desde
    # ya para que el despliegue falle temprano si falta.
    SECRET_KEY: str = SECRET_KEY_DE_DESARROLLO

    # --- CORS ---------------------------------------------------------------
    # Se declara como str (CSV), no como list[str], a propósito: ante un campo
    # de tipo complejo pydantic-settings intenta json.loads() sobre el valor
    # del entorno ANTES de correr cualquier validador, y revienta con un CSV.
    # La lista ya parseada se expone en `cors_origins`.
    BACKEND_CORS_ORIGINS: str = "http://localhost:5173"

    # --- PostgreSQL ---------------------------------------------------------
    POSTGRES_USER: str = "trackin"
    POSTGRES_PASSWORD: str = PASSWORD_DE_DESARROLLO
    POSTGRES_DB: str = "trackin_dev"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Si se define, tiene precedencia sobre las POSTGRES_* de arriba.
    DATABASE_URL: str | None = None

    # --- APIs externas (se consumen a partir de sprints posteriores) --------
    AISSTREAM_API_KEY: str | None = None
    # OpenSky retiró la autenticación Basic: hoy es OAuth2 `client_credentials`.
    # TG-11 lo descubrió el 19/08/2026 y renombró las claves en `.env.example`,
    # pero **este archivo se quedó con los nombres viejos** hasta `US-05`. Los
    # valores guardados ya eran las credenciales OAuth2; no hubo que
    # regenerarlas, solo llamarlas por su nombre.
    OPENSKY_CLIENT_ID: str | None = None
    OPENSKY_CLIENT_SECRET: str | None = None

    # ShipsGo, la fuente comercial de las dos vías (`TASK-28`, go del 14/09).
    # Viaja en la cabecera `X-Shipsgo-User-Token`. Sin token el sistema arranca
    # igual: el rastreo comercial queda inactivo y todo lo demás funciona, que
    # es exactamente la situación mientras no haya créditos comprados.
    SHIPSGO_API_TOKEN: str | None = None

    # --- Ingesta de pedidos (TASK-03 / US-31) -------------------------------
    # Fuente desde la que entran las líneas de orden de compra.
    #   ztracking → el archivo de Logística. Vía **oficial** desde el 03/09/2026
    #               (RF-31). Exige ZTRACKING_RUTA.
    #   semilla   → datos de ejemplo en memoria, para desarrollo y demostración.
    #   ninguno   → sin fuente. Es un valor válido, no un error: el sistema
    #               arranca igual y lo reporta en el healthcheck.
    #
    # **Este `Literal` es la autoridad sobre qué nombres existen** (decisión del
    # 22/09/2026, que resuelve la contradicción detectada el 08/09 entre esta
    # validación y las ramas defensivas de `ingesta.registro`). Una errata en la
    # variable de entorno **impide arrancar**, en vez de degradar en silencio a
    # «sin fuente»: un sistema que arranca sin fuente de pedidos por un typo
    # parece sano y no lo está, y el healthcheck reportaría «sin fuente» como si
    # fuera la configuración deseada.
    INGESTA_ADAPTADOR: Literal["ztracking", "semilla", "ninguno"] = "semilla"

    # Ruta del archivo Z-tracking. Obligatoria si INGESTA_ADAPTADOR=ztracking,
    # por el mismo criterio: la configuración incompleta se detiene al arrancar.
    ZTRACKING_RUTA: Path | None = None

    # --- Derivados ----------------------------------------------------------
    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins(self) -> list[str]:
        """Orígenes permitidos por CORS, a partir del CSV del entorno."""
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sqlalchemy_database_uri(self) -> str:
        """DSN async (asyncpg) que consume el engine de SQLAlchemy."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    # --- Validación cruzada (`US-17`, tercer criterio) -----------------------
    def problemas(self) -> list[str]:
        """Todo lo que impide arrancar, con el nombre de la variable y qué hacer.

        Se juntan **todos** antes de fallar: quien configura un servidor no
        debería descubrir los faltantes de a uno, arrancando y volviendo a
        arrancar. Nada de esto se revisa con la base: lo que falta en
        `parametros_sistema` tiene su valor por defecto en el catálogo
        (`services/parametros.py`), así que ahí no puede faltar nada.
        """
        problemas: list[str] = []

        # Un valor copiado de la plantilla parece configurado y no lo está: el
        # token `<placeholder>` de ShipsGo encendería el rastreo con una
        # credencial falsa, y el primer 401 llegaría en el primer ciclo.
        for nombre, valor in self:
            if isinstance(valor, str) and _MARCADOR_DE_PLANTILLA.match(valor.strip()):
                problemas.append(
                    f"{nombre} todavía tiene el valor de la plantilla ({valor}): "
                    "complételo o bórrelo del .env."
                )

        for primera, segunda in _PAREJAS:
            tiene_primera = bool(getattr(self, primera))
            tiene_segunda = bool(getattr(self, segunda))
            if tiene_primera != tiene_segunda:
                falta = segunda if tiene_primera else primera
                presente = primera if tiene_primera else segunda
                problemas.append(f"{falta} falta: {presente} solo sirve con ella.")

        if self.INGESTA_ADAPTADOR == "ztracking" and self.ZTRACKING_RUTA is None:
            # Mismo criterio que el `Literal` de `INGESTA_ADAPTADOR`: la
            # configuración que no se puede cumplir detiene el arranque en vez
            # de dejar el sistema en pie sin fuente de pedidos.
            problemas.append(
                "ZTRACKING_RUTA falta: INGESTA_ADAPTADOR='ztracking' exige "
                "la ruta del archivo Z-tracking de Logística."
            )

        if self.is_production:
            # En desarrollo los valores del código son cómodos; en producción
            # son secretos publicados en el repositorio.
            if self.SECRET_KEY == SECRET_KEY_DE_DESARROLLO:
                problemas.append(
                    "SECRET_KEY falta: en producción no se acepta la clave de desarrollo."
                )
            if not self.DATABASE_URL and self.POSTGRES_PASSWORD == PASSWORD_DE_DESARROLLO:
                problemas.append(
                    "POSTGRES_PASSWORD falta: en producción no se acepta la de "
                    "desarrollo (o defina DATABASE_URL)."
                )
        return problemas

    @model_validator(mode="after")
    def _configuracion_completa(self) -> Settings:
        problemas = self.problemas()
        if problemas:
            raise ValueError(
                "Configuración incompleta; TrackIn no arranca hasta corregir:\n"
                + "\n".join(f"  - {problema}" for problema in problemas)
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Settings cacheados: se leen del entorno una sola vez por proceso."""
    return Settings()


settings = get_settings()
