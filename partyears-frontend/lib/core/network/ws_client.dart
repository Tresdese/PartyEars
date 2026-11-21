import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'api_client.dart';
import 'api_config.dart';
import 'api_exception.dart';

enum WsEstado { desconectado, conectando, conectado, reconectando, cerrado }
enum WsMotivoCierre { sesionInvalida, sinAcceso, partyNoExiste, partyFinalizada }

class WsEvento {
    const WsEvento({
        required this.tipo,
        this.eventoId,
        this.enviadoEn,
        this.version,
        this.datos = const {},
    });

    factory WsEvento.desdeJson(Map<String, dynamic> json) {
        final enviado = json['enviado_en'];
        final datos = json['datos'];
        
        return WsEvento(tipo: json['tipo'] as String, eventoId: json['evento_id'] as String?, enviadoEn: enviado is String ? DateTime.tryParse(enviado)?.toUtc() : null,
                        version: (json['version'] as num?)?.toInt(), datos: datos is Map ? Map<String, dynamic>.from(datos) : const {},);
    }

    final String tipo;
    final String? eventoId;
    final DateTime? enviadoEn;
    final int? version;
    final Map<String, dynamic> datos;
}

abstract class WsClient {
    Stream<WsEstado> get estado;
    WsEstado get estadoActual;
    Stream<WsEvento> get eventos;
    Stream<WsMotivoCierre> get cierres;
    Future<void> conectar();
    bool enviar(String tipo, [Map<String, dynamic>? datos]);
    Future<void> cerrar();
}

class WsClientReal implements WsClient {
    WsClientReal({required this.api, required this.config, required this.servicio, required this.recursoId, this.usaLatido = false,});

    final ApiClient api;
    final ApiConfig config;
    final Servicio servicio;
    final String recursoId;
    final bool usaLatido;

    static const _tiempoAutenticar = Duration(seconds: 5);
    static const _periodoLatido = Duration(seconds: 5);
    static const _silencioMaximo = Duration(seconds: 15);

    final _estadoCtrl = StreamController<WsEstado>.broadcast();
    final _eventosCtrl = StreamController<WsEvento>.broadcast();
    final _cierresCtrl = StreamController<WsMotivoCierre>.broadcast();
    final _vistos = <String>{};

    WsEstado _estadoActual = WsEstado.desconectado;
    WebSocketChannel? _canal;
    StreamSubscription<dynamic>? _suscripcion;
    Timer? _timerAutenticar;
    Timer? _timerLatido;
    Timer? _timerSilencio;
    Timer? _timerReintento;
    Timer? _timerRenovacion;
    int _generacion = 0; 
    int _intentos = 0;
    int _cierres4001 = 0;
    bool _terminado = false;

    @override
    Stream<WsEstado> get estado => _estadoCtrl.stream;
    @override
    WsEstado get estadoActual => _estadoActual;
    @override
    Stream<WsEvento> get eventos => _eventosCtrl.stream;
    @override
    Stream<WsMotivoCierre> get cierres => _cierresCtrl.stream;

    @override
    Future<void> conectar() async {
        _terminado = false;
        _intentos = 0;
        _cierres4001 = 0;
        await _abrir();
    }

    @override
    bool enviar(String tipo, [Map<String, dynamic>? datos]) {
        if (_estadoActual != WsEstado.conectado) return false;
        
        return _enviarCrudo({'tipo': tipo, 'datos': ?datos});
    }

    @override
    Future<void> cerrar() async {
        _terminado = true;
        _generacion++;
        _timerReintento?.cancel();
        _limpiarCanal();
        _poner(WsEstado.cerrado);
        await Future.wait([_estadoCtrl.close(), _eventosCtrl.close(), _cierresCtrl.close(),]);
    }

    Future<void> _abrir() async {
        if (_terminado) return;
        
        final generacion = ++_generacion;
        _limpiarCanal();
        _poner(_intentos == 0 ? WsEstado.conectando : WsEstado.reconectando);
        WebSocketChannel? canal;

        try {
            final tokens = await api.tokensVigentes();
            
            if (generacion != _generacion) return;
            
            canal = WebSocketChannel.connect(config.ws(servicio, '/parties/$recursoId/'),);
            await canal.ready.timeout(_tiempoAutenticar);
            
            if (generacion != _generacion) {
                canal.sink.close().ignore();
                
                return;
            }
            
            _canal = canal;
            _suscripcion = canal.stream.listen((mensaje) => _alRecibir(generacion, mensaje), onError: (Object _) => _alCerrar(generacion),
                                               onDone: () => _alCerrar(generacion), cancelOnError: true,);
            _enviarCrudo({'tipo': 'autenticar', 'datos': {'token': tokens.tokenAcceso},});
            _timerAutenticar = Timer(_tiempoAutenticar, () => _alCerrar(generacion));
        } on ApiException catch (e) {
            if (e.codigo == ApiException.sesionExpirada) {
                _terminar(WsMotivoCierre.sesionInvalida);
            } else {
                _programarReintento(generacion);
            }
        } catch (_) {
            canal?.sink.close().ignore();
            _programarReintento(generacion);
        }
    }

    void _alRecibir(int generacion, dynamic crudo) {
        if (generacion != _generacion) return;
        if (usaLatido) _armarSilencio(generacion);

        final Map<String, dynamic> json;
        
        try {
            final texto = crudo is String ? crudo : utf8.decode(crudo as List<int>);
            json = jsonDecode(texto) as Map<String, dynamic>;
        } catch (_) {
            return; 
        }
        
        final tipo = json['tipo'];
        
        if (tipo is! String || tipo == 'latido.ok') return;

        if (tipo == 'autenticado') {
            _timerAutenticar?.cancel();
            _intentos = 0;
            _cierres4001 = 0;
            _poner(WsEstado.conectado);
            _iniciarLatido(generacion);
            unawaited(_programarRenovacion(generacion));
        }

        final WsEvento evento;
        
        try {
            evento = WsEvento.desdeJson(json);
        } catch (_) {
            return;
        }
        
        final id = evento.eventoId;
        if (id != null && !_esNuevo(id)) return; 
        if (!_eventosCtrl.isClosed) _eventosCtrl.add(evento);
    }

