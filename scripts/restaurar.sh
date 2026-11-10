#!/usr/bin/env bash
#
# TrackIn: restaurar la base desde un respaldo (`PROD-07`, docs/deployment.md §8).
#
# Se corre en el servidor, desde la raíz del repositorio:
#
#   bash scripts/restaurar.sh respaldos/trackin-20261124-020000.dump
#   bash scripts/restaurar.sh --si <archivo>      # sin pedir confirmación
#
# Reemplaza la base ENTERA por la del respaldo. Antes de tocarla:
#   1. comprueba que el archivo se pueda leer;
#   2. respalda la base actual (`respaldar.sh antes-de-restaurar`), por si el
#      archivo elegido no era el correcto.
# Después detiene la API y el worker, borra y recrea la base, restaura en una
# sola transacción (o todo o nada), vuelve a levantar los servicios y espera a
# que /health diga "ok".
#
# Lo registrado después del respaldo se pierde: por eso pide confirmación.

set -euo pipefail

ENV_FILE="${ENV_FILE:-.env.produccion}"
DC=(docker compose --env-file "$ENV_FILE")
DIR_SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
falla() { log "ERROR: $*" >&2; exit 1; }

_valor() { # igual que en respaldar.sh
  local v
  v=$(grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -n1 | cut -d= -f2- | tr -d '\r"'"'" || true)
  printf '%s' "${v:-${2:-}}"
}

_conteos() { # pedidos, cuentas y bitácora: lo que tiene que volver completo
  local p c b
  # Solo ASCII en el SQL: no depende de la codificación de la terminal.
  IFS='|' read -r p c b < <("${DC[@]}" exec -T postgres psql -U "$pg_user" -d "$pg_db" -Atc "
    SELECT (SELECT count(*) FROM pedidos_transito), (SELECT count(*) FROM usuarios),
           (SELECT count(*) FROM auditoria_intervenciones)" | tr -d '\r')
  printf 'pedidos: %s, cuentas: %s, bitácora: %s' "$p" "$c" "$b"
}

si=false
if [[ "${1:-}" == "--si" ]]; then si=true; shift; fi
archivo="${1:-}"
[[ -n "$archivo" ]] || falla "uso: bash scripts/restaurar.sh [--si] <archivo.dump>"
[[ -s "$archivo" ]] || falla "no existe o está vacío: $archivo"
[[ -f "$ENV_FILE" ]] || falla "no existe $ENV_FILE: correr desde la raíz del repositorio"

pg_user=$(_valor POSTGRES_USER trackin)
pg_db=$(_valor POSTGRES_DB trackin)
puerto=$(_valor TRACKIN_PUERTO 8080)

log "Levantando postgres"
"${DC[@]}" up -d postgres > /dev/null
for _ in $(seq 1 30); do
  "${DC[@]}" exec -T postgres pg_isready -U "$pg_user" -d postgres -q && break
  sleep 2
done
"${DC[@]}" exec -T postgres pg_isready -U "$pg_user" -d postgres -q \
  || falla "postgres no responde"

"${DC[@]}" exec -T postgres pg_restore --list < "$archivo" > /dev/null \
  || falla "pg_restore no puede leer $archivo"

if ! $si; then
  printf '\n  Se va a REEMPLAZAR la base %s por %s.\n' "$pg_db" "$archivo"
  printf '  Lo registrado después de ese respaldo se pierde. Antes se respalda la base actual.\n'
  printf '  Escribir "restaurar" para seguir: '
  read -r respuesta
  [[ "$respuesta" == "restaurar" ]] || falla "cancelado, no se tocó nada"
fi

log "Respaldando la base actual antes de reemplazarla"
ENV_FILE="$ENV_FILE" bash "$DIR_SCRIPTS/respaldar.sh" antes-de-restaurar \
  || falla "no se pudo respaldar la base actual; no se tocó nada"

log "Deteniendo la API y el worker"
"${DC[@]}" stop backend worker > /dev/null

# Desde aquí la base queda a medias si algo falla: se avisa cómo seguir.
trap 'log "La restauración no terminó. La API y el worker quedaron detenidos; el respaldo previo está en respaldos/trackin-antes-de-restaurar-*.dump" >&2' ERR

log "Recreando la base $pg_db"
"${DC[@]}" exec -T postgres dropdb -U "$pg_user" --if-exists --force "$pg_db"
"${DC[@]}" exec -T postgres createdb -U "$pg_user" -O "$pg_user" -T template0 "$pg_db"

log "Restaurando $archivo"
"${DC[@]}" exec -T postgres pg_restore -U "$pg_user" -d "$pg_db" \
  --exit-on-error --single-transaction < "$archivo"
log "Restaurado: $(_conteos)"

trap - ERR
log "Levantando la API y el worker"
"${DC[@]}" up -d backend worker > /dev/null
for _ in $(seq 1 60); do
  if curl -fsS "http://localhost:${puerto}/health" 2>/dev/null | grep -q '"status":"ok"'; then
    log "Listo: /health dice ok"
    exit 0
  fi
  sleep 2
done
falla "la base se restauró, pero /health no dice ok en 2 minutos: revisar ${DC[*]} logs backend"
