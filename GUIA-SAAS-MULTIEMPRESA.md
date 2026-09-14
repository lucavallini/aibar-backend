# Guía: convertir la app en un SaaS multi-empresa (marca blanca)

> Documento de diseño y hoja de ruta. **No está commiteado.** Copialo al nuevo
> directorio cuando clones el proyecto.
>
> Fecha: 2026-09-01

---

## 1. Objetivo

Tomar esta app (hoy de un solo cliente) y convertirla en un producto que se
vende a varias empresas logísticas. Cada empresa:

- entra por su propio subdominio (`empresaA.tuproducto.com`),
- ve su nombre, su logo y sus colores (marca blanca),
- tiene sus datos **totalmente aislados**: no sabe que existen otras empresas,
  no puede ver ni un registro ajeno,
- usa sus propias claves de terceros (GPS/DVL, mapa).

El SaaS vive en un **repo nuevo**. Este proyecto es la base: se clona y se
modifica ahí. El cliente real actual queda intacto y después se migra al SaaS
como "empresa 1".

---

## 2. Decisiones ya tomadas

| Tema | Decisión |
|---|---|
| Aislamiento de datos | **Un schema de Postgres por empresa**, en una sola instancia Postgres, cada schema con su propio rol sin acceso a los demás (modelo "B1"). Se conserva `supabase.table(...)` como capa de datos. |
| Instancia física separada por cliente (modelo "B2") | Descartado por ahora. Sólo si un cliente enterprise lo exige por contrato. |
| Alta de empresas | **Manual**, con runbook + script. Sin panel de aprovisionamiento automático todavía. |
| Acceso de cada empresa | **Subdominio** + pintado de marca en vivo. Dominio propio sólo para el cliente que lo pida. |
| Identidad | **Usuarios por empresa** (en el schema de cada una). Sin identidad compartida entre empresas. Super-admin (vos) aparte, en el plano de control. |
| Punto de partida | **Copiar backend + frontend actuales** al repo nuevo y evolucionarlos. |
| Cobro | **Por fuera de la app**, **suscripción mensual** (no pago único). Fee único de alta + desarrollo a medida presupuestado aparte. |

---

## 3. Arquitectura general

```
                 empresaA.tuproducto.com          empresaB.tuproducto.com
                          │                                │
                          ▼                                ▼
              ┌───────────────────────────────────────────────────┐
              │   FRONTEND (una sola SPA Angular desplegada)       │
              │   Lee el subdominio → pide la marca al backend →   │
              │   se pinta (nombre, logo, colores) en vivo         │
              └───────────────────────────────────────────────────┘
                          │  Authorization: Bearer <jwt>
                          │  Host: empresaA.tuproducto.com
                          ▼
              ┌───────────────────────────────────────────────────┐
              │   BACKEND (una sola API FastAPI desplegada)        │
              │   Middleware: Host → empresa → schema + config     │
              │   Todos los services corren con .schema("empresa_a")│
              └───────────────────────────────────────────────────┘
                    │                                  │
                    ▼                                  ▼
        ┌───────────────────────┐        ┌──────────────────────────────┐
        │  PLANO DE CONTROL     │        │  POSTGRES DE CLIENTES         │
        │  (base propia)        │        │  schema empresa_a  (rol a)    │
        │  - registro empresas  │        │  schema empresa_b  (rol b)    │
        │  - config y keys      │        │  schema empresa_c  (rol c)    │
        │  - plan/estado/cobro  │        │  … un schema por empresa      │
        │  - super-admin (vos)  │        │  + schema _plantilla          │
        └───────────────────────┘        └──────────────────────────────┘
```

- **Un solo despliegue** de backend y uno de frontend sirven a todas las
  empresas. No hay N deploys.
- El **plano de control** es una base chica y aparte. Es lo único que sabe qué
  empresas existen. Ninguna base de cliente la conoce, ni conoce a las otras.
