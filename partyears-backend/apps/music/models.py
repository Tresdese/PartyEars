import uuid

from django.db import models
from django.utils import timezone


class Artista(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    nombre = models.CharField(max_length=150, unique=True)
    creado_en = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = '"music"."artista"'

    def __str__(self):
        return self.nombre


class Cancion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    titulo = models.CharField(max_length=200)
    duracion_ms = models.IntegerField()
    creada_en = models.DateTimeField(default=timezone.now)
    artistas = models.ManyToManyField(
        Artista,
        through='CancionArtista',
        related_name='canciones',
    )

    class Meta:
        managed = False
        db_table = '"music"."cancion"'

    def __str__(self):
        return self.titulo


class CancionArtista(models.Model):
    id = models.BigAutoField(primary_key=True)
    cancion = models.ForeignKey(
        Cancion,
        on_delete=models.DO_NOTHING,
        db_column='cancion_id',
        related_name='creditos',
    )
    artista = models.ForeignKey(
        Artista,
        on_delete=models.DO_NOTHING,
        db_column='artista_id',
        related_name='creditos',
    )
    orden = models.SmallIntegerField()

    class Meta:
        managed = False
        db_table = '"music"."cancion_artista"'


class RecursoAudio(models.Model):
    TIPO_ORIGINAL = 'original'
    TIPO_INSTRUMENTAL = 'instrumental'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    cancion = models.ForeignKey(
        Cancion,
        on_delete=models.DO_NOTHING,
        db_column='cancion_id',
        related_name='variantes',
    )
    tipo = models.CharField(max_length=16, default=TIPO_ORIGINAL)
    formato = models.CharField(max_length=16)
    mime_type = models.CharField(max_length=64)
    ruta_archivo = models.TextField()
    tamano_bytes = models.BigIntegerField()
    duracion_ms = models.IntegerField()
    disponible = models.BooleanField(default=True)
    creado_en = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = '"music"."recurso_audio"'

    def __str__(self):
        return f'{self.cancion.titulo} ({self.tipo} - {self.formato})'
