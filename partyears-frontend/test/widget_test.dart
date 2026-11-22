import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:partyears_frontend/app/party_ears_app.dart';
import 'package:partyears_frontend/core/demo_data.dart';
import 'package:partyears_frontend/core/network/api_exception.dart';
import 'package:partyears_frontend/features/party/data/party_models.dart';
import 'package:partyears_frontend/features/party/data/party_service.dart';
import 'package:partyears_frontend/features/party/presentation/party_screen.dart';
import 'package:partyears_frontend/features/party/sesion_party.dart';

import 'party/falsos.dart';

void _useDesktopSize(WidgetTester tester) {
    tester.view.physicalSize = const Size(1440, 900);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
}

Future<void> _login(WidgetTester tester) async {
    await tester.pumpWidget(const PartyEarsApp());
    await tester.tap(find.text('Entrar a PartyEars'));
    await tester.pumpAndSettle();
}

class _PartyFalso implements PartyService {
    @override
    Future<PartyActual?> actual() async => null;

    @override
    Future<PartyActual> crear(String nombre, {String? clave}) async =>
        PartyActual(
            id: 'p1',
            nombre: nombre,
            codigo: 'K7Q2ZP',
            version: 1,
            anfitrionId: 'u1',
        );

    @override
    Future<PartyActual> unirse(String codigo, {String? clave}) => crear('Unida');

    @override
    Future<PartyActual> consultar(String partyId) => crear('Consultada');
}

