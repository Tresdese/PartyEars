# PartyEars: contrato de API

Contrato entre los clientes Flutter y los servicios Django (T-04, RNF-09). Se basa en el SRS v1.4 y en la especificación de BD v1.0.

**Estado: borrador.** Lo marcado como `PENDIENTE` todavía no está decidido; el nombre entre paréntesis es quien lo cierra. Un cambio a este documento entra por PR a `staging` y lo revisan los tres.

| Sección | Responsable |
|---|---|
| 1. Convenciones, 7. WebSocket, 4.2 a 4.5 (unirse, permisos, anfitrión, expulsión), 5.2 y 5.3 (cola compartida y reproducción) | Darlington |
| 2. auth, 3. music, 5.1 (cola individual) | Axel |
| 4.1 (crear, salir, finalizar), 4.6 (chat), 6. streaming | Mariana |

---

## 1. Convenciones generales

### 1.1 Servicios y URL base

Cada servicio se despliega por separado. Detrás del proxy inverso (T-22) todos comparten host:

```
https://<host>/api/v1/<servicio>/...      REST
wss://<host>/ws/v1/<servicio>/...         WebSocket
```

En desarrollo, sin proxy, cada servicio se llama directo por su puerto:

| Servicio | Puerto | Ejemplo |
|---|---|---|
| auth | 8001 | `http://192.168.1.75:8001/api/v1/auth/login` |
| music | 8002 | |
| party | 8003 | |
| queue | 8004 | |
| streaming | 8005 | |
| logs | 8006 | Sin API para el cliente |

El cliente guarda la URL base de cada servicio en configuración (T-50), nunca fija en el código.

### 1.2 Formato

- JSON en UTF-8 (`Content-Type: application/json; charset=utf-8`).
- Nombres de campos en `snake_case` y en español, iguales a los de la BD cuando existe la columna.
- Identificadores: UUID en texto (`"3f1c..."`). Excepción: los mensajes de chat usan su ID numérico.
- Fechas: ISO 8601 en UTC con milisegundos y `Z`: `"2026-11-10T18:30:00.123Z"`. Nunca fechas sin zona.
- Duraciones y posiciones de audio: enteros en milisegundos (`duracion_ms`, `posicion_ms`).
- Un campo sin valor va como `null`, no se omite.

### 1.3 Autenticación

- `auth` emite un **token de acceso JWT** (RS256) y un **token de renovación** opaco.
- Toda operación protegida manda `Authorization: Bearer <token_acceso>`.
- Contenido del token de acceso:

```json
{ "sub": "<uuid del usuario>", "nombre_usuario": "darlington", "sid": "<uuid de la sesión>", "iat": 1794363600, "exp": 1794363900 }
```

- Los demás servicios validan la firma con la clave pública de `auth`, sin llamarlo.
- Sin token, con token inválido o vencido: `401 TOKEN_INVALIDO`. El cliente intenta una vez renovar (2.3) y, si falla, vuelve al inicio de sesión.

`PENDIENTE (Axel y Darlington)`: RF-04 pide que tras cerrar sesión "la sesión anterior deje de autorizar operaciones". Un JWT sigue siendo válido hasta su `exp` aunque se cierre la sesión. Propuesta: vida del token de acceso de **5 minutos** y, al cerrar sesión, `auth` publica `sesion.revocada` con el `sid` para que `party`, `queue` y `streaming` cierren los WebSocket de esa sesión y rechacen ese `sid` hasta que expire. Requiere agregar `auth.eventos` a RabbitMQ.

### 1.4 Errores

Toda respuesta de error tiene el mismo cuerpo:

```json
{
  "codigo": "PARTY_LLENA",
  "mensaje": "La party ya tiene 20 personas conectadas.",
  "detalles": null
}
```

- `codigo`: constante en mayúsculas; el cliente decide con él, nunca con el texto.
- `mensaje`: texto en español que se puede mostrar al usuario.
- `detalles`: `null` o un objeto. En errores de validación, un objeto con los campos que fallaron: `{"correo": ["Ya está registrado."]}`.

Códigos HTTP:

| HTTP | Uso | Códigos comunes |
|---|---|---|
| 400 | Datos inválidos | `DATOS_INVALIDOS` |
| 401 | Sin autenticación válida | `TOKEN_INVALIDO`, `CREDENCIALES_INVALIDAS` |
| 403 | Autenticado pero sin permiso | `SIN_PERMISO`, `NO_ES_ANFITRION`, `NO_ES_MIEMBRO`, `USUARIO_EXPULSADO`, `CUENTA_INACTIVA` |
| 404 | No existe | `NO_ENCONTRADO`, `CODIGO_INVALIDO` |
| 409 | Choca con el estado actual | `VERSION_OBSOLETA`, `PARTY_LLENA`, `YA_EN_OTRA_PARTY`, `IDEMPOTENCIA_CONFLICTO`, `ELEMENTO_NO_ACTUAL`, `DUPLICADO` |
| 410 | Ya no está disponible | `PARTY_FINALIZADA`, `CODIGO_EXPIRADO`, `AUDIO_NO_DISPONIBLE` |
| 503 | Un servicio del que depende no responde | `SERVICIO_NO_DISPONIBLE` |

Cada sección lista los códigos propios de sus operaciones.

### 1.5 Paginación

Listas con número de página (catálogo):

```
GET ...?pagina=1          (empieza en 1; 20 elementos por página, RF-03)
```

```json
{ "resultados": [ ... ], "pagina": 1, "total_paginas": 3, "total": 47 }
```

Listas que crecen mientras se leen (chat) usan cursor; ver 4.6.

### 1.6 Idempotencia (RF-23, RNF-06)

Toda operación que **modifica** estado de una party o de una cola lleva:

```
Idempotency-Key: <uuid generado por el cliente>
```

- El cliente genera una clave nueva por cada intención del usuario y **reutiliza la misma** al reintentar esa intención (por ejemplo, tras un corte de red).
- Misma clave y mismo contenido: el servidor devuelve el resultado ya confirmado sin repetir el efecto.
- Misma clave con contenido distinto: `409 IDEMPOTENCIA_CONFLICTO`.
- Falta la cabecera en una operación que la requiere: `400 DATOS_INVALIDOS`.

Corresponde a las tablas `operacion_confirmada` de `party` y `queue`. El registro, el login y el chat no la usan.

### 1.7 Versiones y operaciones obsoletas (RF-12, RF-23)

- La party y cada cola tienen un entero `version` que sube con cada cambio confirmado. Toda respuesta y todo evento que describe una party o una cola incluye su `version`.
- Las operaciones que dependen del estado que el usuario está viendo (reordenar, cambiar permisos, saltar) mandan `version_esperada`.
- Si no coincide con la actual: `409 VERSION_OBSOLETA` con `"detalles": {"version_actual": 18}`. El cliente recarga el estado y **no reintenta solo** (RF-21).

---

## 2. auth (Axel)

### 2.1 `POST /api/v1/auth/registro` (RF-01)

Sin autenticación.

```json
{ "nombre_usuario": "darlington", "correo": "d@ejemplo.com", "contrasena": "minimo10caracteres", "confirmacion": "minimo10caracteres" }
```

`201`:

```json
{ "id": "uuid", "nombre_usuario": "darlington", "correo": "d@ejemplo.com", "creado_en": "2026-11-10T18:30:00.000Z" }
```

Errores: `400 DATOS_INVALIDOS` (campos vacíos, correo inválido, contraseña de menos de 10 caracteres, confirmación distinta; con `detalles` por campo), `409 DUPLICADO` (`detalles` indica si es `nombre_usuario` o `correo`).

### 2.2 `POST /api/v1/auth/login` (RF-02)

El SRS (CU-02) inicia sesión con correo y contraseña.

```json
{ "correo": "d@ejemplo.com", "contrasena": "..." }
```

`200`:

```json
{
  "token_acceso": "eyJ...",
  "token_renovacion": "opaco",
  "expira_en": "2026-11-10T18:35:00.000Z",
  "usuario": { "id": "uuid", "nombre_usuario": "darlington" }
}
```

Errores: `401 CREDENCIALES_INVALIDAS` (mismo código si el correo no existe o la contraseña es incorrecta, para no revelar qué correos están registrados), `403 CUENTA_INACTIVA`.

### 2.3 `POST /api/v1/auth/renovar`

