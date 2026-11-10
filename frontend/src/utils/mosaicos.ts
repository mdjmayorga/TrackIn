/**
 * El fondo de los mapas del panel: de dónde salen los mosaicos y su atribución
 * (`PROD-05`). Ver `MapaBase`.
 *
 * Por omisión, OpenStreetMap con la URL **sin** el subdominio `{s}`: la política
 * de uso vigente solo admite `tile.openstreetmap.org`. Pasar al plan B (Stadia
 * Maps Starter, docs/deployment.md §5) es cambiar `VITE_MOSAICOS_URL` y
 * `VITE_MOSAICOS_ATRIBUCION` y reconstruir el panel, sin tocar el código.
 */

export const MOSAICOS_OSM = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
export const ATRIBUCION_OSM =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'

export interface Mosaicos {
  url: string
  atribucion: string
}

/**
 * Una variable vacía cuenta como no definida: docker-compose pasa `""` cuando
 * el servidor no la configura, y el mapa no puede quedarse sin fondo por eso.
 * Si se cambia la URL y no la atribución, se conserva la de OpenStreetMap: todo
 * proveedor de mosaicos con datos de OSM la exige igual.
 */
export function mosaicos(
  url = import.meta.env.VITE_MOSAICOS_URL,
  atribucion = import.meta.env.VITE_MOSAICOS_ATRIBUCION,
): Mosaicos {
  return {
    url: url?.trim() || MOSAICOS_OSM,
    atribucion: atribucion?.trim() || ATRIBUCION_OSM,
  }
}
