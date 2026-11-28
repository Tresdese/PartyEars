import 'dart:async';
import 'dart:convert';
import 'api_client.dart';
import 'api_config.dart';
import 'api_exception.dart';
import 'token_store.dart';
import 'uuid.dart';
import 'ws_client.dart';

String _iso(DateTime d) => DateTime.fromMillisecondsSinceEpoch(d.millisecondsSinceEpoch, isUtc: true,).toIso8601String();

// Shaped like a real JWT instead of a plain id: the screens read sub and nombre_usuario from it.
String _tokenSimulado(Map<String, String> usuario) {
    String parte(Map<String, Object?> datos) => base64Url.encode(utf8.encode(jsonEncode(datos))).replaceAll('=', '');
    return '${parte({'alg': 'none'})}.${parte({'sub': usuario['id'], 'nombre_usuario': usuario['nombre_usuario']})}.simulado-${nuevoUuid()}';
}

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

    final _miCola = MiColaSimulada();

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
    
        // T-55: the party screen asks for the snapshot and the shared queue when it connects.
        final consulta = RegExp(r'^GET party/parties/([^/]+)$').firstMatch(operacion);

        if (consulta != null && _party != null && _party!['id'] == consulta.group(1)) return _party;

        if (operacion.startsWith('GET music/recursos/')) return _detalleRecurso(operacion.split('/').last);

        if (operacion.contains('queue/mi-cola')) return _miCola.atender(operacion, query, datos, _usuarioActual!);

        if (RegExp(r'^GET queue/parties/([^/]+)/cola$').hasMatch(operacion)) {
            return {'id': 'cola-simulada', 'modalidad': 'compartida', 'version': 0, 'actual': null, 'pendientes': <Object>[]};
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
            'token_acceso': _tokenSimulado(usuario),
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

    Map<String, dynamic> _detalleRecurso(String recursoId) {
        for (final cancion in _catalogo) {
            for (final v in cancion['variantes'] as List) {
                final variante = v as Map;
                if (variante['recurso_audio_id'] != recursoId) continue;
                return {'recurso_audio_id': recursoId, 'tipo': variante['tipo'], 'disponible': true,
                        'cancion': {'id': cancion['id'], 'titulo': cancion['titulo'], 'duracion_ms': cancion['duracion_ms'],
                                    'artistas': cancion['artistas']}};
            }
        }
        throw const ApiException(codigo: 'NO_ENCONTRADO', mensaje: 'El recurso de audio solicitado no existe.', estadoHttp: 404);
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
/// Cola individual en memoria con las reglas del contrato 5.1: versión, avance único y
/// elementos que solo se mueven mientras están pendientes.
class MiColaSimulada {
    final _colas = <String, _ColaSimulada>{};

    dynamic atender(String operacion, Map<String, String>? query, Map<String, dynamic> datos, String usuarioId) {
        final cola = _colas.putIfAbsent(usuarioId, () => _ColaSimulada(usuarioId));
        final partes = operacion.split(' ');
        final ruta = partes[1].split('/');
        final elementoId = ruta.length > 3 ? ruta[3] : null;

        switch ((partes[0], ruta.length > 2 ? ruta[2] : '', ruta.length > 4 ? ruta[4] : '')) {
            case ('GET', '', ''):
                return cola.estado();
            case ('POST', 'elementos', ''):
                return cola.agregar(datos['recurso_audio_id'] as String);
            case ('PATCH', 'elementos', ''):
                return cola.reordenar(elementoId!, datos['nueva_posicion'] as int, datos['version_esperada'] as int);
            case ('DELETE', 'elementos', ''):
                return cola.retirar(elementoId!, int.parse(query?['version_esperada'] ?? '-1'));
            case ('POST', 'reproduccion', ''):
                return cola.reproduccion(datos['accion'] as String, datos['elemento_id'] as String?, datos['posicion_ms'] as int?);
            case ('POST', 'elementos', 'terminada'):
                return cola.terminada(elementoId!);
        }
        throw ApiException(codigo: 'NO_ENCONTRADO', mensaje: 'El modo simulado no tiene esta operación: $operacion', estadoHttp: 404);
    }
}

class _ColaSimulada {
    _ColaSimulada(this.usuarioId);

    final String usuarioId;
    final id = nuevoUuid();
    final _elementos = <Map<String, dynamic>>[];
    int version = 0;
    int _orden = 0;

    Iterable<Map<String, dynamic>> get _pendientes => _elementos.where((e) => e['estado'] == 'pendiente');

    Map<String, dynamic>? get _actual {
        for (final e in _elementos) {
            if (e['estado'] == 'reproduciendo' || e['estado'] == 'pausada') return e;
        }
        return null;
    }

    Map<String, dynamic> _publico(Map<String, dynamic> e) => {
        'id': e['id'], 'recurso_audio_id': e['recurso_audio_id'], 'agregado_por': usuarioId, 'orden': e['orden'],
        'estado': e['estado'], 'agregado_en': e['agregado_en'],
    };

    Map<String, dynamic> _reproduccion() {
        final actual = _actual;
        return {
            'cola_id': id, 'version': version, 'elemento_id': actual?['id'], 'recurso_audio_id': actual?['recurso_audio_id'],
            'estado': actual?['estado'] ?? 'detenida', 'posicion_base_ms': actual?['posicion_base_ms'] ?? 0,
            'referencia_en': actual == null ? null : _iso(DateTime.now()), 'duracion_ms': null,
        };
    }

    Map<String, dynamic> estado() {
        final actual = _actual;
        return {
            'id': id, 'modalidad': 'individual', 'version': version,
            'actual': actual == null ? null : {'elemento': _publico(actual), 'reproduccion': _reproduccion()},
            'pendientes': [for (final e in _pendientes) _publico(e)],
        };
    }

    Map<String, dynamic> agregar(String recursoId) {
        _elementos.add({'id': nuevoUuid(), 'recurso_audio_id': recursoId, 'orden': ++_orden, 'estado': 'pendiente',
                        'agregado_en': _iso(DateTime.now()), 'posicion_base_ms': 0});
        version++;
        return estado();
    }

    Map<String, dynamic> _pendiente(String elementoId, int versionEsperada) {
        if (versionEsperada != version) {
            throw ApiException(codigo: 'VERSION_OBSOLETA', mensaje: 'La cola cambió. Recarga para ver la actual.',
                               detalles: {'version_actual': version}, estadoHttp: 409);
        }
        final elemento = _elementos.where((e) => e['id'] == elementoId).firstOrNull;
        if (elemento == null) {
            throw const ApiException(codigo: 'NO_ENCONTRADO', mensaje: 'Esa canción ya no está en la cola.', estadoHttp: 404);
        }
        if (elemento['estado'] != 'pendiente') {
            throw const ApiException(codigo: 'ELEMENTO_NO_PENDIENTE', mensaje: 'Solo se pueden mover o quitar canciones que no han sonado.',
                                     estadoHttp: 409);
        }
        return elemento;
    }

    Map<String, dynamic> reordenar(String elementoId, int nuevaPosicion, int versionEsperada) {
        final elemento = _pendiente(elementoId, versionEsperada);
        final pendientes = _pendientes.toList();
        if (nuevaPosicion < 1 || nuevaPosicion > pendientes.length) {
            throw const ApiException(codigo: 'DATOS_INVALIDOS', mensaje: 'Esa posición no existe en la cola.', estadoHttp: 400);
        }
        final ordenes = [for (final e in pendientes) e['orden'] as int];
        pendientes
            ..remove(elemento)
            ..insert(nuevaPosicion - 1, elemento);
        for (var i = 0; i < pendientes.length; i++) {
            pendientes[i]['orden'] = ordenes[i];
        }
        _elementos.sort((a, b) => (a['orden'] as int).compareTo(b['orden'] as int));
        version++;
        return estado();
    }

    Map<String, dynamic> retirar(String elementoId, int versionEsperada) {
        _pendiente(elementoId, versionEsperada)['estado'] = 'retirada';
        version++;
        return estado();
    }

    void _iniciarSiguiente() {
        final siguiente = _pendientes.firstOrNull;
        if (siguiente == null) return;
        siguiente['estado'] = 'reproduciendo';
        siguiente['posicion_base_ms'] = 0;
    }

    Map<String, dynamic> reproduccion(String accion, String? elementoId, int? posicionMs) {
        final actual = _actual;
        if (accion == 'iniciar') {
            if (actual != null) {
                throw const ApiException(codigo: 'REPRODUCCION_EN_CURSO', mensaje: 'Ya hay una canción sonando.', estadoHttp: 409);
            }
            if (_pendientes.isEmpty) {
                throw const ApiException(codigo: 'COLA_VACIA', mensaje: 'Agrega una canción a la cola para empezar.', estadoHttp: 409);
            }
            _iniciarSiguiente();
        } else {
            if (actual == null || actual['id'] != elementoId) {
                throw const ApiException(codigo: 'ELEMENTO_NO_ACTUAL', mensaje: 'Esa canción ya no es la que está sonando.', estadoHttp: 409);
            }
            switch (accion) {
                case 'pausar':
                    actual['estado'] = 'pausada';
                case 'reanudar':
                    actual['estado'] = 'reproduciendo';
                case 'buscar':
                    actual['posicion_base_ms'] = posicionMs ?? 0;
                case 'saltar':
                    actual['estado'] = 'omitida';
                    _iniciarSiguiente();
            }
        }
        version++;
        return _reproduccion();
    }

    Map<String, dynamic> terminada(String elementoId) {
        final actual = _actual;
        if (actual == null || actual['id'] != elementoId) return _reproduccion();
        actual['estado'] = 'reproducida';
        _iniciarSiguiente();
        version++;
        return _reproduccion();
    }
}
