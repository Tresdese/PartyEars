# T-31: prueba de concepto de sincronización

Objetivo (plan, T-31): dos equipos reproducen el mismo audio, corrigen su desfase y se mide, con meta de 1 s (RNF-03). De aquí salen los dos `PENDIENTE` del contrato 5.3: límite de desfase y método de corrección.

## Cómo funciona

1. `controlar.py` hace de anfitrión: publica `reproduccion.estado` (contrato 5.3) a la party por Redis. Pone `referencia_en` 1.5 s en el futuro para que todos los clientes reciban el mensaje antes del instante de arranque.
2. `cliente_sincronizacion.py` se conecta al WebSocket de party, mide el desfase de su reloj con `reloj.ping` (contrato 7.4, mejor de 15; repite cada 30 s), reproduce con mpv y cada 500 ms compara la posición real con la esperada:
   `esperada = posicion_base_ms + (hora_servidor - referencia_en)`.
   Si se aleja más de `--limite-ms`, corrige (`--metodo saltar` o `velocidad`) y lo anota en el CSV.

Cada cliente mide su error contra la línea de tiempo del servidor. El desfase **entre** dos equipos es aproximadamente la diferencia de sus errores, más el error de la medición del reloj (como mucho la mitad de la ida y vuelta).

## Preparar

En el equipo que corre party (Daphne), con el túnel a Redis abierto y `REDIS_URL` en `.env`:

```bash
sudo ufw allow from 192.168.1.0/24 to any port 8003 proto tcp   # solo si el otro equipo está en la LAN
```

En cada equipo cliente: Python 3.10+, mpv y `websockets`:

```bash
python3 -m venv ~/t31-venv && ~/t31-venv/bin/pip install websockets
```

Audio de prueba (un bip de 50 ms cada segundo, 3 min). El mismo archivo en los dos equipos:

```bash
ffmpeg -f lavfi -i "sine=frequency=1000:duration=180" -af "volume='if(lt(mod(t,1),0.05),1,0)':eval=frame" -ac 1 clicks.wav
```

## Correr

Desde `partyears-backend`, con el venv:

```bash
DJANGO_SETTINGS_MODULE=config.settings.party python manage.py runserver 0.0.0.0:8003
python ../pruebas/t31/controlar.py token        # copia el token para los clientes (dura 4 h)
```

En cada cliente (`<ip>` es la del equipo con Daphne):

```bash
python cliente_sincronizacion.py --url ws://<ip>:8003/ws/v1/party/parties/11111111-1111-1111-1111-111111111111/ \
    --token <token> --audio clicks.wav --nombre pc --csv pc.csv
```

Y desde `partyears-backend`: `python ../pruebas/t31/controlar.py iniciar`, luego `buscar 60000`, `pausar`, `reanudar`. Ctrl+C en cada cliente imprime el resumen (error medio, p95, máximo, correcciones).

## Comprobar con el oído y con una grabación

El CSV mide lo que mpv cree que reproduce, no lo que sale por la bocina (falta la latencia de la tarjeta de sonido). Para medir el desfase real: pon los dos equipos juntos, graba con el celular 20 s y abre la grabación en Audacity. Cada bip suena dos veces; la distancia entre los dos picos es el desfase real. Por debajo de unos 30 ms el oído escucha un solo bip.

## Resultados

| Fecha | Equipos y red | Método y límite | Error p95 (CSV) | Desfase real (grabación) | Correcciones |
|---|---|---|---|---|---|
| 21 nov | Dos clientes en el mismo PC, sin audio (`--mpv-arg=--ao=null`) | saltar, 100 ms | 89 ms y 88 ms | no aplica | 0 |
