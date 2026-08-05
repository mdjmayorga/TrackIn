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
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# --------------------------------------------------------------------------
# runtime: nginx sirviendo los estáticos.
# --------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1
CMD ["nginx", "-g", "daemon off;"]
