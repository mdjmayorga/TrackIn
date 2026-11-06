# Producción: mosaicos del mapa y contexto seguro

Análisis para la puesta en producción de TrackIn en la red interna de Gutis
(10 a 20 usuarios, una pantalla de planta encendida todo el día que refresca
los datos del panel). Todas las fuentes se consultaron el 06/11/2026.

---

## Resumen

### 1. Mosaicos de OpenStreetMap

**Recomendación:** salir a producción con los mosaicos de OpenStreetMap, pero
con tres cambios, y dejar un proveedor comercial listo como plan B que se
active cambiando una variable, sin publicar una versión nueva.

1. Cambiar la URL a `https://tile.openstreetmap.org/{z}/{x}/{y}.png`, sin el
   subdominio `{s}`. La política vigente pide esa URL exacta y avisa que otros
   subdominios pueden volverse lentos o retirarse sin aviso.
2. Sacar la URL del código (`MOSAICOS` en `MapaBase.tsx`) a una variable de
   configuración: la política lo pide ("evitar fijar la URL en el código") y es
   lo que permite pasar al plan B sin una versión nueva.
3. Pedirle a TI la lista blanca para `tile.openstreetmap.org` (no
   `*.tile.openstreetmap.org`, como dice hoy `docs/deployment.md` §3).

El uso de TrackIn cumple los requisitos técnicos (atribución visible, navegador
con su User-Agent y Referer, caché del navegador, sin descarga masiva) y su
volumen es bajo: el refresco de la pantalla de planta vuelve a pedir datos al
backend, no recarga la página ni los mosaicos. **Pero** el servicio no tiene
SLA, puede bloquear sin aviso, y la política advierte expresamente a los
servicios comerciales que el acceso puede retirarse en cualquier momento.
Para una pantalla de planta que no debe quedar sin fondo, eso es un riesgo
aceptable solo si hay un plan B listo.

**Plan B recomendado:** Stadia Maps, plan Starter (USD 20 al mes, 1 000 000 de
créditos, 1 crédito por mosaico raster, uso comercial permitido). Su plan
gratuito prohíbe el uso comercial, así que no sirve para Gutis. Para una
aplicación de intranet exige una API key.

### 2. Contexto seguro

**Respuesta corta:**

- **Screen Wake Lock sí exige contexto seguro** (`[SecureContext]` en la spec).
  En `http://trackin.gutis.local` o `http://10.0.0.5`, `navigator.wakeLock` no
  existe. Solo son seguros HTTPS (y WSS), `localhost` y la red de loopback
  (`127.0.0.0/8`, `::1`), `file:`, y los orígenes que el usuario o la
  organización configuren como confiables.
- **Fullscreen no exige contexto seguro** (hallazgo que corrige el supuesto
  inicial). La spec WHATWG no lo marca `[SecureContext]`; exige un gesto del
  usuario y el permiso de la política `fullscreen`. El botón de pantalla
  completa funciona también por HTTP.
- **Qué hace TrackIn sin la API:** `useWakeLock` comprueba `navigator.wakeLock`
  y, si no existe, sale sin hacer nada ni mostrar error. La pantalla queda a
  merced de la configuración de energía del equipo.

**Recomendación:** servir TrackIn por HTTPS, como ya prevé
`docs/deployment.md` (TLS en el proxy corporativo, nombre provisorio
`trackin.gutis.com`). Si Gutis controla `gutis.com` y su proveedor de DNS tiene
API, la opción más simple es un **certificado público con validación DNS-01**
para un subdominio real que en el DNS interno apunte a la IP privada: los
navegadores lo confían sin distribuir nada. Si no, una **CA interna**
distribuida por GPO. En ambos casos el nombre debe ser un dominio real, no
`.local`. Mientras tanto, solo para la pantalla de planta, una política de
Edge o Chrome (`OverrideSecurityRestrictionsOnInsecureOrigin`) puede tratar el
origen HTTP como seguro; es un parche, no reemplaza al HTTPS (TrackIn tiene
inicio de sesión, y por HTTP las credenciales viajan sin cifrar por la red).