```json
{ "token_renovacion": "opaco" }
```

`200`: mismo cuerpo que 2.2, con un token de renovación nuevo; el anterior queda revocado. Error: `401 TOKEN_INVALIDO`.

### 2.4 `POST /api/v1/auth/logout` (RF-04)

Autenticado.

```json
{ "token_renovacion": "opaco" }
```

`204`. Revoca la sesión. El cliente, antes de llamar, detiene audio y voz y sale de la party (4.1.3). Ver `PENDIENTE` de 1.3.

### 2.5 `GET /api/v1/auth/usuarios?ids=uuid1,uuid2`

Autenticado. Devuelve nombres públicos para mostrar participantes y autores: `{"resultados": [{"id": "uuid", "nombre_usuario": "axel"}]}`. Nunca devuelve correos.

`PENDIENTE (Axel)`: decidir si `party` guarda una copia del `nombre_usuario` al ingresar, para no depender de `auth` en cada consulta de participantes.

---

## 3. music (Axel)

### 3.1 `GET /api/v1/music/canciones?q=texto&pagina=1` (RF-03, RF-25)

Autenticado. Busca por fragmento de título o artista, sin distinguir mayúsculas. `q` vacío lista el catálogo. Sin coincidencias: `200` con `resultados` vacío (no es error).

```json
{
  "resultados": [
    {
      "id": "uuid",
      "titulo": "Canción",
      "duracion_ms": 215000,
      "artistas": [ { "id": "uuid", "nombre": "Artista" } ],
      "variantes": [
        { "recurso_audio_id": "uuid", "tipo": "original", "disponible": true },
        { "recurso_audio_id": "uuid", "tipo": "instrumental", "disponible": true }
      ]
    }
  ],
  "pagina": 1, "total_paginas": 3, "total": 47
}
```

- `artistas` va en el orden de los créditos.
- `variantes` solo trae los tipos que existen; si no hay instrumental, no aparece (RF-25).
- Las colas guardan el `recurso_audio_id`, no el `id` de la canción, para conservar la variante elegida.

### 3.2 `GET /api/v1/music/recursos/{recurso_audio_id}`

Metadatos de un recurso (para mostrar elementos de cola): `{"recurso_audio_id", "tipo", "disponible", "cancion": {id, titulo, duracion_ms, artistas}}`.

### 3.3 `GET /api/v1/music/recursos/{recurso_audio_id}/audio` (RF-24, RES-05)

Autenticado. Entrega el archivo con soporte de rangos HTTP para adelantar y atrasar:

- Petición con `Range: bytes=0-` y respuesta `206 Partial Content` con `Content-Range`, `Accept-Ranges: bytes` y el `Content-Type` del recurso (`mime_type` en la BD).
- Errores: `404 NO_ENCONTRADO`; `410 AUDIO_NO_DISPONIBLE` si el recurso está marcado como no disponible o el archivo falta en el servidor.

`PENDIENTE (Axel, T-02)`: varias librerías de audio de Flutter no permiten mandar la cabecera `Authorization` al reproducir una URL. Si la elegida no lo permite, usar una URL firmada de corta duración (`GET .../audio-url` que devuelve `{"url": "...?firma=...&expira=..."}`), nunca el JWT en la URL, porque quedaría en los logs (RNF-05).

---

## 4. party

Estado completo de una party, usado en varias respuestas:

```json
{
  "id": "uuid",
  "nombre": "Viernes",
  "codigo": "K7Q2ZP",
  "version": 12,
  "creada_en": "...",
  "finalizada_en": null,
  "anfitrion_id": "uuid",
  "cola_id": "uuid",
  "miembros": [
    {
      "usuario_id": "uuid",
      "nombre_usuario": "axel",
      "puede_aportar": true,
      "puede_modificar_cola": false,
      "estado": "habilitado",
      "conectado": true,
      "orden_ingreso": 3
    }
  ]
}
```

- `estado` del miembro: `habilitado` o `expulsado`.
- `conectado`: tiene una participación abierta y su WebSocket no superó los 15 s sin comunicación.
- `orden_ingreso` define la sucesión (RF-22).
- `codigo` solo se incluye si quien consulta es el anfitrión; los demás reciben `null`.