- El **Postgres de clientes** puede ser un único proyecto Supabase o un Postgres
  propio. Cada empresa es un schema con un rol que sólo tiene permiso sobre ese
  schema. Aunque un bug del backend olvide filtrar, el motor lo frena.

---

## 4. Componentes

### 4.1 Plano de control

Base propia (separada de la de clientes) + endpoints internos. Guarda todo lo
que hace que cada empresa sea "suya".

**Tablas**

`empresas` — registro de inquilinos:

| campo | para qué |
|---|---|
| `id` | uuid |
| `slug` | `empresa_a` — es el subdominio y el nombre del schema |
| `nombre_visible` | "Transportes La Rioja S.A." — lo que se muestra |
| `dominio_propio` | `null` o `flota.empresaa.com` si lo pide |
| `db_schema` | normalmente igual al slug |
| `db_rol` / `db_password_enc` | credencial del rol Postgres de esa empresa (cifrada) |
| `estado_schema` | `aprovisionando` / `activo` / `suspendido` |
| `plan` | `chico` / `mediano` / `grande` |
| `estado_cobro` | `al_dia` / `moroso` / `suspendido` |
| `vence_el` | fecha del próximo vencimiento |
| `creada_en` | |

`empresa_branding` (1:1 con empresa):
`logo_url`, `color_primario`, `color_secundario`, `favicon_url`,
`nombre_corto`, `soporte_email`.

`empresa_integraciones` (keys de terceros por empresa, **cifradas**):
`gps_provider`, `gps_client_id_enc`, `gps_client_secret_enc`, `gps_base_url`,
`mapa_api_key_enc`, etc. Hoy esto está en `app/config.py` global; pasa a ser
por empresa.

`superadmins` — vos y quien te ayude a operar. Login aparte, no vive en ninguna
base de cliente. **TOTP obligatorio.**

`eventos_aprovisionamiento` — log **solo-agregar** (sin update ni delete) de
altas, bajas, suspensiones y accesos de soporte.

**Endpoints**

- **Público** (lo usa el frontend en cada carga): `GET /tenant/branding` —
  resuelve la empresa por el `Host` y devuelve sólo lo visual +
  `nombre_visible` + `estado_cobro`. Sin datos sensibles, sin keys.
- **Interno de resolución** (lo usa el backend, no expuesto): dado un `Host`,
  devuelve `schema`, credencial del rol e integraciones descifradas. Cacheado
  en memoria con TTL corto (~60 s).
- **Super-admin** (protegido, sólo vos): CRUD de empresas, marcar pagos,
  suspender/reactivar, disparar el script de alta.

**Conexión al Postgres de clientes**

El backend mantiene **un pool de conexiones por empresa activa**, cada uno
autenticado con el rol de esa empresa (no con un superusuario). Si el código
olvida filtrar, el rol igual no ve otro schema.

**Cifrado de secretos**

Keys de terceros y passwords de rol se guardan cifradas con una clave maestra
`CONTROL_PLANE_KEY` que vive en el gestor de secretos del hosting (Render/Fly
secrets), **nunca en el repo**. Procedimiento de rotación documentado.

**Endurecimiento**

- Backups automáticos diarios del plano de control, retención 30 días,
  restauración probada. Es la pieza más crítica: si se pierde, se pierde el
  mapa de todas las empresas.
- Super-admin con segundo factor (TOTP) y contraseña fuerte; sesión corta.
- Rate limit en `/tenant/branding` y en el login.
- HTTPS forzado + HSTS.
- Cada rol de Postgres de empresa con `USAGE` sólo sobre su schema y `REVOKE`
  sobre `public`.

### 4.2 Resolución de empresa por request

Cómo cada pedido HTTP termina apuntando al schema correcto sin que un service
pueda equivocarse de empresa.

