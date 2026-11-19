import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:partyears_frontend/core/network/api_client.dart';
import 'package:partyears_frontend/core/network/api_config.dart';
import 'package:partyears_frontend/core/network/api_exception.dart';
import 'package:partyears_frontend/core/network/token_store.dart';

http.Response _json(int estado, Object cuerpo) => http.Response.bytes(utf8.encode(jsonEncode(cuerpo)), estado, headers: {'content-type': 'application/json'},);

String _expira() => DateTime.now().toUtc().add(const Duration(minutes: 5)).toIso8601String();

Future<HttpApiClient> _crear(Future<http.Response> Function(http.Request) manejador, {TokenStoreMemoria? tokens,}) async {
    final almacen = tokens ?? TokenStoreMemoria();
    await almacen.guardar(TokensGuardados(tokenAcceso: 'viejo', tokenRenovacion: 'r1', expiraEn: DateTime.now().toUtc().add(const Duration(minutes: 5)),));
    return HttpApiClient(config: ApiConfig.desdeHost('servidor'), tokens: almacen, cliente: MockClient(manejador),);
}

void main() {
    test('muestra el mensaje del backend con los acentos intactos', () async {
        final api = await _crear((_) async => _json(409, {'codigo': 'PARTY_LLENA', 'mensaje': 'La party ya tiene 20 personas conectadas. ¡Qué lástima!', 'detalles': null,}));
        await expectLater(api.post(Servicio.party, '/parties/unirse', cuerpo: {'codigo': 'K7Q2ZP'}, idempotente: true),
                          throwsA(isA<ApiException>().having((e) => e.codigo, 'codigo', 'PARTY_LLENA').having((e) => e.mensaje, 'mensaje', contains('¡Qué lástima!'))),);
    });

    test('renueva el token una sola vez ante TOKEN_INVALIDO y reintenta', () async {
        final tokens = TokenStoreMemoria();
        final llamadas = <String>[];
        final api = await _crear((req) async {llamadas.add('${req.method} ${req.url.path} ${req.headers['authorization'] ?? '-'}');

        if (req.url.path.endsWith('/auth/renovar')) {
            return _json(200, {
                'token_acceso': 'nuevo',
                'token_renovacion': 'r2',
                'expira_en': _expira(),
                'usuario': {'id': 'u1', 'nombre_usuario': 'mariana'},
            });
        }

        if (req.headers['authorization'] == 'Bearer viejo') {
            return _json(401, {
                'codigo': 'TOKEN_INVALIDO',
                'mensaje': 'Sesión vencida.',
                'detalles': null,
            });
        }
        
        return _json(200, {'resultados': [], 'pagina': 1, 'total_paginas': 0, 'total': 0});}, tokens: tokens);

        final r = await api.get(Servicio.music, '/canciones') as Map<String, dynamic>;

        expect(r['total'], 0);
        expect(llamadas, ['GET /api/v1/music/canciones Bearer viejo', 'POST /api/v1/auth/renovar -', 'GET /api/v1/music/canciones Bearer nuevo',]);
        expect((await tokens.leer())!.tokenRenovacion, 'r2');
  });

    test('manda Idempotency-Key y la devuelve en el error para reintentar', () async {
        String? enviada;

        final api = await _crear((req) async {
            enviada = req.headers['idempotency-key'];

            return _json(503, {'codigo': 'SERVICIO_NO_DISPONIBLE', 'mensaje': 'Intenta de nuevo.', 'detalles': null,});
        });

        try {
            await api.post(Servicio.queue, '/parties/p1/cola/reproduccion', cuerpo: {'accion': 'pausar'}, idempotente: true);
            fail('debió lanzar ApiException');
        } on ApiException catch (e) {
            expect(enviada, isNotNull);
            expect(e.idempotencyKey, enviada);
        }
    });
}