import '../../../core/network/api_client.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_exception.dart';
import '../../party/data/cola_models.dart';

/// Cola individual del usuario (contrato 5.1): las mismas operaciones que la compartida,
/// sin party ni permisos.
class MiColaService {
    MiColaService(this._api);

    final ApiClient _api;

    static const _ruta = '/mi-cola';

    Future<EstadoCola> consultar() async => EstadoCola.desdeJson(_comoMapa(await _api.get(Servicio.queue, _ruta)));

    Future<EstadoCola> agregar(String recursoAudioId) async {
        final respuesta = await _api.post(Servicio.queue, '$_ruta/elementos', cuerpo: {'recurso_audio_id': recursoAudioId},
                                          idempotente: true);
        return EstadoCola.desdeJson(_comoMapa(respuesta));
    }

    /// RF-12: [nuevaPosicion] cuenta desde 1 dentro de los pendientes.
    Future<EstadoCola> reordenar(String elementoId, int nuevaPosicion, int versionEsperada) async {
        final respuesta = await _api.patch(Servicio.queue, '$_ruta/elementos/$elementoId',
                                           cuerpo: {'nueva_posicion': nuevaPosicion, 'version_esperada': versionEsperada},
                                           idempotente: true);
        return EstadoCola.desdeJson(_comoMapa(respuesta));
    }

    /// RF-13: la confirmación al usuario se pide antes de llamar.
    Future<EstadoCola> retirar(String elementoId, int versionEsperada) async {
        final respuesta = await _api.delete(Servicio.queue, '$_ruta/elementos/$elementoId',
                                            query: {'version_esperada': '$versionEsperada'}, idempotente: true);
        return EstadoCola.desdeJson(_comoMapa(respuesta));
    }

    /// accion: iniciar, pausar, reanudar, buscar o saltar.
    Future<EstadoReproduccion> reproduccion(String accion, {String? elementoId, int? posicionMs}) async {
        final respuesta = await _api.post(Servicio.queue, '$_ruta/reproduccion',
                                          cuerpo: {'accion': accion, 'elemento_id': elementoId, 'posicion_ms': posicionMs},
                                          idempotente: true);
        return EstadoReproduccion.desdeJson(_comoMapa(respuesta));
    }

    /// CU-26: avisa que la canción terminó; el servidor empieza la siguiente una sola vez.
    Future<EstadoReproduccion> terminada(String elementoId) async {
        final respuesta = await _api.post(Servicio.queue, '$_ruta/elementos/$elementoId/terminada', idempotente: true);
        return EstadoReproduccion.desdeJson(_comoMapa(respuesta));
    }

    static Map<String, dynamic> _comoMapa(Object? respuesta) {
        if (respuesta is! Map<String, dynamic>) {
            throw const ApiException(codigo: ApiException.respuestaInvalida, mensaje: 'El servidor mandó una respuesta que no se pudo leer.');
        }
        return respuesta;
    }
}
