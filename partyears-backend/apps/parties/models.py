import uuid

from django.db import models
from django.db.models import Value
from django.utils import timezone

class Party(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    nombre = models.CharField(max_length=100)
    creada_por = models.UUIDField()
    capacidad = models.SmallIntegerField(default=20)
    version = models.BigIntegerField(default=0)
    creada_en = models.DateTimeField(default=timezone.now)
    finalizada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = '"party"."party"'


class MiembroParty(models.Model):
    id = models.BigAutoField(primary_key=True)
    party = models.ForeignKey(Party, on_delete=models.DO_NOTHING, db_column='party_id', related_name='miembros')
    usuario_id = models.UUIDField()
    puede_aportar = models.BooleanField(default=False)
    puede_modificar_cola = models.BooleanField(default=False)
    estado = models.CharField(max_length=12, default='habilitado')
    incorporado_en = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = '"party"."miembro_party"'


class AnfitrionParty(models.Model):
    party = models.OneToOneField(Party, primary_key=True, on_delete=models.DO_NOTHING, db_column='party_id', related_name='anfitrion')
    usuario_id = models.UUIDField()
    asignado_en = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = '"party"."anfitrion_party"'


class ParticipacionParty(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    orden_ingreso = models.BigIntegerField(db_default=Value(0))
    party = models.ForeignKey(Party, on_delete=models.DO_NOTHING, db_column='party_id', related_name='participaciones')
    usuario_id = models.UUIDField()
    entrada_en = models.DateTimeField(default=timezone.now)
    salida_en = models.DateTimeField(null=True, blank=True)
    motivo_salida = models.CharField(max_length=12, null=True, blank=True)

    class Meta:
        managed = False
        db_table = '"party"."participacion_party"'


class InvitacionParty(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    party = models.ForeignKey(Party, on_delete=models.DO_NOTHING, db_column='party_id', related_name='invitaciones')
    codigo = models.CharField(max_length=6, unique=True)
    creada_por = models.UUIDField()
    creada_en = models.DateTimeField(default=timezone.now)
    expira_en = models.DateTimeField()
    revocada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = '"party"."invitacion_party"'


class OperacionConfirmada(models.Model):
    actor_id = models.UUIDField(primary_key=True)
    clave = models.UUIDField()
    operacion = models.CharField(max_length=64)
    solicitud_sha256 = models.BinaryField()
    codigo_respuesta = models.SmallIntegerField()
    resultado = models.JSONField()
    confirmada_en = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = '"party"."operacion_confirmada"'


class EventoSalida(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    agregado_id = models.UUIDField()
    version = models.BigIntegerField()
    tipo = models.CharField(max_length=80)
    datos = models.JSONField()
    creado_en = models.DateTimeField(default=timezone.now)
    publicado_en = models.DateTimeField(null=True, blank=True)
    intentos = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = '"party"."evento_salida"'