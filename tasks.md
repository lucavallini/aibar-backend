# Plan de Backend — AIBAR SRL App Manager

Documento de referencia para entender la arquitectura del backend y el orden en que se construye. Pensado para poner en contexto a cualquier persona (o IA) que se sume al proyecto.

**Stack:** FastAPI (Python) + Supabase (PostgreSQL) + JWT propio para autenticación.

**Estado:** los archivos marcados con ✅ ya están hechos. Los marcados con ⬜ son los próximos pasos.

---

## 0) Base del proyecto (transversal, se usa en todo)

### ✅ `app/config.py`
**Función:** centraliza la lectura de variables de entorno (`.env`) de forma tipada, usando `pydantic-settings`. Si falta una variable obligatoria, la app falla al arrancar con un error claro.

- **Clase `Settings(BaseSettings)`** — variables:
  - `supabase_url: str`
  - `supabase_service_key: str`
  - `jwt_secret: str`
  - `jwt_algorithm: str` (default `"HS256"`)
  - `jwt_expire_minutes: int` (default `480`)
- **Variable `settings`** — instancia ya creada de `Settings`, se importa desde cualquier otro archivo (`from app.config import settings`).

### ✅ `app/database.py`
**Función:** crea y expone el cliente de conexión a Supabase, usando la `service_role key` (bypassea RLS, pensado para uso exclusivo del backend).

- **Función `get_supabase() -> Client`** — arma y devuelve un cliente nuevo de Supabase.
- **Variable `supabase`** — instancia ya creada, es la que se usa en la práctica en todos los `services` (`from app.database import supabase`).

### ✅ `app/core/security.py`
**Función:** funciones puras de seguridad, sin conocimiento de la base de datos. Solo hashean/verifican contraseñas (más adelante también genera/valida JWT).

- **Variable `pwd_context`** — instancia de `CryptContext` configurada con el esquema `bcrypt`.
- **Función `hash_password(password: str) -> str`** — hashea una contraseña en texto plano.
- **Función `verify_password(plain_password: str, hashed_password: str) -> bool`** — compara una contraseña en texto plano contra su hash.
- ⬜ **Función `create_access_token(data: dict) -> str`** (pendiente) — genera un JWT firmado con `jwt_secret`, con expiración según `jwt_expire_minutes`.
- ⬜ **Función `decode_access_token(token: str) -> dict`** (pendiente) — valida y decodifica un JWT recibido, lanza excepción si es inválido o expiró.

### ⬜ `app/dependencies.py`
**Función:** dependencias reutilizables de FastAPI que se inyectan en los endpoints — quién está haciendo el request y si tiene permiso.

- **Función `get_current_user(token: str) -> UsuarioOut`** — extrae el JWT del header `Authorization`, lo decodifica (usa `decode_access_token`), busca el usuario en Supabase y lo devuelve. Si el token es inválido, lanza `HTTPException 401`.
- **Función `require_rol(*roles_permitidos: str)`** — devuelve una dependencia que chequea que `current_user.rol` esté dentro de `roles_permitidos`. Si no, lanza `HTTPException 403`. Se usa así en los routers: `Depends(require_rol("administrador"))`.

### ✅ `app/main.py`
**Función:** punto de entrada de la aplicación. Instancia FastAPI, configura CORS (para que Angular pueda llamar a la API) e incluye todos los routers.

- **Variable `app`** — instancia de `FastAPI`.
- **Función `health_check()`** — endpoint `GET /`, confirma que la API está viva.
- ⬜ Configuración de **CORS middleware** (pendiente, necesario antes de conectar el frontend).
- Se van sumando acá los `app.include_router(...)` de cada módulo a medida que se crean.

---

## 1) Módulo Usuarios (login y gestión de cuentas)

### ✅ `app/models/usuario.py`
**Función:** esquemas Pydantic de entrada/salida para la entidad `usuarios`. Separa lo que se recibe (`Create`) de lo que se devuelve (`Out`), para nunca exponer el `password_hash`.

