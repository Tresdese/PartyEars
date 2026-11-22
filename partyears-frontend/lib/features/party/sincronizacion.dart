import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../player/reproductor.dart';
import 'data/cola_models.dart';

/// Hora del servidor estimada con reloj.ping/reloj.pong (contrato 7.4).
class RelojServidor {
    RelojServidor({DateTime Function()? ahora}) : _ahora = ahora ?? DateTime.now;

    final DateTime Function() _ahora;
    Duration _desfase = Duration.zero;
    int? _mejorIdaYVuelta;

    bool get medido => _mejorIdaYVuelta != null;

    DateTime ahora() => _ahora().toUtc().add(_desfase);

    int ahoraLocalMs() => _ahora().millisecondsSinceEpoch;

    /// Se queda con la medición de menor ida y vuelta: es la que menos error arrastra.
    void registrar(int tCliente, int tServidor, int tRecibido) {
        final idaYVuelta = tRecibido - tCliente;
        if (_mejorIdaYVuelta != null && idaYVuelta >= _mejorIdaYVuelta!) return;
        _mejorIdaYVuelta = idaYVuelta;
        // Assumes the trip there and back take the same time (contract 7.4).
        _desfase = Duration(milliseconds: (tServidor - (tCliente + tRecibido) / 2).round());
    }

    /// Las mediciones viejas dejan de valer cuando la red cambia: se vuelve a elegir la mejor.
    void reiniciar() => _mejorIdaYVuelta = null;
}

/// Cuánto tarda en sonar el altavoz de este dispositivo lo que el reproductor ya reprodujo.
///
/// Set by hand in the profile instead of measured: measuring needs the microphone. Android
/// adds 100-300 ms and Bluetooth more, so without it the phone sounds behind the PC.
class RetrasoAudio {
    static const _clave = 'partyears.retraso_audio_ms';
    static const maximo = Duration(milliseconds: 500);
    static Duration valor = Duration.zero;

    static Future<void> cargar() async {
        try {
            final ms = (await SharedPreferences.getInstance()).getInt(_clave) ?? 0;
            valor = Duration(milliseconds: ms);
        } catch (_) {
            valor = Duration.zero;
        }
    }

    static Future<void> guardar(Duration nuevo) async {
        valor = nuevo;
        try {
            await (await SharedPreferences.getInstance()).setInt(_clave, nuevo.inMilliseconds);
        } catch (_) {
            // Kept for this run only if storage is unavailable.
        }
    }
}

/// Posición que debería tener el audio según el servidor (contrato 5.3).
Duration posicionEsperada(EstadoReproduccion estado, DateTime horaServidor) {
    final base = Duration(milliseconds: estado.posicionBaseMs);
    final referencia = estado.referenciaEn;
    if (!estado.sonando || referencia == null) return base;
    final transcurrido = horaServidor.difference(referencia);
    return transcurrido.isNegative ? base : base + transcurrido;
}

/// Hace que el reproductor siga el estado de la party: abre la canción, arranca en
/// referencia_en y salta si se aleja más del límite (contrato 5.3, validado en T-31).
class Sincronizador {
    Sincronizador({
        required this.reproductor,
        required this.reloj,
        required this.abrirAudio,
        this.limite = const Duration(milliseconds: 200),
        this.periodo = const Duration(milliseconds: 500),
        this.pausaTrasCorregir = const Duration(milliseconds: 1500),
        Duration Function()? retraso,
    }) : _retraso = retraso ?? (() => RetrasoAudio.valor);

    final Reproductor reproductor;
    final RelojServidor reloj;
    final Future<void> Function(String recursoAudioId, Duration desde) abrirAudio;
    final Duration limite;
    final Duration periodo;
    final Duration pausaTrasCorregir;
    final Duration Function() _retraso;

    static const _adelantoMaximo = Duration(seconds: 3);

    EstadoReproduccion _estado = EstadoReproduccion.detenida;
    String? _elementoAbierto;
    Timer? _arranque;
    Timer? _revision;
    int _generacion = 0;
    int correcciones = 0;
    // How far ahead to seek so the audio lands on time: over Wi-Fi a seek in a FLAC takes longer
    // than the 200 ms limit, and the song keeps moving while it loads.
    Duration _adelanto = Duration.zero;
    DateTime? _corregidoEn;

    EstadoReproduccion get estado => _estado;

    Future<void> aplicar(EstadoReproduccion estado) async {
        _estado = estado;
        final generacion = ++_generacion;
        _arranque?.cancel();
        _arranque = null;

        if (estado.elementoId == null) {
            _elementoAbierto = null;
            _revision?.cancel();
            await reproductor.pausar();
            return;
        }

        if (estado.elementoId != _elementoAbierto) {
            _elementoAbierto = estado.elementoId;
            await abrirAudio(estado.recursoAudioId!, _objetivo());
            // A newer state may have arrived while the file was loading.
            if (generacion != _generacion) return;
        }

        if (!estado.sonando) {
            await reproductor.pausar();
            await reproductor.irA(Duration(milliseconds: estado.posicionBaseMs));
            return;
        }

        final espera = estado.referenciaEn!.difference(reloj.ahora());
        if (espera > Duration.zero) {
            // Pre-seek and wait instead of starting on arrival: every client starts at the same
            // server instant, whenever the message reached each one.
            await reproductor.pausar();
            await reproductor.irA(Duration(milliseconds: estado.posicionBaseMs) + _retraso());
            _arranque = Timer(espera, () {
                if (generacion == _generacion) unawaited(reproductor.reproducir());
            });
        } else {
            await reproductor.irA(_objetivo());
            await reproductor.reproducir();
        }
        _revision ??= Timer.periodic(periodo, (_) => unawaited(revisar()));
    }

    /// Una revisión: si el audio se alejó más del límite, salta a donde debería estar.
    Future<void> revisar() async {
        if (!_estado.sonando || _arranque?.isActive == true || _elementoAbierto == null) return;
        // Waiting after a seek instead of checking on the next tick: the player still reports
        // the old position while it loads, and checking right away seeked forever (T-31).
        final ahora = DateTime.now();
        if (_corregidoEn != null && ahora.difference(_corregidoEn!) < pausaTrasCorregir) return;
        final esperada = _objetivo();
        final desfase = reproductor.posicion - esperada;
        if (desfase.abs() <= limite) {
            _corregidoEn = null;
            return;
        }
        // Still off right after a correction: that error is what the seek costs on this device.
        if (_corregidoEn != null) {
            final nuevo = _adelanto - desfase;
            _adelanto = nuevo.isNegative ? Duration.zero : (nuevo > _adelantoMaximo ? _adelantoMaximo : nuevo);
        }
        correcciones++;
        debugPrint('sync: desfase ${desfase.inMilliseconds} ms, corrección $correcciones, '
                   'adelanto ${_adelanto.inMilliseconds} ms');
        _corregidoEn = ahora;
        await reproductor.irA(esperada + _adelanto);
    }

    // Where the player must be for the speaker to sound on time: ahead by its delay while playing.
    Duration _objetivo() {
        final esperada = posicionEsperada(_estado, reloj.ahora());
        return _estado.sonando ? esperada + _retraso() : esperada;
    }

    void cerrar() {
        _generacion++;
        _arranque?.cancel();
        _revision?.cancel();
    }
}
