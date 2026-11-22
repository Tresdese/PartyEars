import '../../../core/network/api_client.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/network/red.dart';
import 'party_models.dart';

class PartyService {
    PartyService(this._api);

    static PartyService Function() fabrica = () => PartyService(Red.instancia.api);

    final ApiClient _api;

    Future<PartyActual> crear(String nombre, {String? clave}) async {
        final respuesta = await _api.post(Servicio.party, '/parties', cuerpo: {'nombre': nombre}, idempotente: true, idempotencyKey: clave,);

        if (respuesta is! Map<String, dynamic>) {
            throw const ApiException(
                codigo: ApiException.respuestaInvalida,
                mensaje: 'El servidor mandó una respuesta que no se pudo leer.',
            );
        }

        final party = PartyActual.desdeJson(respuesta);

        if (party.codigo == null) {
            throw const ApiException(
                codigo: ApiException.respuestaInvalida,
                mensaje: 'El servidor no devolvió el código de la party.',
            );
        }
        return party;
    }

    /// Contrato 4.2: entra como oyente con el código de invitación.
    Future<PartyActual> unirse(String codigo, {String? clave}) async {
        final respuesta = await _api.post(Servicio.party, '/parties/unirse', cuerpo: {'codigo': codigo}, idempotente: true, idempotencyKey: clave,);

        return PartyActual.desdeJson(_comoMapa(respuesta));
    }

    /// Contrato 4.3: la instantánea que se pide al conectar o reconectar el WebSocket.
    Future<PartyActual> consultar(String partyId) async {
        return PartyActual.desdeJson(_comoMapa(await _api.get(Servicio.party, '/parties/$partyId')));
    }

    static Map<String, dynamic> _comoMapa(Object? respuesta) {
        if (respuesta is! Map<String, dynamic>) {
            throw const ApiException(
                codigo: ApiException.respuestaInvalida,
                mensaje: 'El servidor mandó una respuesta que no se pudo leer.',
            );
        }
        return respuesta;
    }

    Future<PartyActual?> actual() async {
        final respuesta = await _api.get(Servicio.party, '/parties/actual');

        if (respuesta is! Map<String, dynamic>) return null;

        final party = PartyActual.desdeJson(respuesta);
        
        return party.finalizadaEn == null ? party : null;
    }
}