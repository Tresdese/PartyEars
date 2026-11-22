import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';

import '../../core/network/api_config.dart';
import '../../core/network/api_exception.dart';
import '../../core/network/red.dart';
import '../../core/network/ws_client.dart';
import '../player/audio_backend.dart';
import '../player/reproductor.dart';
import 'data/cola_models.dart';
import 'data/cola_service.dart';
import 'data/party_models.dart';
import 'data/party_service.dart';
import 'sincronizacion.dart';

/// Lo que la pantalla de party necesita mientras se está dentro (T-55): la party, la cola,
/// la reproducción sincronizada y el estado de la conexión.
class SesionParty extends ChangeNotifier {
    SesionParty({
        required this._party,
        required this.partyService,
        required this.colaService,
        required this.ws,
        required this.reproductor,
        required Future<void> Function(String recursoAudioId, Duration desde) abrirAudio,
        this.usuarioId,
        this.leerUsuario,
        RelojServidor? reloj,
    }) : reloj = reloj ?? RelojServidor() {
        sincronizador = Sincronizador(reproductor: reproductor, reloj: this.reloj, abrirAudio: abrirAudio);
    }

    static SesionParty Function(PartyActual party) fabrica = (party) {
        final red = Red.instancia;
        final reproductor = ReproductorMediaKit();
        return SesionParty(
            party: party,
            partyService: PartyService(red.api),
            colaService: ColaService(red.api),
            ws: red.crearWs(Servicio.party, party.id),
            reproductor: reproductor,
            abrirAudio: (recurso, desde) => abrirRecurso(reproductor, recurso, desde: desde),
            leerUsuario: () async => usuarioDelToken((await red.api.tokensVigentes()).tokenAcceso),
        );
    };

    static const _pingsAlConectar = 10;
    static const _pingsPeriodicos = 5;
    static const _periodoReloj = Duration(seconds: 30);

    final PartyService partyService;
    final ColaService colaService;
    final WsClient ws;
    final Reproductor reproductor;
    final RelojServidor reloj;
    late final Sincronizador sincronizador;

    /// Id del usuario de esta sesión, para saber sus permisos. Si es null se usa [leerUsuario].
    String? usuarioId;
    final Future<String?> Function()? leerUsuario;
    Completer<void> _relojListo = Completer<void>();

    PartyActual _party;
    EstadoCola _cola = EstadoCola.vacia;
    EstadoReproduccion _reproduccion = EstadoReproduccion.detenida;
    WsEstado _conexion = WsEstado.desconectado;
    String? aviso;
    String? errorAudio;
    WsMotivoCierre? cierre;
    bool _cerrada = false;
    final _suscripciones = <StreamSubscription<Object?>>[];
    Timer? _timerReloj;
    Timer? _pings;

    PartyActual get party => _party;
    EstadoCola get cola => _cola;
    EstadoReproduccion get reproduccion => _reproduccion;
    WsEstado get conexion => _conexion;
    bool get conectada => _conexion == WsEstado.conectado;

    // The server only sends the invitation code to the host (contract 4).
    bool get esAnfitrion => _party.codigo != null || (usuarioId != null && usuarioId == _party.anfitrionId);
    bool get puedeSaltar => esAnfitrion || (_party.miembro(usuarioId)?.puedeModificarCola ?? false);

    Future<void> iniciar() async {
        try {
            usuarioId ??= await leerUsuario?.call();
        } on ApiException {
            usuarioId = null;
        }
        _suscripciones
            ..add(ws.estado.listen((e) => _cambiar(() => _conexion = e)))
            ..add(ws.eventos.listen((e) => unawaited(_alEvento(e))))
            ..add(ws.cierres.listen((motivo) => _cambiar(() => cierre = motivo)))
            ..add(reproductor.errores.listen((m) => _cambiar(() => errorAudio = m)))
            ..add(reproductor.terminado.listen((_) => unawaited(_alTerminar())));
        await ws.conectar();
        _timerReloj = Timer.periodic(_periodoReloj, (_) => _medirReloj(_pingsPeriodicos));
    }

