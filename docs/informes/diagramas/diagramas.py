"""Diagramas del modelo de diseño del Informe 2 (matplotlib)."""
import os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "img")
os.makedirs(OUT, exist_ok=True)
plt.rcParams["font.family"] = "Arial"

AZUL, AZUL2, VERDE, OCRE, MORADO, ROJO, GRIS = "#1F3A5F", "#4E7FA8", "#2E7D5B", "#8A5A00", "#7B3F8C", "#9C2F2F", "#6B7280"
CLARO = {AZUL: "#E4EBF3", AZUL2: "#EAF1F8", VERDE: "#E3F1EA", OCRE: "#F6EEDC", MORADO: "#F1E7F4", ROJO: "#F7E3E3", GRIS: "#F1F2F4"}


def lienzo(w, h):
    fig, ax = plt.subplots(figsize=(w, h), dpi=200)
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


def caja(ax, x, y, w, h, titulo, cuerpo="", color=AZUL, relleno=None, fs=10, fsb=8.2, borde=1.4, alinear="center"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=relleno or CLARO.get(color, "white"), ec=color, lw=borde, zorder=2))
    if cuerpo:
        ax.text(x + w / 2, y + h - 0.2, titulo, ha="center", va="top", fontsize=fs, fontweight="bold", color=color, zorder=3)
        ax.text(x + w / 2 if alinear == "center" else x + 0.12, y + h - 0.52, cuerpo, ha=alinear, va="top",
                fontsize=fsb, color="#1B2A3A", zorder=3, linespacing=1.35)
    else:
        ax.text(x + w / 2, y + h / 2, titulo, ha="center", va="center", fontsize=fs, fontweight="bold", color=color, zorder=3)


def grupo(ax, x, y, w, h, titulo, color=GRIS):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc="none", ec=color, lw=1.1, ls=(0, (4, 3)), zorder=1))
    ax.text(x + 0.15, y + h - 0.12, titulo, ha="left", va="top", fontsize=9, color=color, fontweight="bold", style="italic")


def flecha(ax, p1, p2, texto="", color="#374151", estilo="-|>", ls="-", fs=7.6, off=(0, 0.12), rad=0.0):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=estilo, mutation_scale=11, color=color, lw=1.2, ls=ls,
                                 connectionstyle=f"arc3,rad={rad}", zorder=1.5, shrinkA=2, shrinkB=2))
    if texto:
        ax.text((p1[0] + p2[0]) / 2 + off[0], (p1[1] + p2[1]) / 2 + off[1], texto, ha="center", va="bottom",
                fontsize=fs, color=color, zorder=4, bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.9))


def guardar(fig, nombre):
    fig.savefig(os.path.join(OUT, nombre), bbox_inches="tight", facecolor="white", pad_inches=0.08)
    plt.close(fig)


# ---------------------------------------------------------------- 1. Arquitectura conceptual
fig, ax = lienzo(16, 9.6)
caja(ax, 0.3, 8.35, 15.4, 1.0, "Usuarios de Laboratorios Gutis",
     "Compras  |  Logística  |  Planificación de Producción  |  Administrador  |  Pantalla de planta (solo lectura)", AZUL, fsb=9)
grupo(ax, 0.3, 6.45, 15.4, 1.6, "Capa de presentación | navegador")
caja(ax, 0.6, 6.6, 14.8, 1.05, "Aplicación web (SPA) | React + TypeScript + Vite + Tailwind + Leaflet",
     "Login | dashboard con KPIs, grilla, filtros y próximos arribos | mapas marítimo y aéreo | detalle del pedido | carga del Z-tracking | administración",
     AZUL2, fsb=8.6)
