"""Configuración de la aplicación, leída del entorno / archivo .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# app/core/config.py -> app/core -> app -> backend/
BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent


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
    SECRET_KEY: str = "dev-only-insecure-key-change-me"

    # --- CORS ---------------------------------------------------------------
    # Se declara como str (CSV), no como list[str], a propósito: ante un campo
    # de tipo complejo pydantic-settings intenta json.loads() sobre el valor
    # del entorno ANTES de correr cualquier validador, y revienta con un CSV.
    # La lista ya parseada se expone en `cors_origins`.
    BACKEND_CORS_ORIGINS: str = "http://localhost:5173"

    # --- PostgreSQL ---------------------------------------------------------
    POSTGRES_USER: str = "trackin"
    POSTGRES_PASSWORD: str = "trackin"
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

    # --- Validación cruzada -------------------------------------------------
    @model_validator(mode="after")
    def _ztracking_exige_ruta(self) -> Settings:
        """`ztracking` sin ruta es configuración incompleta, no un arranque degradado.

        Mismo criterio que el `Literal` de `INGESTA_ADAPTADOR`: la configuración
        que no se puede cumplir detiene el arranque en vez de dejar el sistema
        en pie sin fuente de pedidos, que es un fallo silencioso.
        """
        if self.INGESTA_ADAPTADOR == "ztracking" and self.ZTRACKING_RUTA is None:
            raise ValueError(
                "INGESTA_ADAPTADOR='ztracking' exige ZTRACKING_RUTA: "
                "indique la ruta del archivo Z-tracking de Logística."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Settings cacheados: se leen del entorno una sola vez por proceso."""
    return Settings()


settings = get_settings()
