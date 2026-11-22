// End-to-end run of T-55 against the real party and queue services (see README):
// flutter test integration_test/party_e2e_test.dart -d linux \
//   --dart-define=TOKEN_ANFITRION=... --dart-define=TOKEN_MIEMBRO=...
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:media_kit/media_kit.dart';
import 'package:partyears_frontend/core/network/api_client.dart';
import 'package:partyears_frontend/core/network/api_config.dart';
import 'package:partyears_frontend/core/network/token_store.dart';
import 'package:partyears_frontend/core/network/ws_client.dart';
import 'package:partyears_frontend/features/party/data/cola_service.dart';
import 'package:partyears_frontend/features/party/data/party_models.dart';
import 'package:partyears_frontend/features/party/data/party_service.dart';
import 'package:partyears_frontend/features/party/sesion_party.dart';
import 'package:partyears_frontend/features/player/reproductor.dart';

const _tokenAnfitrion = String.fromEnvironment('TOKEN_ANFITRION');
const _tokenMiembro = String.fromEnvironment('TOKEN_MIEMBRO');
final _config = ApiConfig.desdeHost('127.0.0.1');

class _Tokens implements TokenStore {
    _Tokens(this.token);

    final String token;

    @override
    Future<TokensGuardados?> leer() async =>
        TokensGuardados(tokenAcceso: token, tokenRenovacion: 'x', expiraEn: DateTime.now().toUtc().add(const Duration(hours: 1)));
    @override
    Future<void> guardar(TokensGuardados tokens) async {}
    @override
    Future<void> borrar() async {}
}

/// Stands in for music (T-16 does not exist yet): every resource is a 60 s tone with ranges.
Future<HttpServer> _musicFalso() async {
    const muestras = 44100, segundos = 60;
    final datos = ByteData(44 + segundos * muestras * 2);
    void texto(int o, String t) => t.codeUnits.asMap().forEach((i, c) => datos.setUint8(o + i, c));
    texto(0, 'RIFF'); datos.setUint32(4, datos.lengthInBytes - 8, Endian.little); texto(8, 'WAVEfmt ');
    datos.setUint32(16, 16, Endian.little); datos.setUint16(20, 1, Endian.little); datos.setUint16(22, 1, Endian.little);
    datos.setUint32(24, muestras, Endian.little); datos.setUint32(28, muestras * 2, Endian.little);
    datos.setUint16(32, 2, Endian.little); datos.setUint16(34, 16, Endian.little); texto(36, 'data');
    datos.setUint32(40, segundos * muestras * 2, Endian.little);
    for (var i = 0; i < segundos * muestras; i++) {
        datos.setInt16(44 + i * 2, (sin(2 * pi * 440 * i / muestras) * 8000).toInt(), Endian.little);
    }
    final wav = datos.buffer.asUint8List();
    final servidor = await HttpServer.bind(InternetAddress.loopbackIPv4, 8002);
    servidor.listen((p) async {
        final r = p.response;
        if (!(p.headers.value('authorization') ?? '').startsWith('Bearer ')) {
            r.statusCode = 401;
        } else {
            final m = RegExp(r'bytes=(\d+)-(\d*)').firstMatch(p.headers.value('range') ?? '');
            final inicio = m == null ? 0 : int.parse(m.group(1)!);
            final fin = (m == null || m.group(2)!.isEmpty) ? wav.length - 1 : int.parse(m.group(2)!);
            r.headers.set('Accept-Ranges', 'bytes');
            r.headers.contentType = ContentType('audio', 'wav');
            if (m != null) {
                r.statusCode = 206;
                r.headers.set('Content-Range', 'bytes $inicio-$fin/${wav.length}');
            }
            r.contentLength = fin - inicio + 1;
            r.add(wav.sublist(inicio, fin + 1));
        }
        await r.close();
    });
    return servidor;
}

SesionParty _sesion(ApiClient api, String token, PartyActual party) {
    final reproductor = ReproductorMediaKit();
    reproductor.volumen(0);
    return SesionParty(
        party: party,
        partyService: PartyService(api),
        colaService: ColaService(api),
        ws: WsClientReal(api: api, config: _config, servicio: Servicio.party, recursoId: party.id, usaLatido: true),
        reproductor: reproductor,
        abrirAudio: (recurso, desde) => reproductor.abrir(_config.rest(Servicio.music, '/recursos/$recurso/audio'),
                                                          cabeceras: {'Authorization': 'Bearer $token'}, desde: desde),
        usuarioId: usuarioDelToken(token),
    );
}

Future<void> _esperarHasta(bool Function() condicion, {Duration limite = const Duration(seconds: 10)}) async {
    final fin = DateTime.now().add(limite);
    while (!condicion()) {
        if (DateTime.now().isAfter(fin)) throw StateError('no se cumplió a tiempo');
        await Future<void>.delayed(const Duration(milliseconds: 100));
    }
}