    Future<void> _alEvento(WsEvento evento) async {
        switch (evento.tipo) {
            case 'autenticado':
                // Contract 7.5: after (re)connecting, ask for the snapshots and measure the clock.
                reloj.reiniciar();
                _relojListo = Completer<void>();
                _medirReloj(_pingsAlConectar);
                await _pedirInstantaneas();
            case 'reloj.pong':
                final tCliente = (evento.datos['t_cliente'] as num?)?.toInt();
                final tServidor = (evento.datos['t_servidor'] as num?)?.toInt();
                if (tCliente != null && tServidor != null) {
                    reloj.registrar(tCliente, tServidor, reloj.ahoraLocalMs());
                    if (!_relojListo.isCompleted) _relojListo.complete();
                }
            case 'cola.actualizada':
                _aplicarCola(EstadoCola.desdeJson(evento.datos));
            case 'reproduccion.estado':
                await _aplicarReproduccion(EstadoReproduccion.desdeJson(evento.datos));
            case 'party.finalizada':
                _cambiar(() => cierre = WsMotivoCierre.partyFinalizada);
                await cerrar();
            default:
                // Members, permissions and host: a fresh snapshot instead of patching each event.
                // It is one small GET for at most 20 members and never drifts from the server.
                if (evento.tipo.startsWith('miembro.') || evento.tipo.startsWith('anfitrion.')) {
                    await _pedirParty();
                }
        }
    }

    void _medirReloj(int veces) {
        var faltan = veces;
        _pings?.cancel();
        // Spread over a few hundred ms instead of a burst: pings queued behind each other would
        // all report a longer round trip.
        _pings = Timer.periodic(const Duration(milliseconds: 60), (timer) {
            ws.enviar('reloj.ping', {'t_cliente': reloj.ahoraLocalMs()});
            if (--faltan <= 0) timer.cancel();
        });
    }

    Future<void> _pedirInstantaneas() async {
        await _pedirParty();
        try {
            final cola = await colaService.consultar(_party.id);
            _aplicarCola(cola);
            final reproduccion = cola.reproduccion ?? EstadoReproduccion(version: cola.version, estado: 'detenida', posicionBaseMs: 0);
            // Waiting for the first clock reading instead of applying right away: a device whose
            // clock is seconds off would start out of sync and jump on the first check.
            await _relojListo.future.timeout(const Duration(seconds: 2), onTimeout: () {});
            await _aplicarReproduccion(reproduccion);
        } on ApiException catch (e) {
            _cambiar(() => aviso = e.mensaje);
        }
    }

    Future<void> _pedirParty() async {
        try {
            final party = await partyService.consultar(_party.id);
            if (party.version >= _party.version) _cambiar(() => _party = party);
        } on ApiException catch (e) {
            _cambiar(() => aviso = e.mensaje);
        }
    }

    // One counter per event type instead of one for everything: queue sends cola.actualizada and
    // reproduccion.estado with the same version, and both carry the full state, so a gap
    // needs no snapshot.
    void _aplicarCola(EstadoCola cola) {
        if (cola.version <= _cola.version) return;
        _cambiar(() => _cola = cola);
    }

    Future<void> _aplicarReproduccion(EstadoReproduccion estado) async {
        if (estado.version <= _reproduccion.version) return;
        _cambiar(() {
            _reproduccion = estado;
            errorAudio = null;
        });
        await sincronizador.aplicar(estado);
    }

    Future<void> _alTerminar() async {
        final elementoId = _reproduccion.elementoId;
        // Contract 5.3: for the MVP only the host reports the end of a song.
        if (!esAnfitrion || elementoId == null) return;
        await _intentar(() => colaService.terminada(_party.id, elementoId));
    }

    /// Controles: iniciar, pausar, reanudar o saltar (contrato 5.3).
    Future<void> controlar(String accion) async {
        await _intentar(() async {
            final estado = await colaService.reproduccion(_party.id, accion, elementoId: accion == 'iniciar' ? null : _reproduccion.elementoId);
            await _aplicarReproduccion(estado);
        });
    }

    Future<void> reintentarAudio() async {
        _cambiar(() => errorAudio = null);
        await reproductor.reintentar();
    }

    Future<void> _intentar(Future<void> Function() accion) async {
        try {
            await accion();
            _cambiar(() => aviso = null);
        } on ApiException catch (e) {
            _cambiar(() => aviso = e.mensaje);
        }
    }

    void _cambiar(void Function() cambio) {
        if (_cerrada) return;
        cambio();
        notifyListeners();
    }

    Future<void> cerrar() async {
        if (_cerrada) return;
        _cerrada = true;
        _timerReloj?.cancel();
        _pings?.cancel();
        if (!_relojListo.isCompleted) _relojListo.complete();
        sincronizador.cerrar();
        for (final s in _suscripciones) {
            await s.cancel();
        }
        await reproductor.cerrar();
        await ws.cerrar();
    }

    @override
    void dispose() {
        unawaited(cerrar());
        super.dispose();
    }
}

/// El "sub" de un JWT sin verificarlo: solo sirve para mostrar permisos, el servidor decide.
String? usuarioDelToken(String token) {
    final partes = token.split('.');
    if (partes.length != 3) return null;
    try {
        final datos = jsonDecode(utf8.decode(base64Url.decode(base64Url.normalize(partes[1]))));
        return datos is Map ? datos['sub'] as String? : null;
    } on FormatException {
        return null;
    }
}
