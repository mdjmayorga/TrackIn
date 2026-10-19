"""Cronograma de la práctica en formato Microsoft Project (MSPDI XML) y Gantt en PNG.

Uso: python cronograma.py
     (escribe Cronograma_TrackIn.xml e img/g1.png a img/g4.png junto a este script)
Fecha de estado: 16/10/2026 (cierre del Sprint 5).
"""
import os
import sys
from datetime import date, timedelta
from xml.sax.saxutils import escape

_AQUI = os.path.dirname(os.path.abspath(__file__))
if len(sys.argv) < 6:
    sys.argv = [sys.argv[0], os.path.join(_AQUI, "Cronograma_TrackIn.xml")] + [
        os.path.join(_AQUI, "img", f"g{k}.png") for k in range(1, 5)]

CORTE = date(2026, 10, 16)

# (nivel, nombre, inicio, fin, hito)
F = [
    (1, "Práctica de Especialidad TrackIn", None, None, 0),
    (2, "Semana de inducción", None, None, 0),
    (3, "Configuración del entorno de desarrollo y del repositorio", "3/8", "5/8", 0),
    (3, "Instalación de PostgreSQL 16 y PostGIS", "6/8", "7/8", 0),
    (3, "Minuta 01 con el profesor asesor", "7/8", "7/8", 1),
    (2, "Sprint 1: Requerimientos y viabilidad técnica", None, None, 0),
    (3, "SRS v0.1", "10/8", "11/8", 0),
    (3, "Levantamiento de requerimientos con las áreas usuarias", "12/8", "14/8", 0),
    (3, "Minuta 02 con el profesor asesor y el supervisor", "14/8", "14/8", 1),
    (3, "SRS v0.2", "14/8", "14/8", 0),
    (3, "Spike técnico TG-10: AISStream", "17/8", "19/8", 0),
    (3, "Spike técnico TG-11: OpenSky Network", "18/8", "19/8", 0),
    (3, "SRS v0.3 con los hallazgos de los spikes", "20/8", "20/8", 0),
    (3, "Product backlog priorizado (TG-18)", "20/8", "21/8", 0),
    (2, "Sprint 2: Análisis y diseño (OE1)", None, None, 0),
    (3, "Modelo de datos (TASK-12 a TASK-15)", "24/8", "25/8", 0),
    (3, "Diccionario de datos (TASK-16 a TASK-19, TASK-24, TASK-26)", "25/8", "26/8", 0),
    (3, "Arquitectura: componentes, despliegue y secuencia (TASK-20 a TASK-22)", "26/8", "27/8", 0),
    (3, "Wireframes y prototipo navegable en Figma (US-34 a US-38, US-41)", "27/8", "2/9", 0),
    (3, "Validación de prototipos con usuarios clave (US-39)", "2/9", "2/9", 1),
    (3, "SRS v0.4 (TASK-25)", "3/9", "4/9", 0),
    (2, "Sprint 3: Persistencia e ingesta (OE2 y OE4)", None, None, 0),
    (3, "Esquema, migraciones y PostGIS (TASK-01, TASK-02)", "7/9", "8/9", 0),
    (3, "Maestros de países y destinos (TASK-29, TASK-31)", "9/9", "9/9", 0),
    (3, "Contrato de referencia e ingesta semilla (TASK-30, TASK-03, US-01)", "10/9", "11/9", 0),
    (3, "Resiliencia, AIS e historial de posiciones (US-02, US-03, US-04)", "14/9", "16/9", 0),
    (3, "Spike de fuentes comerciales (TASK-28)", "14/9", "16/9", 0),
    (3, "Consolidación del Informe 1 (TASK-23)", "17/9", "18/9", 0),
    (2, "Sprint 4: Ingesta real, fuentes comerciales y motor de cálculo", None, None, 0),
    (3, "Carga y validación del archivo Z-tracking (US-31, US-32)", "21/9", "22/9", 0),
    (3, "Motor de cálculo: fecha proyectada, estado y arribo (US-09, US-10, US-11)", "22/9", "23/9", 0),
    (3, "Integración con ShipsGo marítimo y aéreo (US-45, US-46)", "23/9", "24/9", 0),
    (3, "Planificador, OpenSky y ETA estimada (US-07, US-05, US-06, US-08)", "24/9", "25/9", 0),
    (3, "Entrega del primer informe de avance", "25/9", "25/9", 1),
    (3, "Guías hijas por TICA (US-49)", "28/9", "28/9", 0),
    (3, "Reunión de seguimiento con el profesor asesor y la empresa", "28/9", "28/9", 1),
    (3, "Worker de rastreo y salud de las fuentes (US-50, US-51)", "29/9", "30/9", 0),
    (3, "Reunión con Compras y usuarios clave", "29/9", "29/9", 1),
    (3, "Puerto de llegada desde ShipsGo (US-52) y pruebas en vivo", "30/9", "1/10", 0),
    (3, "Revisión y cierre del Sprint 4 con el supervisor", "2/10", "2/10", 1),
    (2, "Sprint 5: Reglas de negocio, API y seguridad", None, None, 0),
    (3, "API REST de pedidos y documentación OpenAPI (US-16, TASK-04)", "5/10", "6/10", 0),
    (3, "Reunión con Compras: prototipo final, ShipsGo y MAWB", "6/10", "6/10", 1),
    (3, "Recálculo y configuración fuera del código (US-12, US-17)", "6/10", "7/10", 0),
    (3, "Reunión con el supervisor: no existirá API de SAP", "7/10", "7/10", 1),
    (3, "Fecha comprometida y puerto de llegada (US-53, US-54)", "7/10", "7/10", 0),
    (3, "Spike Parcels (TASK-32) y maestro de destinos (US-13)", "8/10", "9/10", 0),
    (3, "Autenticación, sesión y roles (US-42)", "9/10", "12/10", 0),
    (3, "Auditoría de intervenciones (US-15)", "12/10", "13/10", 0),
    (3, "Desembarco, paso a aduana y recepción (US-14, US-18)", "13/10", "14/10", 0),
    (3, "Liberación de Calidad y ajuste manual (US-47, US-40)", "14/10", "15/10", 0),
    (3, "Revisión y cierre del Sprint 5 con el supervisor", "16/10", "16/10", 1),
    (2, "Sprint 6: Dashboard web y carga desde la interfaz", None, None, 0),
    (3, "Andamiaje del frontend y grilla de pedidos (TASK-05, US-19)", "19/10", "21/10", 0),
    (3, "Carga del Z-tracking desde la interfaz (US-58)", "21/10", "22/10", 0),
    (3, "Entrega del segundo informe de avance", "23/10", "23/10", 1),
    (3, "Detalle, filtros y cinta de KPIs (US-20, US-21, US-22)", "22/10", "27/10", 0),
    (3, "Semáforo, frescura, próximos arribos y bandeja (US-23, US-24, US-28, US-48)", "27/10", "28/10", 0),
    (3, "Vistas por rol, alta de embarques y saldo de créditos (US-43, US-55, US-57)", "29/10", "30/10", 0),
    (2, "Sprint 7: Mapas, historial y validación de la carga", None, None, 0),
    (3, "Mapa interactivo marítimo (US-25)", "2/11", "4/11", 0),
    (3, "Mapa interactivo aéreo (US-26)", "5/11", "6/11", 0),
    (3, "Información emergente y detalle con país de origen (US-27, US-44)", "9/11", "10/11", 0),
    (3, "Plantilla y validación de formato del Z-tracking (US-59)", "10/11", "11/11", 0),
    (3, "Historial, trayecto y transbordos (US-29, US-30)", "11/11", "12/11", 0),
    (3, "Pantalla de planta y retención del historial (US-33, TASK-10)", "13/11", "13/11", 0),
    (2, "Cierre: Pruebas y documentación", None, None, 0),
    (3, "Pruebas de integración extremo a extremo (TASK-06)", "16/11", "18/11", 0),
    (3, "Manual de instalación y manual de usuario (TASK-07, TASK-08)", "18/11", "19/11", 0),
    (3, "Entrega del informe final", "20/11", "20/11", 1),
    (3, "Guía de despliegue para producción (TASK-09)", "19/11", "20/11", 0),
    (3, "Fin de la práctica y demostración funcional", "21/11", "21/11", 1),
    (2, "Extensión opcional", None, None, 0),
    (3, "Correcciones derivadas de la validación con usuarios", "23/11", "27/11", 0),
    (3, "Traspaso técnico al Centro de Competencias", "30/11", "4/12", 0),
]


