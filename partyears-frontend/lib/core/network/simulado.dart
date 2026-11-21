import 'dart:async';
import 'api_client.dart';
import 'api_config.dart';
import 'api_exception.dart';
import 'token_store.dart';
import 'uuid.dart';
import 'ws_client.dart';

String _iso(DateTime d) => DateTime.fromMillisecondsSinceEpoch(d.millisecondsSinceEpoch, isUtc: true,).toIso8601String();

class MockApiClient implements ApiClient {
    MockApiClient({this.latencia = const Duration(milliseconds: 300)});

    final Duration latencia;
    final _tokens = TokenStoreMemoria();
    final _sesionExpiradaCtrl = StreamController<void>.broadcast();
    final _usuarios = <Map<String, String>>[{'id': 'usuario-demo', 'nombre_usuario': 'demo', 'correo': 'demo@partyears.mx', 'contrasena': 'demopassword1',},];
    final _sesiones = <String, String>{}; 
    final _resultadosPorClave = <String, dynamic>{};
    
    String? _usuarioActual;
    
    Map<String, dynamic>? _party;

    late final List<Map<String, dynamic>> _catalogo = [
        _cancion(1, 'Noche de Neón', 'Luna Roja', 215000, instrumental: true),
        _cancion(2, 'Camino a Xalapa', 'Los Cafetales', 188000),
        _cancion(3, 'Marea Alta', 'Costa Norte', 241000, instrumental: true),
        _cancion(4, 'Sábado sin prisa', 'Los Cafetales', 199000),
        _cancion(5, 'Ñandú', 'Selva Azul', 176000),
        _cancion(6, 'Luces de la ciudad', 'Luna Roja', 232000),
    ];

    Map<String, dynamic> _cancion(int n, String titulo, String artista, int ms, {bool instrumental = false,}) => {
        'id': 'cancion-$n',
        'titulo': titulo,
        'duracion_ms': ms,
        'artistas': [{'id': 'artista-$n', 'nombre': artista},],
        'variantes': [{'recurso_audio_id': 'recurso-$n-original', 'tipo': 'original', 'disponible': true,},
                      if (instrumental) {'recurso_audio_id': 'recurso-$n-instrumental', 'tipo': 'instrumental', 'disponible': true,},],
    };

    @override
    Stream<void> get sesionExpirada => _sesionExpiradaCtrl.stream;

    @override
    Future<dynamic> enviar(String metodo, Servicio servicio, String ruta, {Map<String, String>? query, Object? cuerpo, bool autenticado = true,
                                                                           bool idempotente = false, String? idempotencyKey,}) async {
        await Future<void>.delayed(latencia);
        final clave = idempotente ? (idempotencyKey ?? nuevoUuid()) : null;

        try {
            if (clave != null && _resultadosPorClave.containsKey(clave)) {
                return _resultadosPorClave[clave];
            }
            
            if (autenticado && _usuarioActual == null) {
                throw _errorSesionExpirada();
            }
            
            final datos = cuerpo is Map ? Map<String, dynamic>.from(cuerpo) : <String, dynamic>{};
            final resultado = await _atender('$metodo ${servicio.nombre}$ruta', query, datos);
            
            if (clave != null) _resultadosPorClave[clave] = resultado;
            
            return resultado;
        } on ApiException catch (e) {
            throw clave == null ? e : e.conClave(clave);
        }
    }

    Future<dynamic> _atender(String operacion, Map<String, String>? query, Map<String, dynamic> datos,) async {
        switch (operacion) {
            case 'POST auth/registro':
                return _registro(datos);
            case 'POST auth/login':
                return _login(datos);
            case 'POST auth/renovar':
                final id = _sesiones.remove(datos['token_renovacion']);

                if (id == null) {
                    throw const ApiException(codigo: 'TOKEN_INVALIDO', mensaje: 'Tu sesión ya no es válida. Inicia sesión de nuevo.', estadoHttp: 401,);
                }

                return _abrirSesion(_usuarios.firstWhere((u) => u['id'] == id));
            case 'POST auth/logout':
                _sesiones.remove(datos['token_renovacion']);
                _usuarioActual = null;
                _party = null;
                return null;
            case 'GET music/canciones':
                return _buscar(query);
            case 'POST party/parties':
                return _crearParty(datos);
            case 'GET party/parties/actual':
                return _party; 
            case 'POST party/parties/unirse':
                if (_party != null) {
                    throw const ApiException(codigo: 'YA_EN_OTRA_PARTY', mensaje: 'Ya estás en otra party. Sal de ella para continuar.', estadoHttp: 409,);
                }

                throw const ApiException(codigo: 'CODIGO_INVALIDO', mensaje: 'No existe una party con ese código.', estadoHttp: 404,);
        }
    
        final cierre = RegExp(r'^(POST) party/parties/([^/]+)/(salir|finalizar)$').firstMatch(operacion);
        
        if (cierre != null) {
            _party = null;
            
            return null;
        }
    
        throw ApiException(codigo: 'NO_ENCONTRADO', mensaje: 'El modo simulado no tiene esta operación: $operacion', estadoHttp: 404,);
    }

