#!/usr/bin/env bash
#
# TrackIn: vigilancia de /health con aviso por correo (`PROD-08`,
# docs/deployment.md §9).
#
# Se programa en el servidor cada 5 minutos, desde la raíz del repositorio:
#
#   */5 * * * * cd /opt/trackin && bash scripts/vigilar_salud.sh >> vigilancia/vigilar.log 2>&1
#
# Avisa cuando aparece un problema y otra vez cuando se resuelve; mientras sigue
# igual, no repite el aviso. Los problemas que mira:
#
#   - /health no responde (la API o nginx caídos);
#   - la base no está "up";
#   - una fuente (ShipsGo, TICA) lleva más de $AVISO_FUENTE_HORAS degradada;
#   - los créditos de ShipsGo piden atención (cualquier nivel salvo OK);
#   - el contenedor del worker no está corriendo (/health no lo ve: sin
#     worker, las fuentes solo dejan de actualizarse).
#
# El correo sale por SMTP con curl, con las variables AVISO_* de
# $ENV_FILE. Sin AVISO_SMTP_URL el aviso queda solo en el log. Si el envío
# falla, no se da por avisado: se reintenta en la próxima corrida.

set -euo pipefail

ENV_FILE="${ENV_FILE:-.env.produccion}"
DC=(docker compose --env-file "$ENV_FILE")

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
falla() { log "ERROR: $*" >&2; exit 1; }

_valor() { # igual que en respaldar.sh
  local v
  v=$(grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -n1 | cut -d= -f2- | tr -d '\r"'"'" || true)
  printf '%s' "${v:-${2:-}}"
}

[[ -f "$ENV_FILE" ]] || falla "no existe $ENV_FILE: correr desde la raíz del repositorio"

puerto=$(_valor TRACKIN_PUERTO 8080)
url_salud="${VIGILAR_URL:-http://localhost:$puerto/health}"
dir_estado="${VIGILANCIA_DIR:-vigilancia}"
horas_fuente=$(_valor AVISO_FUENTE_HORAS 1)
smtp_url=$(_valor AVISO_SMTP_URL)
smtp_usuario=$(_valor AVISO_SMTP_USUARIO)
smtp_clave=$(_valor AVISO_SMTP_CLAVE)
remitente=$(_valor AVISO_DE)
destinatarios=$(_valor AVISO_PARA)
[[ "$horas_fuente" =~ ^[0-9]+$ ]] || falla "AVISO_FUENTE_HORAS tiene que ser un entero"

mkdir -p "$dir_estado"
estado="$dir_estado/problemas"
touch "$estado"
actual=$(mktemp)
trap 'rm -f "$actual" "$actual.correo"' EXIT

# --- Qué está mal ahora: una línea «clave<TAB>mensaje» por problema ----------

if salud=$(curl -fsS --max-time 15 "$url_salud" 2>&1); then
  # El JSON lo lee el Python del propio backend: el servidor no necesita jq ni
  # Python. Si /health respondió, el contenedor está arriba.
  printf '%s' "$salud" | "${DC[@]}" exec -T backend python -c '
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
horas = int(sys.argv[1])
s = json.load(sys.stdin)
if s.get("database") != "up":
    print("base\tLa base no responde: " + str(s.get("detail") or s.get("database")))
for f in s.get("fuentes") or []:
    edad = f.get("antiguedad_s")
    if f.get("degradada") and (edad is None or edad > horas * 3600):
        nombre = f.get("fuente")
        motivo = f.get("motivo_ultimo_fallo") or f.get("clase_ultimo_fallo")
        hace = "nunca respondió" if edad is None else "último dato bueno hace %.1f h" % (edad / 3600)
        print("fuente:%s\tLa fuente %s está degradada (%s): %s" % (nombre, nombre, hace, motivo))
c = s.get("creditos_shipsgo")
if c and c.get("nivel") != "OK":
    nivel = c.get("nivel")
    print("creditos:%s\tCréditos de ShipsGo, nivel %s: %s" % (nivel, nivel, c.get("mensaje")))
' "$horas_fuente" | tr -d '\r' >> "$actual" \
    || printf 'salud\t/health respondió algo que no se pudo leer\n' >> "$actual"
else
  printf 'api\t/health no responde en %s: %s\n' "$url_salud" "${salud//$'\n'/ }" >> "$actual"
  # Sin /health no se sabe cómo están la base, las fuentes ni los créditos: lo
  # que ya estaba mal sigue contando como mal, no como resuelto.
  grep -vE '^(api|worker)'$'\t' "$estado" >> "$actual" || true