- **Clase `UsuarioCreate(BaseModel)`** — campos: `nombre_completo`, `dni`, `password`, `rol` (default `"empleado"`). Es lo que llega en el body al crear un usuario.
- **Clase `UsuarioOut(BaseModel)`** — campos: `id`, `nombre_usuario`, `nombre_completo`, `dni`, `rol`, `activo`, `creado_en`. Es lo que se devuelve como respuesta (nunca incluye password).

### ✅ `app/services/usuario_service.py`
**Función:** lógica de negocio de usuarios — generar el `nombre_usuario` automáticamente, evitar DNIs duplicados, hashear contraseña e insertar en Supabase.

- **Función `_normalizar(texto: str) -> str`** — saca tildes y pasa a minúscula (uso interno, prefijo `_`).
- **Función `_generar_base_usuario(nombre_completo: str) -> str`** — arma `nombre.apellido` en minúscula sin caracteres raros (uso interno).
- **Función `generar_nombre_usuario(nombre_completo: str, dni: str) -> str`** — devuelve `nombre.apellido`, y si ya existe, le agrega los últimos 4 dígitos del DNI (`nombre.apellido.1234`).
- **Función `crear_usuario(datos: UsuarioCreate) -> dict`** — valida DNI único, genera `nombre_usuario`, hashea password, inserta en la tabla `usuarios` y devuelve el registro creado.

### ✅ `app/routers/usuarios.py`
**Función:** expone los endpoints HTTP de usuarios.

- **Variable `router`** — instancia de `APIRouter(prefix="/usuarios", tags=["usuarios"])`.
- **Función `alta_usuario(datos: UsuarioCreate)`** — `POST /usuarios/`. Llama a `crear_usuario` y devuelve un `UsuarioOut`.
  - ⚠️ Pendiente: proteger este endpoint con `Depends(require_rol("administrador"))` en cuanto el login esté funcionando (hoy está abierto para poder crear el primer admin).
- ⬜ **Función `listar_usuarios()`** (pendiente) — `GET /usuarios/`, solo admin.
- ⬜ **Función `dar_de_baja_usuario(usuario_id)`** (pendiente) — soft-delete (`activo = false`), solo admin.

---

## 2) Módulo Auth (login) — próximo paso

### ✅ `app/models/token.py`
**Función:** esquemas Pydantic relacionados al JWT.

- **Clase `Token(BaseModel)`** — campos: `access_token: str`, `token_type: str` (default `"bearer"`). Es la respuesta del login.
- **Clase `TokenPayload(BaseModel)`** — campos: `sub` (id de usuario), `rol`, `exp`. Es lo que va *adentro* del JWT.

### ✅ `app/services/auth_service.py`
**Función:** junta todo lo necesario para loguear a alguien — busca el usuario, verifica password, genera el token.

- **Función `autenticar_usuario(nombre_usuario: str, password: str) -> dict`** — busca el usuario en Supabase por `nombre_usuario`, valida con `verify_password`, y si es correcto arma y devuelve el `access_token` usando `create_access_token`. Si falla, lanza `HTTPException 401`.

### ✅ `app/routers/auth.py`
**Función:** expone el endpoint de login.

- **Variable `router`** — `APIRouter(prefix="/auth", tags=["auth"])`.
- **Función `login(form_data: OAuth2PasswordRequestForm)`** — `POST /auth/login`. Recibe `username`/`password` como form-data (estándar OAuth2), llama a `autenticar_usuario`, devuelve un `Token`.

---

## 3) Módulo Camiones

### ⬜ `app/models/camion.py`
- **Clase `CamionCreate`** — `patente`, `marca`, `modelo`, `anio`, `tipo`.
- **Clase `CamionOut`** — todo lo anterior + `id`, `activo`, `creado_en`.
- **Clase `CamionUpdate`** — mismos campos que `Create`, todos opcionales (para editar parcialmente).

### ⬜ `app/services/camion_service.py`
- **Función `crear_camion(datos: CamionCreate) -> dict`**
- **Función `listar_camiones(activos_only: bool = True) -> list`**
- **Función `actualizar_camion(camion_id, datos: CamionUpdate) -> dict`**
- **Función `dar_de_baja_camion(camion_id) -> dict`** — soft-delete (`activo = false`).

