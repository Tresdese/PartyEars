from django.db import models
from django.utils import timezone


class EventoLog(models.Model):
    id = models.UUIDField(primary_key=True)
    servicio_codigo = models.CharField(max_length=16)
    tipo = models.CharField(max_length=80)
    nivel = models.CharField(max_length=10, default='info')
    ocurrido_en = models.DateTimeField()
    recibido_en = models.DateTimeField(default=timezone.now)
    actor_usuario_id = models.UUIDField(null=True)
    party_id = models.UUIDField(null=True)
    recurso_tipo = models.CharField(max_length=40, null=True)
    recurso_id = models.UUIDField(null=True)
    correlacion_id = models.UUIDField(null=True)
    mensaje = models.TextField()
    detalle = models.JSONField(default=dict)

    class Meta:
        managed = False
        db_table = '"logs"."evento_log"'
