import 'package:flutter_test/flutter_test.dart';
import 'package:partyears_frontend/core/network/api_client.dart';
import 'package:partyears_frontend/core/network/api_config.dart';
import 'package:partyears_frontend/core/network/simulado.dart';
import 'package:partyears_frontend/features/music/data/catalogo_service.dart';
import 'package:partyears_frontend/features/queue/data/mi_cola_service.dart';
import 'package:partyears_frontend/features/queue/mi_cola.dart';

import '../party/falsos.dart';

void main() {
    late MockApiClient api;
    late MiColaService servicio;
    late ReproductorFalso reproductor;
    late ControladorMiCola controlador;
    late List<String> abiertos;

    setUp(() async {
        api = MockApiClient(latencia: Duration.zero);
        await api.post(Servicio.auth, '/login', autenticado: false,
                       cuerpo: {'correo': 'demo@partyears.mx', 'contrasena': 'demopassword1'});
        servicio = MiColaService(api);
        reproductor = ReproductorFalso();
        abiertos = [];
        controlador = ControladorMiCola(
            servicio: servicio,
            detalle: CatalogoService(api).detalle,
            reproductor: reproductor,
            abrirAudio: (recurso, desde) async => abiertos.add(recurso),
        );
        addTearDown(controlador.dispose);
    });

    Future<void> llenar() async {
        for (final recurso in ['recurso-1-original', 'recurso-2-original', 'recurso-3-instrumental']) {
            await controlador.agregar(recurso);
        }
    }

    test('agregar no interrumpe ni inicia la reproducción', () async {
        final mensaje = await controlador.agregar('recurso-1-original');
        expect(mensaje, 'Noche de Neón se agregó a tu cola.');
        expect(controlador.pendientes, hasLength(1));
        expect(controlador.hayActual, isFalse);
        expect(reproductor.llamadas, isEmpty);
    });

    test('reproducir desde el catálogo con la cola parada empieza esa canción', () async {
        await controlador.agregar('recurso-3-instrumental', reproducirSiNoSuena: true);
        expect(controlador.sonando, isTrue);
        expect(abiertos, ['recurso-3-instrumental']);
        expect(reproductor.llamadas, ['reproducir']);
        expect(controlador.detalleDe('recurso-3-instrumental')!.tituloConVariante, 'Marea Alta (instrumental)');
    });

    test('pausar y reanudar no vuelven a abrir el audio', () async {
        await llenar();
        await controlador.alternar();
        await controlador.alternar();
        expect(controlador.reproduccion.estado, 'pausada');
        await controlador.alternar();
        expect(controlador.sonando, isTrue);
        expect(abiertos, ['recurso-1-original']);
        expect(reproductor.llamadas, ['reproducir', 'pausar', 'reproducir']);
    });

    test('al terminar una canción sigue la siguiente y al final se detiene', () async {
        await llenar();
        await controlador.alternar();
        for (var i = 0; i < 3; i++) {
            reproductor.terminadoCtrl.add(null);
            await pumpEventQueue();
        }
        expect(abiertos, ['recurso-1-original', 'recurso-2-original', 'recurso-3-instrumental']);
        expect(controlador.hayActual, isFalse);
        expect(controlador.pendientes, isEmpty);
        expect(reproductor.llamadas.last, 'pausar');
    });

    test('saltar empieza la siguiente pendiente', () async {
        await llenar();
        await controlador.alternar();
        await controlador.saltar();
        expect(abiertos, ['recurso-1-original', 'recurso-2-original']);
        expect(controlador.pendientes.map((e) => e.recursoAudioId), ['recurso-3-instrumental']);
    });

    test('mover y retirar cambian los pendientes', () async {
        await llenar();
        final ultimo = controlador.pendientes.last.id;
        await controlador.mover(ultimo, 1);
        expect(controlador.pendientes.first.id, ultimo);
        await controlador.retirar(ultimo);
        expect(controlador.pendientes.map((e) => e.id), isNot(contains(ultimo)));
        expect(controlador.pendientes, hasLength(2));
    });

    test('con la cola vieja muestra el aviso y recarga en vez de reintentar', () async {
        await llenar();
        final primero = controlador.pendientes.first.id;
        // Another device of the same user changes the queue in between.
        await servicio.agregar('recurso-4-original');
        await controlador.mover(primero, 2);
        expect(controlador.error, 'La cola cambió. Recarga para ver la actual.');
        expect(controlador.pendientes, hasLength(4));
        expect(controlador.pendientes.first.id, primero);
    });

    test('una posición fuera de la canción no se manda al servidor', () async {
        await llenar();
        await controlador.alternar();
        final version = controlador.reproduccion.version;
        await controlador.buscar(const Duration(hours: 1));
        expect(controlador.error, 'La posición de reproducción no es válida.');
        expect(controlador.reproduccion.version, version);
    });

    test('al abrir la app con una canción sonando en el servidor queda en pausa', () async {
        await llenar();
        await servicio.reproduccion('iniciar');
        await controlador.cargar();
        expect(controlador.reproduccion.estado, 'pausada');
        expect(reproductor.llamadas, isEmpty);
    });

    test('la cola individual se conserva al cerrar sesión', () async {
        await llenar();
        await api.post(Servicio.auth, '/logout', cuerpo: {'token_renovacion': 'x'});
        await api.post(Servicio.auth, '/login', autenticado: false,
                       cuerpo: {'correo': 'demo@partyears.mx', 'contrasena': 'demopassword1'});
        await controlador.cargar();
        expect(controlador.pendientes, hasLength(3));
    });
}
