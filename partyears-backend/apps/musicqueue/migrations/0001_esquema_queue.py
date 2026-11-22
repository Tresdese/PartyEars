from django.db import migrations

# Schema copied from the BD specification, annex A.4.
CREAR_ESQUEMA_QUEUE = """
CREATE SCHEMA queue;
CREATE TABLE queue.cola (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  party_id uuid UNIQUE, -- RE: party.party.id
  usuario_id uuid, -- RE: auth.usuario.id
  version bigint NOT NULL DEFAULT 0 CHECK (version >= 0),
  version_party bigint CHECK (version_party >= 0),
  creada_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT cola_usuario_uq UNIQUE (usuario_id),
  CONSTRAINT cola_propietario_ck CHECK (
    (party_id IS NULL) <> (usuario_id IS NULL)
  ),
  CONSTRAINT cola_version_party_ck CHECK (
    (party_id IS NULL) = (version_party IS NULL)
  )
);
CREATE TABLE queue.elemento_cola (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  cola_id uuid NOT NULL REFERENCES queue.cola(id)
    ON DELETE RESTRICT,
  recurso_audio_id uuid NOT NULL, -- RE: music.recurso_audio.id
  agregado_por uuid NOT NULL, -- RE: auth.usuario.id
  orden bigint NOT NULL CHECK (orden > 0),
  estado varchar(15) NOT NULL DEFAULT 'pendiente' CHECK
    (estado IN ('pendiente', 'reproduciendo', 'pausada',
                'reproducida', 'omitida', 'retirada')),
  agregado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  inicio_en timestamptz,
  fin_en timestamptz,
  posicion_base_ms bigint NOT NULL DEFAULT 0
    CHECK (posicion_base_ms >= 0),
  referencia_en timestamptz,
  CONSTRAINT elemento_orden_uq UNIQUE (cola_id, orden)
    DEFERRABLE INITIALLY IMMEDIATE,
  CHECK (inicio_en IS NULL OR inicio_en >= agregado_en),
  CHECK (fin_en IS NULL OR
    fin_en >= COALESCE(inicio_en, agregado_en)),
  CHECK (referencia_en IS NULL OR
    (inicio_en IS NOT NULL AND referencia_en >= inicio_en)),
  CHECK (fin_en IS NULL OR referencia_en IS NULL
    OR fin_en >= referencia_en),
  CHECK (
    (estado = 'pendiente' AND inicio_en IS NULL
      AND fin_en IS NULL AND referencia_en IS NULL
      AND posicion_base_ms = 0)
    OR (estado IN ('reproduciendo', 'pausada')
      AND inicio_en IS NOT NULL AND fin_en IS NULL
      AND referencia_en IS NOT NULL)
    OR (estado = 'reproducida' AND inicio_en IS NOT NULL
      AND fin_en IS NOT NULL AND referencia_en IS NOT NULL)
    OR (estado = 'omitida' AND fin_en IS NOT NULL
      AND ((inicio_en IS NULL AND referencia_en IS NULL
            AND posicion_base_ms = 0)
        OR (inicio_en IS NOT NULL AND referencia_en IS NOT NULL)))
    OR (estado = 'retirada' AND inicio_en IS NULL
      AND fin_en IS NOT NULL AND referencia_en IS NULL
      AND posicion_base_ms = 0)
  )
);
CREATE UNIQUE INDEX elemento_actual_uq
  ON queue.elemento_cola (cola_id)
  WHERE estado IN ('reproduciendo', 'pausada');
CREATE INDEX elemento_cola_estado_orden_ix
  ON queue.elemento_cola (cola_id, estado, orden);
CREATE INDEX elemento_recurso_ix
  ON queue.elemento_cola (recurso_audio_id);
-- Infraestructura transaccional
CREATE TABLE queue.operacion_confirmada (
  actor_id uuid NOT NULL, -- RE: auth.usuario.id
  clave uuid NOT NULL,
  operacion varchar(64) NOT NULL CHECK (btrim(operacion) <> ''),
  solicitud_sha256 bytea NOT NULL
    CHECK (octet_length(solicitud_sha256) = 32),
  codigo_respuesta smallint NOT NULL
    CHECK (codigo_respuesta BETWEEN 200 AND 499),
  resultado jsonb NOT NULL CHECK (jsonb_typeof(resultado) = 'object'),
  confirmada_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (actor_id, clave)
);
CREATE TABLE queue.evento_salida (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agregado_id uuid NOT NULL REFERENCES queue.cola(id)
    ON DELETE RESTRICT,
  version bigint NOT NULL CHECK (version >= 0),
  tipo varchar(80) NOT NULL CHECK (btrim(tipo) <> ''),
  datos jsonb NOT NULL CHECK (jsonb_typeof(datos) = 'object'),
  creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  publicado_en timestamptz,
  intentos integer NOT NULL DEFAULT 0 CHECK (intentos >= 0),
  CHECK (publicado_en IS NULL OR publicado_en >= creado_en)
);
CREATE INDEX evento_salida_pendiente_ix
  ON queue.evento_salida (creado_en, id)
  WHERE publicado_en IS NULL;
CREATE TABLE queue.evento_entrada (
  evento_id uuid PRIMARY KEY,
  contenido_sha256 bytea NOT NULL
    CHECK (octet_length(contenido_sha256) = 32),
  procesado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

BORRAR_ESQUEMA_QUEUE = 'DROP SCHEMA queue CASCADE;'


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.RunSQL(CREAR_ESQUEMA_QUEUE, BORRAR_ESQUEMA_QUEUE),
    ]