void main() {
    IntegrationTestWidgetsFlutterBinding.ensureInitialized();
    MediaKit.ensureInitialized();

    testWidgets('dos clientes suenan sincronizados, incluido el que llega tarde', (_) async {
        final music = await _musicFalso();
        final apiAnfitrion = HttpApiClient(config: _config, tokens: _Tokens(_tokenAnfitrion));
        final apiMiembro = HttpApiClient(config: _config, tokens: _Tokens(_tokenMiembro));

        final party = await PartyService(apiAnfitrion).crear('E2E T-55');
        for (var i = 0; i < 2; i++) {
            await apiAnfitrion.post(Servicio.queue, '/parties/${party.id}/cola/elementos',
                                    cuerpo: {'recurso_audio_id': '00000000-0000-4000-8000-00000000000$i'}, idempotente: true);
        }

        final anfitrion = _sesion(apiAnfitrion, _tokenAnfitrion, party);
        await anfitrion.iniciar();
        await _esperarHasta(() => anfitrion.cola.pendientes.length == 2);
        await anfitrion.controlar('iniciar');
        await _esperarHasta(() => anfitrion.reproductor.posicion > const Duration(seconds: 3));

        // The member joins while the song is already playing (SRS 1.3, late joiner).
        final unida = await PartyService(apiMiembro).unirse(party.codigo!);
        final miembro = _sesion(apiMiembro, _tokenMiembro, unida);
        await miembro.iniciar();
        await _esperarHasta(() => miembro.reproductor.posicion > const Duration(seconds: 3));
        await Future<void>.delayed(const Duration(seconds: 4));

        final diferencias = <int>[];
        for (var i = 0; i < 10; i++) {
            diferencias.add((anfitrion.reproductor.posicion - miembro.reproductor.posicion).inMilliseconds.abs());
            await Future<void>.delayed(const Duration(milliseconds: 300));
        }
        diferencias.sort();
        // ignore: avoid_print
        print('diferencia entre clientes (ms): $diferencias, saltos del miembro: ${miembro.sincronizador.correcciones}');
        expect(diferencias.last, lessThan(200), reason: 'contrato 5.3: límite de 200 ms');
        expect(miembro.party.miembros.length, 2);
        expect(miembro.esAnfitrion, isFalse);

        await anfitrion.controlar('pausar');
        await _esperarHasta(() => miembro.reproduccion.estado == 'pausada');
        await Future<void>.delayed(const Duration(milliseconds: 500));
        final pausaA = anfitrion.reproductor.posicion, pausaM = miembro.reproductor.posicion;
        expect((pausaA - pausaM).inMilliseconds.abs(), lessThan(200));

        final primera = anfitrion.reproduccion.elementoId;
        await anfitrion.controlar('reanudar');
        await _esperarHasta(() => miembro.reproduccion.sonando);
        await anfitrion.controlar('saltar');
        await _esperarHasta(() => miembro.reproduccion.elementoId != primera && miembro.cola.pendientes.isEmpty);
        expect(miembro.reproduccion.elementoId, anfitrion.reproduccion.elementoId);
        expect(miembro.conexion, WsEstado.conectado);

        // T-56: the host grants "add songs", the member adds one and the host sees it live.
        final yo = miembro.party.miembro(miembro.usuarioId)!;
        expect(await miembro.agregar('00000000-0000-4000-8000-000000000009'),
               'Ya no tienes permiso para agregar canciones a esta party');
        expect(await anfitrion.cambiarPermisos(yo, puedeAportar: true, puedeModificarCola: false),
               'Permisos otorgados correctamente');
        await _esperarHasta(() => miembro.puedeAportar);
        expect(await miembro.agregar('00000000-0000-4000-8000-000000000009'), 'Canción agregada a la cola');
        await _esperarHasta(() => anfitrion.cola.pendientes.any((e) => e.recursoAudioId.endsWith('9')));

        final conPermiso = miembro.party.miembro(miembro.usuarioId)!;
        expect(await anfitrion.cambiarPermisos(conPermiso, puedeAportar: false, puedeModificarCola: false),
               'Permisos retirados correctamente');
        await _esperarHasta(() => !miembro.puedeAportar);
        expect(await miembro.agregar('00000000-0000-4000-8000-000000000008'),
               'Ya no tienes permiso para agregar canciones a esta party');

        await miembro.cerrar();
        await anfitrion.cerrar();
        await music.close(force: true);
        // ignore: avoid_print
        print('PARTY_ID ${party.id}');
    }, skip: _tokenAnfitrion.isEmpty);
}