```
1. Llega  GET /viajes   con  Host: empresaA.tuproducto.com  + Bearer <jwt>
2. Middleware de tenant:
     - extrae "empresaA" del Host
     - pide al plano de control (cache TTL 60s) → schema, rol, integraciones, estado_cobro
     - si la empresa no existe            → 404 genérico (no revela nada)
     - si estado_schema != activo         → 503 "en mantenimiento"
     - si estado_cobro == suspendido      → 402 "cuenta suspendida" (con página propia)
     - guarda el contexto en un ContextVar de la request
3. Autenticación:
     - valida el JWT con el secreto del backend
     - el JWT lleva sub, rol y  ten (slug de empresa)
     - si  ten  del token != empresa del Host  → 401  (token de otro tenant)
4. Capa de datos:
     - get_db() devuelve un cliente ligado al schema/rol de esa empresa
     - TODOS los services usan get_db(), nunca un cliente global
5. El service corre  select("*")  sobre el schema de la empresa y responde
```

Puntos de diseño:

- **`ContextVar` por request**, no variable global ni parámetro pasado a mano.
  El middleware lo setea, `get_db()` lo lee.
- **El `slug` de empresa viaja en el JWT (`ten`)** y se verifica contra el
  `Host`. Un token de empresa A es inservible en el subdominio de empresa B.
- **`get_db()` reemplaza al `supabase` global de hoy.** Único cambio que toca a
  todos los services, y es mecánico: `supabase.table(x)` → `get_db().table(x)`.
  El `.schema(...)` lo aplica `get_db()` internamente.
- **Doble candado**: aunque un service olvide todo esto, el rol de Postgres de
  esa conexión no puede leer otro schema. Falla a "no ve nada".
- **Errores genéricos hacia afuera**: "empresa no encontrada" y "no autorizado"
  no distinguen casos.
- El endpoint público de branding no pasa por autenticación pero sí por la
  resolución de empresa por `Host`.

### 4.3 Migraciones multi-schema

Hoy el schema se maneja a mano desde Supabase. Con N empresas eso no escala.

**Piezas**

- **Migraciones como archivos versionados en el repo**, numeradas, en SQL
  plano: `migraciones/0001_init.sql`, `0002_add_columna_kms.sql`, etc. Única
  fuente de verdad del schema.
- **Un runner** (`scripts/migrar.py`, o `yoyo-migrations`) que:
  1. Lee del plano de control las empresas con `estado_schema = activo`.
  2. Para cada schema: setea `search_path`, mira su tabla `_migraciones` (qué ya
     se aplicó), corre las pendientes **en orden**, cada una en su transacción,
     y registra el resultado.
  3. Si una empresa falla, corta ahí y reporta; las que ya pasaron quedan bien
     (cada schema lleva su propio registro, son independientes).
- **Un schema plantilla** (`_plantilla`) que siempre tiene todas las
  migraciones aplicadas. El alta de una empresa nueva es: `CREATE SCHEMA
  empresa_x` → crear rol → correr **todas** las migraciones contra `empresa_x` →
  sembrar datos base (roles, usuario admin inicial).

**Cambios sin downtime — patrón expandir/contraer**

Ejemplo, renombrar una columna:

1. **Expandir**: migración que *agrega* la columna nueva (nullable). Deploy.
2. Deploy del código que escribe en las dos y lee de la nueva.
3. **Backfill**: migración que copia datos viejos → nuevos.
4. **Contraer**: migración que borra la columna vieja. Deploy final.

Cambios aditivos simples (columna nueva opcional, tabla nueva) van en un paso.

**Orden de despliegue**

1. Correr migraciones contra `_plantilla` y contra una **empresa canaria** (la
   tuya, "empresa 1").
2. Verificar.
3. Correr contra el resto.
4. Deploy del backend.

### 4.4 Marca blanca en el frontend

Una sola SPA Angular desplegada que se ve distinta según el subdominio, sin
build por cliente.

**Arranque de la app**

