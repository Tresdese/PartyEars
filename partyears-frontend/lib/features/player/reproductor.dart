import 'dart:async';

import 'package:media_kit/media_kit.dart';

/// Lo que la app necesita de un reproductor de audio (T-53). La sincronización de la party
/// (T-55) solo usa abrir, irA, posicion y pausar/reproducir; las pruebas de pantallas pueden
/// usar una implementación falsa.
abstract class Reproductor {
    Stream<bool> get reproduciendo;
    Stream<void> get terminado;

    /// Mensajes listos para mostrar cuando el audio no se puede reproducir (RF-24).
    Stream<String> get errores;

    Duration get posicion;
    Duration get duracion;

    Future<void> abrir(Uri url, {Map<String, String> cabeceras = const {}, Duration desde = Duration.zero});
    Future<void> reproducir();
    Future<void> pausar();
    Future<void> irA(Duration posicion);

    /// Volumen local de 0 a 1: solo cambia este dispositivo, nunca la party.
    Future<void> volumen(double valor);

    /// Vuelve a abrir el último audio en la posición donde falló (RF-24, "ofreciendo reintento").
    Future<void> reintentar();
    Future<void> cerrar();
}

class ReproductorMediaKit implements Reproductor {
    ReproductorMediaKit() {
        _suscripciones.add(_player.stream.error.listen((_) => _fallar()));
        _suscripciones.add(_player.stream.completed.listen((fin) {
            if (fin && !_terminadoCtrl.isClosed) _terminadoCtrl.add(null);
        }));
    }

    static const mensajeError = 'No se pudo reproducir esta canción. Puedes intentarlo de nuevo.';
    // Waiting for the duration instead of returning right after open: a seek sent before the
    // file is loaded is dropped, and the party sync seeks right away.
    static const _esperaCarga = Duration(seconds: 10);

    final _player = Player();
    final _erroresCtrl = StreamController<String>.broadcast();
    final _terminadoCtrl = StreamController<void>.broadcast();
    final _suscripciones = <StreamSubscription<Object?>>[];

    Uri? _url;
    Map<String, String> _cabeceras = const {};

    @override
    Stream<bool> get reproduciendo => _player.stream.playing;
    @override
    Stream<void> get terminado => _terminadoCtrl.stream;
    @override
    Stream<String> get errores => _erroresCtrl.stream;
    @override
    Duration get posicion => _player.state.position;
    @override
    Duration get duracion => _player.state.duration;

    @override
    Future<void> abrir(Uri url, {Map<String, String> cabeceras = const {}, Duration desde = Duration.zero}) async {
        _url = url;
        _cabeceras = cabeceras;
        // stop() first instead of opening on top: reopening the same file keeps the same
        // duration, so the "loaded" signal below would never fire.
        await _player.stop();

        final listo = Completer<void>();
        final cargado = _player.stream.duration.listen((d) {
            if (d > Duration.zero && !listo.isCompleted) listo.complete();
        });
        final fallo = _player.stream.error.listen((_) {
            if (!listo.isCompleted) listo.complete();
        });

        try {
            await _player.open(Media(url.toString(), httpHeaders: cabeceras, start: desde), play: false);
            await listo.future.timeout(_esperaCarga);
        } on TimeoutException {
            _fallar();
        } finally {
            await cargado.cancel();
            await fallo.cancel();
        }
    }

    @override
    Future<void> reproducir() => _player.play();

    @override
    Future<void> pausar() => _player.pause();

    @override
    Future<void> irA(Duration posicion) => _player.seek(posicion < Duration.zero ? Duration.zero : posicion);

    @override
    Future<void> volumen(double valor) => _player.setVolume(valor.clamp(0.0, 1.0) * 100);

    @override
    Future<void> reintentar() async {
        final url = _url;

        if (url == null) return;

        final estabaSonando = _player.state.playing;
        await abrir(url, cabeceras: _cabeceras, desde: _player.state.position);

        if (estabaSonando) await reproducir();
    }

    void _fallar() {
        // Pausing instead of leaving mpv as is: a failed song must not look like it is playing.
        unawaited(_player.pause());

        if (!_erroresCtrl.isClosed) _erroresCtrl.add(mensajeError);
    }

    @override
    Future<void> cerrar() async {
        for (final s in _suscripciones) {
            await s.cancel();
        }
        await _player.dispose();
        await _erroresCtrl.close();
        await _terminadoCtrl.close();
    }
}

