-- ===========================================================================
-- TrackIn — extensiones de base de datos.
--
-- Se ejecuta UNA sola vez, cuando el volumen de datos está vacío y Postgres
-- inicializa el cluster. Si cambiás este archivo después, hay que recrear el
-- volumen para que vuelva a correr:
--     docker compose down -v && docker compose up -d postgres
--
-- La imagen postgis/postgis ya crea `postgis` por su cuenta; lo repetimos con
-- IF NOT EXISTS para que el archivo sea autocontenido y el orden no importe.
-- ===========================================================================

-- Tipos geométricos y geográficos (puertos, rutas, posiciones de buques/aviones).
CREATE EXTENSION IF NOT EXISTS postgis;

-- Genera UUIDs del lado de la base (gen_random_uuid).
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Búsqueda por similitud de texto: útil para matchear nombres de proveedores,
-- puertos y navieras que llegan con tipeos distintos desde los Excel.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