---

## 1. Mosaicos de OpenStreetMap: detalle

### 1.1 Qué dice la Tile Usage Policy vigente

Fuente: OSMF Operations Working Group, *Tile Usage Policy*,
<https://operations.osmfoundation.org/policies/tiles/> (consulta 06/11/2026).
La página no muestra fecha de revisión; cubre solo los mosaicos raster de
`tile.openstreetmap.org` (sección 9, *Scope*).

| Tema | Lo que dice la política |
|---|---|
| **URL** | Sección 1: usar exactamente `https://tile.openstreetmap.org/{z}/{x}/{y}.png`. "Other subdomains or hostnames may be slower or withdrawn without notice." Prohíbe la URL por HTTP. |
| **Subdominios a/b/c** | La política ya no los menciona; solo admite la URL sin subdominio. El pedido del equipo de operaciones explica el motivo: el servidor admite HTTP/2 y HTTP/3, así que los alias a/b/c ya no hacen falta para abrir más conexiones (issue #737, "Use preferred tile.openstreetmap.org URL", abierta el 30/08/2022, <https://github.com/openstreetmap/operations/issues/737>). |
| **Atribución** | Sección 2 y resumen: atribución de licencia visible en el mapa, sin esconderla detrás de un botón. TrackIn la cumple: Leaflet la muestra abajo a la derecha (`ATRIBUCION` en `MapaBase.tsx`). |
| **User-Agent** | Sección 3.1: "Browsers will use the browser's default `User-Agent`." Lo prohibido es el User-Agent por defecto de una biblioteca (apps nativas, scripts). Un navegador cumple. |
| **Referer** | Sección 3.1: los navegadores deben enviar un Referer válido; no poner una `Referrer-Policy` restrictiva. TrackIn no la define, así que rige la del navegador. |
| **Caché** | Sección 3.2: respetar `Cache-Control`, `Expires` y `Etag`, o guardar cada mosaico al menos 7 días; no enviar `no-cache`. "Modern browsers, with default settings, already satisfy these technical requirements." |
| **Descarga masiva** | Sección 4: prohibida la descarga masiva y el prefetch ("any pre-emptive fetching of tiles other than those a user is actively viewing"), y el uso sin conexión. |
| **Proxy de caché propio** | Sección 5: "We generally do not recommend" poner un proxy de caché delante. No conviene que TI cachee los mosaicos en el proxy corporativo. |
| **Uso por empresas / "heavy"** | No hay una categoría de "empresas" ni un umbral numérico de uso intensivo. Introducción: "heavy or inappropriate use harms others' ability to edit and view the map", y el acceso puede bloquearse si el uso degrada el servicio. Sección 7: "Commercial services, or those that seek donations, should be especially aware that access may be withdrawn at any point". |
| **SLA** | "Availability is best-effort: there is no SLA or guarantee." Sección 7: "Access may be blocked without prior notice." La política puede cambiar en cualquier momento. |
| **Recomendaciones (no obligatorias)** | Resumen: no fijar la URL en el código para poder cambiarla sin actualizar el software; enlace "Report a map issue" a <https://www.openstreetmap.org/fixthemap>; publicar un correo de contacto; usar HTTP/2 o HTTP/3. |

### 1.2 ¿Encaja el caso de TrackIn?

**Sí, con reservas.**

- **Cumple los requisitos técnicos.** Es una aplicación web en el navegador
  (User-Agent y Referer del navegador, caché HTTP del navegador), con
  atribución visible y sin prefetch.
- **El volumen es bajo.** Los refrescos automáticos (`refetchInterval` en
  `usePedidos.ts`, cada 2 min para el panel y 5 min para otras consultas)
  vuelven a pedir datos con TanStack Query; el `MapContainer` sigue montado y
  Leaflet no vuelve a pedir los mosaicos que ya tiene. Estimación propia (no
  de una fuente): con unos 10 a 16 mosaicos de 256 px por vista de mapa (la
  cifra que da MapTiler para una vista raster, ver 1.3), dos mapas en el panel
  y 20 usuarios abriendo el panel varias veces al día, son unos pocos miles de
  mosaicos diarios como máximo, y buena parte sale de la caché del navegador.
- **Contras.** Gutis es una empresa y TrackIn una herramienta de trabajo: cae
  en la advertencia a servicios comerciales de la sección 7. Sin SLA y con
  bloqueo posible sin aviso, la pantalla de planta podría quedarse sin fondo de
  mapa (los marcadores siguen; `docs/deployment.md` §3 ya lo anota).
- **Incumplimientos menores hoy.** Usa `{s}.tile.openstreetmap.org` en vez de la
  URL exacta, y la URL está fija en el código.

### 1.3 Alternativas

Precios y límites según las páginas oficiales, consultadas el 06/11/2026.

| Opción | Precio | Límite | Uso comercial | Notas |
|---|---|---|---|---|
| **Stadia Maps** <https://stadiamaps.com/pricing/> | Free USD 0; Starter USD 20/mes; Standard USD 80/mes | Free 200 000 créditos; Starter 1 000 000 (excedente 3 centavos por 1 000) | Free: no permitido; Starter en adelante: permitido | Raster para Leaflet: 1 crédito por mosaico. Para sitios de intranet exige API key; la autenticación por dominio usa `Origin`/`Referer` y la doc no dice que sirva para nombres internos (<https://docs.stadiamaps.com/authentication/>). |
| **MapTiler Cloud** <https://www.maptiler.com/cloud/pricing/> | Free USD 0; Flex USD 30/mes | Free: 5 000 sesiones y 100 000 peticiones de API al mes; Flex: 25 000 sesiones y 500 000 peticiones | Free: "suitable for testing, PoC, prototyping, personal, or non-commercial use"; Flex: "any standard use case" | Free se pausa al agotar la cuota y exige el logo de MapTiler. Un mosaico raster de 256 px cuenta 1 petición; de 512 px, 4. |
| **Thunderforest** <https://www.thunderforest.com/pricing/> | Hobby Project gratis; Solo Developer USD 125/mes | Hobby 150 000 mosaicos/mes; Solo 1 500 000 | Los términos dicen "Commercial use is permitted and encouraged" en general (<https://www.thunderforest.com/terms/>), pero la página de precios presenta Hobby como plan para probar ideas | Al agotar la cuota avisan por correo, "we won't suddenly cut you off". Prohíbe el pre-cacheo sin un plan adecuado. |
| **Mosaicos propios (Protomaps / PMTiles)** <https://docs.protomaps.com/> | Sin costo de licencia; solo almacenamiento en el servidor de TrackIn | Sin cuota | Sí (ODbL, con atribución a OpenStreetMap) | El planeta completo pesa unos 120 GB (z0 a z15); con `pmtiles extract` se recorta una región y con `--maxzoom` se reduce el tamaño (<https://docs.protomaps.com/basemaps/downloads>). El mapa base es vectorial: en Leaflet necesita `protomaps-leaflet`, que la doc declara en modo mantenimiento y recomienda MapLibre GL JS en su lugar (<https://docs.protomaps.com/pmtiles/leaflet>). El filtro CSS gris oscuro actual habría que reemplazarlo por un estilo. Quita la dependencia de internet de los navegadores. |

### 1.4 Recomendación

1. **Ahora:** OpenStreetMap con la URL sin subdominio, la URL en una variable
   de configuración del frontend y la lista blanca exacta. Opcional: el enlace
   "Report a map issue".
2. **Plan B listo:** cuenta en Stadia Maps Starter (USD 20/mes) creada y
   probada. Si OSM bloquea o se degrada, se cambia la variable y listo. Es la
   opción comercial más barata que permite uso comercial en forma explícita y
   su cuota sobra para el volumen estimado. Ojo: su API key queda visible en el
   navegador; la doc de Stadia la indica igual para intranets.
3. **Si TI no quiere salida a internet desde los navegadores**, o si se quiere
   eliminar la dependencia externa por completo: mosaicos propios con
   PMTiles, sabiendo que implica pasar a mosaicos vectoriales y probablemente a
   MapLibre. Es más trabajo de lo que justifican 20 usuarios hoy.

---

## 2. Contexto seguro: detalle

### 2.1 Qué cuenta como contexto seguro

Fuente: W3C, *Secure Contexts*, Candidate Recommendation Draft del 10/11/2023,
<https://www.w3.org/TR/secure-contexts/> (consulta 06/11/2026). La definición
de "secure context" vive en el HTML Standard; esta spec define qué origen es
"potentially trustworthy" (sección 3.1):

- `https` y `wss`: confiables.
- `127.0.0.0/8` y `::1/128` (loopback): confiables.
- `localhost`, `localhost.` y `*.localhost`: confiables si el navegador los
  resuelve siempre a loopback (sección 5.2).
- `file`: confiable (el navegador "SHOULD", aunque puede excluirlo).
- Orígenes que el usuario configuró como confiables (sección 7.2, p. ej.
  servidores de staging).
- **Todo lo demás: "Not Trustworthy"**, incluido `http` hacia cualquier otro
  host.

MDN lo resume igual, con `http://example.com` como "Not secure"
(<https://developer.mozilla.org/en-US/docs/Web/Security/Secure_Contexts>).

**Por lo tanto `http://trackin.gutis.local` y `http://10.0.0.5` no son
contextos seguros.** Ni las IP privadas ni los nombres `.local` aparecen en la
lista; caen en la regla final.

### 2.2 Screen Wake Lock API

Fuente: W3C, *Screen Wake Lock API* (Editor's Draft),
<https://w3c.github.io/screen-wake-lock/> (consulta 06/11/2026).

- La IDL marca `[SecureContext]` tanto `Navigator.wakeLock` como la interfaz
  `WakeLock`: en un contexto no seguro el atributo no existe.
- Política de permisos `screen-wake-lock`, por defecto `'self'`.
- `request()` rechaza con `NotAllowedError` si el documento está oculto, y el
  navegador suelta el candado cuando la pestaña se oculta.

MDN: "available only in secure contexts (HTTPS)"; Baseline 2025 ("since March
2025, this feature works across the latest devices and browser versions"); la
petición puede rechazarse por ahorro de energía o batería baja
(<https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API>).

### 2.3 Fullscreen API

Fuente: WHATWG, *Fullscreen API Standard*, Living Standard actualizado el
19/10/2026, <https://fullscreen.spec.whatwg.org/> (consulta 06/11/2026).

- La IDL de `Element.requestFullscreen()` **no** lleva `[SecureContext]` y la
  spec no menciona contextos seguros.
- Exige activación transitoria (un gesto del usuario), que el documento pueda
  usar la característica `fullscreen` de la política de permisos (por defecto
  `'self'`) y que el elemento cumpla ciertas condiciones.

MDN tampoco indica requisito de contexto seguro
(<https://developer.mozilla.org/en-US/docs/Web/API/Element/requestFullscreen>).
**El botón de pantalla completa de TrackIn funciona por HTTP.**

### 2.4 Qué hace TrackIn si la API no está

`frontend/src/hooks/usePantallaPermanente.ts`:

- `useWakeLock` comprueba `nav.wakeLock`; si no existe (contexto no seguro o
  navegador sin soporte), hace `return` sin hacer nada. Si existe pero el
  navegador rechaza la petición, el `.catch(() => undefined)` lo silencia. En
  ambos casos no hay aviso: la pantalla depende de la configuración de energía
  del equipo, como dice el propio comentario del archivo.
- Vuelve a pedir el candado en `visibilitychange`, que es lo que recomienda MDN
  porque el navegador lo suelta al ocultar la pestaña.
- `usePantallaCompleta` expone `posible` según exista
  `requestFullscreen`; por HTTP será `true`.

Consecuencia práctica: por HTTP la pantalla de planta se apagará según la
política de energía de Windows, sin que TrackIn lo advierta.

### 2.5 Opciones de HTTPS en la red interna

#### A. Certificado de una CA interna distribuido por GPO

- Una CA propia (p. ej. AD CS) emite el certificado para el nombre que se
  quiera, incluso `.local` o una IP privada.
- La raíz se distribuye por GPO: Computer Configuration > Policies > Windows
  Settings > Security Settings > Public Key Policies > Trusted Root
  Certification Authorities > Import; requiere Domain Admins o Enterprise
  Admins y reiniciar los equipos (Microsoft Learn, *Distribute certificates to
  Windows devices by using Group Policy*,
  <https://learn.microsoft.com/en-us/windows-server/identity/ad-cs/distribute-certificates-group-policy>).
- Chrome (y Edge, basado en Chromium) en Windows confía en las raíces del
  almacén de la máquina y de Group Policy para conexiones TLS sobre TCP; para
  QUIC no honra raíces añadidas localmente (Chrome Root Store FAQ,
  <https://chromium.googlesource.com/chromium/src/+/main/net/data/ssl/chrome_root_store/faq.md>).
- **Implica:** que Gutis tenga dominio de Active Directory y alguien que opere
  la CA (renovaciones, revocación, custodia de la clave). Los equipos fuera del
  dominio (una pantalla de planta no unida al dominio, teléfonos) necesitan
  instalar la raíz a mano o no confiarán. No expone nombres internos.

#### B. Certificado público con validación DNS-01

- Let's Encrypt valida con un registro TXT en `_acme-challenge.<dominio>`;
  sirve "to validate domain names whose webservers aren't exposed to the public
  internet" y admite comodines (<https://letsencrypt.org/docs/challenge-types/>).
- Para TrackIn: `trackin.gutis.com` (o un subdominio interno de un dominio que
  Gutis posea) resuelve en el DNS interno a la IP privada; el certificado se
  emite validando el TXT en el DNS público.
- **No sirve para `.local` ni para IP privadas:** las CA públicas no emiten
  para "Internal Names or Reserved IP Addresses" (CA/Browser Forum, Baseline
  Requirements v2.3.1, sección 4.2.2; definición de *Internal Name* en 1.6.1,
  <https://cabforum.org/working-groups/server/baseline-requirements/requirements/>).
- **Implica:**
  - Ningún equipo necesita instalar nada: la raíz ya es confiable.
  - El proveedor de DNS debe tener API para automatizar; las credenciales de esa
    API en el servidor amplían el daño si lo comprometen, y Let's Encrypt
    recomienda credenciales acotadas o validar desde otra máquina (misma página).
  - El nombre queda público en los registros de Certificate Transparency: "Let's
    Encrypt submits all certificates we issue to CT logs"
    (<https://letsencrypt.org/docs/ct-logs/>). Solo el nombre, no el acceso.
  - La renovación debe ser automática y vigilada: el perfil por defecto pasa de
    90 a 64 días el 10/02/2027 y a 45 días el 16/02/2028
    (<https://letsencrypt.org/2025/12/02/from-90-to-45>). El TLS va en el proxy
    corporativo (`docs/deployment.md`), así que la renovación la hace TI allí.

#### C. Parche sin HTTPS: política del navegador para la pantalla de planta

- La spec permite orígenes configurados como confiables (sección 7.2). En Edge,
  la política `OverrideSecurityRestrictionsOnInsecureOrigin` acepta orígenes o
  patrones de host para los que no aplican las restricciones de orígenes
  inseguros; equivale a `--unsafely-treat-insecure-origin-as-secure` y Microsoft
  la describe para "legacy applications that can't deploy TLS or for internal
  web development staging servers"
  (<https://learn.microsoft.com/en-us/deployedge/microsoft-edge-browser-policies/overridesecurityrestrictionsoninsecureorigin>,
  actualizada el 01/10/2026). Chrome tiene una política con el mismo nombre.
- **Implica:** el Wake Lock funcionaría en ese equipo, pero el tráfico sigue sin
  cifrar (incluido el inicio de sesión). Sirve como puente, no como solución.

#### D. Sin Wake Lock

- Configurar la energía del equipo de planta para que la pantalla no se apague.
  Es lo que ya hace TrackIn por defecto cuando la API no está.

### 2.6 Recomendación

- HTTPS en el proxy corporativo con un nombre de dominio real
  (`trackin.gutis.com`, ya previsto), no `trackin.gutis.local`.
- **Opción B** si Gutis controla ese dominio y su DNS tiene API: es la que menos
  toca los equipos de los usuarios.
- **Opción A** si TI ya opera una CA interna y todos los equipos (incluida la
  pantalla de planta) están en el dominio.
- Mientras llega el HTTPS: configurar la energía del equipo de planta (D) y,
  si hace falta el Wake Lock antes, la política del navegador (C) solo en ese
  equipo.
- La pantalla completa no depende de nada de esto.

---

## Fuentes

Consultadas el 06/11/2026.

- OSMF, Tile Usage Policy: <https://operations.osmfoundation.org/policies/tiles/>
- OpenStreetMap operations, issue #737: <https://github.com/openstreetmap/operations/issues/737>
- Stadia Maps, precios: <https://stadiamaps.com/pricing/>
- Stadia Maps, autenticación: <https://docs.stadiamaps.com/authentication/>
- MapTiler Cloud, precios: <https://www.maptiler.com/cloud/pricing/>
- Thunderforest, precios: <https://www.thunderforest.com/pricing/>
- Thunderforest, términos: <https://www.thunderforest.com/terms/>
- Protomaps, documentación: <https://docs.protomaps.com/>
- Protomaps, descargas: <https://docs.protomaps.com/basemaps/downloads>
- Protomaps, PMTiles en Leaflet: <https://docs.protomaps.com/pmtiles/leaflet>
- W3C, Secure Contexts: <https://www.w3.org/TR/secure-contexts/>
- MDN, Secure contexts: <https://developer.mozilla.org/en-US/docs/Web/Security/Secure_Contexts>
- W3C, Screen Wake Lock API: <https://w3c.github.io/screen-wake-lock/>
- MDN, Screen Wake Lock API: <https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API>
- WHATWG, Fullscreen API: <https://fullscreen.spec.whatwg.org/>
- MDN, Element.requestFullscreen(): <https://developer.mozilla.org/en-US/docs/Web/API/Element/requestFullscreen>
- Microsoft Learn, distribuir certificados por GPO: <https://learn.microsoft.com/en-us/windows-server/identity/ad-cs/distribute-certificates-group-policy>
- Chromium, Chrome Root Store FAQ: <https://chromium.googlesource.com/chromium/src/+/main/net/data/ssl/chrome_root_store/faq.md>
- Let's Encrypt, tipos de desafío: <https://letsencrypt.org/docs/challenge-types/>
- Let's Encrypt, Certificate Transparency: <https://letsencrypt.org/docs/ct-logs/>
- Let's Encrypt, vigencia de 45 días: <https://letsencrypt.org/2025/12/02/from-90-to-45>
- CA/Browser Forum, Baseline Requirements: <https://cabforum.org/working-groups/server/baseline-requirements/requirements/>
- Microsoft Learn, política OverrideSecurityRestrictionsOnInsecureOrigin: <https://learn.microsoft.com/en-us/deployedge/microsoft-edge-browser-policies/overridesecurityrestrictionsoninsecureorigin>
