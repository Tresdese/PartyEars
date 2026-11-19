import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'api_config.dart';
import 'api_exception.dart';
import 'token_store.dart';
import 'uuid.dart';

abstract class ApiClient {
    Future<dynamic> enviar(String metodo, Servicio servicio, String ruta, 
                           {Map<String, String>? query, Object? cuerpo, bool autenticado = true, bool idempotente = false, String? idempotencyKey,}
    );
    Future<TokensGuardados> tokensVigentes();
    Future<TokensGuardados> renovarSesion({bool forzar = true});
    Future<bool> haySesion();
    Future<void> cerrarSesion();

    Stream<void> get sesionExpirada;

    void cerrar();
}

extension ApiClientAtajos on ApiClient {
    Future<dynamic> get(Servicio servicio, String ruta, {Map<String, String>? query, bool autenticado = true,
    }) => enviar('GET', servicio, ruta, query: query, autenticado: autenticado);

    Future<dynamic> post(Servicio servicio,String ruta, {Object? cuerpo, bool autenticado = true, bool idempotente = false, String? idempotencyKey,
    }) => enviar('POST', servicio, ruta, cuerpo: cuerpo, autenticado: autenticado, idempotente: idempotente, idempotencyKey: idempotencyKey);

    Future<dynamic> put(Servicio servicio, String ruta, {Object? cuerpo, bool idempotente = false, String? idempotencyKey,
    }) => enviar('PUT', servicio, ruta, cuerpo: cuerpo, idempotente: idempotente, idempotencyKey: idempotencyKey);

    Future<dynamic> patch(Servicio servicio, String ruta, {Object? cuerpo, bool idempotente = false, String? idempotencyKey,
    }) => enviar('PATCH', servicio, ruta, cuerpo: cuerpo, idempotente: idempotente, idempotencyKey: idempotencyKey);

    Future<dynamic> delete(Servicio servicio, String ruta, {Map<String, String>? query, bool idempotente = false, String? idempotencyKey,
    }) => enviar('DELETE', servicio, ruta, query: query, idempotente: idempotente, idempotencyKey: idempotencyKey);
}

class HttpApiClient implements ApiClient {
    HttpApiClient({required this.config, required this.tokens, http.Client? cliente, this.tiempoLimite = const Duration(seconds: 15),})
    : _http = cliente ?? http.Client();

    ApiConfig config;

    final TokenStore tokens;
    final Duration tiempoLimite;
    final http.Client _http;
    final _sesionExpiradaCtrl = StreamController<void>.broadcast();

    Future<TokensGuardados>? _renovando;

    @override
    Stream<void> get sesionExpirada => _sesionExpiradaCtrl.stream;

    @override
    Future<dynamic> enviar(String metodo, Servicio servicio, String ruta, 
                           {Map<String, String>? query, Object? cuerpo, bool autenticado = true, bool idempotente = false, String? idempotencyKey, }) 
                           async {
        final clave = idempotente ? (idempotencyKey ?? nuevoUuid()) : null;
        
        try {
            final resultado = await _conSesion( autenticado, (token) => _enviarUnaVez(metodo, servicio, ruta, query: query, cuerpo: cuerpo, token: token, idempotencyKey: clave,),);
            
            if (servicio == Servicio.auth && ruta == '/login' && resultado is Map<String, dynamic>) {
                await tokens.guardar(TokensGuardados.desdeJson(resultado));
            }
            
            return resultado;
        } on ApiException catch (e) {
            throw clave == null ? e : e.conClave(clave);
        }
    }

    Future<dynamic> _conSesion(bool autenticado, Future<dynamic> Function(String? token) accion,) async {
        if (!autenticado) return accion(null);
        
        final actuales = await tokensVigentes();
        
        try {
            return await accion(actuales.tokenAcceso);
        } on ApiException catch (e) {
            if (e.estadoHttp != 401 || e.codigo != 'TOKEN_INVALIDO') rethrow;
        }
        
        final nuevos = await renovarSesion();
        
        try {
            return await accion(nuevos.tokenAcceso);
        } on ApiException catch (e) {
            if (e.estadoHttp == 401) await _expirarSesion();
            
            rethrow;
        }
    }