### 4.1 Crear, salir y finalizar (Mariana)

#### 4.1.1 `POST /api/v1/party/parties` (RF-06, RF-07)

Requiere `Idempotency-Key`.

```json
{ "nombre": "Viernes", "recurso_audio_id_inicial": "uuid o null" }
```

`201`: estado completo de la party. El creador queda como anfitrión con ambos permisos. Si hay canción inicial, `party` publica el evento de creación y `queue` crea la cola compartida con esa solicitud pendiente; no inicia la reproducción.

Errores: `400 DATOS_INVALIDOS`, `409 YA_EN_OTRA_PARTY`.

`PENDIENTE (Mariana)`: vigencia del código (`invitacion_party.expira_en` es obligatoria y el SRS no la define). Propuesta: mientras la party esté activa, con `expira_en` = creación + 24 h y renovación al consultarlo el anfitrión.

#### 4.1.2 `GET /api/v1/party/parties/actual`

La party activa del usuario autenticado, o `204` si no está en ninguna. Lo usa el cliente al abrir la app para retomar.

#### 4.1.3 `POST /api/v1/party/parties/{party_id}/salir` (RF-19, RF-22)

Requiere `Idempotency-Key`. `204`. Si sale el anfitrión y hay candidatos, el servidor aplica la sucesión; si no queda nadie conectado, finaliza la party (RF-20).

#### 4.1.4 `POST /api/v1/party/parties/{party_id}/finalizar` (RF-20)

Requiere `Idempotency-Key`. Solo el anfitrión. `204`. Todos reciben `party.finalizada`.

Errores comunes de 4.1.3 y 4.1.4: `403 NO_ES_MIEMBRO`, `403 NO_ES_ANFITRION`, `410 PARTY_FINALIZADA`.

### 4.2 `POST /api/v1/party/parties/unirse` (RF-08, RF-36)

Requiere `Idempotency-Key`.

```json
{ "codigo": "K7Q2ZP" }
```

`200`: estado completo de la party. Entra como oyente (sin permisos), salvo reconexión dentro de los 60 s, que conserva los permisos vigentes (RF-21).

Errores: `404 CODIGO_INVALIDO`, `410 CODIGO_EXPIRADO`, `410 PARTY_FINALIZADA`, `403 USUARIO_EXPULSADO`, `409 PARTY_LLENA`, `409 YA_EN_OTRA_PARTY`.

### 4.3 `GET /api/v1/party/parties/{party_id}` (RF-09)

Estado completo. Solo miembros. Es la instantánea que el cliente pide al conectar o reconectar el WebSocket (7.5).

### 4.4 `PUT /api/v1/party/parties/{party_id}/miembros/{usuario_id}/permisos` (RF-17, RF-18)

Requiere `Idempotency-Key`. Solo el anfitrión.

```json
{ "puede_aportar": true, "puede_modificar_cola": false, "version_esperada": 12 }
```

`200`: el miembro actualizado y la nueva `version`. Las cuatro combinaciones son válidas. No se pueden cambiar los permisos del propio anfitrión.

Errores: `403 NO_ES_ANFITRION`, `404 NO_ENCONTRADO`, `409 VERSION_OBSOLETA`.

### 4.5 Anfitrión y expulsión (RF-30, RF-31)

Todas requieren `Idempotency-Key`, solo las ejecuta el anfitrión y devuelven `204`.

| Operación | Endpoint | Cuerpo |
|---|---|---|
| Transferir el cargo | `POST .../parties/{party_id}/anfitrion` | `{"usuario_id": "uuid", "version_esperada": 12}` |
| Expulsar | `POST .../parties/{party_id}/miembros/{usuario_id}/expulsar` | `{"version_esperada": 12}` |
| Rehabilitar | `POST .../parties/{party_id}/miembros/{usuario_id}/rehabilitar` | `{"version_esperada": 12}` |

- Transferir: el destinatario debe estar conectado y habilitado; si no, `409 DESTINATARIO_NO_ELEGIBLE`.
- Expulsar cierra su participación y su voz e impide que vuelva a entrar. Rehabilitar le permite entrar otra vez como oyente, sin conectarlo.

### 4.6 Chat (Mariana, RF-26)

