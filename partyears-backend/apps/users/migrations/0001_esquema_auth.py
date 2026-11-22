from django.db import migrations

CREAR_ESQUEMA_AUTH = """
CREATE SCHEMA auth;

CREATE TABLE auth.usuario (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre_usuario varchar(40) NOT NULL CHECK (btrim(nombre_usuario) <> ''),
    correo varchar(254) NOT NULL CHECK (btrim(correo) <> ''),
    contrasena_hash varchar(255) NOT NULL CHECK (btrim(contrasena_hash) <> ''),
    activo boolean NOT NULL DEFAULT true,
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX usuario_nombre_uq ON auth.usuario (lower(nombre_usuario));
CREATE UNIQUE INDEX usuario_correo_uq ON auth.usuario (lower(correo));

CREATE TABLE auth.sesion (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id uuid NOT NULL REFERENCES auth.usuario(id) ON DELETE RESTRICT,
    token_renovacion_hash varchar(64) NOT NULL UNIQUE,
    creada_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expira_en timestamptz NOT NULL,
    revocada_en timestamptz,
    CHECK (expira_en > creada_en),
    CHECK (revocada_en IS NULL OR revocada_en >= creada_en)
);

CREATE INDEX sesion_usuario_ix ON auth.sesion (usuario_id, revocada_en);
"""

BORRAR_ESQUEMA_AUTH = "DROP SCHEMA auth CASCADE;"


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.RunSQL(CREAR_ESQUEMA_AUTH, BORRAR_ESQUEMA_AUTH),
    ]
