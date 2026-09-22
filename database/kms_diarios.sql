-- Kilómetros por unidad y por día, traídos del servicio de rastreo satelital.
--
-- Por qué existe: el proveedor conserva alrededor de 6 meses de recorridos y su odómetro
-- es un parcial que se reinicia cada medianoche local. Para tener kilometraje acumulado
-- propio hay que guardarlo acá.
--
-- La clave (patente, fecha) hace que el backfill sea idempotente: correrlo dos veces no
-- duplica nada y permite reanudarlo si se corta.

create table if not exists kms_diarios (
    id           uuid primary key default gen_random_uuid(),
    patente      text        not null,
    fecha        date        not null,

    -- NULL cuando el equipo no reportó: es "no sabemos", no "no anduvo".
    -- Un 0 acá es una afirmación: el camión estuvo quieto y el equipo lo confirmó.
    km           numeric(10, 2),

    -- con_movimiento | detenido | sin_datos
    estado       text        not null,

    -- Se guardan para poder auditar la clasificación sin volver a pedirle al proveedor.
    tramos       integer     not null default 0,
    paradas      integer     not null default 0,
    eventos      integer     not null default 0,

    actualizado_en timestamptz not null default now(),

    constraint kms_diarios_unico unique (patente, fecha),
    constraint kms_diarios_estado check (estado in ('con_movimiento', 'detenido', 'sin_datos')),
    -- Un día sin datos no puede tener kilómetros, y uno con datos no puede tenerlos nulos.
    constraint kms_diarios_coherente check (
        (estado = 'sin_datos' and km is null) or (estado <> 'sin_datos' and km is not null)
    )
);

create index if not exists kms_diarios_patente_fecha on kms_diarios (patente, fecha desc);
create index if not exists kms_diarios_fecha on kms_diarios (fecha desc);
