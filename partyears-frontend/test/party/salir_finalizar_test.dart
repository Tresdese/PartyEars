import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:partyears_frontend/core/network/api_exception.dart';
import 'package:partyears_frontend/core/network/ws_client.dart';
import 'package:partyears_frontend/features/party/data/party_models.dart';
import 'package:partyears_frontend/features/party/presentation/party_en_curso.dart';
import 'package:partyears_frontend/features/party/sesion_party.dart';

import 'falsos.dart';

const _oyente = PartyActual(id: 'p1', nombre: 'Viernes', codigo: null, version: 1, anfitrionId: 'u1');

void main() {
    late PartyServiceFalso partyService;
    late WsConectado ws;
    late ReproductorFalso reproductor;

    SesionParty sesion(PartyActual party) {
        partyService = PartyServiceFalso(party);
        ws = WsConectado();
        reproductor = ReproductorFalso();
        return SesionParty(party: party, partyService: partyService, colaService: ColaServiceFalsa(), ws: ws,
                           reproductor: reproductor, abrirAudio: (_, _) async {}, usuarioId: 'u2');
    }

    group('salir (CU-15)', () {
        test('sale sin mensaje y detiene el audio', () async {
            final s = sesion(_oyente);
            expect(await s.salir(), isNull);
            await Future<void>.delayed(Duration.zero);
            expect(partyService.salidas, ['salir']);
            expect(reproductor.cerrado, isTrue);
        });

        test('si ya había salido o la party terminó, sale igual sin error (FA-2.1)', () async {
            final s = sesion(_oyente);
            partyService.errorSalir = const ApiException(codigo: 'PARTY_FINALIZADA', mensaje: 'x');
            expect(await s.salir(), isNull);
        });

        test('sin red avisa, pero sale igual (EX-01)', () async {
            final s = sesion(_oyente);
            partyService.errorSalir = const ApiException(codigo: ApiException.sinConexion, mensaje: 'x');
            expect(await s.salir(), 'No fue posible confirmar la salida con el servidor');
            await Future<void>.delayed(Duration.zero);
            expect(reproductor.cerrado, isTrue);
        });
    });

    group('finalizar (CU-16)', () {
        test('el anfitrión finaliza', () async {
            final s = sesion(partyDePrueba);
            expect(await s.finalizar(), 'La party ha finalizado');
            expect(s.cierre, WsMotivoCierre.partyFinalizada);
        });

        test('quien no es anfitrión recibe el mensaje del SRS y sigue en la party', () async {
            final s = sesion(partyDePrueba);
            partyService.errorFinalizar = const ApiException(codigo: 'NO_ES_ANFITRION', mensaje: 'x');
            expect(await s.finalizar(), 'Solo el anfitrión puede finalizar la party');
            expect(s.cierre, isNull);
            expect(reproductor.cerrado, isFalse);
        });
    });

    group('pantalla', () {
        late List<String?> salidas;

        Future<SesionParty> mostrar(WidgetTester tester, PartyActual party) async {
            final s = sesion(party);
            SesionParty.fabrica = (_) => s;
            salidas = [];
            tester.view.physicalSize = const Size(1440, 1600);
            tester.view.devicePixelRatio = 1.0;
            addTearDown(tester.view.reset);
            await tester.pumpWidget(MaterialApp(home: Scaffold(body: PartyEnCurso(party: party, onLeave: salidas.add))));
            await tester.pump();
            return s;
        }

        testWidgets('el anfitrión ve "Finalizar party"', (tester) async {
            await mostrar(tester, partyDePrueba);
            expect(find.text('Finalizar party'), findsOneWidget);
        });

        testWidgets('un oyente solo puede salir', (tester) async {
            await mostrar(tester, _oyente);
            expect(find.text('Finalizar party'), findsNothing);
            expect(find.text('Salir de la party'), findsOneWidget);
        });

        testWidgets('cancelar la confirmación deja la party activa (FA-2.1)', (tester) async {
            await mostrar(tester, partyDePrueba);
            await tester.tap(find.text('Finalizar party'));
            await tester.pumpAndSettle();
            expect(find.text('¿Deseas finalizar la party? La reproducción compartida terminará para todos los participantes'),
                   findsOneWidget);
            await tester.tap(find.text('Cancelar'));
            await tester.pumpAndSettle();
            expect(partyService.salidas, isEmpty);
            expect(salidas, isEmpty);
        });

        testWidgets('al recibir party.finalizada vuelve a la pantalla principal con el mensaje', (tester) async {
            await mostrar(tester, _oyente);
            ws.emitir('party.finalizada', {'motivo': 'anfitrion'});
            await tester.pump();
            await tester.pump();
            expect(salidas, ['La party ha finalizado']);
        });
    });
}
