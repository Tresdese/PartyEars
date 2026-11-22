import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:partyears_frontend/core/network/api_exception.dart';
import 'package:partyears_frontend/features/music/data/catalogo_service.dart';
import 'package:partyears_frontend/features/party/data/party_models.dart';
import 'package:partyears_frontend/features/party/presentation/agregar_cancion_screen.dart';
import 'package:partyears_frontend/features/party/presentation/party_en_curso.dart';
import 'package:partyears_frontend/features/party/sesion_party.dart';

import 'falsos.dart';

const _anfitrion = 'u1';
const _oyente = 'u2';

PartyActual _party({String? codigo = 'K7Q2ZP', bool aportar = false, bool conectado = true}) => PartyActual(
    id: 'p1', nombre: 'Viernes', codigo: codigo, version: 5, anfitrionId: _anfitrion,
    miembros: [
        const MiembroParty(usuarioId: _anfitrion, puedeAportar: true, puedeModificarCola: true, conectado: true),
        MiembroParty(usuarioId: _oyente, puedeAportar: aportar, puedeModificarCola: false, conectado: conectado),
    ],
);

final _catalogo = [
    const CancionCatalogo(titulo: 'Ñandú', artistas: ['Selva Azul'], duracionMs: 176000, variantes: [
        VarianteAudio(recursoAudioId: 'r1', tipo: 'original', disponible: true),
        VarianteAudio(recursoAudioId: 'r2', tipo: 'instrumental', disponible: false),
    ]),
];

const _errorRed = ApiException(codigo: ApiException.sinConexion, mensaje: 'sin red', idempotencyKey: 'clave-1');