1. Antes de renderizar el shell, un inicializador (`provideAppInitializer` en
   Angular 22) llama a `GET /tenant/branding`. El backend resuelve la empresa
   por el `Host`.
2. Respuesta: `nombre_visible`, `nombre_corto`, `logo_url`, `favicon_url`,
   `color_primario`, `color_secundario`, `soporte_email`, `estado_cobro`.
   **Nada sensible, ninguna key.**
3. Un `BrandingService` con un `signal()` guarda eso. Si la llamada falla, hay
   un branding por defecto para no dejar la pantalla rota.

**Aplicación del tema**

- **Colores por variables CSS**: el inicializador setea `--color-primario` y
  `--color-secundario` en `:root`. Los estilos con color de marca hardcodeado
  se pasan a esas variables. Refactor acotado y mecánico.
- **Logo** en el `Header` desde el signal del `BrandingService`.
- **`document.title` y favicon** dinámicos al cargar.
- **Login también tematizado**: lee el branding (no requiere auth), así el
  cliente ve su logo desde el primer momento.

**Cuenta suspendida**

Si `estado_cobro = suspendido`, pantalla de bloqueo a página completa con la
marca del cliente y su email de soporte, antes del login. El backend además
responde 402 en las rutas de datos: el bloqueo no depende sólo del frontend.

**Desarrollo local**

Los navegadores resuelven `*.localhost` a `127.0.0.1` solos:
`empresa-a.localhost:4200`, `empresa-b.localhost:4200` para probar varias
empresas sin tocar `/etc/hosts`. El backend lee el `Host` igual que en
producción.

**Sin build por cliente**

`environment.apiUrl` sigue saliendo de `environments/`. La empresa se distingue
por subdominio en tiempo de ejecución, no por compilación.

### 4.5 Aislamiento y seguridad (resumen)

1. **Datos**: schema por empresa + rol por empresa (`USAGE` sólo su schema,
   `REVOKE` sobre `public`). Pool de conexiones por empresa con su rol, nunca
   superusuario. Plano de control en base aparte con credencial propia.
2. **Identidad**: usuarios por empresa. JWT con `sub`, `rol`, `ten`; el
   middleware verifica `ten` contra el `Host`. Firma con secreto en el gestor
   de secretos. Expiración corta. Super-admin con TOTP y sin acceso a datos de
   clientes salvo modo "soporte" explícito y logueado.
3. **Transporte/borde**: HTTPS + HSTS. CORS restringido a `https://*.tuproducto.com`
   y a los dominios propios registrados. Rate limit en login y branding.
   Cabeceras `X-Content-Type-Options`, `X-Frame-Options: DENY`,
   `Referrer-Policy`.
4. **Secretos**: keys de terceros cifradas con `CONTROL_PLANE_KEY` (env var),
   descifradas sólo en memoria. Nada de secretos en el repo.
5. **Auditoría/respaldo**: auditoría de negocio por empresa (ya existe
   `auditoria_service`). Log de aprovisionamiento solo-agregar en el plano de
   control. Backups diarios de ambos Postgres, retención 30 días, restauración
   probada.
6. **Errores hacia afuera** genéricos: no revelan qué empresas existen.

---

## 5. Cómo arrancar — orden de construcción

Pensado como sub-proyectos independientes. Hacé uno, verificá, seguí.

### Fase 0 — Preparar el repo nuevo

1. Clonar este proyecto a otro directorio, repo git nuevo, remoto nuevo.
2. Copiar este `.md` al directorio nuevo.
3. Decidir nombre del producto y dominio. Registrar `.com` y `.com.ar`.
4. Levantar la instancia Postgres de clientes (un proyecto Supabase nuevo, o un
   Postgres administrado). Crear la base del plano de control (puede ser otra
   base en la misma instancia o un proyecto Supabase free aparte).

### Fase 1 — Migraciones (base de todo lo demás)

