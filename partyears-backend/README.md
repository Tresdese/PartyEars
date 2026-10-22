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

## 4. Configurar variables de entorno

El archivo `.env` contiene configuraciones privadas, como las credenciales de PostgreSQL, y no se incluye en GitHub.

Si existe un archivo:

```text
.env.example
```

crear una copia:

```powershell
Copy-Item .env.example .env
```

Después editar `.env` y colocar las credenciales correspondientes.

Ejemplo:

```env
DB_NAME=partyears
DB_USER=partyears_user
DB_PASSWORD=PASSWORD
DB_HOST=IP_O_HOST_DE_POSTGRESQL
DB_PORT=5432
```

## 5. Aplicar migraciones

Antes de ejecutar Django por primera vez:

```powershell
python manage.py migrate
```

Esto crea o actualiza las tablas necesarias en PostgreSQL utilizando las migraciones del proyecto.

## 6. Ejecutar el servidor

Con el entorno virtual activo:

```powershell
python manage.py runserver
```

Si todo funciona correctamente se mostrará:

```text
Starting development server at http://127.0.0.1:8000/
```

El backend estará disponible en:

```text
http://127.0.0.1:8000/
```

El panel administrativo de Django estará disponible en:

```text
http://127.0.0.1:8000/admin/
```

## Ejecución habitual

Una vez configurado el proyecto, normalmente solo será necesario abrir PowerShell en:

```text
PartyEars\partyears-backend
```

y ejecutar:

```powershell
.\partyearsBackend
```

Después iniciar Django:

```powershell
python manage.py runserver
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
