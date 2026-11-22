import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';

import '../../core/network/api_config.dart';
import '../../core/network/api_exception.dart';
import '../../core/network/red.dart';
import '../../core/network/ws_client.dart';
import '../music/data/catalogo_service.dart';
import '../player/audio_backend.dart';
import '../player/reproductor.dart';
import 'data/cola_models.dart';
import 'data/cola_service.dart';
import 'data/party_models.dart';
import 'data/party_service.dart';
import 'segundo_plano.dart';
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
        this.buscarCanciones,
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
            buscarCanciones: CatalogoService(red.api).buscar,
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

    /// Búsqueda del catálogo para P-06 (contrato 3.1).
    final Future<List<CancionCatalogo>> Function(String texto)? buscarCanciones;
    Completer<void> _relojListo = Completer<void>();

    PartyActual _party;
    EstadoCola _cola = EstadoCola.vacia;
    EstadoReproduccion _reproduccion = EstadoReproduccion.detenida;
    WsEstado _conexion = WsEstado.desconectado;
    String? aviso;
    String? errorAudio;
    WsMotivoCierre? cierre;
    bool _cerrada = false;
    // The server told this socket that the person left or was expelled (contract 7.4).
    bool _meSacaron = false;
    Timer? _timerReingreso;
    static const _esperaReingreso = Duration(seconds: 3);
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
    bool get puedeAportar => esAnfitrion || (_party.miembro(usuarioId)?.puedeAportar ?? false);

    String? _claveAgregar;
    String? _recursoReintento;

    /// CU-11 en modo compartido. Devuelve el mensaje para el usuario.
    Future<String> agregar(String recursoAudioId) async {
        // Same key when retrying the same song after a network failure (contract 1.6): the
        // first try may have reached the server, and the song must not be added twice.
        final clave = recursoAudioId == _recursoReintento ? _claveAgregar : null;
        try {
            _aplicarCola(await colaService.agregar(_party.id, recursoAudioId, clave: clave));
            _recursoReintento = null;
            return 'Canción agregada a la cola';
        } on ApiException catch (e) {
            _recursoReintento = e.esDeRed ? recursoAudioId : null;
            _claveAgregar = e.esDeRed ? e.idempotencyKey : null;
            return switch (e.codigo) {
                'SIN_PERMISO' => 'Ya no tienes permiso para agregar canciones a esta party',
                'NO_ES_MIEMBRO' || 'PARTY_FINALIZADA' => 'Ya no puedes agregar canciones a esta sesión',
                'AUDIO_NO_DISPONIBLE' => 'Esta canción no está disponible',
                _ => 'No fue posible confirmar que la canción se agregó',
            };
        }
    }

    /// CU-15. Devuelve el mensaje para el usuario, o null si salió sin novedad. Siempre deja la
    /// sesión cerrada: el usuario vuelve a la pantalla principal pase lo que pase.
    Future<String?> salir() async {
        String? mensaje;
        try {
            await partyService.salir(_party.id);
        } on ApiException catch (e) {
            mensaje = switch (e.codigo) {
                // FA-2.1: already out or the party ended; the result is the same.
                'NO_ES_MIEMBRO' || 'PARTY_FINALIZADA' => null,
                // EX-01: the server drops the member on its own when the heartbeat stops (T-38).
                _ => 'No fue posible confirmar la salida con el servidor',
            };
        }
        // Not awaited: the user leaves the screen now; the audio and socket close behind.
        unawaited(cerrar());
        return mensaje;
    }

    /// CU-16 desde el anfitrión. Devuelve el mensaje; [cierre] indica si la party terminó.
    Future<String> finalizar() async {
        try {
            await partyService.finalizar(_party.id);
        } on ApiException catch (e) {
            switch (e.codigo) {
                case 'NO_ES_ANFITRION':
                    return 'Solo el anfitrión puede finalizar la party';
                case 'PARTY_FINALIZADA':
                    break;
                default:
                    return 'No fue posible finalizar la party. Intenta de nuevo.';
            }
        }
        _cambiar(() => cierre = WsMotivoCierre.partyFinalizada);
        unawaited(cerrar());
        return 'La party ha finalizado';
    }

    /// CU-13 y CU-14: el anfitrión da o quita permisos. Devuelve el mensaje para el anfitrión.
    Future<String> cambiarPermisos(MiembroParty miembro, {required bool puedeAportar, required bool puedeModificarCola}) async {
        final otorga = (puedeAportar && !miembro.puedeAportar) || (puedeModificarCola && !miembro.puedeModificarCola);
        try {
            await partyService.cambiarPermisos(_party.id, miembro.usuarioId, puedeAportar: puedeAportar,
                                               puedeModificarCola: puedeModificarCola, versionEsperada: _party.version);
            await _pedirParty();
            return otorga ? 'Permisos otorgados correctamente' : 'Permisos retirados correctamente';
        } on ApiException catch (e) {
            // EX-01: whatever happened, show the permissions the server has now.
            await _pedirParty();
            return switch (e.codigo) {
                'PARTICIPANTE_NO_CONECTADO' => 'El participante ya no está conectado a la party',
                'NO_ES_ANFITRION' || 'PARTY_FINALIZADA' =>
                    otorga ? 'No es posible otorgar permisos en esta sesión' : 'No es posible retirar permisos en esta sesión',
                _ => 'No fue posible confirmar la asignación de permisos',
            };
        }
    }

    Future<void> iniciar() async {
        try {
            usuarioId ??= await leerUsuario?.call();
        } on ApiException {
            usuarioId = null;
        }
        _suscripciones
            ..add(ws.estado.listen((e) => _cambiar(() => _conexion = e)))
            ..add(ws.eventos.listen((e) => unawaited(_alEvento(e))))
            ..add(ws.cierres.listen((motivo) => unawaited(_alCerrarWs(motivo))))
            ..add(reproductor.errores.listen((m) => _cambiar(() => errorAudio = m)))
            ..add(reproductor.terminado.listen((_) => unawaited(_alTerminar())));
        await SegundoPlano.mantener(_party.nombre);
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
                    final esSalida = evento.tipo == 'miembro.salida' || evento.tipo == 'miembro.expulsado';
                    if (esSalida && evento.datos['usuario_id'] == usuarioId) _meSacaron = true;
                    await _pedirParty();
                }
        }
    }

    // Contract 7.5 step 6: a 4003 nobody announced means the server detected a disconnection
    // (15 s without heartbeat). Coming back through unirse keeps the permissions within 60 s
    // (RF-21) instead of throwing the person out of a party they never left.
    Future<void> _alCerrarWs(WsMotivoCierre motivo) async {
        final codigo = PartyService.codigosDeIngreso[_party.id] ?? _party.codigo;
        if (motivo != WsMotivoCierre.sinAcceso || _meSacaron || codigo == null) {
            _cambiar(() => cierre = motivo);
            return;
        }
        await _volverAUnirse(codigo);
    }

    Future<void> _volverAUnirse(String codigo) async {
        if (_cerrada) return;
        _cambiar(() => _conexion = WsEstado.reconectando);
        try {
            final party = await partyService.unirse(codigo);
            if (_cerrada) return;
            // The new snapshot instead of the old one: after a succession the former host
            // comes back as a listener and loses the code (contract 4).
            _cambiar(() => _party = party);
            await ws.conectar();
        } on ApiException catch (e) {
            if (_cerrada) return;
            if (e.esDeRed) {
                // Still offline: keep trying, the code lasts 24 h on the server.
                _timerReingreso = Timer(_esperaReingreso, () => unawaited(_volverAUnirse(codigo)));
                return;
            }
            // Expelled meanwhile, party over, full: the server's answer is final.
            _cambiar(() => cierre = switch (e.codigo) {
                'PARTY_FINALIZADA' => WsMotivoCierre.partyFinalizada,
                ApiException.sesionExpirada => WsMotivoCierre.sesionInvalida,
                _ => WsMotivoCierre.sinAcceso,
            });
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
        _timerReingreso?.cancel();
        _pings?.cancel();
        if (!_relojListo.isCompleted) _relojListo.complete();
        sincronizador.cerrar();
        for (final s in _suscripciones) {
            await s.cancel();
        }
        await reproductor.cerrar();
        await ws.cerrar();
        await SegundoPlano.soltar();
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