    Map<String, dynamic> _registro(Map<String, dynamic> datos) {
        final nombre = (datos['nombre_usuario'] as String? ?? '').trim();
        final correo = (datos['correo'] as String? ?? '').trim();
        final contrasena = datos['contrasena'] as String? ?? '';
        final errores = <String, List<String>>{};

        if (nombre.isEmpty) errores['nombre_usuario'] = ['Este campo es obligatorio.'];

        if (!correo.contains('@')) errores['correo'] = ['Escribe un correo válido.'];

        if (contrasena.length < 10) {
            errores['contrasena'] = ['Debe tener al menos 10 caracteres.'];
        }

        if (datos['confirmacion'] != contrasena) {
            errores['confirmacion'] = ['No coincide con la contraseña.'];
        }
        
        if (errores.isNotEmpty) {
            throw ApiException(codigo: 'DATOS_INVALIDOS', mensaje: 'Revisa los datos del formulario.', detalles: errores, estadoHttp: 400,);
        }

        if (_usuarios.any((u) => u['correo']!.toLowerCase() == correo.toLowerCase())) {
            throw const ApiException(codigo: 'DUPLICADO', mensaje: 'Ya existe una cuenta con ese correo.', 
                                     detalles: {'correo': ['Ya está registrado.'],}, estadoHttp: 409,);
        }

        final usuario = {'id': nuevoUuid(), 'nombre_usuario': nombre, 'correo': correo, 'contrasena': contrasena,};
        _usuarios.add(usuario);
        
        return {'id': usuario['id'], 'nombre_usuario': nombre, 'correo': correo, 'creado_en': _iso(DateTime.now()),};
    }

    Future<Map<String, dynamic>> _login(Map<String, dynamic> datos) async {
        final correo = (datos['correo'] as String? ?? '').trim().toLowerCase();
        final usuario = _usuarios.where((u) => u['correo']!.toLowerCase() == correo && u['contrasena'] == datos['contrasena']);
        
        if (usuario.isEmpty) {
            throw const ApiException(codigo: 'CREDENCIALES_INVALIDAS', mensaje: 'Correo o contraseña incorrectos.', estadoHttp: 401,);
        }
        
        return _abrirSesion(usuario.first);
    }

    Future<Map<String, dynamic>> _abrirSesion(Map<String, String> usuario) async {
        final json = <String, dynamic>{
            'token_acceso': 'simulado.${nuevoUuid()}',
            'token_renovacion': nuevoUuid(),
            'expira_en': _iso(DateTime.now().add(const Duration(minutes: 5))),
            'usuario': {'id': usuario['id'], 'nombre_usuario': usuario['nombre_usuario']},
        };
        
        _sesiones[json['token_renovacion'] as String] = usuario['id']!;
        _usuarioActual = usuario['id'];
        await _tokens.guardar(TokensGuardados.desdeJson(json));
        return json;
    }

    Map<String, dynamic> _buscar(Map<String, String>? query) {
        final q = (query?['q'] ?? '').trim().toLowerCase();
        var pagina = int.tryParse(query?['pagina'] ?? '') ?? 1;
        
        if (pagina < 1) pagina = 1;

        final coincidencias = _catalogo.where((c) {
            final artistas = (c['artistas'] as List).map((a) => (a as Map)['nombre']).join(' ');
            return '${c['titulo']} $artistas'.toLowerCase().contains(q);
        }).toList();

        return {'resultados': coincidencias.skip((pagina - 1) * 20).take(20).toList(), 'pagina': pagina,
                'total_paginas': (coincidencias.length / 20).ceil(), 'total': coincidencias.length,};
    }

