import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:media_kit/media_kit.dart';
import 'package:partyears_frontend/features/player/reproductor.dart';

const _token = 'Bearer prueba';

/// WAV mono de 16 bits: un tono de 440 Hz durante [segundos].
Uint8List _wav(int segundos) {
    const muestras = 44100;
    final datos = ByteData(segundos * muestras * 2);
    for (var i = 0; i < segundos * muestras; i++) {
        datos.setInt16(i * 2, (sin(2 * pi * 440 * i / muestras) * 8000).toInt(), Endian.little);
    }
    final cabecera = ByteData(44);
    void texto(int o, String t) => t.codeUnits.asMap().forEach((i, c) => cabecera.setUint8(o + i, c));
    texto(0, 'RIFF');
    cabecera.setUint32(4, 36 + datos.lengthInBytes, Endian.little);
    texto(8, 'WAVEfmt ');
    cabecera.setUint32(16, 16, Endian.little);
    cabecera.setUint16(20, 1, Endian.little);
    cabecera.setUint16(22, 1, Endian.little);
    cabecera.setUint32(24, muestras, Endian.little);
    cabecera.setUint32(28, muestras * 2, Endian.little);
    cabecera.setUint16(32, 2, Endian.little);
    cabecera.setUint16(34, 16, Endian.little);
    texto(36, 'data');
    cabecera.setUint32(40, datos.lengthInBytes, Endian.little);
    return Uint8List.fromList([...cabecera.buffer.asUint8List(), ...datos.buffer.asUint8List()]);
}

/// Servidor como el de music (contrato 3.3): exige el token y responde rangos con 206.
class _ServidorAudio {
    final archivos = {'/larga': _wav(20), '/corta': _wav(2)};
    final cabecerasRecibidas = <String?>[];
    late final HttpServer _servidor;

    Future<void> iniciar() async {
        _servidor = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
        _servidor.listen(_responder);
    }

    Uri url(String ruta) => Uri.parse('http://127.0.0.1:${_servidor.port}$ruta');

    Future<void> _responder(HttpRequest peticion) async {
        final r = peticion.response;
        cabecerasRecibidas.add(peticion.headers.value('authorization'));
        final archivo = archivos[peticion.uri.path];

        if (peticion.headers.value('authorization') != _token) {
            r.statusCode = 401;
        } else if (archivo == null) {
            r.statusCode = 410;
        } else {
            final rango = RegExp(r'bytes=(\d+)-(\d*)').firstMatch(peticion.headers.value('range') ?? '');
            final inicio = rango == null ? 0 : int.parse(rango.group(1)!);
            final fin = (rango == null || rango.group(2)!.isEmpty) ? archivo.length - 1 : int.parse(rango.group(2)!);
            r.headers.set('Accept-Ranges', 'bytes');
            r.headers.contentType = ContentType('audio', 'wav');
            if (rango != null) {
                r.statusCode = 206;
                r.headers.set('Content-Range', 'bytes $inicio-$fin/${archivo.length}');
            }
            r.contentLength = fin - inicio + 1;
            r.add(archivo.sublist(inicio, fin + 1));
        }
        await r.close();
    }

    Future<void> cerrar() => _servidor.close(force: true);
}

Future<void> _esperar(Duration tiempo) => Future<void>.delayed(tiempo);

void main() {
    IntegrationTestWidgetsFlutterBinding.ensureInitialized();
    MediaKit.ensureInitialized();

    late _ServidorAudio servidor;
    late ReproductorMediaKit reproductor;
    late List<String> errores;

    setUp(() async {
        servidor = _ServidorAudio();
        await servidor.iniciar();
        reproductor = ReproductorMediaKit();
        errores = [];
        reproductor.errores.listen(errores.add);
        await reproductor.volumen(0);
    });

    tearDown(() async {
        await reproductor.cerrar();
        await servidor.cerrar();
    });

    Future<void> abrir(String ruta, {Duration desde = Duration.zero, String token = _token}) =>
        reproductor.abrir(servidor.url(ruta), cabeceras: {'Authorization': token}, desde: desde);

    testWidgets('reproduce desde el servidor mandando el token en la cabecera', (_) async {
        await abrir('/larga');
        expect(reproductor.duracion.inSeconds, 20);
        await reproductor.reproducir();
        await _esperar(const Duration(milliseconds: 1500));
        expect(reproductor.posicion.inMilliseconds, greaterThan(800));
        expect(servidor.cabecerasRecibidas, everyElement(_token));
        expect(errores, isEmpty);
    });

    testWidgets('pausar detiene la posición', (_) async {
        await abrir('/larga');
        await reproductor.reproducir();
        await _esperar(const Duration(milliseconds: 800));
        await reproductor.pausar();
        // The position is refreshed every few tens of ms; read it once it settles.
        await _esperar(const Duration(milliseconds: 200));
        final pausada = reproductor.posicion;
        await _esperar(const Duration(milliseconds: 700));
        expect((reproductor.posicion - pausada).inMilliseconds.abs(), lessThan(50));
    });

    testWidgets('irA salta a la posición pedida con rangos HTTP', (_) async {
        await abrir('/larga');
        await reproductor.irA(const Duration(seconds: 12));
        await _esperar(const Duration(milliseconds: 500));
        expect((reproductor.posicion.inMilliseconds - 12000).abs(), lessThan(200));
    });

    testWidgets('abrir desde una posición empieza ahí', (_) async {
        await abrir('/larga', desde: const Duration(seconds: 7));
        await _esperar(const Duration(milliseconds: 300));
        expect((reproductor.posicion.inMilliseconds - 7000).abs(), lessThan(200));
    });

    testWidgets('avisa al terminar la canción', (_) async {
        final fin = reproductor.terminado.first;
        await abrir('/corta');
        await reproductor.reproducir();
        await fin.timeout(const Duration(seconds: 6));
    });

    testWidgets('audio que no existe da un aviso y no queda sonando', (_) async {
        await abrir('/falta');
        await reproductor.reproducir();
        await _esperar(const Duration(milliseconds: 500));
        expect(errores, [ReproductorMediaKit.mensajeError]);
        expect(reproductor.posicion, Duration.zero);
    });

    testWidgets('token rechazado da un aviso', (_) async {
        await abrir('/larga', token: 'Bearer otro');
        expect(errores, [ReproductorMediaKit.mensajeError]);
    });

    testWidgets('reintentar vuelve a abrir en la misma posición', (_) async {
        await abrir('/larga', desde: const Duration(seconds: 5));
        await reproductor.reintentar();
        await _esperar(const Duration(milliseconds: 300));
        expect((reproductor.posicion.inMilliseconds - 5000).abs(), lessThan(300));
        expect(errores, isEmpty);
    });
}