fi

if [[ -z "$("${DC[@]}" ps -q --status running worker 2>/dev/null)" ]]; then
  printf 'worker\tEl contenedor del worker no está corriendo: no se rastrea nada\n' >> "$actual"
fi

# --- Qué cambió desde la corrida anterior -----------------------------------

# _en A B: las líneas de B cuya clave está en A; _fuera A B: las que no.
# FILENAME y no NR==FNR: el estado está vacío en la primera corrida.
_en()    { awk -F'\t' 'FILENAME==ARGV[1] {k[$1]=1; next} ($1 in k)' "$1" "$2"; }
_fuera() { awk -F'\t' 'FILENAME==ARGV[1] {k[$1]=1; next} !($1 in k)' "$1" "$2"; }
nuevos=$(_fuera "$estado" "$actual")
resueltos=$(_fuera "$actual" "$estado")
siguen=$(_en "$estado" "$actual")

if [[ -z "$nuevos" && -z "$resueltos" ]]; then
  [[ -s "$actual" ]] && log "Sin cambios: $(wc -l < "$actual") problema(s) ya avisado(s)"
  exit 0
fi

if [[ -n "$nuevos" ]]; then
  asunto="[TrackIn] Aviso: $(printf '%s\n' "$nuevos" | wc -l | tr -d ' ') problema(s) nuevo(s)"
else
  asunto="[TrackIn] Resuelto: $(printf '%s\n' "$resueltos" | wc -l | tr -d ' ') problema(s)"
fi

_lista() { [[ -n "$1" ]] && printf '%s\n' "$1" | cut -f2- | sed 's/^/  - /'; return 0; }
cuerpo=$(
  printf 'Servidor: %s\nRevisado: %s (%s)\n' "$(hostname)" "$(date '+%Y-%m-%d %H:%M')" "$url_salud"
  [[ -n "$nuevos" ]] && printf '\nProblemas nuevos:\n%s\n' "$(_lista "$nuevos")"
  [[ -n "$siguen" ]] && printf '\nSiguen sin resolver:\n%s\n' "$(_lista "$siguen")"
  [[ -n "$resueltos" ]] && printf '\nResueltos:\n%s\n' "$(_lista "$resueltos")"
  printf '\nQué hacer con cada uno: docs/deployment.md §9 («Qué mirar en /health»).\n'
)

log "$asunto"
printf '%s\n' "$cuerpo" | sed 's/^/    /'

# --- Avisar ------------------------------------------------------------------

if [[ -z "$smtp_url" ]]; then
  log "Sin AVISO_SMTP_URL: el aviso queda solo en este log"
else
  [[ -n "$remitente" && -n "$destinatarios" ]] || falla "faltan AVISO_DE o AVISO_PARA en $ENV_FILE"
  {
    printf 'From: %s\r\n' "$remitente"
    printf 'To: %s\r\n' "$destinatarios"
    # El asunto lleva tildes: va codificado (RFC 2047) para que llegue bien.
    printf 'Subject: =?UTF-8?B?%s?=\r\n' "$(printf '%s' "$asunto" | base64 | tr -d '\n')"
    printf 'Date: %s\r\n' "$(LC_ALL=C date -R)"
    printf 'MIME-Version: 1.0\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: 8bit\r\n\r\n'
    printf '%s\n' "$cuerpo" | sed 's/$/\r/'
  } > "$actual.correo"

  rcpt=()
  IFS=',' read -ra lista <<< "$destinatarios"
  for d in "${lista[@]}"; do rcpt+=(--mail-rcpt "$(printf '%s' "$d" | tr -d ' ')"); done

  # La clave va por la entrada estándar (-K -), no en la línea de comandos: así
  # no aparece en `ps` mientras curl corre.
  if ! { [[ -n "$smtp_usuario" ]] && printf 'user = "%s:%s"\n' "$smtp_usuario" "$smtp_clave"; true; } \
       | curl -sS --max-time 30 -K - --url "$smtp_url" --mail-from "$remitente" "${rcpt[@]}" \
              --upload-file "$actual.correo"; then
    falla "no se pudo enviar el correo por $smtp_url; se reintenta en la próxima corrida"
  fi
  log "Correo enviado a $destinatarios"
fi

# Solo ahora queda como avisado.
cp "$actual" "$estado"
