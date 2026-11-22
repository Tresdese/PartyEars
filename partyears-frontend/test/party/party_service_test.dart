import 'package:flutter_test/flutter_test.dart';
import 'package:partyears_frontend/core/network/api_client.dart';
import 'package:partyears_frontend/core/network/api_config.dart';
import 'package:partyears_frontend/core/network/api_exception.dart';
import 'package:partyears_frontend/core/network/simulado.dart';
import 'package:partyears_frontend/features/party/data/party_service.dart';

Future<PartyService> _servicioConSesion() async {
    final api = MockApiClient(latencia: Duration.zero);

    await api.post(
        Servicio.auth,
        '/login',
        cuerpo: {'correo': 'demo@partyears.mx', 'contrasena': 'demopassword1'},
        autenticado: false,
    );
    
    return PartyService(api);
}

void main() {
    test('sin party activa, actual() devuelve null', () async {
        final servicio = await _servicioConSesion();
        expect(await servicio.actual(), isNull);
    });

    test('crear devuelve un código de 6 caracteres A-Z/0-9', () async {
        final servicio = await _servicioConSesion();
        final party = await servicio.crear('Fiesta de prueba');
        expect(party.nombre, 'Fiesta de prueba');
        expect(RegExp(r'^[A-Z0-9]{6}$').hasMatch(party.codigo!), isTrue);
    });

    test('actual() devuelve la party creada con el mismo código', () async {
        final servicio = await _servicioConSesion();
        final creada = await servicio.crear('Fiesta');
        final actual = await servicio.actual();
        expect(actual?.codigo, creada.codigo);
    });

    test('crear otra party estando en una da YA_EN_OTRA_PARTY', () async {
        final servicio = await _servicioConSesion();
        await servicio.crear('Primera');
        await expectLater(
        servicio.crear('Segunda'),
        throwsA(isA<ApiException>()
            .having((e) => e.codigo, 'codigo', 'YA_EN_OTRA_PARTY')),
        );
    });

    test('un nombre vacío da DATOS_INVALIDOS', () async {
        final servicio = await _servicioConSesion();
        await expectLater(
        servicio.crear('   '),
        throwsA(isA<ApiException>()
            .having((e) => e.codigo, 'codigo', 'DATOS_INVALIDOS')),
        );
    });
}