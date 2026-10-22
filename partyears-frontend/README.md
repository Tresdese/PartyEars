# PartyEars — Frontend

Frontend de **PartyEars** desarrollado con **Dart y Flutter**, organizado por módulos. El proyecto forma parte de un monorepositorio que también contiene el backend en **Python/Django**.

Esta guía explica cómo preparar el entorno, descargar el repositorio y ejecutar la aplicación en **Windows**, **Linux** o un **dispositivo Android**.

> **Estado actual:** el frontend es un prototipo modular. Las pantallas y la navegación de demostración no implican que la autenticación, la reproducción de música, la sincronización de parties o el chat de voz estén conectados al backend.

## Requisitos

### Obligatorios

- **Git:** [descargar Git](https://git-scm.com/downloads).
- **Flutter SDK (canal stable):** [instalar Flutter](https://docs.flutter.dev/install). **Dart ya viene incluido**; no es necesario instalarlo por separado.
- **Editor:** [Visual Studio Code](https://code.visualstudio.com/) con las extensiones **Flutter** y **Dart**, o Android Studio con sus plugins correspondientes.
- Conexión a Internet durante la primera descarga de dependencias.

El entorno inicial del proyecto se creó con **Flutter 3.47.7**. Para reproducir ese entorno, se recomienda usar esa versión o una compatible con el `pubspec.yaml` y `pubspec.lock` del repositorio. **No actualices Flutter ni las dependencias principales para todo el equipo sin coordinarlo.**

### Según la plataforma que quieras ejecutar

| Destino | Herramientas adicionales |
| --- | --- |
| **Windows (escritorio)** | Windows 10/11 compatible, **Visual Studio** (no solo VS Code) con **Desktop development with C++**. |
| **Linux (escritorio)** | Compilador C++, CMake, Ninja, pkg-config y bibliotecas de GTK (ver sección Linux). |
| **Android** | Android Studio, Android SDK, SDK Platform-Tools, SDK Command-line Tools y NDK si la compilación lo solicita; teléfono con depuración USB o emulador. |

No hace falta instalar herramientas de **todas** las plataformas: solo las correspondientes al destino donde vayas a desarrollar.

## 1. Clonar el repositorio

Abre una terminal (PowerShell en Windows, o una terminal normal en Linux):

```bash
git clone URL_DEL_REPOSITORIO
cd PartyEars
```

Sustituye `URL_DEL_REPOSITORIO` por la dirección real de GitHub proporcionada por el equipo.

La estructura principal es:

```text
PartyEars/
├── .git/
├── .gitignore
├── partyears-backend/        # API Django
└── partyears-frontend/       # Aplicación Flutter
    ├── android/
    ├── linux/
    ├── windows/
    ├── lib/
    ├── test/
    ├── pubspec.yaml
    ├── pubspec.lock
    └── README.md
```

Entra a la carpeta del frontend:

```bash
cd partyears-frontend
```

> **Importante:** el proyecto Flutter **ya está creado** y versionado. **No ejecutes `flutter create` ni `git init`** después de clonarlo; hacerlo es innecesario y podría modificar archivos del equipo.

## 2. Instalar y verificar Flutter

Si todavía no tienes Flutter, instálalo siguiendo la [guía oficial](https://docs.flutter.dev/install). Añade la carpeta `bin` del SDK de Flutter a la variable de entorno **PATH**, y reinicia la terminal.

En la terminal ejecuta:

```bash
flutter --version
dart --version
flutter doctor -v
```

`flutter doctor -v` muestra qué componentes necesitas instalar o corregir. Las advertencias de plataformas que **no** vayas a desarrollar no impiden trabajar en tu plataforma elegida.

### Windows: preparar aplicaciones de escritorio

1. Instala [Visual Studio Community](https://visualstudio.microsoft.com/downloads/) o una edición compatible.
2. Abre **Visual Studio Installer** y añade la carga de trabajo **Desktop development with C++** (incluyendo MSVC, CMake y Windows SDK).
3. Ejecuta `flutter doctor -v` y comprueba la sección **Visual Studio - develop Windows apps**.

**Visual Studio Code no sustituye a Visual Studio** para compilar el ejecutable nativo de Windows.

### Linux (Ubuntu, Xubuntu, Debian o derivados): preparar escritorio

Instala las herramientas de compilación:

```bash
sudo apt update
sudo apt install -y clang cmake ninja-build pkg-config libgtk-3-dev libstdc++-12-dev
flutter doctor -v
```

Compila el destino Linux **desde Linux** y el destino Windows **desde Windows**.

### Android: preparar un teléfono o emulador

1. Instala [Android Studio](https://developer.android.com/studio) y completa su configuración inicial.
2. Abre **SDK Manager**. Instala la plataforma Android compatible con el proyecto y, en **SDK Tools**, verifica **Android SDK Build-Tools**, **Android SDK Platform-Tools**, **Android SDK Command-line Tools** y las herramientas adicionales que solicite la compilación.
3. Si el SDK solicita aceptar licencias, ejecuta:

   ```bash
   flutter doctor --android-licenses
   ```

   Las versiones nuevas de Android CLI pueden indicar que `--licenses` ya no es necesario; comprueba el resultado real de `flutter doctor`.
4. Para usar un teléfono físico: habilita **Opciones de desarrollador** y **Depuración USB**, conéctalo por cable de datos y acepta la autorización de la computadora.
5. Comprueba los dispositivos:

   ```bash
   flutter devices
   ```

   También puedes crear y arrancar un emulador desde **Android Studio > Device Manager**.

> **NDK:** si Android/Gradle muestra el error `Android sdkmanager did not install NDK 28.2.13676358`, abre **SDK Manager > SDK Tools > Show Package Details > NDK (Side by side)** e instala **28.2.13676358**. No cambies la versión requerida por Gradle solo para ocultar el error.

## 3. Instalar las dependencias del frontend

Ubicado en `PartyEars/partyears-frontend`, ejecuta:

```bash
flutter pub get
```

Este comando descarga las dependencias declaradas en `pubspec.yaml` respetando las versiones resueltas en `pubspec.lock`. Es normal que aparezcan avisos sobre versiones más recientes disponibles; no equivalen a errores.

Para comprobar el proyecto:

```bash
flutter analyze
flutter test
```

Antes de subir cambios, ambos comandos deberían finalizar sin errores. Si una prueba falla, revisa su salida en vez de borrarla automáticamente.

## 4. Ejecutar PartyEars

Primero identifica los destinos disponibles:

```bash
flutter devices
```

### Windows

En **Windows**, ejecuta:

```bash
flutter run -d windows
```

### Linux

En **Linux**, ejecuta:

```bash
flutter run -d linux
```

### Android

Con el teléfono conectado y autorizado, o con un emulador activo:

```bash
flutter devices
flutter run -d ID_DEL_DISPOSITIVO
```

Reemplaza `ID_DEL_DISPOSITIVO` por el identificador que muestre `flutter devices`. **No copies el identificador USB de otro integrante.**

### Navegador (opcional)

El proyecto compartido originalmente contiene `android/`, `linux/` y `windows/`. **No des por hecho que también está habilitada la plataforma web.** Solo si el repositorio ya incluye la carpeta `web/` y el equipo decidió soportarla, se puede ejecutar:

```bash
flutter run -d chrome
```

Añadir `web/` es una decisión de proyecto que debe versionarse y coordinarse; no es un paso obligatorio de instalación.

### Durante la ejecución

- En la terminal donde corre `flutter run`, presiona **`r`** para **Hot Reload**.
- Presiona **`R`** para **Hot Restart**.
- Presiona **`q`** para salir, o **Ctrl + C** para detener la ejecución.

## 5. Estructura modular del código

El código de Flutter está dentro de `lib/`:

```text
lib/
├── main.dart
├── app/
│   ├── party_ears_app.dart
│   └── navigation/
│       └── main_shell.dart
├── core/
│   └── theme/
│       └── app_theme.dart
└── features/
    ├── auth/
    │   └── presentation/
    │       ├── login_screen.dart
    │       └── register_screen.dart
    ├── home/
    │   └── presentation/home_screen.dart
    ├── music/
    │   └── presentation/music_screen.dart
    ├── party/
    │   └── presentation/party_screen.dart
    ├── queue/
    │   └── presentation/queue_screen.dart
    ├── voice/
    │   └── presentation/voice_screen.dart
    └── profile/
        └── presentation/profile_screen.dart
```

- **`main.dart`:** punto de entrada de la aplicación.
- **`app/`:** configuración general y navegación adaptable a la pantalla.
- **`core/`:** elementos compartidos, como el tema visual; se ampliará cuando exista infraestructura común de red.
- **`features/`:** funcionalidades independientes. Por ahora las pantallas están en `presentation/`.
- **`test/`:** pruebas automáticas; deben mantenerse al cambiar pantallas o navegación.

Al añadir funcionalidades reales, cada módulo podrá incorporar sus propias carpetas de modelos, servicios, repositorios y estado, sin concentrar toda la lógica en `main.dart`.

## 6. Trabajar con el backend

El backend Django se encuentra en `../partyears-backend/`; sigue **su propio `README.md`** para instalar Python, dependencias, variables de entorno, PostgreSQL y ejecutar el servidor.

**Actualmente el prototipo Flutter funciona de forma local y no necesita iniciar Django** para mostrar las ventanas de demostración. Cuando se integre la API, el equipo deberá documentar los endpoints y la forma de configurar la URL del servidor.

Ten en cuenta que:

- `localhost` dentro de Android se refiere al **teléfono**, no al equipo que ejecuta Django.
- Para probar desde un teléfono en la misma red, se utilizará una dirección alcanzable del servidor y Django deberá aceptar las conexiones correspondientes.
- El frontend **no debe conectarse directamente a PostgreSQL** ni incluir contraseñas, tokens permanentes o claves privadas en el código fuente.
- **No existe todavía una variable `API_BASE_URL` implementada en el prototipo**: no basta con añadir un `.env` o un parámetro para que se conecte automáticamente.

## 7. Flujo de trabajo para colaboradores

Antes de empezar una tarea, situado en `partyears-frontend/`, actualiza el código desde la rama acordada por el equipo:

```bash
git pull
flutter pub get
```

> Ejecuta `git pull` desde la carpeta raíz del repositorio o desde el frontend: Git detecta la raíz automáticamente. No lo hagas si tienes cambios locales sin guardar o confirmar; primero consérvalos apropiadamente.

Para trabajar sin modificar directamente la rama principal, crea una rama de funcionalidad desde `partyears-frontend/` (Git reconoce el monorepositorio):

```bash
git switch -c feature/nombre-del-modulo
```

Después de editar:

```bash
flutter analyze
flutter test
git status
```

Prepara y guarda solo los cambios que correspondan a tu tarea:

```bash
git add lib test pubspec.yaml pubspec.lock
git commit -m "Implementar cambios del frontend"
git push -u origin feature/nombre-del-modulo
```

Ajusta `git add` a los archivos realmente modificados, incluidos `android/`, `windows/`, `linux/` o recursos cuando corresponda. Abre un Pull Request para integrar el trabajo según las reglas del equipo.

**No subas** `build/`, `.dart_tool/`, configuraciones locales (`android/local.properties`), claves de firma ni secretos. En cambio, **sí se versionan** `lib/`, `test/`, los proyectos de plataforma, `pubspec.yaml` y `pubspec.lock`.

## 8. Problemas frecuentes

| Problema | Qué revisar |
| --- | --- |
| `flutter` no se reconoce | Flutter SDK instalado y su carpeta `bin` agregada a `PATH`; reabrir la terminal. |
| `No devices found` | `flutter devices`, emulador iniciado o teléfono autorizado por USB. |
| Android: `cmdline-tools component is missing` | Instalar **Android SDK Command-line Tools** desde SDK Manager. |
| Android: fallo de NDK | Instalar en SDK Manager la **versión exacta** indicada por Gradle. |
| Windows: faltan componentes de Visual Studio | Instalar la carga **Desktop development with C++** en Visual Studio Installer. |
| Linux: faltan compiladores o GTK | Instalar los paquetes indicados en la sección Linux. |
| Paquetes no encontrados | Ejecutar `flutter pub get` dentro de `partyears-frontend/`. |
| `flutter analyze` muestra advertencias | Corregir imports no usados y otros problemas antes del commit. |
| La prueba menciona `MyApp` | Es una prueba del proyecto Flutter predeterminado; debe usar la clase actual `PartyEarsApp`. |

Como último recurso ante archivos de compilación inconsistentes (no para solucionar cualquier error de código):

```bash
flutter clean
flutter pub get
```

## 9. Ejecución habitual

Una vez configurado el entorno, los comandos cotidianos son:

```bash
cd PartyEars/partyears-frontend
flutter pub get
flutter run -d windows    # En Windows
# o: flutter run -d linux # En Linux
# o: flutter run -d ID_DEL_DISPOSITIVO # En Android
```

El comando `cd` anterior es ilustrativo: si ya estás en `partyears-frontend/`, no vuelvas a entrar.

## Documentación oficial

- [Instalar Flutter](https://docs.flutter.dev/install)
- [Configurar Flutter para Windows](https://docs.flutter.dev/platform-integration/windows/setup)
- [Configurar Flutter para Linux](https://docs.flutter.dev/platform-integration/linux/setup)
- [Configurar Flutter para Android](https://docs.flutter.dev/platform-integration/android/setup)
- [Administración de dependencias en Flutter](https://docs.flutter.dev/packages-and-plugins/dependency-management)

---

**Nota para colaboradores:** ejecuten los comandos de Flutter dentro de `partyears-frontend/`. Las instrucciones del backend Django están documentadas de forma independiente en `partyears-backend/README.md`.