1. Volcar el schema actual a `migraciones/0001_init.sql` (podés sacarlo con
   `pg_dump --schema-only` del Supabase actual).
2. Escribir el runner (`scripts/migrar.py` o adoptar `yoyo-migrations`): recorre
   los schemas de empresas activas del plano de control y aplica pendientes.
3. Crear el schema `_plantilla` y aplicarle `0001`.
4. Probar: crear un schema `empresa_demo` a mano y correr el runner contra él.

### Fase 2 — Plano de control

1. Migraciones propias del plano de control (`empresas`, `empresa_branding`,
   `empresa_integraciones`, `superadmins`, `eventos_aprovisionamiento`).
2. Módulo de cifrado (Fernet / `cryptography`) con `CONTROL_PLANE_KEY`.
3. Cliente del plano de control en el backend: función que, dado un `Host`,
   devuelve `{schema, rol, password, integraciones, branding, estado_*}`, con
   cache en memoria TTL 60 s.
4. Endpoint público `GET /tenant/branding`.
5. Endpoints de super-admin (CRUD empresas, marcar pago, suspender/reactivar) +
   login de super-admin con TOTP.

### Fase 3 — Capa multi-tenant en el backend

1. `ContextVar` de contexto de request (`tenant_ctx`).
2. Middleware de resolución: `Host` → plano de control → setea `tenant_ctx`;
   maneja 404 / 503 / 402.
3. `app/database.py`: reemplazar el `supabase` global por `get_db()` que lee
   `tenant_ctx`, toma el pool de esa empresa y devuelve el cliente con
   `.schema(<slug>)` ya aplicado. Mantener un pool por empresa.
4. Cambio mecánico en todos los services: `supabase.table(` → `get_db().table(`.
   (Es puro reemplazo; los tests que hoy parchean `supabase.table` se adaptan
   para parchear `get_db`.)
5. JWT: agregar `ten` (slug) al emitir; verificar `ten == Host` en el
   middleware de auth. El login ahora resuelve empresa por `Host` antes de
   validar credenciales contra su schema.
6. `config.py`: sacar `gc_*` global; esos valores vienen del plano de control
   por empresa. `gc_client.py` recibe la config del `tenant_ctx`.
7. Ajustar CORS a `https://*.tuproducto.com`.

### Fase 4 — Marca blanca en el frontend

1. `BrandingService` (signal) + `provideAppInitializer` que llama a
   `/tenant/branding`.
2. Reemplazar colores de marca hardcodeados por `--color-primario` /
   `--color-secundario`; el inicializador las setea en `:root`.
3. `Header` y login toman logo/nombre del `BrandingService`.
4. `document.title` y favicon dinámicos.
5. Pantalla de bloqueo por `estado_cobro = suspendido`.
6. Dev: probar con `empresa-a.localhost:4200` y `empresa-b.localhost:4200`.

### Fase 5 — Runbook de alta (manual) y despliegue