flecha(ax, (8, 8.35), (8, 7.67), "HTTPS", off=(0.55, -0.25))
grupo(ax, 0.3, 3.2, 9.6, 2.95, "Proceso 1 | API REST (FastAPI, uvicorn)")
caja(ax, 0.6, 4.55, 4.4, 1.1, "Seguridad", "Sesión por token | roles | bloqueo\npor intentos | expiración por inactividad", VERDE, fsb=7.8)
caja(ax, 5.2, 4.55, 4.4, 1.1, "Routers /api/v1", "pedidos | destinos | usuarios\nauth | cargas | health | OpenAPI", VERDE, fsb=7.8)
caja(ax, 0.6, 3.35, 9.0, 0.95, "Servicios de dominio",
     "consulta de pedidos | intervenciones manuales y auditoría | recálculo de fecha y estado | maestros | parámetros", VERDE, fsb=7.8)
flecha(ax, (5.0, 6.6), (5.0, 5.67), "JSON", off=(0.45, -0.2))
grupo(ax, 10.2, 3.2, 5.5, 2.95, "Proceso 2 | Worker de rastreo (asyncio)")
caja(ax, 10.45, 4.55, 5.0, 1.1, "Planificador y colectores", "ShipsGo (marítimo y aéreo) | TICA (guía hija)\nAISStream (respaldo del mapa)", OCRE, fsb=7.8)
caja(ax, 10.45, 3.35, 5.0, 0.95, "Motor de cálculo", "arribo | ETA | fecha proyectada | etapa y cumplimiento", OCRE, fsb=7.8)
flecha(ax, (12.95, 4.55), (12.95, 4.32))
caja(ax, 3.0, 0.75, 10.0, 1.35, "PostgreSQL 16 + PostGIS 3",
     "15 tablas | pedidos en tránsito, elementos rastreados, historial inmutable de posiciones,\nmaestros, auditoría inmutable, usuarios y sesiones, parámetros, salud de fuentes",
     MORADO, fsb=8.4)
flecha(ax, (5.1, 3.35), (5.6, 2.12), "SQLAlchemy | lectura y escritura", off=(1.75, -0.12))
flecha(ax, (12.95, 3.35), (11.6, 2.12), "lecturas y estados", off=(-1.3, -0.12))
caja(ax, 0.3, 0.05, 2.45, 2.6, "Entrada", "Archivo\nZ-tracking\n(Excel) que\nCompras\nexporta de SAP", VERDE, fsb=7.8)
caja(ax, 13.25, 0.05, 2.45, 2.6, "Fuentes", "API de ShipsGo\nTICA (Hacienda)\nAISStream", OCRE, fsb=7.8)
flecha(ax, (2.75, 1.4), (3.0, 1.4))
flecha(ax, (14.47, 2.65), (14.2, 3.2), "", ls=(0, (3, 2)))
guardar(fig, "arquitectura.png")

# ---------------------------------------------------------------- 2. Subsistemas
fig, ax = lienzo(16, 6.6)
S = [
    (0.3, 4.1, "S1 - Ingesta de pedidos", "Lector del Z-tracking, normalización\ncontra catálogos (RN-17), carga\nidempotente, ausencias e informe", VERDE),
    (5.55, 4.1, "S2 - Rastreo", "Planificador, colectores de ShipsGo,\nTICA y AISStream, política de\nresiliencia y salud de las fuentes", OCRE),
    (10.8, 4.1, "S3 - Motor de cálculo", "Arribo por hito o geocerca, ETA,\nfecha proyectada (RN-01), etapa\ny cumplimiento, recálculo", OCRE),
    (0.3, 1.0, "S6 - Seguridad", "Usuarios, roles, sesiones por token,\nbloqueo por intentos, expiración\npor inactividad, argon2id", VERDE),
    (5.55, 1.0, "S5 - Consulta y maestros", "Listado con filtros y paginación,\ndetalle con desglose del cálculo,\ndestinos y parámetros", AZUL2),
    (10.8, 1.0, "S4 - Intervenciones y auditoría", "Desembarco, paso a aduana, recepción,\ncierre forzado, liberación de Calidad,\najuste manual; bitácora inmutable", MORADO),
]
for x, y, t, c, col in S:
    caja(ax, x, y, 4.9, 1.95, t, c, col, fs=10.5, fsb=8.6)
