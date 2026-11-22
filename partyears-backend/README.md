# PartyEars Backend

Backend de **PartyEars** desarrollado con **Python, Django y Django REST Framework**.

## Requisitos

Antes de ejecutar el backend es necesario tener instalado:

* Python
* Git
* Bash (Linux) o PowerShell (Windows)
* PostgreSQL o acceso a la base de datos PostgreSQL utilizada por el proyecto

## 1. Clonar el repositorio

```powershell
git clone URL_DEL_REPOSITORIO
```

Entrar a la carpeta del proyecto:

```powershell
cd PartyEars
```

Después entrar al backend:

```powershell
cd partyears-backend
```

## 2. Ejecutar un servicio con el script

Antes, configura `.env` (sección 5). Desde `partyears-backend`, indica el servicio:

```bash
./partyearsBackend.sh party
```

```powershell
.\partyearsBackend.ps1 party
```

El script crea el entorno virtual si no existe (`venv` en Linux, `.venv` en Windows, para que no choquen si el disco es compartido), instala `requirements.txt` y levanta el servicio en `0.0.0.0` con su puerto de la sección 4. Para que un celular u otra PC lleguen por la red, agrega tu IP a `ALLOWED_HOSTS` en `.env`; en Windows, permite Python en el firewall cuando lo pregunte.

No aplica migraciones: la base de desarrollo es compartida, así que se migra a mano (sección 6).

## 2.1 Levantar todo el backend en tu máquina (prueba del MVP)

En la prueba, el profesor elige la PC de uno del equipo para correr el backend y los demás se conectan a ella. Con esto, cualquiera puede hacerlo:

1. **Conéctate a la VPN** del servidor (OpenVPN). El servidor queda en `10.9.0.1` y tu PC recibe una IP `10.9.0.x`: anótala, porque es la que los demás van a escribir en la app.
2. **Configura `.env`** (sección 5) con:
   - `DB_HOST=10.9.0.1` y tu `DB_USER` y `DB_PASSWORD`;
   - `ALLOWED_HOSTS=<tu IP 10.9.0.x>`;
   - `REDIS_URL` (sin Redis, los cambios de la cola no llegan a los teléfonos);
   - las `*_RABBITMQ_URL`, que son opcionales: sin ellas no se guarda el registro técnico, pero la party funciona;
   - `MUSIC_MEDIA_ROOT` apuntando a tu copia del catálogo.
3. **Genera tus claves JWT** si no tienes `claves-dev/`. Usa los dos comandos `openssl` de `.env.example`; en Windows, desde Git Bash. Cada máquina puede tener las suyas: los tokens solo valen en el backend que los emitió.
4. **Abre los puertos 8001 a 8004** en el firewall:
   - en Linux, `sudo ufw allow 8001:8004/tcp`;
   - en Windows, acepta el aviso de Python, o desde PowerShell como administrador:
     ```powershell
     New-NetFirewallRule -DisplayName PartyEars -Direction Inbound -Protocol TCP -LocalPort 8001-8004 -Action Allow
     ```
5. **Levanta todo:**
   ```bash
   ./partyearsBackend.sh todos     # una terminal; Ctrl+C detiene todo
   ```
   ```powershell
   .\partyearsBackend.ps1 todos   # una ventana por servicio; ciérralas para detener
   ```
   Arranca auth, music, party y queue, más los procesos de eventos cuyas URL estén en `.env`.
6. **Comprueba desde otra PC de la VPN:** `curl http://<tu IP>:8002/api/v1/music/canciones` debe responder `401` (llega y pide sesión).
7. **En la app,** cada persona toca **Servidor → Cambiar** en la pantalla de inicio de sesión y escribe tu IP. Las cuentas y las parties están en la base compartida, así que sirven las mismas en cualquier máquina; solo hay que volver a iniciar sesión.

## 3. Instalar dependencias sin el script

Con el entorno virtual activado:

```bash
pip install -r requirements.txt
```

## 4. Servicios y bases de datos

El backend son seis servicios que se despliegan por separado; cada uno corre en su propio proceso. Cada base vive en su propio contenedor PostgreSQL 17 en el servidor (ver `DECISIONES.md` en `/srv/compartido/partyears/`), con su propio puerto y rol:

