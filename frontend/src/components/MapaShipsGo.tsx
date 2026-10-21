/**
 * El mapa en vivo de ShipsGo para un envío (ShipsGo Embed, 21/10/2026; `US-44`).
 *
 * Muestra el buque o el vuelo, los puertos, la ETA y el trayecto del envío con
 * los datos de ShipsGo, dentro del detalle del pedido. Solo aplica a lo que
 * ShipsGo rastrea —BL, contenedor, booking o MAWB— y que ya está dado de alta
 * en la cuenta: la HAWB la sigue TICA, que no tiene mapa. Para el resto queda
 * el mapa propio (`MapaBase`).
 *
 * **El token del Embed no es el de la API.** Sirve solo para mostrar el mapa,
 * va en el navegador (`VITE_SHIPSGO_EMBED_TOKEN`) y lo protege la lista de
 * «Allowed HTTP Origins» de la cuenta: sin el dominio de TrackIn en esa lista,
 * el mapa no carga. El token de la API, que da de alta y gasta créditos, vive
 * solo en el backend.
 */

export function MapaShipsGo({ url, referencia }: { url: string; referencia: string }) {
  return (
    <section aria-labelledby="titulo-mapa-shipsgo">
      <h2 id="titulo-mapa-shipsgo" className="sr-only">
        Mapa en vivo de ShipsGo
      </h2>
      <iframe
        src={url}
        title={`Mapa en vivo de ShipsGo para ${referencia}`}
        loading="lazy"
        className="h-[28rem] w-full rounded border border-panel-borde bg-panel-mapa"
      />
      <p className="mt-1 text-xs text-slate-500">
        Mapa en vivo de ShipsGo para {referencia}: buque o vuelo, puertos, ETA y trayecto.
      </p>
    </section>
  )
}