flecha(ax, (5.2, 5.07), (5.55, 5.07))
ax.text(5.37, 5.35, "referencias\nde embarque", ha="center", fontsize=6.8, color="#374151")
flecha(ax, (10.45, 5.07), (10.8, 5.07))
ax.text(10.62, 5.35, "lecturas\nnormalizadas", ha="center", fontsize=6.8, color="#374151")
flecha(ax, (13.25, 2.95), (13.25, 4.1), "un acto manual dispara el recálculo", off=(1.5, -0.25))
ax.text(7.9, 0.55, "La seguridad protege las rutas de consulta e intervención · los seis subsistemas comparten la base PostgreSQL + PostGIS",
        ha="center", fontsize=8, color="#374151", style="italic")
guardar(fig, "subsistemas.png")

# ---------------------------------------------------------------- 3. Despliegue
fig, ax = lienzo(16, 8.2)
grupo(ax, 0.3, 0.3, 10.6, 7.5, "Equipo de desarrollo | Windows 11 | sin permisos de administrador")
caja(ax, 0.7, 5.8, 3.0, 1.4, "Navegador", "localhost:5173", AZUL2, fsb=8.5)
caja(ax, 4.2, 5.8, 3.0, 1.4, "Vite dev server", "puerto 5173 · npm run dev", AZUL2, fsb=8.5)
caja(ax, 0.7, 3.3, 3.0, 1.6, "API | uvicorn", "puerto 8000\napp.main:app", VERDE, fsb=8.5)
caja(ax, 7.55, 3.3, 3.0, 1.6, "Worker de rastreo", "python -m app.workers\nsin puerto", OCRE, fsb=8.5)
caja(ax, 4.2, 3.3, 3.0, 1.6, "Pruebas (pytest)", "base trackin_test\nseparada", GRIS, fsb=8.5)
caja(ax, 2.2, 0.7, 6.6, 1.5, "PostgreSQL 16.14 + PostGIS 3.6.2", "puerto 5432 · binarios portables en ~/pgsql\nbases trackin_dev y trackin_test", MORADO, fsb=8.5)
flecha(ax, (3.7, 6.5), (4.2, 6.5))
flecha(ax, (2.2, 5.8), (2.2, 4.92), "HTTP / JSON", off=(-0.95, -0.1))
flecha(ax, (2.2, 3.3), (3.6, 2.22))
flecha(ax, (5.7, 3.3), (5.5, 2.22))
flecha(ax, (9.05, 3.3), (7.6, 2.22))
grupo(ax, 11.3, 0.3, 4.4, 7.5, "Internet | salida desde la red de Gutis")
caja(ax, 11.6, 5.6, 3.8, 1.5, "API de ShipsGo", "REST · token · créditos por alta", OCRE, fsb=8.2)
caja(ax, 11.6, 3.5, 3.8, 1.5, "TICA · Hacienda", "consulta pública de\nconocimientos de embarque", OCRE, fsb=8.2)
caja(ax, 11.6, 1.4, 3.8, 1.5, "AISStream", "WebSocket · plan gratuito", OCRE, fsb=8.2)
flecha(ax, (10.55, 4.6), (11.6, 6.3), "HTTPS", off=(-0.35, 0.05))
flecha(ax, (10.55, 4.1), (11.6, 4.25))
flecha(ax, (10.55, 3.6), (11.6, 2.2), "wss", off=(-0.25, 0))
guardar(fig, "despliegue.png")

