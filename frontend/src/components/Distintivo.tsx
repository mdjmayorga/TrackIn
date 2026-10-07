/** La pastilla de color de la grilla, siempre con su texto. */
export function Distintivo({ texto, clases }: { texto: string; clases: string }) {
  return (
    <span
      className={`inline-block w-[5.5rem] rounded px-1 py-0.5 text-center text-[11px] font-medium ${clases}`}
    >
      {texto}
    </span>
  )
}
