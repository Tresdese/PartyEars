import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:partyears_frontend/features/party/data/party_models.dart';
import 'package:partyears_frontend/features/party/presentation/party_en_curso.dart';
import 'package:partyears_frontend/features/party/sesion_party.dart';

import 'falsos.dart';

const _ana = MiembroParty(usuarioId: 'u1', nombreUsuario: 'Ana', puedeAportar: true, puedeModificarCola: true, conectado: true);
const _anaDesconectada = MiembroParty(usuarioId: 'u1', nombreUsuario: 'Ana', puedeAportar: true, puedeModificarCola: true, conectado: false);
const _beto = MiembroParty(usuarioId: 'u2', nombreUsuario: 'Beto', puedeAportar: false, puedeModificarCola: false, conectado: true);
const _carla = MiembroParty(usuarioId: 'u3', nombreUsuario: 'Carla', puedeAportar: true, puedeModificarCola: true, conectado: true);

const _inicial = PartyActual(id: 'p1', nombre: 'Viernes', codigo: null, version: 1, anfitrionId: 'u1', miembros: [_ana, _beto, _carla]);

const _desconexion = 'Anfitrión desconectado: Carla es el sucesor por orden de ingreso';
const _nuevo = 'Nuevo anfitrión: Carla';

void main() {
    late PartyServiceFalso partyService;
    late WsConectado ws;

    Future<void> mostrar(WidgetTester tester) async {
        partyService = PartyServiceFalso(_inicial);
        ws = WsConectado();
        final s = SesionParty(party: _inicial, partyService: partyService, colaService: ColaServiceFalsa(), ws: ws,
                              reproductor: ReproductorFalso(), abrirAudio: (_, _) async {}, usuarioId: 'u2');
        SesionParty.fabrica = (_) => s;
        tester.view.physicalSize = const Size(1440, 1600);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.reset);
        await tester.pumpWidget(MaterialApp(home: Scaffold(body: PartyEnCurso(party: _inicial, onLeave: (_) {}))));
        await tester.pump();
    }

    Future<void> cambiarAnfitrion(WidgetTester tester, {required bool anteriorSigue, String motivo = 'sucesion'}) async {
        partyService.party = PartyActual(
            id: 'p1', nombre: 'Viernes', codigo: null, version: 2, anfitrionId: 'u3',
            miembros: [if (anteriorSigue) _anaDesconectada, _beto, _carla],
        );
        ws.emitir('anfitrion.cambio', {'anterior_id': 'u1', 'nuevo_id': 'u3', 'motivo': motivo});
        await tester.pump();
        await tester.pump();
    }

    testWidgets('en escritorio explica que el anfitrión se desconectó y quién lo sucede (P-08)', (tester) async {
        await mostrar(tester);
        await cambiarAnfitrion(tester, anteriorSigue: true);
        expect(find.text(_desconexion), findsOneWidget);
    }, variant: TargetPlatformVariant.only(TargetPlatform.windows));

    testWidgets('en Android solo dice quién es el nuevo anfitrión (P-08)', (tester) async {
        await mostrar(tester);
        await cambiarAnfitrion(tester, anteriorSigue: true);
        expect(find.text(_nuevo), findsOneWidget);
        expect(find.text(_desconexion), findsNothing);
    }, variant: TargetPlatformVariant.only(TargetPlatform.android));

    testWidgets('si el anterior ya no está en la lista, escritorio dice solo "Nuevo anfitrión"', (tester) async {
        await mostrar(tester);
        await cambiarAnfitrion(tester, anteriorSigue: false);
        expect(find.text(_nuevo), findsOneWidget);
        expect(find.text(_desconexion), findsNothing);
    }, variant: TargetPlatformVariant.only(TargetPlatform.windows));

    testWidgets('una transferencia manual no muestra el aviso de sucesión', (tester) async {
        await mostrar(tester);
        await cambiarAnfitrion(tester, anteriorSigue: true, motivo: 'manual');
        expect(find.text(_desconexion), findsNothing);
        expect(find.text(_nuevo), findsNothing);
    });

    testWidgets('el aviso desaparece a los 10 segundos', (tester) async {
        await mostrar(tester);
        await cambiarAnfitrion(tester, anteriorSigue: true);
        expect(find.text(_nuevo), findsOneWidget);
        await tester.pump(const Duration(seconds: 11));
        await tester.pump();
        expect(find.text(_nuevo), findsNothing);
    });
}