Solo miembros habilitados y conectados. No usa `Idempotency-Key`.

#### `GET /api/v1/party/parties/{party_id}/mensajes?antes_de=<id>&limite=50`

Mensajes del más nuevo al más viejo. Sin `antes_de`, los más recientes. `limite` máximo 100.

```json
{
  "resultados": [ { "id": 812, "autor_id": "uuid", "nombre_usuario": "mariana", "contenido": "hola", "creado_en": "..." } ],
  "hay_mas": true
}
```

#### `POST /api/v1/party/parties/{party_id}/mensajes`

```json
{ "contenido": "hola" }
```

`201`: el mensaje creado. Todos los miembros lo reciben como `chat.mensaje` (7.6). Errores: `400 DATOS_INVALIDOS` (vacío o más de 4096 bytes), `403 NO_ES_MIEMBRO`, `410 PARTY_FINALIZADA`.

---

## 5. queue

Elemento de cola, usado en varias respuestas:

```json
{
  "id": "uuid",
  "recurso_audio_id": "uuid",
  "agregado_por": "uuid",
  "orden": 4,
  "estado": "pendiente",
  "agregado_en": "..."
}
```

`estado`: `pendiente`, `reproduciendo`, `pausada`, `reproducida`, `omitida`, `retirada`. El cliente pide los metadatos del recurso a `music` (3.2).

Estado de una cola:

```json
{
  "id": "uuid",
  "modalidad": "individual",
  "version": 31,
  "actual": { "elemento": "...", "reproduccion": "ver 5.3" },
  "pendientes": [ "elementos en orden" ]
}
```

`modalidad` es `individual` o `compartida` y se deriva del propietario; no se guarda. El historial no se devuelve al cliente.

### 5.1 Cola individual (Axel, RF-05)

La crea el servidor la primera vez que se consulta. Se conserva al cerrar sesión. Las rutas son las mismas que las de 5.2 cambiando `parties/{party_id}/cola` por `mi-cola`:

| Operación | Endpoint |
|---|---|
| Consultar | `GET /api/v1/queue/mi-cola` |
| Agregar | `POST /api/v1/queue/mi-cola/elementos` |
| Reordenar | `PATCH /api/v1/queue/mi-cola/elementos/{elemento_id}` |
| Retirar | `DELETE /api/v1/queue/mi-cola/elementos/{elemento_id}` |
| Reproducción | `POST /api/v1/queue/mi-cola/reproduccion` |
| Fin de canción | `POST /api/v1/queue/mi-cola/elementos/{elemento_id}/terminada` |

Diferencias con la compartida: solo la usa su dueño, no hay permisos, no hay WebSocket (la respuesta de cada operación trae el estado nuevo) y la reproducción la controla el propio usuario.

### 5.2 Cola compartida (Darlington)

Solo miembros. Agregar requiere ser anfitrión o tener `puede_aportar`; reordenar, retirar y saltar requieren ser anfitrión o tener `puede_modificar_cola` (RF-11 a RF-13, RF-15). Todas las operaciones de cambio requieren `Idempotency-Key` y responden con el estado de la cola; los demás miembros reciben `cola.actualizada`.

`queue` conoce miembros, permisos y anfitrión por los eventos que publica `party` (RabbitMQ `party.eventos`); no llama a `party` en cada operación.

#### `GET /api/v1/queue/parties/{party_id}/cola`

Estado de la cola compartida.

#### `POST /api/v1/queue/parties/{party_id}/cola/elementos` (RF-11)

```json
{ "recurso_audio_id": "uuid" }
```

Se agrega al final. No inicia la reproducción aunque la cola esté vacía. La misma canción puede estar varias veces. Errores: `403 SIN_PERMISO`, `410 AUDIO_NO_DISPONIBLE`, `410 PARTY_FINALIZADA`.

#### `PATCH /api/v1/queue/parties/{party_id}/cola/elementos/{elemento_id}` (RF-12)

```json
{ "nueva_posicion": 1, "version_esperada": 31 }
```

`nueva_posicion` cuenta desde 1 dentro de los pendientes. Solo se mueven pendientes; mover el actual o el historial da `409 ELEMENTO_NO_PENDIENTE`. Errores: `403 SIN_PERMISO`, `409 VERSION_OBSOLETA`.

