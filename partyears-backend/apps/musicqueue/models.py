import uuid

from django.db import models
from django.utils import timezone


class Cola(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    party_id = models.UUIDField(null=True, unique=True)
    usuario_id = models.UUIDField(null=True, unique=True)
    version = models.BigIntegerField(default=0)
    version_party = models.BigIntegerField(null=True)
    creada_en = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = '"queue"."cola"'


class ElementoCola(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    cola = models.ForeignKey(Cola, on_delete=models.DO_NOTHING, db_column='cola_id',
                             related_name='elementos')
    recurso_audio_id = models.UUIDField()
    agregado_por = models.UUIDField()
    orden = models.BigIntegerField()
    estado = models.CharField(max_length=15, default='pendiente')
    agregado_en = models.DateTimeField(default=timezone.now)
    inicio_en = models.DateTimeField(null=True)
    fin_en = models.DateTimeField(null=True)
    posicion_base_ms = models.BigIntegerField(default=0)
    referencia_en = models.DateTimeField(null=True)

    class Meta:
        managed = False
        db_table = '"queue"."elemento_cola"'


class OperacionConfirmada(models.Model):
    # actor_id as primary key instead of the real (actor_id, clave): Django needs a single
    # column, and rows are always looked up by both.
    actor_id = models.UUIDField(primary_key=True)
    clave = models.UUIDField()
    operacion = models.CharField(max_length=64)
    solicitud_sha256 = models.BinaryField()
    codigo_respuesta = models.SmallIntegerField()
    resultado = models.JSONField()
    confirmada_en = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = '"queue"."operacion_confirmada"'


class EventoSalida(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    agregado_id = models.UUIDField()
    version = models.BigIntegerField()
    tipo = models.CharField(max_length=80)
    datos = models.JSONField()
    creado_en = models.DateTimeField(default=timezone.now)
    publicado_en = models.DateTimeField(null=True)
    intentos = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = '"queue"."evento_salida"'