# ---------------------------------------------------------------- 4. Secuencia del ciclo del worker
fig, ax = lienzo(16, 10.6)
part = ["Planificador", "Colector\n(ShipsGo / TICA)", "Fuente externa", "Motor de cálculo", "Base de datos", "API REST", "Dashboard"]
xs = [1.2 + i * 2.27 for i in range(len(part))]
for x, p in zip(xs, part):
    caja(ax, x - 0.95, 9.55, 1.9, 0.85, p, "", AZUL, fs=8.5)
    ax.plot([x, x], [1.3, 9.55], color="#9CA3AF", lw=0.9, ls=(0, (3, 3)), zorder=0)
pasos = [
    (0, 4, "1. elementos activos cuyo intervalo venció", 9.0),
    (0, 1, "2. despacha según el tipo de referencia", 8.45),
    (1, 2, "3. consulta por referencia (sin costo)", 7.9),
    (2, 1, "4. hitos, ETA, buque, posición", 7.35),
    (1, 4, "5. historial inmutable + posición actual", 6.8),
    (1, 3, "6. elemento actualizado", 6.25),
    (3, 4, "7. pedidos del elemento y parámetros", 5.7),
    (3, 3, "8. arribo · ETA · fecha proyectada · etapa · cumplimiento", 5.15),
    (3, 4, "9. actualiza cada pedido (aislado ante fallos)", 4.6),
    (1, 4, "10. salud de la fuente", 4.05),
    (6, 5, "11. GET /api/v1/pedidos con filtros", 3.0),
    (5, 4, "12. lee el estado ya calculado", 2.45),
    (5, 6, "13. JSON paginado", 1.9),
]
for a, b, t, y in pasos:
    if a == b:
        ax.add_patch(FancyArrowPatch((xs[a], y + 0.1), (xs[a] + 0.01, y - 0.18), connectionstyle="arc3,rad=-2.2",
                                     arrowstyle="-|>", mutation_scale=10, color=AZUL, lw=1.1))
        ax.text(xs[a] + 0.6, y - 0.05, t, fontsize=7.6, va="center", color="#1B2A3A")
    else:
        flecha(ax, (xs[a], y), (xs[b], y), t, color=AZUL if b >= a else VERDE, fs=7.4, off=(0, 0.03))
ax.add_patch(FancyBboxPatch((0.15, 3.65), 15.7, 5.62, boxstyle="round,pad=0.02", fc="#FBF7EE", ec=OCRE, lw=0.8, zorder=-1))
ax.text(0.3, 9.18, "Proceso 2 · worker, cada ciclo", fontsize=8, color=OCRE, style="italic", fontweight="bold")
ax.add_patch(FancyBboxPatch((0.15, 1.45), 15.7, 1.95, boxstyle="round,pad=0.02", fc="#EEF4FA", ec=AZUL2, lw=0.8, zorder=-1))
ax.text(0.3, 3.15, "Proceso 1 · API, a petición del usuario", fontsize=8, color=AZUL2, style="italic", fontweight="bold")
guardar(fig, "secuencia.png")

# ---------------------------------------------------------------- 5. Estados del pedido
fig, ax = lienzo(16, 6.1)
etapas = [("SIN_TRACKING", "sin referencia"), ("EN_ORIGEN", "referencia asociada"), ("EN_TRANSITO", "zarpe o despegue"),
          ("EN_DESTINO", "hito de arribo, TICA\no confirmación manual"), ("EN_PROCESO\n_ADUANAL", "paso manual\nconfirmado"),
          ("RECIBIDO_EN\n_PLANTA", "recepción dentro\nde la tolerancia"), ("CERRADO", "liberación total\nde Calidad")]
