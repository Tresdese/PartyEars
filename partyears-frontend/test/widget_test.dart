import 'package:flutter_test/flutter_test.dart';
import 'package:partyears_frontend/app/party_ears_app.dart';

void main() {
  group('Pruebas de PartyEars', () {
    testWidgets('Muestra la pantalla de inicio de sesión',
        (WidgetTester tester) async {
      await tester.pumpWidget(const PartyEarsApp());

      expect(find.text('PartyEars'), findsOneWidget);
      expect(find.text('Correo electrónico'), findsOneWidget);
      expect(find.text('Contraseña'), findsOneWidget);
      expect(find.text('Entrar (demo)'), findsOneWidget);
      expect(find.text('Crear cuenta'), findsOneWidget);
    });

    testWidgets('Permite ingresar a la pantalla principal',
        (WidgetTester tester) async {
      await tester.pumpWidget(const PartyEarsApp());

      await tester.tap(find.text('Entrar (demo)'));
      await tester.pumpAndSettle();

      expect(
        find.text('PartyEars · Inicio'),
        findsOneWidget,
      );
    });
  });
}