#### `DELETE /api/v1/queue/parties/{party_id}/cola/elementos/{elemento_id}?version_esperada=31` (RF-13)

Pasa el elemento a `retirada`. La confirmación al usuario la hace el cliente antes de llamar. Errores: los mismos de reordenar.

### 5.3 Reproducción compartida (Darlington, RF-14 a RF-16)

#### `POST /api/v1/queue/parties/{party_id}/cola/reproduccion`

Requiere `Idempotency-Key`.

```json
{ "accion": "pausar", "elemento_id": "uuid", "posicion_ms": null, "version_esperada": 31 }
```

| `accion` | Quién | Efecto |
|---|---|---|
| `iniciar` | Anfitrión | Empieza la primera pendiente desde 0 |
| `pausar` | Anfitrión | Congela la posición |
| `reanudar` | Anfitrión | Continúa desde la posición congelada |
| `buscar` | Anfitrión | Cambia a `posicion_ms` (obligatoria) |
| `saltar` | Anfitrión o `puede_modificar_cola` | Marca la actual como `omitida` y empieza la siguiente; si no hay, se detiene |

- `elemento_id` es el elemento que el usuario ve como actual. Si ya no es el actual: `409 ELEMENTO_NO_ACTUAL` y no se salta otro (RF-23).
- Un participante con `puede_modificar_cola` que intenta pausar recibe `403 NO_ES_ANFITRION` (RF-14).
- Respuesta y evento `reproduccion.estado` (7.6):

```json
{
  "cola_id": "uuid",
  "version": 32,
  "elemento_id": "uuid",
  "recurso_audio_id": "uuid",
  "estado": "reproduciendo",
  "posicion_base_ms": 45000,
  "referencia_en": "2026-11-10T18:30:00.000Z",
  "duracion_ms": 215000
}
```

`estado` de la reproducción: `reproduciendo`, `pausada` o `detenida` (sin actual; `elemento_id` y `recurso_audio_id` en `null`).

Posición actual en el cliente:

```
si reproduciendo: posicion = posicion_base_ms + (hora_servidor_ahora - referencia_en)
si pausada:       posicion = posicion_base_ms
```

`hora_servidor_ahora` = hora local + desfase de reloj medido con `reloj.ping` (7.4). Si el audio local se aleja más del límite acordado, el cliente corrige la posición (RF-10, RNF-03).

#### `POST /api/v1/queue/parties/{party_id}/cola/elementos/{elemento_id}/terminada` (RF-16)

Requiere `Idempotency-Key`. Lo manda el cliente cuando su audio llega al final. Avanza a la siguiente pendiente **una sola vez**: si el elemento ya no es el actual, responde `200` con el estado vigente sin hacer nada más.

`PENDIENTE (Darlington, T-31 y T-34)`: en la party, ¿se acepta el aviso de cualquier miembro o solo del anfitrión? Propuesta: de cualquier miembro conectado, siempre que hayan pasado al menos `duracion_ms` - 2 s de reproducción según el servidor. Así la party no se atasca si el anfitrión se desconecta.

`PENDIENTE (Darlington, T-31)`: límite de desfase y método de corrección (saltar a la posición o ajustar velocidad). Se define con las mediciones de la prueba de concepto; el SRS propone 1 s para el MVP.

---

## 6. streaming (Mariana, RF-27 a RF-29)

Solo miembros habilitados y conectados de la party. Requieren `Idempotency-Key`.

| Operación | Endpoint | Quién |
|---|---|---|
| Entrar al canal de voz | `POST /api/v1/streaming/parties/{party_id}/voz/entrar` | Miembro sin bloqueo |
| Salir del canal | `POST /api/v1/streaming/parties/{party_id}/voz/salir` | Miembro |
| Aplicar restricción | `POST /api/v1/streaming/parties/{party_id}/voz/restricciones` | Anfitrión |
| Quitar restricción | `DELETE /api/v1/streaming/parties/{party_id}/voz/restricciones/{restriccion_id}` | Anfitrión |
| Consultar canal | `GET /api/v1/streaming/parties/{party_id}/voz` | Miembro |