1. Escribir `scripts/alta_empresa.py` (ver runbook abajo).
2. Configurar el hosting: backend con dominio wildcard `*.tuproducto.com`,
   certificado wildcard (Let's Encrypt / incluido en la plataforma), frontend
   con el mismo wildcard.
3. Configurar backups diarios de ambos Postgres. Probar una restauración.
4. Migrar el cliente real actual como `empresa 1` (crear su schema, importar sus
   datos, dar de alta en el plano de control, apuntar su subdominio).

### Fase 6 — Antes de vender

- Contrato SaaS + Anexo de datos + T&C + Política de Privacidad (mínimos, con
  abogado o plantilla revisada).
- Estar inscripto para facturar.
- Búsqueda y registro de marca en INPI.

---

## 6. Runbook de alta de una empresa (manual)

Objetivo: 15–30 min por empresa.

1. **Datos del cliente**: nombre visible, slug (`empresa_x`, minúsculas, sin
   espacios), plan, precio, email de soporte, logo, colores, keys de GPS/mapa.
2. **Crear el schema y el rol** en el Postgres de clientes:
   ```sql
   CREATE SCHEMA empresa_x;
   CREATE ROLE empresa_x_rol LOGIN PASSWORD '<generada>';
   GRANT USAGE ON SCHEMA empresa_x TO empresa_x_rol;
   ALTER DEFAULT PRIVILEGES IN SCHEMA empresa_x
     GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO empresa_x_rol;
   REVOKE ALL ON SCHEMA public FROM empresa_x_rol;
   ```
3. **Correr todas las migraciones** contra `empresa_x` (runner de la Fase 1).
4. **Sembrar** datos base: roles del sistema, primer usuario admin del cliente
   (con contraseña temporal).
5. **Dar de alta en el plano de control**: fila en `empresas` (con
   `db_password_enc` cifrada), `empresa_branding`, `empresa_integraciones`.
   `estado_schema = activo`, `estado_cobro = al_dia`, `vence_el` = hoy + 1 mes.
6. **DNS**: el subdominio ya funciona si tenés wildcard. Si el cliente quiere
   dominio propio, agregar CNAME + registrar `dominio_propio`.
7. **Verificar**: entrar a `empresa_x.tuproducto.com`, login con el admin
   temporal, revisar que se ve su marca y que no hay datos de otra empresa.
8. **Registrar el evento** en `eventos_aprovisionamiento`.

**Baja / suspensión**: `estado_cobro = suspendido` (bloquea acceso, conserva
datos). Baja definitiva: exportar datos → entregar al cliente → `DROP SCHEMA
empresa_x CASCADE` + `DROP ROLE` → registrar evento.

---

## 7. Costos

### Infraestructura mensual (todas las empresas juntas)

| Ítem | USD/mes | Nota |
|---|---|---|
| Hosting backend (Render/Fly/Railway) | 7 – 25 | El plan gratis "se duerme" |
| Hosting frontend (Netlify/Vercel) | 0 | Free tier alcanza un buen tiempo |
| Postgres de clientes (1 instancia) | 10 – 25 | Supabase Pro (25) / Postgres administrado (7–20) / VPS (5–10) |
| Base del plano de control | 0 – 7 | Proyecto Supabase free o base chica en la misma instancia |
| Email transaccional | 0 | Resend/Postmark free tier |
| Monitoreo de errores (Sentry) | 0 | Free tier |
| **Total para arrancar** | **~25 – 60** | Con B1 casi no sube al sumar clientes |

### Gastos únicos / legales

| Ítem | Costo aprox. | Urgencia |
|---|---|---|
| Dominio (`.com` + `.com.ar`) | USD 10 – 30/año | Ya |
| Certificado TLS wildcard | 0 | Incluido en la plataforma |
| Registro de marca INPI (1 clase) | USD 100 – 250 con gestor | Cuando el nombre esté decidido |
| Registro del software en DNDA | USD 20 – 50 | Opcional |
| Abogado: contrato + anexo datos + T&C + privacidad | USD 150 – 500 una vez | Antes de la primera venta |
| Inscripción para facturar (monotributo) | Según categoría | Ya |

El gasto real más grande es tu tiempo de desarrollo y soporte.

---

## 8. Legal (Argentina, SaaS B2B) — checklist

> No es asesoramiento legal. Es el mapa de qué contratar y en qué orden.

**Estructura**

- Estar inscripto (monotributo para empezar).
- Constituir una **SAS** cuando haya 2–3 clientes o ingresos serios: separa tu
  patrimonio personal del negocio.

**Contrato con cada empresa cliente** (lo más importante):

- Objeto: acceso al software **como servicio**, no venta ni entrega de código.
- Precio, forma de pago y **cláusula de ajuste** (índice + periodicidad).
- Nivel de servicio realista: disponibilidad "comercialmente razonable",
  ventanas de mantenimiento, canal y horario de soporte. **No prometer 99,9%.**
- **Límite de responsabilidad** topeado (p. ej. a lo pagado en los últimos 3–6
  meses). Exclusión de daños indirectos y lucro cesante.
- Plazo, renovación y rescisión: preaviso, y qué pasa con los datos al terminar
  → **exportación en formato estándar + borrado definitivo** en X días.
- El software es tuyo; **los datos cargados son del cliente**.
- Confidencialidad mutua.

**En el sitio**

- Términos y Condiciones y Política de Privacidad públicos.

**Protección de datos personales** (Ley 25.326, autoridad AAIP; viene ley nueva
más estricta):

- Datos de choferes (nombre, DNI, licencia) y usuarios **son datos personales**.
- Frente a tus clientes-empresa: ellos son el **responsable** y vos el
  **encargado de tratamiento**. Necesitás un **Anexo de Tratamiento de Datos**:
  qué datos tratás, para qué, medidas de seguridad, subcontratistas (hosting),
  devolución/borrado al final, aviso ante incidente.
- Obligaciones tuyas: política de privacidad, medidas de seguridad (Sección 4.5
  las cubre), atender derechos de acceso / rectificación / actualización /
  supresión, notificar brechas.
- Consultar al abogado si corresponde inscribir bases ante la AAIP.

**Propiedad intelectual — "¿hay que patentar?"**

- **No se patenta software en Argentina.** La Ley de Patentes excluye los
  programas de computación como tales.
- Ya tenés automáticamente el **derecho de autor** sobre el código (Ley 11.723),
  sin trámite.
- Opcional: depósito de la obra (software) en la **DNDA** — prueba de autoría y
  fecha, barato.
- **Lo que sí conviene: registrar la MARCA** (nombre + logo) en el **INPI**,
  clases 9 (software) y 42 (servicios SaaS). Es lo único con peso comercial:
  impide que otro use tu nombre. Dura 10 años renovables. Antes, **búsqueda de
  antecedentes**.
- Registrar los dominios.

**Si sumás gente**

- Todo colaborador (empleado o freelance) firma **cesión de derechos** sobre lo
  que produzca. Sin eso, el código lo tiene su autor.

**Terceros**

- Cumplir los términos del proveedor de GPS/DVL y del de mapas. Las keys por
  empresa ayudan a atribuir consumo y a que cada cliente pague su propio uso.

**Prioridad**

| Cuándo | Qué |
|---|---|
| Antes de la primera venta | Contrato SaaS + Anexo de datos + T&C + Privacidad (mínimos). Inscripción para facturar. |
| Ni bien el nombre esté decidido | Búsqueda + registro de marca en INPI. Registrar dominios. |
| Con 2–3 clientes o ingresos serios | Constituir SAS. Revisar inscripción de bases ante AAIP. |
| Opcional | Depósito del software en DNDA. |

---

## 9. Qué queda explícitamente afuera por ahora (YAGNI)

- SSO / login con Google corporativo.
- Panel de aprovisionamiento automático (el alta sigue siendo manual).
- Autoservicio de registro y pago.
- Pasarela de pagos integrada (el cobro es por fuera).
- Registro de auditoría inmutable con firma criptográfica.
- Aislamiento a nivel de instancia física por cliente (modelo B2), salvo que un
  enterprise lo exija por contrato.

---

## 10. Modelo comercial sugerido

- **Abono mensual por empresa**, escalonado por tamaño (cantidad de camiones, o
  de viajes/mes, o de usuarios): plan chico / mediano / grande.
- **Fee único de alta (setup)**: cubre el aprovisionamiento manual, la carga
  inicial de datos y la personalización de marca.
- **Desarrollo a medida** presupuestado aparte, por proyecto u hora, cuando un
  cliente quiere una función propia.

No pago único: vos cargás costo de hosting y soporte todos los meses, y el SaaS
es un servicio que operás, no un producto que entregás.
