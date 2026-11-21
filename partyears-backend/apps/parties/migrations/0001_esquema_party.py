from django.db import migrations

CREAR_ESQUEMA_PARTY = """
CREATE SCHEMA party;
CREATE TABLE party.party (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre varchar(100) NOT NULL CHECK (btrim(nombre) <> ''),
    creada_por uuid NOT NULL, -- RE: auth.usuario.id
    capacidad smallint NOT NULL DEFAULT 20 CHECK (capacidad = 20),
    version bigint NOT NULL DEFAULT 0 CHECK (version >= 0),
    creada_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finalizada_en timestamptz,
    CHECK (finalizada_en IS NULL OR finalizada_en >= creada_en)
);
CREATE INDEX party_creador_ix ON party.party (creada_por);
CREATE TABLE party.miembro_party (
    id bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
    party_id uuid NOT NULL REFERENCES party.party(id)
        ON DELETE RESTRICT,
    usuario_id uuid NOT NULL, -- RE: auth.usuario.id
    puede_aportar boolean NOT NULL DEFAULT false,
    puede_modificar_cola boolean NOT NULL DEFAULT false,
    estado varchar(12) NOT NULL DEFAULT 'habilitado'
        CHECK (estado IN ('habilitado', 'expulsado')),
    incorporado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (party_id, usuario_id)
);
CREATE INDEX miembro_usuario_ix
    ON party.miembro_party (usuario_id);
CREATE TABLE party.anfitrion_party (
    party_id uuid PRIMARY KEY REFERENCES party.party(id)
        ON DELETE RESTRICT,
    usuario_id uuid NOT NULL,
    asignado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (party_id, usuario_id)
        REFERENCES party.miembro_party (party_id, usuario_id)
        ON DELETE RESTRICT
);
CREATE TABLE party.participacion_party (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    orden_ingreso bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
    party_id uuid NOT NULL,
    usuario_id uuid NOT NULL,
    entrada_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    salida_en timestamptz,
    motivo_salida varchar(12) CHECK (motivo_salida IN
        ('voluntaria', 'desconexion', 'expulsion', 'fin_party')),
    FOREIGN KEY (party_id, usuario_id)
        REFERENCES party.miembro_party (party_id, usuario_id)
        ON DELETE RESTRICT,
    CHECK (salida_en IS NULL OR salida_en >= entrada_en),
    CHECK ((salida_en IS NULL) = (motivo_salida IS NULL))
);
CREATE UNIQUE INDEX participacion_abierta_uq
    ON party.participacion_party (usuario_id)
    WHERE salida_en IS NULL;
CREATE INDEX participacion_sucesion_ix
    ON party.participacion_party (party_id, orden_ingreso)
    WHERE salida_en IS NULL;
CREATE INDEX participacion_historial_ix
    ON party.participacion_party
        (party_id, usuario_id, entrada_en DESC);
CREATE TABLE party.invitacion_party (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    party_id uuid NOT NULL REFERENCES party.party(id)
        ON DELETE RESTRICT,
    codigo varchar(6) NOT NULL UNIQUE
        CHECK (codigo ~ '^[A-Z0-9]{6}$'),
    creada_por uuid NOT NULL,
    creada_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expira_en timestamptz NOT NULL,
    revocada_en timestamptz,
    FOREIGN KEY (party_id, creada_por)
        REFERENCES party.miembro_party (party_id, usuario_id)
        ON DELETE RESTRICT,
    CHECK (expira_en > creada_en),
    CHECK (revocada_en IS NULL OR revocada_en >= creada_en)
);
CREATE INDEX invitacion_creador_ix
    ON party.invitacion_party (party_id, creada_por);
CREATE TABLE party.mensaje_chat (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    miembro_id bigint NOT NULL REFERENCES party.miembro_party(id)
        ON DELETE RESTRICT,
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    contenido text COMPRESSION pglz NOT NULL
        CHECK (octet_length(contenido) BETWEEN 1 AND 4096
        AND btrim(contenido) <> '')
);
CREATE INDEX mensaje_miembro_id_ix
    ON party.mensaje_chat (miembro_id, id);
CREATE TABLE party.archivo_chat (
    party_id uuid NOT NULL REFERENCES party.party(id)
        ON DELETE RESTRICT,
    numero_bloque integer NOT NULL CHECK (numero_bloque > 0),
    mensaje_inicial bigint NOT NULL CHECK (mensaje_inicial > 0),
    mensaje_final bigint NOT NULL,
    mensajes integer NOT NULL CHECK (mensajes > 0),
    bytes_originales integer NOT NULL
        CHECK (bytes_originales BETWEEN 1 AND 4194304),
    contenido_zstd bytea STORAGE EXTERNAL NOT NULL
        CHECK (octet_length(contenido_zstd) > 0),
    sha256 bytea NOT NULL CHECK (octet_length(sha256) = 32),
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (party_id, numero_bloque),
    CHECK (mensaje_final >= mensaje_inicial)
);
-- Infraestructura transaccional
CREATE TABLE party.operacion_confirmada (
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
CREATE TABLE party.evento_salida (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agregado_id uuid NOT NULL REFERENCES party.party(id)
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
    ON party.evento_salida (creado_en, id)
    WHERE publicado_en IS NULL;
"""

BORRAR_ESQUEMA_PARTY = 'DROP SCHEMA party CASCADE;'

class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.RunSQL(CREAR_ESQUEMA_PARTY, BORRAR_ESQUEMA_PARTY),
    ]