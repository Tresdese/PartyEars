import '../../../core/network/api_client.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_exception.dart';
import 'cola_models.dart';

/// Cola compartida y reproducción de una party (contrato 5.2 y 5.3).
class ColaService {
    ColaService(this._api);

    final ApiClient _api;

    Future<EstadoCola> consultar(String partyId) async {
        return EstadoCola.desdeJson(_comoMapa(await _api.get(Servicio.queue, '/parties/$partyId/cola')));
    }

    /// accion: iniciar, pausar, reanudar, buscar o saltar.
    Future<EstadoReproduccion> reproduccion(String partyId, String accion, {String? elementoId, int? posicionMs}) async {
        final respuesta = await _api.post(Servicio.queue, '/parties/$partyId/cola/reproduccion',
                                          cuerpo: {'accion': accion, 'elemento_id': elementoId, 'posicion_ms': posicionMs}, idempotente: true,);
        return EstadoReproduccion.desdeJson(_comoMapa(respuesta));
    }

    /// RF-16: avisa que la canción terminó; el servidor avanza una sola vez.
    Future<void> terminada(String partyId, String elementoId) async {
        await _api.post(Servicio.queue, '/parties/$partyId/cola/elementos/$elementoId/terminada', idempotente: true);
    }

    static Map<String, dynamic> _comoMapa(Object? respuesta) {
        if (respuesta is! Map<String, dynamic>) {
            throw const ApiException(codigo: ApiException.respuestaInvalida, mensaje: 'El servidor mandó una respuesta que no se pudo leer.');
        }
        return respuesta;
    }
}
