import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:partyears_frontend/app/party_ears_app.dart';
import 'package:partyears_frontend/core/demo_data.dart';

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

void main() {
  group('Pruebas de PartyEars', () {
    testWidgets('Muestra la pantalla de inicio de sesión',
        (WidgetTester tester) async {
      _useDesktopSize(tester);
      await tester.pumpWidget(const PartyEarsApp());

      expect(find.text('Inicia sesión'), findsOneWidget);
      expect(find.text('Correo electrónico'), findsOneWidget);
      expect(find.text('Contraseña'), findsOneWidget);
      expect(find.text('Entrar a PartyEars'), findsOneWidget);
      expect(find.text('Crear una cuenta'), findsOneWidget);
    });

    testWidgets('Sin party no se muestra código de sala',
        (WidgetTester tester) async {
      _useDesktopSize(tester);
      await _login(tester);

      expect(find.text('Bienvenido a PartyEars'), findsOneWidget);
      expect(find.text('Crea o únete a una Party'), findsOneWidget);
      expect(find.text(demoPartyCode), findsNothing);
      expect(find.text('Sala activa'.toUpperCase()), findsNothing);
    });

    testWidgets('Crear party muestra el código y salir lo quita',
        (WidgetTester tester) async {
      _useDesktopSize(tester);
      await _login(tester);

      await tester.tap(find.text('Party'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Crear Party (demo)'));
      await tester.pumpAndSettle();
      expect(find.text(demoPartyCode), findsNWidgets(2));

      await tester.tap(find.text('Salir de la party (demo)'));
      await tester.pumpAndSettle();
      expect(find.text(demoPartyCode), findsNothing);
    });

    testWidgets('Rechaza códigos con formato inválido',
        (WidgetTester tester) async {
      _useDesktopSize(tester);
      await _login(tester);

      await tester.tap(find.text('Party'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField).last, 'AB-12');
      await tester.tap(find.text('Unirse a una Party (demo)'));
      await tester.pump();
      expect(find.text('Ingresa un código válido de seis caracteres'),
          findsOneWidget);
    });

    testWidgets('En teléfono usa navegación inferior sin desbordarse',
        (WidgetTester tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      await _login(tester);

      expect(find.byType(NavigationBar), findsOneWidget);
      await tester.tap(find.text('Música'));
      await tester.pumpAndSettle();
      expect(find.text('Catálogo musical'), findsOneWidget);
    });

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
    });
  });
}