    Future<dynamic> _enviarUnaVez(String metodo, Servicio servicio, String ruta, 
                                  {Map<String, String>? query, Object? cuerpo, String? token, String? idempotencyKey, }) async {
        final peticion = http.Request(metodo, config.rest(servicio, ruta, query));
        peticion.headers['Accept'] = 'application/json';
        
        if (cuerpo != null) {
            peticion.headers['Content-Type'] = 'application/json; charset=utf-8';
            peticion.bodyBytes = utf8.encode(jsonEncode(cuerpo));
        }
        
        if (token != null) peticion.headers['Authorization'] = 'Bearer $token';
        
        if (idempotencyKey != null) {
            peticion.headers['Idempotency-Key'] = idempotencyKey;
        }

        final http.Response respuesta;
    
        try {
            final flujo = await _http.send(peticion).timeout(tiempoLimite);
            respuesta = await http.Response.fromStream(flujo).timeout(tiempoLimite);
        } on TimeoutException {
            throw const ApiException(codigo: ApiException.tiempoAgotado, mensaje: 'El servidor tardó demasiado en responder.',);
        } on Exception {
            throw const ApiException(codigo: ApiException.sinConexion, mensaje: 'No se pudo conectar con el servidor. Revisa tu conexión.',);
        }

        Object? json;
        
        if (respuesta.bodyBytes.isNotEmpty) {
            try {
                json = jsonDecode(utf8.decode(respuesta.bodyBytes));
            } on FormatException {
                json = null;
            }
        }

        if (respuesta.statusCode >= 200 && respuesta.statusCode < 300) {
            if (respuesta.statusCode == 204 || respuesta.bodyBytes.isEmpty) {
                return null;
            }
            
            if (json == null) {
                throw ApiException(codigo: ApiException.respuestaInvalida, mensaje: 'El servidor mandó una respuesta que no se pudo leer.', estadoHttp: respuesta.statusCode,);
            }
            
            return json;
        }
    
        throw ApiException.desdeRespuesta(respuesta.statusCode, json);
    }

    @override
    Future<TokensGuardados> tokensVigentes() async {
        final t = await tokens.leer();
        
        if (t == null) {
            await _expirarSesion();
            throw _errorSesionExpirada();
        }

        if (t.tiempoRestante < const Duration(seconds: 30)) {
            return renovarSesion(forzar: false);
        }

        return t;
    }

    @override
    Future<TokensGuardados> renovarSesion({bool forzar = true}) {
        return _renovando ??= _renovarInterno(forzar).whenComplete(() => _renovando = null);
    }

    Future<TokensGuardados> _renovarInterno(bool forzar) async {
        final actuales = await tokens.leer();
        
        if (actuales == null) {
            await _expirarSesion();
            throw _errorSesionExpirada();
        }

        if (!forzar && actuales.tiempoRestante > const Duration(seconds: 30)) {
            return actuales; 
        }

        try {
            final respuesta = await _enviarUnaVez('POST', Servicio.auth, '/renovar', cuerpo: {'token_renovacion': actuales.tokenRenovacion},);
            final nuevos = TokensGuardados.desdeJson(respuesta as Map<String, dynamic>);
            await tokens.guardar(nuevos);

            return nuevos;
        } on ApiException catch (e) {
            if (e.estadoHttp == 401 || e.estadoHttp == 403) {
                await _expirarSesion();
                throw _errorSesionExpirada();
            }
        
            rethrow;
        }
    }

    @override
    Future<bool> haySesion() async => (await tokens.leer()) != null;

    @override
    Future<void> cerrarSesion() async {
        final t = await tokens.leer();

        try {
            if (t != null) {
                await enviar('POST', Servicio.auth, '/logout', cuerpo: {'token_renovacion': t.tokenRenovacion},);
            }
        } on ApiException {
            // Ignorar errores al cerrar sesión, ya que el objetivo es borrar los tokens locales.
        } finally {
            await tokens.borrar();
        }
    }

    Future<void> _expirarSesion() async {
        await tokens.borrar();
        
        if (!_sesionExpiradaCtrl.isClosed) _sesionExpiradaCtrl.add(null);
    }

    ApiException _errorSesionExpirada() => const ApiException(codigo: ApiException.sesionExpirada, mensaje: 'Tu sesión terminó. Inicia sesión de nuevo.', estadoHttp: 401,);

    @override
    void cerrar() {
        _http.close();
        _sesionExpiradaCtrl.close();
    }
}