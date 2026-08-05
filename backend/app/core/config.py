"""Configuración de la aplicación, leída del entorno / archivo .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import computed_field
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
    OPENSKY_USERNAME: str | None = None
    OPENSKY_PASSWORD: str | None = None

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


@lru_cache
def get_settings() -> Settings:
    """Settings cacheados: se leen del entorno una sola vez por proceso."""
    return Settings()


settings = get_settings()
