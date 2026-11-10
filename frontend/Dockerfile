# ===========================================================================
# TrackIn frontend — build multi-etapa.
#
#   builder -> dev server de Vite con hot reload (docker-compose.dev.yml)
#   runtime -> bundle estático servido por nginx
#
# Ojo: VITE_API_URL se resuelve en TIEMPO DE BUILD para la etapa runtime,
# porque Vite la embebe en el bundle. Si cambia la URL de la API hay que
# reconstruir la imagen, no solo reiniciar el contenedor.
# ===========================================================================

# --------------------------------------------------------------------------
FROM node:22-alpine AS base
WORKDIR /app
ENV CI=true

# --------------------------------------------------------------------------
# deps: instala node_modules una sola vez y las cachea mientras no cambien
# package.json ni package-lock.json.
# --------------------------------------------------------------------------
FROM base AS deps
COPY package.json package-lock.json* ./
RUN npm ci

# --------------------------------------------------------------------------
# builder: imagen de desarrollo. El código llega por bind mount.
# --------------------------------------------------------------------------
FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# --------------------------------------------------------------------------
# build: compila el bundle de producción.
# --------------------------------------------------------------------------
FROM builder AS build
# Vacía por omisión: el panel llama a la API en su mismo origen, y nginx la
# reenvía (nginx.conf). Solo se completa si la API vive en otro dominio.
ARG VITE_API_URL=
# Opcional: el mapa en vivo de ShipsGo en el detalle. Vacío, usa el mapa propio.
ARG VITE_SHIPSGO_EMBED_TOKEN=
# Opcionales: el fondo de los mapas (`PROD-05`). Vacías, OpenStreetMap.
ARG VITE_MOSAICOS_URL=
ARG VITE_MOSAICOS_ATRIBUCION=
ENV VITE_API_URL=$VITE_API_URL \
    VITE_SHIPSGO_EMBED_TOKEN=$VITE_SHIPSGO_EMBED_TOKEN \
    VITE_MOSAICOS_URL=$VITE_MOSAICOS_URL \
    VITE_MOSAICOS_ATRIBUCION=$VITE_MOSAICOS_ATRIBUCION
RUN npm run build

# --------------------------------------------------------------------------
# runtime: nginx sirviendo los estáticos.
# --------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Fuera de conf.d/: ahí nginx lo incluiría solo, a nivel `http` (`PROD-11`).
COPY nginx-seguridad.conf /etc/nginx/snippets/seguridad.conf
# La CSP deja pasar las imágenes del dominio de los mosaicos, y ese dominio sale
# de la misma variable que el panel: cambiar de proveedor no deja el mapa gris
# por olvidar la política (`PROD-05`). Solo HTTPS y sin `{s}`: la CSP necesita
# un dominio fijo.
ARG VITE_MOSAICOS_URL=
RUN set -eu; \
    url="$VITE_MOSAICOS_URL"; \
    [ -n "$url" ] || url="https://tile.openstreetmap.org/"; \
    origen="$(printf '%s' "$url" | sed -nE 's#^(https://[^/?{}]+)/.*#\1#p')"; \
    if [ -z "$origen" ]; then \
        echo "VITE_MOSAICOS_URL debe empezar con https:// y un dominio fijo, sin {s}: $url" >&2; \
        exit 1; \
    fi; \
    sed -i "s#__MOSAICOS_ORIGEN__#$origen#" /etc/nginx/snippets/seguridad.conf; \
    grep -q "img-src 'self' data: blob: $origen;" /etc/nginx/snippets/seguridad.conf
EXPOSE 80
# 127.0.0.1 y no localhost: en la imagen alpine, localhost resuelve primero a
# ::1 (IPv6) y nginx escucha solo en IPv4, así que el chequeo fallaba con el
# panel funcionando (`PROD-03`, 06/11/2026).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://127.0.0.1/ || exit 1
CMD ["nginx", "-g", "daemon off;"]
