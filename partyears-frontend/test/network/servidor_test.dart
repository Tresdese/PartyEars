import 'package:flutter_test/flutter_test.dart';
import 'package:partyears_frontend/core/network/api_config.dart';
import 'package:partyears_frontend/core/network/red.dart';
import 'package:partyears_frontend/features/auth/presentation/login_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
    test('el servidor escrito se reduce al host', () {
        expect(hostDeTexto(' 10.8.0.6 '), '10.8.0.6');
        expect(hostDeTexto('http://10.8.0.6:8001/api/v1/auth/login'), '10.8.0.6');
        expect(hostDeTexto('mi pc'), '');
    });

    test('cambiar de servidor apunta todos los servicios al nuevo host y se recuerda', () async {
        TestWidgetsFlutterBinding.ensureInitialized();
        SharedPreferences.setMockInitialValues({});
        await Red.iniciar();

        await Red.instancia.cambiarServidor('10.8.0.6');

        expect(Red.instancia.host, '10.8.0.6');
        expect(Red.instancia.config.urlBase(Servicio.party), 'http://10.8.0.6:8003');
        expect((await ApiConfig.cargar()).urlBase(Servicio.music), 'http://10.8.0.6:8002');
    });
}