def d(s):
    dd, mm = s.split("/")
    return date(2026, int(mm), int(dd))


def habiles(a, b):
    n, cur = 0, a
    while cur <= b:
        n += cur.weekday() < 5
        cur += timedelta(days=1)
    return n


tareas = [dict(niv=n, nombre=nom, ini=d(i) if i else None, fin=d(f) if f else None, hito=h) for n, nom, i, f, h in F]
for i, t in enumerate(tareas):
    t["resumen"] = 0
    if t["ini"]:
        continue
    hijos = []
    for u in tareas[i + 1:]:
        if u["niv"] <= t["niv"]:
            break
        if u["ini"]:
            hijos.append(u)
    t["ini"], t["fin"], t["resumen"] = min(h["ini"] for h in hijos), max(h["fin"] for h in hijos), 1


def avance(t):
    if t["fin"] <= CORTE:
        return 100
    if t["ini"] > CORTE:
        return 0
    return round(100 * habiles(t["ini"], CORTE) / habiles(t["ini"], t["fin"]))


for t in tareas:
    t["pct"] = avance(t)
# avance de los resúmenes ponderado por duración
for i, t in enumerate(tareas):
    if not t["resumen"]:
        continue
    hijos = []
    for u in tareas[i + 1:]:
        if u["niv"] <= t["niv"]:
            break
        if not u["resumen"] and not u["hito"]:
            hijos.append(u)
    tot = sum(habiles(h["ini"], h["fin"]) for h in hijos)
    t["pct"] = round(sum(habiles(h["ini"], h["fin"]) * h["pct"] for h in hijos) / tot) if tot else 0

