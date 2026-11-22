import 'package:flutter_test/flutter_test.dart';
import 'package:partyears_frontend/features/party/data/cola_models.dart';
import 'package:partyears_frontend/features/party/sincronizacion.dart';

import 'falsos.dart';

EstadoReproduccion estado(String tipo, {int base = 0, DateTime? referencia, String elemento = 'e1', int version = 1}) =>
    EstadoReproduccion(version: version, estado: tipo, posicionBaseMs: base, elementoId: elemento,
                       recursoAudioId: 'r-$elemento', referenciaEn: referencia ?? DateTime.now().toUtc());

void main() {
    group('RelojServidor', () {
        test('calcula el desfase con la fórmula del contrato 7.4', () {
            final reloj = RelojServidor();
            reloj.registrar(1000, 6050, 1100);
            expect(reloj.ahora().difference(DateTime.now().toUtc()).inMilliseconds, closeTo(5000, 20));
        });

        test('se queda con la medición de menor ida y vuelta', () {
            final reloj = RelojServidor();
            reloj.registrar(1000, 2000, 1400);
            reloj.registrar(1000, 3050, 1100);
            reloj.registrar(1000, 9000, 1300);
            expect(reloj.ahora().difference(DateTime.now().toUtc()).inMilliseconds, closeTo(2000, 20));
        });
    });

    group('posicionEsperada', () {
        final referencia = DateTime.utc(2026, 11, 22, 12);

        test('sonando: base más lo transcurrido desde la referencia', () {
            final e = estado('reproduciendo', base: 45000, referencia: referencia);
            expect(posicionEsperada(e, referencia.add(const Duration(seconds: 3))), const Duration(milliseconds: 48000));
        });

        test('antes de la referencia todavía no avanza', () {
            final e = estado('reproduciendo', base: 1000, referencia: referencia);
            expect(posicionEsperada(e, referencia.subtract(const Duration(seconds: 1))), const Duration(milliseconds: 1000));
        });

        test('en pausa es la base', () {
            final e = estado('pausada', base: 30000, referencia: referencia);
            expect(posicionEsperada(e, referencia.add(const Duration(minutes: 1))), const Duration(milliseconds: 30000));
        });
    });

    group('Sincronizador', () {
        late ReproductorFalso reproductor;
        late List<String> abiertos;
        late Sincronizador sincronizador;

        setUp(() {
            reproductor = ReproductorFalso();
            abiertos = [];
            sincronizador = Sincronizador(reproductor: reproductor, reloj: RelojServidor(),
                                          abrirAudio: (recurso, desde) async => abiertos.add('$recurso ${desde.inSeconds}'),
                                          periodo: const Duration(milliseconds: 50));
        });

        tearDown(() => sincronizador.cerrar());

        test('con referencia futura se coloca, espera y arranca en ese instante', () async {
            final referencia = DateTime.now().toUtc().add(const Duration(milliseconds: 300));
            await sincronizador.aplicar(estado('reproduciendo', base: 5000, referencia: referencia));
            expect(reproductor.llamadas, ['pausar', 'irA 5000']);
            await Future<void>.delayed(const Duration(milliseconds: 400));
            expect(reproductor.llamadas.last, 'reproducir');
        });

        test('quien llega tarde abre en la posición actual de la party', () async {
            final referencia = DateTime.now().toUtc().subtract(const Duration(seconds: 20));
            await sincronizador.aplicar(estado('reproduciendo', base: 10000, referencia: referencia));
            expect(abiertos, ['r-e1 30']);
            expect(reproductor.llamadas.last, 'reproducir');
        });

        test('la misma canción no se vuelve a abrir', () async {
            await sincronizador.aplicar(estado('pausada', base: 1000));
            await sincronizador.aplicar(estado('pausada', base: 2000, version: 2));
            expect(abiertos.length, 1);
            expect(reproductor.llamadas.last, 'irA 2000');
        });

        test('detenida pausa sin abrir nada', () async {
            await sincronizador.aplicar(const EstadoReproduccion(version: 3, estado: 'detenida', posicionBaseMs: 0));
            expect(abiertos, isEmpty);
            expect(reproductor.llamadas, ['pausar']);
        });

        test('salta si se aleja más de 200 ms', () async {
            final referencia = DateTime.now().toUtc().subtract(const Duration(seconds: 5));
            await sincronizador.aplicar(estado('reproduciendo', referencia: referencia));
            reproductor.posicionActual = const Duration(seconds: 1);
            await sincronizador.revisar();
            expect(sincronizador.correcciones, 1);
            expect(reproductor.llamadas.last, startsWith('irA 5'));
        });

        test('no salta si está dentro del límite', () async {
            final referencia = DateTime.now().toUtc().subtract(const Duration(seconds: 5));
            await sincronizador.aplicar(estado('reproduciendo', referencia: referencia));
            reproductor.posicionActual = DateTime.now().toUtc().difference(referencia) - const Duration(milliseconds: 150);
            await sincronizador.revisar();
            expect(sincronizador.correcciones, 0);
        });
    });
}
