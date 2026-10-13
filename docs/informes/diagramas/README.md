# Diagramas de los informes

Fuentes de los diagramas del segundo informe de avance. Las imágenes se generan con
matplotlib; para corregir un texto se edita el script y se vuelve a correr.

| Script | Genera | Figuras del Informe 2 |
|---|---|---|
| `diagramas.py` | `img/arquitectura.png`, `img/subsistemas.png`, `img/estados.png`, `img/secuencia.png`, `img/er.png`, `img/despliegue.png` | 2.1, 2.2, 2.3, 2.11, 2.12 y 2.13 |
| `cronograma.py` | `Cronograma_TrackIn.xml` (Microsoft Project) e `img/g1.png` a `img/g4.png` | 4.1 a 4.4 |

## Cómo regenerarlos

Requiere Python con matplotlib (en este equipo, el Python 3.12):

```bash
cd docs/informes/diagramas
"$LOCALAPPDATA/Programs/Python/Python312/python.exe" diagramas.py
"$LOCALAPPDATA/Programs/Python/Python312/python.exe" cronograma.py
```

Después, en Word: clic derecho sobre la figura → **Cambiar imagen** → **Desde un archivo**, y
elegir el PNG nuevo de `img/`. Así se conservan el tamaño y la leyenda.

## Dónde está cada texto

Todo texto visible es una cadena entre comillas en el script. Lo más rápido es buscar en el
archivo una palabra del texto que se quiere corregir.

| Diagrama | Sección de `diagramas.py` |
|---|---|
| Arquitectura | `# 1. Arquitectura conceptual` |
| Subsistemas | `# 2. Subsistemas` (lista `S`) |
| Despliegue | `# 3. Despliegue` |
| Secuencia del worker | `# 4. Secuencia` (listas `part` y `pasos`) |
| Estados del pedido | `# 5. Estados del pedido` (lista `etapas`) |
| Entidad-relación | `# 6. ER` (diccionario `T` con las columnas de cada tabla y lista `rel` con las relaciones) |

En `cronograma.py`, los nombres y fechas de las tareas están en la lista `F` al inicio del
archivo, una tarea por línea: `(nivel, "nombre", "inicio d/m", "fin d/m", hito)`.

**Cuidado con el largo.** Las cajas tienen tamaño fijo: si un texto corregido queda más largo,
puede salirse de la caja. En ese caso conviene partirlo con `\n` o acortarlo.