dur = lambda n: f"PT{n * 8}H0M0S"
dias = "".join(
    f'<WeekDay><DayType>{k}</DayType><DayWorking>{1 if 2 <= k <= 6 else 0}</DayWorking>'
    + ('<WorkingTimes><WorkingTime><FromTime>08:00:00</FromTime><ToTime>12:00:00</ToTime></WorkingTime>'
       '<WorkingTime><FromTime>13:00:00</FromTime><ToTime>17:00:00</ToTime></WorkingTime></WorkingTimes>' if 2 <= k <= 6 else "")
    + "</WeekDay>" for k in range(1, 8))
xml = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
       '<Project xmlns="http://schemas.microsoft.com/project">',
       '<SaveVersion>14</SaveVersion>', '<Name>Cronograma_TrackIn.xml</Name>',
       '<Title>TrackIn - Cronograma de la Practica de Especialidad</Title>',
       '<Author>Mariano de Jesus Mayorga Halabi</Author>', '<Company>Laboratorios Gutis Ltda.</Company>',
       '<Manager>Greivin Mora Ferreto</Manager>', '<ScheduleFromStart>1</ScheduleFromStart>',
       '<StartDate>2026-08-03T08:00:00</StartDate>', '<FinishDate>2026-12-04T17:00:00</FinishDate>',
       f'<CurrentDate>{CORTE:%Y-%m-%d}T17:00:00</CurrentDate>', f'<StatusDate>{CORTE:%Y-%m-%d}T17:00:00</StatusDate>',
       '<CalendarUID>1</CalendarUID>', '<DefaultStartTime>08:00:00</DefaultStartTime>',
       '<DefaultFinishTime>17:00:00</DefaultFinishTime>', '<MinutesPerDay>480</MinutesPerDay>',
       '<MinutesPerWeek>2400</MinutesPerWeek>', '<DaysPerMonth>20</DaysPerMonth>', '<DurationFormat>7</DurationFormat>',
       '<WorkFormat>2</WorkFormat>', '<NewTasksAreManual>1</NewTasksAreManual>',
       f'<Calendars><Calendar><UID>1</UID><Name>Estándar</Name><IsBaseCalendar>1</IsBaseCalendar>'
       f'<BaseCalendarUID>-1</BaseCalendarUID><WeekDays>{dias}</WeekDays></Calendar></Calendars>', '<Tasks>']
