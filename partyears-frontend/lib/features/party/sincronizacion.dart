import 'dart:async';

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
    });

    final Reproductor reproductor;
    final RelojServidor reloj;
    final Future<void> Function(String recursoAudioId, Duration desde) abrirAudio;
    final Duration limite;
    final Duration periodo;

    EstadoReproduccion _estado = EstadoReproduccion.detenida;
    String? _elementoAbierto;
    Timer? _arranque;
    Timer? _revision;
    int _generacion = 0;
    int correcciones = 0;

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
            await abrirAudio(estado.recursoAudioId!, posicionEsperada(estado, reloj.ahora()));
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
            await reproductor.irA(Duration(milliseconds: estado.posicionBaseMs));
            _arranque = Timer(espera, () {
                if (generacion == _generacion) unawaited(reproductor.reproducir());
            });
        } else {
            await reproductor.irA(posicionEsperada(estado, reloj.ahora()));
            await reproductor.reproducir();
        }
        _revision ??= Timer.periodic(periodo, (_) => unawaited(revisar()));
    }

    /// Una revisión: si el audio se alejó más del límite, salta a donde debería estar.
    Future<void> revisar() async {
        if (!_estado.sonando || _arranque?.isActive == true || _elementoAbierto == null) return;
        final esperada = posicionEsperada(_estado, reloj.ahora());
        if ((reproductor.posicion - esperada).abs() > limite) {
            correcciones++;
            await reproductor.irA(esperada);
        }
    }

    void cerrar() {
        _generacion++;
        _arranque?.cancel();
        _revision?.cancel();
    }
}
