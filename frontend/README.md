# TrackIn — Frontend

Dashboard de TrackIn: React + TypeScript sobre Vite, con TailwindCSS y Leaflet
para los mapas.

> Sprint 0: solo el esqueleto. La página `Dashboard` es un placeholder que
> además muestra el estado de conexión con el backend.

## Setup

Desde `frontend/`:

```bash
npm install
```

```bash
cp .env.example .env
```

```bash
npm run dev
```

Queda en <http://localhost:5173>.

Para que el dashboard muestre datos, el backend tiene que estar corriendo en
<http://localhost:8000> (ver [../backend/README.md](../backend/README.md)).

## Variables de entorno

| Variable | Default | Para qué |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | URL base de la API |

Dos cosas importantes:

- Vite **solo** expone al navegador las variables con prefijo `VITE_`.
- Todo lo que empiece con `VITE_` queda **embebido en el bundle** y es visible
  para cualquiera que abra el sitio. Nunca poner secretos ahí.

## Estructura

```
src/
├── main.tsx        Punto de entrada
├── App.tsx         Providers (react-query) y rutas
├── components/     Componentes reutilizables
├── pages/          Vistas: Dashboard (+ Pedidos y Mapas en Sprint 2+)
├── services/       Cliente axios y llamadas a la API
├── hooks/          Custom hooks (useHealth, …)
├── types/          Tipos del contrato con la API
└── utils/
tests/              Tests de vitest + Testing Library
```

Está configurado el alias `@` → `src/`, así que se importa
`@/services/api` en vez de `../../services/api`. El alias vive en dos lugares
que deben mantenerse sincronizados: `resolve.alias` de `vite.config.ts` y
`paths` de `tsconfig.app.json` — Vite y TypeScript resuelven por separado.

## Comandos

| Comando | Qué hace |
|---|---|
| `npm run dev` | Dev server con hot reload |
| `npm run build` | Build de producción a `dist/` |
| `npm run preview` | Sirve el build de producción |
| `npm run typecheck` | Chequeo de tipos |
| `npm run lint` | ESLint |
| `npm run lint:fix` | ESLint con autofix |
| `npm run format` | Prettier |
| `npm test` | Tests |
| `npm run test:watch` | Tests en modo watch |
| `npm run test:coverage` | Tests con cobertura |

## Notas

- **React 19.** El scaffold de `create-vite` ya viene con React 19, y
  `react-leaflet` v5 lo requiere. El anteproyecto mencionaba React 18; si hay
  que ajustarlo a la documentación formal, hay que bajar también
  `react-leaflet` a v4.
- **TailwindCSS v3** con `tailwind.config.js` clásico. La v4 cambia a
  configuración CSS-first y eliminaría ese archivo.
- **Leaflet necesita altura explícita** en su contenedor o el mapa renderiza
  con 0 px de alto. Para eso está la clase `.mapa-contenedor` en `index.css`.
- Los tests corren en `jsdom`. Los servicios se mockean con `vi.mock`, no se
  golpea la API real.

## Aviso de seguridad conocido (aceptado)

`npm audit` reporta 2 vulnerabilidades **high** en `react-router` / `react-router-dom`:

> [GHSA-qwww-vcr4-c8h2](https://github.com/advisories/GHSA-qwww-vcr4-c8h2) —
> RSC Mode CSRF Bypass Allows Action Execution Before 400 Response
> Rango afectado: 7.12.0 – 8.2.0

Se decidió **no actuar**, por dos razones:

1. El fallo es específico del **modo RSC** (React Server Components) con server
   actions. TrackIn es una SPA cliente con `BrowserRouter`, sin RSC ni server
   actions: la ruta de código vulnerable no se ejecuta.
2. No hay versión parcheada. La última publicada (7.18.2, la que tenemos) sigue
   dentro del rango afectado, y `npm audit fix --force` propone **bajar** a
   7.11.0, perdiendo siete versiones de correcciones.

**Revisar cuando salga un parche** y actualizar entonces. Si en algún momento
el proyecto adopta RSC o server actions, esto pasa a ser bloqueante.