cols = ["#9CA3AF", "#93C5FD", "#3B82F6", "#8B5CF6", "#EAB308", "#14B8A6", "#111827"]
for i, ((e, cond), c) in enumerate(zip(etapas, cols)):
    x = 0.3 + i * 2.25
    ax.add_patch(FancyBboxPatch((x, 3.6), 1.95, 1.2, boxstyle="round,pad=0.02,rounding_size=0.15", fc="white", ec=c, lw=2.2))
    ax.text(x + 0.975, 4.2, e, ha="center", va="center", fontsize=7.6, fontweight="bold", color="#111827")
    if i:
        flecha(ax, (x - 0.3, 4.2), (x, 4.2))
        ax.text(x - 0.15, 4.95, cond, ha="center", va="bottom", fontsize=6.6, color="#374151")
ax.add_patch(FancyBboxPatch((9.4, 1.0), 2.2, 1.0, boxstyle="round,pad=0.02,rounding_size=0.15", fc="white", ec="#4B5563", lw=2.2))
ax.text(10.5, 1.5, "CANCELADO", ha="center", va="center", fontsize=8, fontweight="bold")
ax.text(10.5, 0.25, "anulación de la OC antes de la recepción\n(desde cualquier etapa no terminal)", ha="center", fontsize=7, color="#374151")
for x in (1.3, 3.5, 5.8, 8.0, 10.3, 12.5):
    flecha(ax, (x, 3.6), (10.5, 2.02), ls=(0, (2, 2)), color="#6B7280")
ax.text(0.3, 5.75, "Dimensión 1 · etapa del viaje (solo avanza)", fontsize=10, fontweight="bold", color=AZUL)
ax.text(0.3, 2.3, "Dimensión 2 · cumplimiento\nA_TIEMPO · EN_RIESGO · RETRASADO\no sin proyección (fecha proyectada frente\na la fecha de llegada a Gutis)",
        fontsize=8.8, color=ROJO, va="top", fontweight="bold")
guardar(fig, "estados.png")

# ---------------------------------------------------------------- 6. ER
T = {
    "pedidos_transito": (["PK id", "oc_numero · posicion_oc", "FK id_proveedor", "FK id_material", "FK id_destino", "FK id_pais_origen",
                          "FK id_elemento_rastreado", "via_transporte · incoterm", "fecha_entrega_pedido", "eta_utilizada · ata_confirmada",
                          "fecha_proyectada_disponible", "etapa_viaje · estado_cumplimiento", "fecha_recepcion_planta", "fecha_liberacion_calidad",
                          "ausente_desde · … (40 col.)"], (5.6, 4.6), AZUL),
    "elementos_rastreados": (["PK id", "tipo_tracking_externo", "tracking_externo", "via_transporte · nombre · imo", "eta_api · ata_api",
                              "posicion_actual (geography)", "guia_madre · manifiesto_aduana", "activo"], (11.2, 7.3), OCRE),
    "pedido_elemento_rastreado": (["PK id", "FK id_pedido", "FK id_elemento_rastreado", "tramo · fecha_desde · fecha_hasta", "puerto_transbordo"], (11.2, 3.75), OCRE),
    "historial_tracking": (["PK id", "FK id_elemento_rastreado", "fecha_registro", "posicion (geography)", "velocidad · rumbo · estado_api", "payload_api (JSONB)"], (15.6, 7.3), OCRE),
    "maestro_destinos": (["PK id", "codigo (UN/LOCODE) · nombre", "via_transporte", "ubicacion (geography)", "radio_geocerca_km", "lead_time_dias"], (0.3, 9.0), VERDE),
    "proveedores": (["PK id", "codigo · nombre · pais"], (0.3, 6.2), VERDE),
    "materiales": (["PK id", "codigo · descripcion", "unidad_medida"], (0.3, 4.7), VERDE),
    "maestro_paises": (["PK id", "codigo · nombre"], (0.3, 2.9), VERDE),
    "alias_paises": (["PK id", "FK id_pais", "alias"], (0.3, 1.0), VERDE),
    "auditoria_intervenciones": (["PK id", "FK id_pedido", "FK id_usuario", "fecha_hora · tipo_intervencion", "campo · valor anterior y nuevo", "motivo"], (5.6, 0.2), MORADO),
    "usuarios": (["PK id", "usuario · correo · rol", "hash_contrasena (argon2id)", "intentos_fallidos · bloqueado_hasta"], (11.2, 0.6), MORADO),
    "sesiones": (["PK id", "FK id_usuario", "hash_token · recordada", "ultimo_uso · cerrada_en"], (15.6, 0.6), MORADO),
    "parametros_sistema": (["PK clave", "valor · tipo_dato", "FK id_usuario_modificacion"], (15.6, 4.0), GRIS),
    "salud_fuentes": (["PK nombre", "degradada · fallos_consecutivos", "ultimo_contacto_ok"], (15.6, 10.6), GRIS),
    "cargas_ztracking": (["PK id", "FK id_usuario → usuarios", "archivo · estado", "recibidas · insertadas · rechazadas", "informe (JSONB)"], (5.6, 10.3), GRIS),
}
W, LH = 3.9, 0.33
fig, ax = lienzo(19.8, 13.4)
pos = {}
for nombre, (cols_, (x, y), col) in T.items():
    h = 0.42 + LH * len(cols_)
    ax.add_patch(FancyBboxPatch((x, y), W, h, boxstyle="round,pad=0.01,rounding_size=0.05", fc="white", ec=col, lw=1.3, zorder=2))
    ax.add_patch(FancyBboxPatch((x, y + h - 0.42), W, 0.42, boxstyle="round,pad=0.01,rounding_size=0.05", fc=col, ec=col, lw=1.3, zorder=2))
    ax.text(x + W / 2, y + h - 0.21, nombre, ha="center", va="center", fontsize=8.3, fontweight="bold", color="white", zorder=3)
    for k, c in enumerate(cols_):
        ax.text(x + 0.1, y + h - 0.42 - LH * (k + 0.5), c, ha="left", va="center", fontsize=7, zorder=3,
                color="#9C2F2F" if c.startswith("PK") else ("#1F3A5F" if c.startswith("FK") else "#1B2A3A"),
                fontweight="bold" if c[:2] in ("PK", "FK") else "normal")
    pos[nombre] = (x, y, W, h)


