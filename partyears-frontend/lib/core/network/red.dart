import 'api_client.dart';
import 'api_config.dart';
import 'simulado.dart';
import 'token_store.dart';
import 'ws_client.dart';

class Red {
    Red._(this.api, this.config);

    static const simulado = bool.fromEnvironment('PARTYEARS_SIMULADO', defaultValue: true);
    static late Red instancia;

    final ApiClient api;
    final ApiConfig config;

    static Future<void> iniciar() async {
        final config = await ApiConfig.cargar();
        final ApiClient api = simulado ? MockApiClient() : HttpApiClient(config: config, tokens: TokenStoreSeguro());
        instancia = Red._(api, config);
    }

    WsClient crearWs(Servicio servicio, String recursoId) {
        if (simulado) return WsSimulado();
        
        return WsClientReal(api: api, config: config, servicio: servicio, recursoId: recursoId, usaLatido: servicio == Servicio.party,);
    }
}