void main() {
    setUpAll(() {
        PartyService.fabrica = () => _PartyFalso();
        SesionParty.fabrica = sesionFalsa;
    });

    group('Pruebas de PartyEars', () {
        testWidgets('Muestra la pantalla de inicio de sesión', 
            (WidgetTester tester,) async {
                _useDesktopSize(tester);
                await tester.pumpWidget(const PartyEarsApp());
                expect(find.text('Inicia sesión'), findsOneWidget);
                expect(find.text('Correo electrónico'), findsOneWidget);
                expect(find.text('Contraseña'), findsOneWidget);
                expect(find.text('Entrar a PartyEars'), findsOneWidget);
                expect(find.text('Crear una cuenta'), findsOneWidget);
            }
        );

        testWidgets('El inicio de sesión no se desborda en ventanas pequeñas', 
            (WidgetTester tester,) async {
                addTearDown(tester.view.reset);
                tester.view.devicePixelRatio = 1.0;
                for (final size in const [Size(800, 600), Size(720, 400)]) {
                    tester.view.physicalSize = size;
                    await tester.pumpWidget(const PartyEarsApp());
                    await tester.pump();
                    expect(tester.takeException(), isNull, reason: '$size');
                }
            }
        );

        testWidgets('Sin party no se muestra código de sala', 
            (WidgetTester tester,) async {
                _useDesktopSize(tester);
                await _login(tester);
                expect(find.text('Bienvenido a PartyEars'), findsOneWidget);
                expect(find.text('Crea o únete a una Party'), findsOneWidget);
                expect(find.text(demoPartyCode), findsNothing);
                expect(find.text('Sala activa'.toUpperCase()), findsNothing);
            }
        );

        testWidgets('Crear party muestra el código del servidor y salir lo quita', 
            (WidgetTester tester,) async {
                _useDesktopSize(tester);
                await _login(tester);
                await tester.tap(find.text('Party'));
                await tester.pumpAndSettle();
                await tester.enterText(find.byType(TextField).first, 'Fiesta de Mariana');
                await tester.tap(find.text('Crear Party'));
                await tester.pumpAndSettle();
                expect(find.text('K7Q2ZP'), findsNWidgets(2));
                await tester.tap(find.text('Salir de la party (demo)'));
                await tester.pumpAndSettle();
                expect(find.text('K7Q2ZP'), findsNothing);
            }
        );

        testWidgets('El código copiado coincide con el mostrado', 
            (WidgetTester tester,) async {
                _useDesktopSize(tester);
                String? copiado;
                tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, 
                    (call) async {
                        if (call.method == 'Clipboard.setData') {
                            copiado = (call.arguments as Map)['text'] as String?;
                        }
                        return null;
                    },
                );
                addTearDown(() => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, null));
                await _login(tester);
                await tester.tap(find.text('Party'));
                await tester.pumpAndSettle();
                await tester.enterText(find.byType(TextField).first, 'Fiesta');
                await tester.tap(find.text('Crear Party'));
                await tester.pumpAndSettle();
                await tester.tap(find.byTooltip('Copiar código'));
                await tester.pump();
                expect(copiado, 'K7Q2ZP');
                expect(find.text('K7Q2ZP'), findsWidgets);
            }
        );

        testWidgets('Crear party sin nombre pide un nombre', 
            (WidgetTester tester,) async {
                _useDesktopSize(tester);
                var llamadas = 0;
                await tester.pumpWidget(MaterialApp(
                    home: Scaffold(
                        body: PartyScreen(
                            partyCode: null,
                            onCreate: (nombre, {clave}) async {
                                llamadas++;
                            },
                            onLeave: () {},
                        ),
                    ),
                ));
                await tester.tap(find.widgetWithText(FilledButton, 'Crear Party'));
                await tester.pumpAndSettle();
                expect(llamadas, 0);
                expect(find.text('Ponle un nombre a la party.'), findsOneWidget);
            }
        );

        testWidgets('Muestra el error del servidor al crear', 
            (WidgetTester tester,) async {
                _useDesktopSize(tester);
                await tester.pumpWidget(MaterialApp(
                    home: Scaffold(
                        body: PartyScreen(
                            partyCode: null,
                            onCreate: (nombre, {clave}) async => throw const ApiException(
                                codigo: 'YA_EN_OTRA_PARTY',
                                mensaje: 'Ya estás en otra party. Sal de ella para continuar.',
                                estadoHttp: 409,
                            ),
                            onLeave: () {},
                        ),
                    ),
                ));
                await tester.enterText(find.byType(TextField).first, 'Fiesta');
                await tester.tap(find.text('Crear Party'));
                await tester.pumpAndSettle();
                expect(
                    find.text('Ya estás en otra party. Sal de ella para continuar.'),
                    findsOneWidget,
                );
            }
        );

        testWidgets('Tras un fallo de red, el reintento reutiliza la clave', 
            (WidgetTester tester,) async {
                _useDesktopSize(tester);
                final claves = <String?>[];
                await tester.pumpWidget(MaterialApp(
                    home: Scaffold(
                        body: PartyScreen(
                            partyCode: null,
                            onCreate: (nombre, {clave}) async {
                                claves.add(clave);
                                if (claves.length == 1) {
                                    throw const ApiException(
                                        codigo: ApiException.sinConexion,
                                        mensaje: 'No se pudo conectar con el servidor.',
                                        idempotencyKey: 'clave-1',
                                    );
                                }
                            },
                            onLeave: () {},
                        ),
                    ),
                ));
                await tester.enterText(find.byType(TextField).first, 'Fiesta');
                await tester.tap(find.text('Crear Party'));
                await tester.pumpAndSettle();
                await tester.tap(find.text('Crear Party'));
                await tester.pumpAndSettle();
                expect(claves, [null, 'clave-1']);
            }
        );

        testWidgets('Rechaza códigos con formato inválido', 
            (WidgetTester tester,) async {
                _useDesktopSize(tester);
                await _login(tester);
                await tester.tap(find.text('Party'));
                await tester.pumpAndSettle();
                await tester.enterText(find.byType(TextField).last, 'AB-12');
                await tester.tap(find.text('Unirse a una Party'));
                await tester.pump();
                expect(
                    find.text('Ingresa un código válido de seis caracteres'),
                    findsOneWidget,
                );
            }
        );

        testWidgets('En teléfono usa navegación inferior sin desbordarse', 
            (WidgetTester tester,) async {
                tester.view.physicalSize = const Size(390, 844);
                tester.view.devicePixelRatio = 1.0;
                addTearDown(tester.view.reset);
                await _login(tester);
                expect(find.byType(NavigationBar), findsOneWidget);
                await tester.tap(find.text('Música'));
                await tester.pumpAndSettle();
                expect(find.text('Catálogo musical'), findsOneWidget);
            }
        );

        testWidgets('Sin party se puede agregar a la cola individual', 
            (WidgetTester tester,) async {
                _useDesktopSize(tester);
                await _login(tester);
                await tester.tap(find.text('Música'));
                await tester.pumpAndSettle();
                await tester.tap(find.byIcon(Icons.add).first);
                await tester.pump();
                expect(
                    find.textContaining('a la cola requiere el backend'),
                    findsOneWidget,
                );
                expect(find.textContaining('Únete a una party'), findsNothing);
            }
        );

        testWidgets('Filtra el catálogo por género', 
            (WidgetTester tester) async {
                _useDesktopSize(tester);
                await _login(tester);

                await tester.tap(find.text('Música'));
                await tester.pumpAndSettle();
                expect(find.text('6 resultados'), findsOneWidget);

                await tester.tap(find.text('Pop'));
                await tester.pumpAndSettle();
                expect(find.text('1 resultado'), findsOneWidget);
                expect(find.text('Blinding Lights'), findsOneWidget);
                expect(find.text('After Dark'), findsNothing);
            }
        );
    });
}