| Servicio | App | Settings | Base | Rol | Puerto BD | Puerto HTTP |
|---|---|---|---|---|---|---|
| auth | apps.users | config.settings.auth | partyears_auth | auth_svc | 5441 | 8001 |
| music | apps.music | config.settings.music | partyears_music | music_svc | 5442 | 8002 |
| party | apps.parties | config.settings.party | partyears_party | party_svc | 5443 | 8003 |
| queue | apps.musicqueue | config.settings.queue | partyears_queue | queue_svc | 5444 | 8004 |
| streaming | apps.streaming | config.settings.streaming | partyears_streaming | streaming_svc | 5445 | 8005 |
| logs | apps.logs | config.settings.logs | partyears_logs | logs_svc | 5446 | 8006 |

Regla: una app nunca importa modelos de otra. Las referencias entre servicios son UUID que se validan por contrato.

## 5. Configurar `.env`

```bash
cp .env.example .env
```

Pon en `DB_HOST` la IP por la que llegas al servidor (LAN, WireGuard u OpenVPN).

- **En tu PC (desarrollo):** llena `DB_USER` y `DB_PASSWORD` con tu cuenta personal de PostgreSQL. Sirve para los 6 servicios: al conectarte, el servidor te cambia al rol del servicio (`auth_svc`, `music_svc`, ...), así que las tablas quedan con el mismo dueño que en producción.
- **En el servidor (despliegue):** deja `DB_USER` vacío y llena las contraseñas `*_DB_PASSWORD` de los roles `*_svc`.

## 6. Migrar y ejecutar un servicio

Cada comando indica el servicio con `DJANGO_SETTINGS_MODULE`:

```bash
DJANGO_SETTINGS_MODULE=config.settings.auth python manage.py migrate
DJANGO_SETTINGS_MODULE=config.settings.auth python manage.py runserver 8001
```

En PowerShell:

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.auth"
python manage.py runserver 8001
```

El panel administrativo solo existe en el servicio auth: `http://127.0.0.1:8001/admin/`.

## 6.1 Eventos entre servicios y registro técnico (RabbitMQ, T-21)

Además del servidor web, party y queue corren un proceso que manda su outbox a RabbitMQ, y logs corre uno que lo guarda en `logs.evento_log`. Cada uno necesita su `<SERVICIO>_RABBITMQ_URL` en `.env` (ver `.env.example`). RabbitMQ solo escucha en `127.0.0.1` del servidor: desde otra PC hace falta el túnel SSH.

```bash
DJANGO_SETTINGS_MODULE=config.settings.party python manage.py publicar_eventos
DJANGO_SETTINGS_MODULE=config.settings.queue python manage.py publicar_eventos
DJANGO_SETTINGS_MODULE=config.settings.logs python manage.py consumir_eventos
```

Si alguno está apagado no se pierde nada: los eventos esperan en el outbox o en la cola de RabbitMQ.

Para consultar los registros (CU-27), por party, por usuario o por la `Idempotency-Key` de una operación:

```bash
DJANGO_SETTINGS_MODULE=config.settings.logs python manage.py ver_registros --party <uuid>
DJANGO_SETTINGS_MODULE=config.settings.logs python manage.py ver_registros --actor <uuid> --desde 2026-11-25T10:00:00-06:00
```

## 7. Conectarse a una base desde la terminal

```bash
psql -h IP_DEL_SERVIDOR -p 5441 -U TU_ROL -d partyears_auth   # 5441 auth … 5446 logs
```

## Estructura básica

```text
partyears-backend/
│
├── apps/
│   └── users/
│
├── config/
│
├── .venv/
├── .env
├── manage.py
├── requirements.txt
└── partyearsBackend
```

### `apps/`

Contiene las aplicaciones que forman el backend de PartyEars.

### `config/`

Contiene la configuración general de Django.

### `.venv/`

Entorno virtual de Python utilizado para aislar las dependencias del proyecto.

Esta carpeta no se almacena en GitHub.

### `.env`

Contiene variables de entorno y credenciales privadas.

Este archivo tampoco se almacena en GitHub.

### `requirements.txt`

Contiene las dependencias necesarias para ejecutar el backend.

### `partyearsBackend`

Script utilizado para preparar o activar el entorno de ejecución del backend.

## Detener el servidor

Para detener Django:

```text
Ctrl + C
```

## Nota

Siempre se deben ejecutar los comandos desde la carpeta:

```text
partyears-backend
```

Antes de trabajar en el backend, ejecutar:

```powershell
.\partyearsBackend
```
