from django.db import migrations

# Schema copied from the BD specification, annex A.6.
CREAR_ESQUEMA_LOGS = """
CREATE SCHEMA logs;
CREATE TABLE logs.servicio (
  codigo varchar(16) PRIMARY KEY,
  nombre varchar(60) NOT NULL CHECK (btrim(nombre) <> ''),
  CHECK (codigo IN ('auth', 'music', 'queue',
                   'party', 'streaming', 'logs'))
);
INSERT INTO logs.servicio (codigo, nombre) VALUES
  ('auth', 'Autenticacion'), ('music', 'Catalogo musical'),
  ('queue', 'Cola y reproduccion'), ('party', 'Parties'),
  ('streaming', 'Voz en directo'), ('logs', 'Registro de eventos');
CREATE TABLE logs.evento_log (
  id uuid PRIMARY KEY, -- ID generado por el productor
  servicio_codigo varchar(16) NOT NULL
    REFERENCES logs.servicio(codigo) ON DELETE RESTRICT,
  tipo varchar(80) NOT NULL CHECK (btrim(tipo) <> ''),
  nivel varchar(10) NOT NULL DEFAULT 'info'
    CHECK (nivel IN ('debug', 'info', 'warning',
                     'error', 'critical')),
  ocurrido_en timestamptz NOT NULL,
  recibido_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actor_usuario_id uuid, -- RE opcional: auth.usuario.id
  party_id uuid, -- RE opcional: party.party.id
  recurso_tipo varchar(40),
  recurso_id uuid,
  correlacion_id uuid,
  mensaje text NOT NULL CHECK (btrim(mensaje) <> ''),
  detalle jsonb NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(detalle) = 'object'),
  CHECK ((recurso_tipo IS NULL AND recurso_id IS NULL)
    OR (recurso_tipo IS NOT NULL AND recurso_id IS NOT NULL))
);
CREATE INDEX evento_servicio_tiempo_ix
  ON logs.evento_log (servicio_codigo, ocurrido_en DESC);
CREATE INDEX evento_tiempo_ix ON logs.evento_log (ocurrido_en DESC);
CREATE INDEX evento_correlacion_ix
  ON logs.evento_log (correlacion_id)
  WHERE correlacion_id IS NOT NULL;
"""

BORRAR_ESQUEMA_LOGS = 'DROP SCHEMA logs CASCADE;'


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.RunSQL(CREAR_ESQUEMA_LOGS, BORRAR_ESQUEMA_LOGS),
    ]
