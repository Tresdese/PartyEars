from django.db import migrations

CREAR_ESQUEMA_MUSIC = """
CREATE SCHEMA music;

CREATE TABLE music.artista (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre varchar(150) NOT NULL CHECK (btrim(nombre) <> ''),
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX artista_nombre_uq ON music.artista (lower(nombre));

CREATE TABLE music.cancion (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    titulo varchar(200) NOT NULL CHECK (btrim(titulo) <> ''),
    duracion_ms integer NOT NULL CHECK (duracion_ms > 0),
    creada_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX cancion_titulo_ix ON music.cancion (lower(titulo));

CREATE TABLE music.cancion_artista (
    id bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
    cancion_id uuid NOT NULL REFERENCES music.cancion(id) ON DELETE CASCADE,
    artista_id uuid NOT NULL REFERENCES music.artista(id) ON DELETE RESTRICT,
    orden smallint NOT NULL CHECK (orden > 0),
    PRIMARY KEY (cancion_id, artista_id),
    CONSTRAINT cancion_artista_orden_uq UNIQUE (cancion_id, orden)
);

CREATE TABLE music.recurso_audio (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cancion_id uuid NOT NULL REFERENCES music.cancion(id) ON DELETE CASCADE,
    tipo varchar(16) NOT NULL CHECK (tipo IN ('original', 'instrumental')),
    formato varchar(16) NOT NULL CHECK (btrim(formato) <> ''),
    mime_type varchar(64) NOT NULL CHECK (btrim(mime_type) <> ''),
    ruta_archivo text NOT NULL CHECK (btrim(ruta_archivo) <> ''),
    tamano_bytes bigint NOT NULL CHECK (tamano_bytes > 0),
    duracion_ms integer NOT NULL CHECK (duracion_ms > 0),
    disponible boolean NOT NULL DEFAULT true,
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT recurso_cancion_tipo_uq UNIQUE (cancion_id, tipo)
);
"""

BORRAR_ESQUEMA_MUSIC = "DROP SCHEMA music CASCADE;"


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.RunSQL(CREAR_ESQUEMA_MUSIC, BORRAR_ESQUEMA_MUSIC),
    ]
