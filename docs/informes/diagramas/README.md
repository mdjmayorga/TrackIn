# Diagramas de los informes

Fuentes de los diagramas del segundo informe de avance y del informe final. Las imágenes se generan con
matplotlib; para corregir un texto se edita el script y se vuelve a correr.

| Script | Genera | Figuras del Informe 2 |
|---|---|---|
| `diagramas.py` | `img/arquitectura.png`, `img/subsistemas.png`, `img/estados.png`, `img/secuencia.png`, `img/er.png`, `img/despliegue.png` | 2.1, 2.2, 2.3, 2.11, 2.12 y 2.13 |
| `cronograma.py` | `Cronograma_TrackIn.xml` (Microsoft Project) e `img/g1.png` a `img/g4.png` | 4.1 a 4.4 |

Para el informe final hay una versión de cada script, que no toca la del Informe 2:

| Script | Genera | Figuras del informe final |
|---|---|---|
| `diagramas_final.py` | `img/final_arquitectura.png`, `img/final_subsistemas.png`, `img/final_estados.png`, `img/final_secuencia.png`, `img/final_er.png` (17 tablas), `img/final_despliegue.png` | 3.1 a 3.3, 3.14 a 3.16 |
| `cronograma_final.py` | `Cronograma_TrackIn_final.xml` e `img/final_g0.png` a `img/final_g4.png` | 3.17 a 3.21 |

## Cómo regenerarlos

Requiere Python con matplotlib (en este equipo, el Python 3.12). En PowerShell:

```powershell
cd docs\informes\diagramas
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" diagramas.py
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" cronograma.py
```

En Git Bash, la misma ruta se escribe `"$LOCALAPPDATA/Programs/Python/Python312/python.exe"`, sin el `&`.

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