def ancla(n, lado):
    x, y, w, h = pos[n]
    return {"l": (x, y + h / 2), "r": (x + w, y + h / 2), "t": (x + w / 2, y + h), "b": (x + w / 2, y)}[lado]


rel = [("maestro_destinos", "r", "pedidos_transito", "l", "1 : N"), ("proveedores", "r", "pedidos_transito", "l", "1 : N"),
       ("materiales", "r", "pedidos_transito", "l", "1 : N"), ("maestro_paises", "r", "pedidos_transito", "l", "1 : N"),
       ("maestro_paises", "b", "alias_paises", "t", "1 : N"), ("elementos_rastreados", "l", "pedidos_transito", "r", "1 : N (vigente)"),
       ("pedidos_transito", "r", "pedido_elemento_rastreado", "l", "1 : N"), ("elementos_rastreados", "b", "pedido_elemento_rastreado", "t", "1 : N"),
       ("elementos_rastreados", "r", "historial_tracking", "l", "1 : N"), ("pedidos_transito", "b", "auditoria_intervenciones", "t", "1 : N"),
       ("usuarios", "l", "auditoria_intervenciones", "r", "1 : N"), ("usuarios", "r", "sesiones", "l", "1 : N"),
       ("usuarios", "t", "parametros_sistema", "b", "1 : N")]
for a, la, b, lb, card in rel:
    p1, p2 = ancla(a, la), ancla(b, lb)
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-", color="#6B7280", lw=1.0, zorder=1, connectionstyle="arc3,rad=0.0"))
    ax.text((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2, card, fontsize=6.6, ha="center", va="center", color="#374151",
            bbox=dict(fc="white", ec="none", pad=0.5), zorder=1.6)
guardar(fig, "er.png")
print("ok")