for i, t in enumerate(tareas, start=1):
    n = 0 if t["hito"] else habiles(t["ini"], t["fin"])
    xml.append(
        f'<Task><UID>{i}</UID><ID>{i}</ID><Name>{escape(t["nombre"])}</Name><Active>1</Active><Manual>1</Manual>'
        f'<Type>0</Type><IsNull>0</IsNull><OutlineLevel>{t["niv"]}</OutlineLevel><Priority>500</Priority>'
        f'<Start>{t["ini"]:%Y-%m-%d}T08:00:00</Start><Finish>{t["fin"]:%Y-%m-%d}T17:00:00</Finish>'
        f'<ManualStart>{t["ini"]:%Y-%m-%d}T08:00:00</ManualStart><ManualFinish>{t["fin"]:%Y-%m-%d}T17:00:00</ManualFinish>'
        f'<Duration>{dur(n)}</Duration><DurationFormat>7</DurationFormat><ManualDuration>{dur(n)}</ManualDuration>'
        f'<PercentComplete>{t["pct"]}</PercentComplete>'
        f'<Milestone>{t["hito"]}</Milestone><Summary>{t["resumen"]}</Summary><Critical>0</Critical>'
        f'<CalendarUID>1</CalendarUID><ConstraintType>0</ConstraintType></Task>')
xml.append("</Tasks></Project>")
open(sys.argv[1], "w", encoding="utf-8").write("\n".join(xml))

# ---------------- Gantt ----------------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch

plt.rcParams["font.family"] = "Arial"
COL_S, COL_T, COL_H, COL_HECHO = "#1F3A5F", "#9DB7D2", "#9C2F2F", "#4E7FA8"
todas = [t for t in tareas if t["niv"] >= 2]
cortes = [0] + [next(i for i, t in enumerate(todas) if t["nombre"].startswith(n)) for n in ("Sprint 3", "Sprint 5", "Sprint 6")] + [len(todas)]
for k in range(4):
    vis = todas[cortes[k]:cortes[k + 1]]
    fig, ax = plt.subplots(figsize=(15, 0.34 * len(vis) + 1.7), dpi=200)
    for j, t in enumerate(vis):
        y = len(vis) - j
        ini, fin = mdates.date2num(t["ini"]), mdates.date2num(t["fin"] + timedelta(days=1))
        if t["hito"]:
            ax.plot([ini], [y], marker="D", color=COL_H, markersize=6, zorder=3)
        elif t["niv"] == 2:
            ax.barh(y, fin - ini, left=ini, height=0.55, color=COL_S, zorder=2)
        else:
            ax.barh(y, fin - ini, left=ini, height=0.42, color=COL_T, edgecolor="white", linewidth=0.4, zorder=2)
            ax.barh(y, (fin - ini) * t["pct"] / 100, left=ini, height=0.42, color=COL_HECHO, zorder=2.5)
    ax.set_yticks(range(len(vis), 0, -1))
    ax.set_yticklabels([("     " if t["niv"] == 3 else "") + t["nombre"] + (f"  ({t['pct']} %)" if t["niv"] == 2 else "")
                        for t in vis], fontsize=6.6)
    for lbl, t in zip(ax.get_yticklabels(), vis):
        if t["niv"] == 2:
            lbl.set_fontweight("bold")
        if t["hito"]:
            lbl.set_color(COL_H)
    ax.set_ylim(0.3, len(vis) + 0.9)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    ax.xaxis.set_minor_formatter(mdates.DateFormatter("%d"))
    ax.tick_params(axis="x", which="major", labelsize=8, pad=14)
    ax.tick_params(axis="x", which="minor", labelsize=5.2)
    ax.grid(axis="x", which="minor", color="#DDDDDD", linewidth=0.4, zorder=0)
    ax.grid(axis="x", which="major", color="#AAAAAA", linewidth=0.7, zorder=0)
    ax.set_xlim(mdates.date2num(date(2026, 8, 1)), mdates.date2num(date(2026, 12, 7)))
    ax.axvline(mdates.date2num(CORTE + timedelta(days=1)), color=COL_H, linestyle="--", linewidth=0.9, zorder=1)
    ax.text(mdates.date2num(CORTE + timedelta(days=2)), 0.55, "corte del informe (16/10)", fontsize=6, color=COL_H)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.legend(handles=[Patch(color=COL_S, label="Fase o sprint"), Patch(color=COL_HECHO, label="Avance completado"),
                       Patch(color=COL_T, label="Pendiente"),
                       plt.Line2D([], [], marker="D", color=COL_H, linestyle="", label="Hito")],
              loc="lower right", fontsize=6.5, frameon=False, ncol=4)
    plt.tight_layout()
    plt.savefig(sys.argv[2 + k], bbox_inches="tight", facecolor="white")
    plt.close(fig)
print("ok", len(tareas), "tareas")
for t in tareas:
    if t["niv"] <= 2:
        print(f'{t["pct"]:>4}%  {t["ini"]:%d/%m}-{t["fin"]:%d/%m}  {t["nombre"]}')
