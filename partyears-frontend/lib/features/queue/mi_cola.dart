import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../core/network/api_exception.dart';
import '../../core/network/red.dart';
import '../music/data/catalogo_service.dart';
import '../party/data/cola_models.dart';
import '../player/audio_backend.dart';
import '../player/reproductor.dart';
import 'data/mi_cola_service.dart';

/// Cola individual y su reproducción en este dispositivo (RF-05, CU-25 y CU-26).
///
/// El servidor guarda la cola y qué canción va; el reproductor local la hace sonar. Cada
/// acción se confirma primero con el servidor y después se aplica al reproductor, así la cola
/// queda igual si se cierra la app.
class ControladorMiCola extends ChangeNotifier {
    ControladorMiCola({
        required MiColaService servicio,
        required Future<DetalleRecurso> Function(String recursoAudioId) detalle,
        required Reproductor reproductor,
        required Future<void> Function(String recursoAudioId, Duration desde) abrirAudio,
    }) : _servicio = servicio, _detalle = detalle, _reproductor = reproductor, _abrirAudio = abrirAudio {
        _suscripciones.add(_reproductor.terminado.listen((_) => unawaited(_alTerminar())));
        _suscripciones.add(_reproductor.errores.listen((mensaje) {
            error = mensaje;
            _dejarDeAvanzar();
            notifyListeners();
        }));
    }

    static ControladorMiCola Function() fabrica = _real;

    static ControladorMiCola _real() {
        final red = Red.instancia;
        final reproductor = ReproductorMediaKit();
        return ControladorMiCola(
            servicio: MiColaService(red.api),
            detalle: CatalogoService(red.api).detalle,
            reproductor: reproductor,
            abrirAudio: (recurso, desde) => abrirRecurso(reproductor, recurso, desde: desde),
        );
    }

    static const _cadaCuanto = Duration(milliseconds: 500);

    final MiColaService _servicio;
    final Future<DetalleRecurso> Function(String) _detalle;
    final Reproductor _reproductor;
    final Future<void> Function(String, Duration) _abrirAudio;
    final _suscripciones = <StreamSubscription<Object?>>[];
    final _detalles = <String, DetalleRecurso>{};

    EstadoCola cola = EstadoCola.vacia;
    EstadoReproduccion reproduccion = EstadoReproduccion.detenida;

    /// Último mensaje para el usuario; la pantalla lo muestra y lo borra.
    String? error;
    bool ocupado = false;
    Duration posicion = Duration.zero;

    /// El elemento cuyo audio está abierto en el reproductor, para no reabrirlo al reanudar.
    String? _abierto;
    Timer? _avance;
    bool _cerrado = false;

    ElementoCola? get actual => cola.actual;
    bool get sonando => reproduccion.sonando;
    bool get hayActual => reproduccion.elementoId != null;
    List<ElementoCola> get pendientes => cola.pendientes;

    DetalleRecurso? detalleDe(String recursoAudioId) => _detalles[recursoAudioId];

    Duration get duracion {
        final recurso = reproduccion.recursoAudioId;
        final ms = recurso == null ? 0 : (_detalles[recurso]?.duracionMs ?? 0);
        return ms > 0 ? Duration(milliseconds: ms) : _reproductor.duracion;
    }

    Future<void> cargar() => _intentar(() async {
        cola = await _servicio.consultar();
        reproduccion = cola.reproduccion ?? EstadoReproduccion.detenida;
        final elemento = reproduccion.elementoId;
        // Pausing instead of resuming on its own: the app was closed while the song played, and
        // nothing sounds here until the user presses play again.
        if (reproduccion.sonando && elemento != null) {
            reproduccion = await _servicio.reproduccion('pausar', elementoId: elemento);
        }
        posicion = Duration(milliseconds: reproduccion.posicionBaseMs);
        await _cargarDetalles();
    });

    /// RF-05: agrega al final sin interrumpir lo que suena. Devuelve el mensaje para el usuario.
    Future<String?> agregar(String recursoAudioId, {bool reproducirSiNoSuena = false}) async {
        String? mensaje;
        await _intentar(() async {
            cola = await _servicio.agregar(recursoAudioId);
            await _cargarDetalles();
            final titulo = _detalles[recursoAudioId]?.tituloConVariante ?? 'La canción';
            mensaje = '$titulo se agregó a tu cola.';
            if (reproducirSiNoSuena && !hayActual) {
                await _aplicar(await _servicio.reproduccion('iniciar'));
                mensaje = 'Reproduciendo $titulo.';
            }
        });
        return mensaje;
    }

