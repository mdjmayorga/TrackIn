#!/usr/bin/env bash
#
# TrackIn: respaldo de la base con retención (`PROD-07`, docs/deployment.md §8).
#
# Se corre en el servidor, desde la raíz del repositorio:
#
#   bash scripts/respaldar.sh                    # respaldo programado
#   bash scripts/respaldar.sh antes-de-v1.1.0    # respaldo con nombre, antes de actualizar
#
# Deja un `pg_dump -Fc` en $RESPALDOS_DIR, comprueba que se pueda leer, lo copia a
# $RESPALDOS_COPIA si TI definió una copia fuera del servidor, y borra los
# respaldos programados de más de $RESPALDOS_DIAS días. Los que llevan nombre no
# se borran solos: son los que permiten volver atrás una actualización.
#
# Termina con código distinto de 0 si algo falla, para que cron (o quien lo
# vigile) se entere. No borra nada viejo si el respaldo nuevo falló.
#
# Variables (todas opcionales):
#   ENV_FILE         .env.produccion
#   RESPALDOS_DIR    respaldos
#   RESPALDOS_DIAS   14
#   RESPALDOS_COPIA  vacía: sin copia fuera del servidor

set -euo pipefail

ENV_FILE="${ENV_FILE:-.env.produccion}"
RESPALDOS_DIR="${RESPALDOS_DIR:-respaldos}"
RESPALDOS_DIAS="${RESPALDOS_DIAS:-14}"
RESPALDOS_COPIA="${RESPALDOS_COPIA:-}"
DC=(docker compose --env-file "$ENV_FILE")

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
falla() { log "ERROR: $*" >&2; exit 1; }

# _valor CLAVE [omisión]: lee una variable de $ENV_FILE sin ejecutarlo.
_valor() {
  local v
  v=$(grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -n1 | cut -d= -f2- | tr -d '\r"'"'" || true)
  printf '%s' "${v:-${2:-}}"
}

[[ -f "$ENV_FILE" ]] || falla "no existe $ENV_FILE: correr desde la raíz del repositorio"
[[ "$RESPALDOS_DIAS" =~ ^[1-9][0-9]*$ ]] || falla "RESPALDOS_DIAS tiene que ser un entero positivo"

etiqueta="${1:-}"
if [[ -n "$etiqueta" && ! "$etiqueta" =~ ^[A-Za-z0-9._-]+$ ]]; then
  falla "el nombre del respaldo solo admite letras, números, punto, guion y guion bajo"
fi

pg_user=$(_valor POSTGRES_USER trackin)
pg_db=$(_valor POSTGRES_DB trackin)
mkdir -p "$RESPALDOS_DIR"

# Los programados empiezan con la fecha (trackin-2026...); los que llevan nombre,
# con el nombre. La retención solo mira los primeros.
sello=$(date +%Y%m%d-%H%M%S)
archivo="$RESPALDOS_DIR/trackin-${etiqueta:+$etiqueta-}$sello.dump"
parcial="$archivo.parcial"
trap 'rm -f "$parcial"' EXIT

log "Respaldando la base $pg_db en $archivo"
"${DC[@]}" exec -T postgres pg_dump -U "$pg_user" -d "$pg_db" -Fc > "$parcial" \
  || falla "pg_dump falló (¿está levantado el servicio postgres?)"
[[ -s "$parcial" ]] || falla "el respaldo quedó vacío"

# Un respaldo que pg_restore no puede leer no sirve: se comprueba antes de darlo
# por bueno, leyendo su índice con el mismo pg_restore que lo va a restaurar.
"${DC[@]}" exec -T postgres pg_restore --list < "$parcial" > /dev/null \
  || falla "pg_restore no puede leer el respaldo"
mv "$parcial" "$archivo"

pedidos=$("${DC[@]}" exec -T postgres psql -U "$pg_user" -d "$pg_db" -Atc \
  "SELECT count(*) FROM pedidos_transito" 2>/dev/null | tr -d '\r' || echo "?")
log "Listo: $(du -h "$archivo" | cut -f1), $pedidos pedidos"

if [[ -n "$RESPALDOS_COPIA" ]]; then
  [[ -d "$RESPALDOS_COPIA" ]] || falla "no existe la carpeta de copia $RESPALDOS_COPIA"
  cp "$archivo" "$RESPALDOS_COPIA/" || falla "no se pudo copiar a $RESPALDOS_COPIA"
  log "Copiado a $RESPALDOS_COPIA"
fi

# Retención: solo después de un respaldo bueno, y solo los programados.
borrados=$(find "$RESPALDOS_DIR" -maxdepth 1 -type f -name 'trackin-[0-9]*.dump' \
  -mmin +$((RESPALDOS_DIAS * 24 * 60)) -print -delete | wc -l)
log "Retención de $RESPALDOS_DIAS días: $borrados respaldo(s) viejo(s) borrado(s)"
