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
    ApiConfig config;

    /// Host (IP o nombre) de la máquina que corre el backend en este momento.
    String get host => Uri.parse(config.urlBase(Servicio.auth)).host;

    /// The backend moves between machines (the professor picks whose PC runs it), so the host
    /// is chosen in the app and saved instead of fixed when compiling (PARTYEARS_HOST).
    Future<void> cambiarServidor(String host) async {
        config = ApiConfig.desdeHost(host.trim());
        final cliente = api;
        if (cliente is HttpApiClient) cliente.config = config;
        await config.guardar();
    }

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