Cuerpo de una restricción: `{"usuario_id": "uuid", "tipo": "silencio", "motivo": null}`. `tipo` es `silencio` (no puede publicar) o `bloqueo` (no puede conectarse ni permanecer).

`GET .../voz` devuelve quién está en el canal, quién publica audio y las restricciones vigentes.

Errores: `403 VOZ_BLOQUEADA`, `403 VOZ_SILENCIADA`, `403 NO_ES_ANFITRION`, `410 PARTY_FINALIZADA`.

La señalización WebRTC viaja por el WebSocket de `streaming` (7.6).

`PENDIENTE (Mariana, T-41)`: topología (malla entre pares o servidor de medios), servidor STUN/TURN y su URL, y si `entrar` devuelve las credenciales ICE.

---

## 7. WebSocket (Darlington)

### 7.1 Conexiones

Cada servicio con eventos tiene su propio WebSocket por party. Si un servicio cae, los demás siguen funcionando (por ejemplo, el chat sigue aunque `queue` no responda).

| Servicio | URL | Eventos |
|---|---|---|
| party | `wss://<host>/ws/v1/party/parties/{party_id}/` | Miembros, permisos, anfitrión, chat, cierre, presencia |
| queue | `wss://<host>/ws/v1/queue/parties/{party_id}/` | Cola compartida y reproducción |
| streaming | `wss://<host>/ws/v1/streaming/parties/{party_id}/` | Canal de voz y señalización |

La cola individual no usa WebSocket.

`PENDIENTE (los tres)`: la alternativa es un único WebSocket en un servicio que reenvíe los eventos de todos. Es más simple para el cliente, pero si ese servicio cae, la party pierde todo el tiempo real. La propuesta es la de la tabla.

### 7.2 Autenticación

El token no va en la URL, porque las URL quedan en los logs del proxy (RNF-05). El primer mensaje del cliente, antes de 5 s, es:

```json
{ "tipo": "autenticar", "datos": { "token": "eyJ..." } }
```

Respuesta: `{"tipo": "autenticado", "datos": {"version": 12}}` con la versión actual de la party o la cola.

Cierres del servidor (código de cierre WebSocket):

| Código | Motivo |
|---|---|
| 4001 | Sin token, token inválido o vencido |
| 4003 | No es miembro, fue expulsado o tiene la voz bloqueada |
| 4004 | La party no existe |
| 4010 | La party finalizó |
| 4008 | No se autenticó a tiempo |

Cuando el token de acceso vence con la conexión abierta, el cliente lo renueva (2.3) y manda otro `autenticar` sin cerrar la conexión.

### 7.3 Sobre común

Todos los mensajes, en ambas direcciones:

```json
{
  "tipo": "cola.actualizada",
  "evento_id": "uuid",
  "enviado_en": "2026-11-10T18:30:00.123Z",
  "version": 32,
  "datos": { }
}
```

- `tipo`: `<recurso>.<suceso>`.
- `evento_id`: UUID único del evento; el cliente ignora un `evento_id` repetido.
- `enviado_en`: hora del servidor.
- `version`: versión de la party o la cola después del cambio (`null` en mensajes que no cambian estado).

### 7.4 Latido, presencia y reloj (RF-21, RNF-07)

Solo en el WebSocket de `party`, que es el que define la presencia:

- El cliente manda `{"tipo": "latido"}` cada **5 s**. El servidor responde `{"tipo": "latido.ok"}`.
- El servidor marca al miembro desconectado tras **15 s** sin un mensaje válido suyo y avisa a los demás (`miembro.desconectado`).
- El cliente se considera desconectado tras **15 s** sin recibir nada del servidor: lo muestra, deshabilita las modificaciones y reintenta conectar.
- La pertenencia y los permisos se conservan **60 s** desde que el servidor detecta la desconexión (`miembro.reconectado` si vuelve a tiempo).

Medición del desfase de reloj, en el WebSocket de `queue` (sincronización, T-31):

```json
cliente →  { "tipo": "reloj.ping", "datos": { "t_cliente": 1794363600123 } }
servidor → { "tipo": "reloj.pong", "datos": { "t_cliente": 1794363600123, "t_servidor": 1794363600210 } }
```

