import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone


class Usuario(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    nombre_usuario = models.CharField(max_length=40, unique=True)
    correo = models.EmailField(max_length=254, unique=True)
    contrasena_hash = models.CharField(max_length=255)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(default=timezone.now)
    actualizado_en = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = '"auth"."usuario"'

    def establecer_contrasena(self, contrasena_plana: str) -> None:
        self.contrasena_hash = make_password(contrasena_plana)

    def verificar_contrasena(self, contrasena_plana: str) -> bool:
        return check_password(contrasena_plana, self.contrasena_hash)


class Sesion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.DO_NOTHING,
        db_column='usuario_id',
        related_name='sesiones',
    )
    token_renovacion_hash = models.CharField(max_length=64, unique=True)
    creada_en = models.DateTimeField(default=timezone.now)
    expira_en = models.DateTimeField()
    revocada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = '"auth"."sesion"'