    Map<String, dynamic> _crearParty(Map<String, dynamic> datos) {
        final nombre = (datos['nombre'] as String? ?? '').trim();

        if (nombre.isEmpty) {
            throw const ApiException(codigo: 'DATOS_INVALIDOS', mensaje: 'Ponle un nombre a la party.', detalles: {'nombre': ['Este campo es obligatorio.'],}, estadoHttp: 400,);
        }

        if (_party != null) {
            throw const ApiException(codigo: 'YA_EN_OTRA_PARTY', mensaje: 'Ya estás en otra party. Sal de ella para continuar.', estadoHttp: 409,);
        }

        const letras = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';

        final codigo = List.generate(6, (i) => letras[DateTime.now().microsecondsSinceEpoch * (i + 7) % letras.length],).join();
        final usuario = _usuarios.firstWhere((u) => u['id'] == _usuarioActual);

        return _party = {'id': nuevoUuid(), 'nombre': nombre, 'codigo': codigo, 'version': 1, 'creada_en': _iso(DateTime.now()), 
                         'finalizada_en': null, 'anfitrion_id': usuario['id'], 'cola_id': nuevoUuid(), 
                         'miembros': [{'usuario_id': usuario['id'], 'nombre_usuario': usuario['nombre_usuario'], 'puede_aportar': true,
                                       'puede_modificar_cola': true, 'estado': 'habilitado', 'conectado': true, 'orden_ingreso': 1,},],};
    }

    @override
    Future<TokensGuardados> tokensVigentes() async {
        final t = await _tokens.leer();

        if (t == null) throw _errorSesionExpirada();

        return t;
    }

    @override
    Future<TokensGuardados> renovarSesion({bool forzar = true}) async {
        final t = await _tokens.leer();
        final id = t == null ? null : _sesiones.remove(t.tokenRenovacion);

        if (id == null) {
            await _tokens.borrar();
            _sesiones.clear();
            _usuarioActual = null;

            if (!_sesionExpiradaCtrl.isClosed) _sesionExpiradaCtrl.add(null);
            
            throw _errorSesionExpirada();
        }

        await _abrirSesion(_usuarios.firstWhere((u) => u['id'] == id));

        return (await _tokens.leer())!;
    }

    @override
    Future<bool> haySesion() async => (await _tokens.leer()) != null;

    @override
    Future<void> cerrarSesion() async {
        await _tokens.borrar();
        _sesiones.clear();
        _usuarioActual = null;
        _party = null;
    }

    ApiException _errorSesionExpirada() => const ApiException(codigo: ApiException.sesionExpirada, mensaje: 'Tu sesión terminó. Inicia sesión de nuevo.', estadoHttp: 401,);

    @override
    void cerrar() {
        _sesionExpiradaCtrl.close();
    }
}

class WsSimulado implements WsClient {
    final _estadoCtrl = StreamController<WsEstado>.broadcast();
    final _eventosCtrl = StreamController<WsEvento>.broadcast();
    final _cierresCtrl = StreamController<WsMotivoCierre>.broadcast();

    WsEstado _estadoActual = WsEstado.desconectado;

    int _version = 1;

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
        _poner(WsEstado.conectando);
        await Future<void>.delayed(const Duration(milliseconds: 200));
        _alConectar();
    }

    void _alConectar() {
        _poner(WsEstado.conectado);
        _emitirEvento(WsEvento(tipo: 'autenticado', datos: {'version': _version}));
    }

    @override
    bool enviar(String tipo, [Map<String, dynamic>? datos]) => _estadoActual == WsEstado.conectado;

    void emitir(String tipo, {Map<String, dynamic> datos = const {}, bool cambiaVersion = true,}) {
        if (cambiaVersion) _version++;

        _emitirEvento(WsEvento(tipo: tipo, eventoId: nuevoUuid(), enviadoEn: DateTime.now().toUtc(), version: cambiaVersion ? _version : null, datos: datos,));
    }

    Future<void> simularCorte({Duration duracion = const Duration(seconds: 3),}) async {
        _poner(WsEstado.reconectando);
        await Future<void>.delayed(duracion);

        if (_estadoActual == WsEstado.reconectando) _alConectar();
    }

    void simularCierre(WsMotivoCierre motivo) {
        _poner(WsEstado.cerrado);

        if (!_cierresCtrl.isClosed) _cierresCtrl.add(motivo);
    }

    @override
    Future<void> cerrar() async {
        _poner(WsEstado.cerrado);
        await Future.wait([_estadoCtrl.close(), _eventosCtrl.close(), _cierresCtrl.close(),]);
    }

    void _emitirEvento(WsEvento e) {
        if (!_eventosCtrl.isClosed) _eventosCtrl.add(e);
    }

    void _poner(WsEstado nuevo) {
        if (_estadoActual == nuevo) return;

        _estadoActual = nuevo;
        
        if (!_estadoCtrl.isClosed) _estadoCtrl.add(nuevo);
    }
}