Tiempos en milisegundos desde 1970. Con `t_recibido` = hora local al recibir el `pong`:
`desfase = t_servidor - (t_cliente + t_recibido) / 2`. El cliente repite la medición varias veces al conectar y usa la de menor ida y vuelta.

### 7.5 Conexión y reconexión (RF-10, RF-21)

1. Abrir el WebSocket y mandar `autenticar`.
2. Pedir la instantánea por REST (`GET` de la party, la cola o el canal de voz).
3. Aplicar los eventos con `version` mayor que la de la instantánea; descartar los de versión menor o igual.
4. Si llega un evento con un salto de versión (por ejemplo, de 14 a 16), volver a pedir la instantánea.
5. Al reconectar, repetir desde el paso 1. Las acciones que el usuario intentó durante el corte no se reenvían solas (RF-21).

### 7.6 Eventos

Servidor → cliente, salvo que se indique otra dirección.

**party**

| `tipo` | `datos` | RF |
|---|---|---|
| `miembro.ingreso` | Miembro (formato de 4) | RF-08, RF-32 |
| `miembro.salida` | `{"usuario_id", "motivo"}` (`voluntaria`, `desconexion`, `expulsion`) | RF-19, RF-32 |
| `miembro.desconectado` | `{"usuario_id"}` | RF-21 |
| `miembro.reconectado` | `{"usuario_id"}` | RF-21 |
| `miembro.permisos` | `{"usuario_id", "puede_aportar", "puede_modificar_cola"}` | RF-17, RF-32 |
| `miembro.expulsado` | `{"usuario_id"}` | RF-30 |
| `miembro.rehabilitado` | `{"usuario_id"}` | RF-30 |
| `anfitrion.cambio` | `{"anterior_id", "nuevo_id", "motivo"}` (`manual`, `sucesion`) | RF-22, RF-31, RF-32 |
| `party.finalizada` | `{"finalizada_en", "motivo"}` (`anfitrion`, `sin_conectados`) | RF-20 |
| `chat.mensaje` | Mensaje (formato de 4.6) | RF-26 |

Al recibir `miembro.expulsado` sobre sí mismo o `party.finalizada`, el cliente detiene el audio, sale de la voz y cierra los tres WebSocket.

**queue**

| `tipo` | `datos` | RF |
|---|---|---|
| `cola.actualizada` | Estado de la cola (formato de 5) | RF-11 a RF-13 |
| `reproduccion.estado` | Estado de reproducción (formato de 5.3) | RF-10, RF-14 a RF-16 |
| `reloj.pong` | Ver 7.4 | RNF-03 |

**streaming**

| `tipo` | Dirección | `datos` | RF |
|---|---|---|---|
| `voz.ingreso` / `voz.salida` | Servidor → cliente | `{"usuario_id"}` | RF-27 |
| `voz.publicando` | Servidor → cliente | `{"usuario_id", "publicando": true}` | RF-28 |
| `voz.restriccion` | Servidor → cliente | `{"restriccion_id", "usuario_id", "tipo", "activa"}` | RF-29 |
| `voz.senal` | Ambas | `{"para": "uuid", "de": "uuid", "sdp": "..."}` o `{"para", "de", "candidato": {...}}` | RF-27, RF-28 |

En `voz.senal` el cliente manda `para`; el servidor agrega `de` y solo lo reenvía si ambos están en el canal y sin bloqueo.

---

## 8. Fuera de este contrato

- Eventos entre servicios por RabbitMQ (`party.eventos`, `queue.eventos`): contrato interno del backend; ver `DECISIONES.md` en el servidor.
- `logs` (RF-34): sin API para el cliente.
- Archivo técnico del chat (RF-33): proceso interno de `party`.

## 9. Pendientes

| Tema | Sección | Responsable |
|---|---|---|
| Revocación de sesión con JWT (RF-04) | 1.3 | Axel y Darlington |
| Nombres de usuario en `party` | 2.5 | Axel |
| Audio con cabecera o URL firmada | 3.3 | Axel |
| Vigencia del código de party | 4.1.1 | Mariana |
| Quién puede avisar el fin de canción | 5.3 | Darlington |
| Límite de desfase y corrección | 5.3 | Darlington |
| Topología de voz y TURN | 6 | Mariana |
| WebSocket por servicio o único | 7.1 | Los tres |