### ⬜ `app/routers/camiones.py`
- **Función `alta_camion(...)`** — `POST /camiones/`
- **Función `obtener_camiones(...)`** — `GET /camiones/`
- **Función `editar_camion(...)`** — `PATCH /camiones/{camion_id}`
- **Función `baja_camion(...)`** — `DELETE /camiones/{camion_id}` (soft-delete)

---

## 4) Módulo Choferes

### ⬜ `app/models/chofer.py`
- **Clase `ChoferCreate`** — `nombre_completo`, `dni`, `telefono`, `camion_id` (opcional).
- **Clase `ChoferOut`** — + `id`, `estado`, `activo`, `creado_en`, `creado_por`.
- **Clase `ChoferUpdate`** — campos editables (nombre, teléfono, camión asignado, estado).

### ⬜ `app/services/chofer_service.py`
- **Función `crear_chofer(datos: ChoferCreate, creado_por: UUID) -> dict`**
- **Función `listar_choferes(activos_only: bool = True) -> list`**
- **Función `obtener_chofer_detalle(chofer_id) -> dict`** — incluye historial de viajes.
- **Función `actualizar_estado_chofer(chofer_id, nuevo_estado: str) -> dict`**
- **Función `calcular_kms_mes_actual(chofer_id) -> float`** — `SUM(kms_recorridos)` de `viajes` filtrando por `chofer_id` y fecha del mes en curso.
- **Función `calcular_kms_historico(chofer_id) -> list`** — `SUM(kms_recorridos) GROUP BY mes` para el detalle avanzado.
- **Función `dar_de_baja_chofer(chofer_id) -> dict`** — soft-delete.

### ⬜ `app/routers/choferes.py`
- **Función `alta_chofer(...)`** — `POST /choferes/` (solo admin)
- **Función `obtener_choferes(...)`** — `GET /choferes/`
- **Función `obtener_chofer_por_id(...)`** — `GET /choferes/{chofer_id}` (incluye kms del mes + histórico)
- **Función `editar_chofer(...)`** — `PATCH /choferes/{chofer_id}`
- **Función `baja_chofer(...)`** — `DELETE /choferes/{chofer_id}` (solo admin)

---

## 5) Módulo Viajes (el corazón del sistema)

### ⬜ `app/models/viaje.py`
- **Clase `ViajeCreate`** — `chofer_id`, `camion_id`, `origen`, `destino`, `carga`, `tarifa`, `fecha_inicio`.
- **Clase `ViajeOut`** — todos los campos de la tabla `viajes`.
- **Clase `ViajeEditar`** — campos editables (destino, tarifa, carga, etc).
- **Clase `ViajeCancelar`** — `motivo_cancelacion: str`.
- **Clase `ViajeFinalizar`** — `fecha_fin`, `kms_recorridos`.

### ⬜ `app/services/viaje_service.py`
- **Función `crear_viaje(datos: ViajeCreate, asignado_por: UUID) -> dict`** — valida que el chofer esté `disponible` con **optimistic locking** (`UPDATE choferes SET estado='viajando' WHERE id=X AND estado='disponible'`; si afecta 0 filas → `HTTPException 409`), crea el viaje, y llama a `registrar_evento(...)` de auditoría.
- **Función `editar_viaje(viaje_id, datos: ViajeEditar, usuario_id: UUID) -> dict`** — actualiza y audita (`tipo_accion='edicion'`).
- **Función `cancelar_viaje(viaje_id, datos: ViajeCancelar, usuario_id: UUID) -> dict`** — pasa el viaje a `cancelado`, guarda `motivo_cancelacion`, y en la misma operación vuelve el chofer a `disponible`. Audita (`tipo_accion='cancelacion'`).
- **Función `iniciar_viaje(viaje_id, usuario_id: UUID) -> dict`** — pasa de `pendiente` a `en_curso` (cualquier empleado puede hacerlo, no solo el creador).
- **Función `finalizar_viaje(viaje_id, datos: ViajeFinalizar, usuario_id: UUID) -> dict`** — carga `fecha_fin` y `kms_recorridos`, pasa a `finalizado`, vuelve el chofer a `disponible`.
- **Función `listar_viajes(filtros: dict) -> list`** — filtros por chofer, estado, rango de fechas.

