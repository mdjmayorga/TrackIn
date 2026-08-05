# ===========================================================================
# TrackIn backend — build multi-etapa.
#
#   deps    -> compila las dependencias a wheels (etapa descartable)
#   builder -> imagen de desarrollo: wheels + herramientas de dev, hot reload
#   runtime -> imagen final: solo dependencias de ejecución, usuario no-root
#
# Construir explícitamente una etapa:
#   docker build --target runtime -t trackin-backend .
# ===========================================================================

# --------------------------------------------------------------------------
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# --------------------------------------------------------------------------
# deps: compila wheels una sola vez para reutilizarlas en builder y runtime.
# --------------------------------------------------------------------------
FROM base AS deps

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./
RUN pip wheel --wheel-dir /wheels -r requirements-dev.txt

# --------------------------------------------------------------------------
# builder: imagen de desarrollo. Trae pytest/ruff/mypy y corre con --reload.
# El código llega por bind mount desde docker-compose.dev.yml.
# --------------------------------------------------------------------------
FROM base AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=deps /wheels /wheels
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-index --find-links=/wheels -r requirements-dev.txt \
    && rm -rf /wheels

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# --------------------------------------------------------------------------
# runtime: imagen final, mínima y sin herramientas de desarrollo.
# --------------------------------------------------------------------------
FROM base AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=deps /wheels /wheels
COPY requirements.txt ./
RUN pip install --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

# Nunca correr la API como root.
RUN useradd --create-home --uid 1000 trackin \
    && chown -R trackin:trackin /app
USER trackin

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