void main() {
    late PartyServiceFalso partyService;
    late ColaServiceFalsa colaService;

    SesionParty sesion(PartyActual party, {String usuario = _anfitrion}) {
        partyService = PartyServiceFalso(party);
        colaService = ColaServiceFalsa();
        return SesionParty(party: party, partyService: partyService, colaService: colaService, ws: WsConectado(),
                           reproductor: ReproductorFalso(), abrirAudio: (_, _) async {}, usuarioId: usuario,
                           buscarCanciones: (texto) async => texto == 'zzz' ? [] : _catalogo);
    }

    group('agregar (CU-11)', () {
        test('agrega y confirma con el mensaje del SRS', () async {
            final s = sesion(_party());
            expect(await s.agregar('r1'), 'Canción agregada a la cola');
            expect(colaService.agregadas, ['r1']);
        });

        test('cada error muestra su mensaje del SRS', () async {
            final s = sesion(_party());
            final casos = {
                'SIN_PERMISO': 'Ya no tienes permiso para agregar canciones a esta party',
                'PARTY_FINALIZADA': 'Ya no puedes agregar canciones a esta sesión',
                'AUDIO_NO_DISPONIBLE': 'Esta canción no está disponible',
                'ERROR': 'No fue posible confirmar que la canción se agregó',
            };
            for (final caso in casos.entries) {
                colaService.errorAgregar = ApiException(codigo: caso.key, mensaje: 'x');
                expect(await s.agregar('r1'), caso.value);
            }
        });

        test('el reintento tras un fallo de red reutiliza la clave', () async {
            final s = sesion(_party());
            colaService.errorAgregar = _errorRed;
            await s.agregar('r1');
            colaService.errorAgregar = null;
            await s.agregar('r1');
            await s.agregar('r1');
            expect(colaService.clavesAgregar, [null, 'clave-1', null]);
        });

        test('el oyente sin permiso no puede aportar; con permiso sí', () {
            expect(sesion(_party(codigo: null), usuario: _oyente).puedeAportar, isFalse);
            expect(sesion(_party(codigo: null, aportar: true), usuario: _oyente).puedeAportar, isTrue);
        });
    });

    group('permisos (CU-13, CU-14)', () {
        test('otorgar manda la versión que ve el anfitrión y confirma', () async {
            final s = sesion(_party());
            final mensaje = await s.cambiarPermisos(_party().miembros[1], puedeAportar: true, puedeModificarCola: false);
            expect(mensaje, 'Permisos otorgados correctamente');
            expect(partyService.cambiosPermisos, ['$_oyente true false v5']);
        });

        test('retirar confirma con su propio mensaje', () async {
            final s = sesion(_party(aportar: true));
            final mensaje = await s.cambiarPermisos(_party(aportar: true).miembros[1], puedeAportar: false, puedeModificarCola: false);
            expect(mensaje, 'Permisos retirados correctamente');
        });

        test('participante desconectado', () async {
            final s = sesion(_party());
            partyService.errorPermisos = const ApiException(codigo: 'PARTICIPANTE_NO_CONECTADO', mensaje: 'x');
            final mensaje = await s.cambiarPermisos(_party().miembros[1], puedeAportar: true, puedeModificarCola: false);
            expect(mensaje, 'El participante ya no está conectado a la party');
            expect(partyService.consultas, 1, reason: 'EX-01: vuelve a pedir los permisos vigentes');
        });
    });

    group('pantallas', () {
        Future<void> mostrar(WidgetTester tester, SesionParty s) async {
            SesionParty.fabrica = (_) => s;
            tester.view.physicalSize = const Size(1440, 900);
            tester.view.devicePixelRatio = 1.0;
            addTearDown(tester.view.reset);
            await tester.pumpWidget(MaterialApp(home: Scaffold(body: PartyEnCurso(party: s.party, onLeave: (_) {}))));
            await tester.pump();
        }

        testWidgets('el anfitrión ve los permisos de los demás y los cambia', (tester) async {
            final s = sesion(_party());
            await mostrar(tester, s);
            expect(find.text('Agregar canciones'), findsOneWidget, reason: 'solo en la fila del oyente, no en la del anfitrión');
            await tester.tap(find.text('Agregar canciones'));
            await tester.pump();
            await tester.pump();
            expect(partyService.cambiosPermisos, ['$_oyente true false v5']);
            expect(find.text('Permisos otorgados correctamente'), findsOneWidget);
        });

        testWidgets('a un desconectado no se le puede otorgar', (tester) async {
            await mostrar(tester, sesion(_party(conectado: false)));
            final chip = tester.widget<FilterChip>(find.widgetWithText(FilterChip, 'Agregar canciones'));
            expect(chip.onSelected, isNull);
        });

        testWidgets('un oyente no ve permisos ni el botón de agregar', (tester) async {
            await mostrar(tester, sesion(_party(codigo: null), usuario: _oyente));
            expect(find.byType(FilterChip), findsNothing);
            expect(find.text('Agregar canción'), findsNothing);
        });

        testWidgets('con permiso de aportar ve el botón de agregar', (tester) async {
            await mostrar(tester, sesion(_party(codigo: null, aportar: true), usuario: _oyente));
            expect(find.text('Agregar canción'), findsOneWidget);
        });

        testWidgets('P-06: busca, marca lo no disponible y agrega', (tester) async {
            final agregadas = <String>[];
            await tester.pumpWidget(MaterialApp(home: AgregarCancionScreen(
                buscar: (texto) async => texto == 'zzz' ? [] : _catalogo,
                agregar: (r) async {
                    agregadas.add(r);
                    return 'Canción agregada a la cola';
                },
            )));
            await tester.pump();
            expect(find.text('Ñandú'), findsOneWidget);
            expect(find.text('No disponible'), findsOneWidget);
            await tester.tap(find.text('Agregar a la cola'));
            await tester.pump();
            await tester.pump();
            expect(agregadas, ['r1']);
            expect(find.text('Canción agregada a la cola'), findsOneWidget);

            await tester.enterText(find.byType(TextField), 'zzz');
            await tester.pump(const Duration(milliseconds: 350));
            await tester.pump();
            expect(find.text('No se encontraron canciones'), findsOneWidget);
        });
    });
}