### ⬜ `app/routers/viajes.py`
- **Función `alta_viaje(...)`** — `POST /viajes/`
- **Función `obtener_viajes(...)`** — `GET /viajes/`
- **Función `editar_viaje_endpoint(...)`** — `PATCH /viajes/{viaje_id}`
- **Función `cancelar_viaje_endpoint(...)`** — `POST /viajes/{viaje_id}/cancelar`
- **Función `iniciar_viaje_endpoint(...)`** — `POST /viajes/{viaje_id}/iniciar`
- **Función `finalizar_viaje_endpoint(...)`** — `POST /viajes/{viaje_id}/finalizar`

---

## 6) Módulo Multas

### ⬜ `app/models/multa.py`
- **Clase `MultaCreate`** — `camion_id`, `chofer_id` (opcional), `viaje_id` (opcional), `motivo`, `monto`, `fecha`.
- **Clase `MultaOut`** — + `id`, `registrado_por`, `creado_en`.

### ⬜ `app/services/multa_service.py`
- **Función `crear_multa(datos: MultaCreate, registrado_por: UUID) -> dict`**
- **Función `listar_multas_por_camion(camion_id) -> list`**
- **Función `listar_multas_por_chofer(chofer_id) -> list`**

### ⬜ `app/routers/multas.py`
- **Función `alta_multa(...)`** — `POST /multas/`
- **Función `obtener_multas(...)`** — `GET /multas/` (con query params `camion_id` o `chofer_id`)

---

## 7) Módulo Auditoría

### ⬜ `app/models/auditoria.py`
- **Clase `AuditoriaOut`** — `id`, `usuario_id`, `tipo_accion`, `entidad`, `entidad_id`, `detalle`, `fecha_hora`.

### ⬜ `app/services/auditoria_service.py`
- **Función `registrar_evento(usuario_id: UUID, tipo_accion: str, entidad: str, entidad_id: UUID, detalle: str = None) -> None`** — inserta un registro en la tabla `auditoria`. Se llama desde `viaje_service.py` (y a futuro desde otros services) cada vez que un empleado hace una acción relevante. **Esta es la función clave que conecta todo el sistema de auditoría definido en los requerimientos.**
- **Función `listar_auditoria(filtros: dict) -> list`** — para el panel del admin (filtra por usuario, entidad, rango de fechas).

### ⬜ `app/routers/auditoria.py`
- **Función `obtener_auditoria(...)`** — `GET /auditoria/` (solo admin, usa `Depends(require_rol("administrador"))`).

---

## Orden recomendado de trabajo (de acá en adelante)

1. **Terminar Auth** (`token.py` → `auth_service.py` → `routers/auth.py`) — sin esto no podés probar permisos.
2. **`dependencies.py`** (`get_current_user`, `require_rol`) — depende de que Auth ya exista.
3. **Proteger `POST /usuarios/`** con `require_rol("administrador")` una vez que haya al menos un admin.
4. **Módulo Camiones** (el más simple, CRUD directo, sirve para practicar el patrón model → service → router).
5. **Módulo Choferes** (depende de Camiones por la FK `camion_id`).
6. **Módulo Viajes** (el más complejo: depende de Choferes + Camiones + Usuarios, incluye optimistic locking).
7. **`auditoria_service.py`** — en paralelo con Viajes, ya que se llama desde ahí.
8. **Módulo Multas** (depende de Camiones + Choferes + Viajes).
9. **Módulo Auditoría (router)** — panel de consulta para el admin.
10. **CORS en `main.py`** — antes de conectar el frontend Angular.

Cada módulo nuevo sigue siempre el mismo patrón de 3 capas:
**`models/` (forma de los datos) → `services/` (lógica de negocio) → `routers/` (expone los endpoints HTTP)**.