    /// Botón de reproducir y pausar (FA-3.1: cada acción solo si corresponde al estado).
    Future<void> alternar() => _intentar(() async {
        final elemento = reproduccion.elementoId;
        if (elemento == null) {
            await _aplicar(await _servicio.reproduccion('iniciar'));
            return;
        }
        if (sonando) {
            await _reproductor.pausar();
            reproduccion = await _servicio.reproduccion('pausar', elementoId: elemento);
            _dejarDeAvanzar();
            return;
        }
        reproduccion = await _servicio.reproduccion('reanudar', elementoId: elemento);
        await _sonar(reproduccion);
    });

    Future<void> saltar() => _intentar(() async {
        final elemento = reproduccion.elementoId;
        if (elemento == null) return;
        await _aplicar(await _servicio.reproduccion('saltar', elementoId: elemento));
    });

    /// FA-3.2: una posición fuera de la canción no cambia nada.
    Future<void> buscar(Duration destino) => _intentar(() async {
        final elemento = reproduccion.elementoId;
        final total = duracion;
        if (elemento == null || destino < Duration.zero || (total > Duration.zero && destino > total)) {
            error = 'La posición de reproducción no es válida.';
            return;
        }
        reproduccion = await _servicio.reproduccion('buscar', elementoId: elemento, posicionMs: destino.inMilliseconds);
        posicion = destino;
        await _reproductor.irA(destino);
    });

    /// RF-12: mueve un pendiente a [nuevaPosicion], contando desde 1.
    Future<void> mover(String elementoId, int nuevaPosicion) => _intentar(() async {
        cola = await _servicio.reordenar(elementoId, nuevaPosicion, cola.version);
    });

    /// RF-13: la pantalla ya pidió la confirmación.
    Future<void> retirar(String elementoId) => _intentar(() async {
        cola = await _servicio.retirar(elementoId, cola.version);
    });

    Future<void> volumen(double valor) => _reproductor.volumen(valor);

    /// PRE-03 de CU-25: en una party la música individual se detiene.
    Future<void> pausarPorParty() async {
        if (!sonando) return;
        await alternar();
    }

    Future<void> _alTerminar() => _intentar(() async {
        final elemento = reproduccion.elementoId;
        if (elemento == null) return;
        await _aplicar(await _servicio.terminada(elemento));
    });

    /// Lleva el reproductor al estado que confirmó el servidor y refresca la cola.
    Future<void> _aplicar(EstadoReproduccion estado) async {
        reproduccion = estado;
        cola = await _servicio.consultar();
        await _cargarDetalles();
        if (estado.elementoId == null) {
            await _reproductor.pausar();
            _abierto = null;
            posicion = Duration.zero;
            _dejarDeAvanzar();
            return;
        }
        if (estado.sonando) {
            await _sonar(estado);
        }
    }

    Future<void> _sonar(EstadoReproduccion estado) async {
        final elemento = estado.elementoId;
        final recurso = estado.recursoAudioId;
        if (elemento == null || recurso == null) return;
        if (_abierto != elemento) {
            final desde = Duration(milliseconds: estado.posicionBaseMs);
            await _abrirAudio(recurso, desde);
            _abierto = elemento;
            posicion = desde;
        }
        await _reproductor.reproducir();
        _avanzar();
    }

    void _avanzar() {
        _avance?.cancel();
        // Only while playing: a timer that keeps firing would redraw the screen for nothing.
        _avance = Timer.periodic(_cadaCuanto, (_) {
            posicion = _reproductor.posicion;
            notifyListeners();
        });
    }

    void _dejarDeAvanzar() {
        _avance?.cancel();
        _avance = null;
    }

    Future<void> _cargarDetalles() async {
        final recursos = {
            if (actual != null) actual!.recursoAudioId,
            for (final e in pendientes) e.recursoAudioId,
        }.where((r) => !_detalles.containsKey(r));
        // All at once instead of one by one: a queue of 20 songs would take 20 round trips.
        await Future.wait([
            for (final recurso in recursos)
                _detalle(recurso).then((d) => _detalles[recurso] = d).catchError(
                    // Without its metadata the item still shows, with a generic name.
                    (Object _) => const DetalleRecurso(recursoAudioId: '', tipo: 'original', titulo: 'Canción', artistas: [], duracionMs: 0),
                    test: (e) => e is ApiException,
                ),
        ]);
    }

    Future<void> _intentar(Future<void> Function() accion) async {
        if (_cerrado) return;
        ocupado = true;
        notifyListeners();
        try {
            await accion();
        } on ApiException catch (e) {
            error = e.mensaje;
            // Reloading instead of retrying: the user must see the new queue before deciding (1.7).
            if (e.esVersionObsoleta) {
                try {
                    cola = await _servicio.consultar();
                } on ApiException {
                    // The message already tells the user to try again.
                }
            }
        } finally {
            ocupado = false;
            if (!_cerrado) notifyListeners();
        }
    }

    @override
    void dispose() {
        _cerrado = true;
        _dejarDeAvanzar();
        for (final s in _suscripciones) {
            unawaited(s.cancel());
        }
        unawaited(_reproductor.cerrar());
        super.dispose();
    }
}