    void _alCerrar(int generacion) {
        if (generacion != _generacion || _terminado) return;

        final codigo = _canal?.closeCode;
        _limpiarCanal();

        switch (codigo) {
            case 4001:
                unawaited(_renovarYReabrir());
            case 4003:
                _terminar(WsMotivoCierre.sinAcceso);
            case 4004:
                _terminar(WsMotivoCierre.partyNoExiste);
            case 4010:
                _terminar(WsMotivoCierre.partyFinalizada);
            default: 
                _programarReintento(generacion);
        }
    }

    Future<void> _renovarYReabrir() async {
        _cierres4001++;
        
        if (_cierres4001 > 1) {
            _terminar(WsMotivoCierre.sesionInvalida);
            
            return;
        }
        
        _poner(WsEstado.reconectando);
        
        try {
            await api.renovarSesion();
            await _abrir();
        } on ApiException catch (e) {
            if (e.codigo == ApiException.sesionExpirada) {
                _terminar(WsMotivoCierre.sesionInvalida);
            } else {
                _programarReintento(_generacion);
            }
        }
    }

    void _programarReintento(int generacion) {
        if (_terminado || generacion != _generacion) return;
        
        _limpiarCanal();
        _poner(WsEstado.reconectando);
        final segundos = min(1 << min(_intentos, 3), 5);
        _intentos++;
        _timerReintento?.cancel();
        _timerReintento = Timer(Duration(seconds: segundos), _abrir);
    }

    void _terminar(WsMotivoCierre motivo) {
        _terminado = true;
        _generacion++;
        _timerReintento?.cancel();
        _limpiarCanal();
        _poner(WsEstado.cerrado);
        if (!_cierresCtrl.isClosed) _cierresCtrl.add(motivo);
    }

    void _iniciarLatido(int generacion) {
        _timerLatido?.cancel();
        if (!usaLatido) return;
        _timerLatido = Timer.periodic(_periodoLatido, (_) {if (generacion == _generacion) _enviarCrudo({'tipo': 'latido'});});
    }

    void _armarSilencio(int generacion) {
        _timerSilencio?.cancel();
        _timerSilencio = Timer(_silencioMaximo, () => _alCerrar(generacion));
    }

    Future<void> _programarRenovacion(int generacion) async {
        try {
            final t = await api.tokensVigentes();

            if (generacion != _generacion) return;

            var espera = t.tiempoRestante - const Duration(seconds: 25);

            if (espera < const Duration(seconds: 1)) {
                espera = const Duration(seconds: 1);
            }

            _timerRenovacion?.cancel();
            _timerRenovacion = Timer(espera, () => unawaited(_renovarEnConexion(generacion)));
        } on ApiException catch (e) {
            if (generacion != _generacion) return;

            if (e.codigo == ApiException.sesionExpirada) {
                _terminar(WsMotivoCierre.sesionInvalida);
            } else {
                _timerRenovacion = Timer(const Duration(seconds: 10), () => unawaited(_programarRenovacion(generacion)));
            }
        }
    }

    Future<void> _renovarEnConexion(int generacion) async {
        try {
            final t = await api.tokensVigentes();
            
            if (generacion != _generacion) return;
            
            _enviarCrudo({'tipo': 'autenticar', 'datos': {'token': t.tokenAcceso},});
            await _programarRenovacion(generacion);
        } on ApiException catch (e) {
            if (generacion != _generacion) return;

            if (e.codigo == ApiException.sesionExpirada) {
                _terminar(WsMotivoCierre.sesionInvalida);
            } else {
                _timerRenovacion = Timer(const Duration(seconds: 10), () => unawaited(_renovarEnConexion(generacion)));
            }
        }
    }

    bool _enviarCrudo(Map<String, dynamic> mensaje) {
        final canal = _canal;

        if (canal == null) return false;

        try {
            canal.sink.add(jsonEncode(mensaje));
            
            return true;
        } catch (_) {
            return false;
        }
    }

    bool _esNuevo(String id) {
        if (!_vistos.add(id)) return false;

        if (_vistos.length > 500) _vistos.remove(_vistos.first);

        return true;
    }

    void _poner(WsEstado nuevo) {
        if (_estadoActual == nuevo) return;

        _estadoActual = nuevo;

        if (!_estadoCtrl.isClosed) _estadoCtrl.add(nuevo);
    }

    void _limpiarCanal() {
        _timerAutenticar?.cancel();
        _timerLatido?.cancel();
        _timerSilencio?.cancel();
        _timerRenovacion?.cancel();
        _suscripcion?.cancel();
        _suscripcion = null;
        _canal?.sink.close(1000).ignore();
        _canal = null;
    }
}

enum DecisionVersion { aplicar, descartar, pedirInstantanea }

class ControlVersion {
    int? _actual;

    void alRecibirInstantanea(int version) => _actual = version;

    DecisionVersion evaluar(int? version) {
        if (version == null) return DecisionVersion.aplicar;

        final actual = _actual;

        if (actual == null) return DecisionVersion.pedirInstantanea;

        if (version <= actual) return DecisionVersion.descartar;
        
        if (version == actual + 1) {
            _actual = version;
            
            return DecisionVersion.aplicar;
        }
        
        return DecisionVersion.pedirInstantanea;
    }
}