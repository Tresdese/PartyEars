# PartyEars Backend

Backend de **PartyEars** desarrollado con **Python, Django y Django REST Framework**.

## Requisitos

Antes de ejecutar el backend es necesario tener instalado:

* Python
* Git
* PowerShell
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

## 2. Ejecutar el backend

Desde la raíz de `partyears-backend`, ejecutar:

```powershell
.\partyearsBackend
```

El script se encarga de utilizar el entorno virtual correspondiente al backend.

Después de activarse correctamente, la terminal debería indicar que se está utilizando el entorno virtual de PartyEars.

Por ejemplo:

```text
(PartyEars) PS C:\...\PartyEars\partyears-backend>
```

## 3. Instalar dependencias

Si es la primera vez que se ejecuta el proyecto y las dependencias todavía no están instaladas:

```powershell
pip install -r requirements.txt
```

Las dependencias necesarias para el backend se encuentran registradas en:

```text
requirements.txt
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
