import '../../../core/network/api_client.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/network/red.dart';
import 'party_models.dart';

class PartyService {
    PartyService(this._api);

    static PartyService Function() fabrica = () => PartyService(Red.instancia.api);

    final ApiClient _api;

    /// Code each party was entered with on this device, to come back after a disconnection
    /// (contract 7.5 step 6). Members never get the code from the server, only who typed it.
    static final codigosDeIngreso = <String, String>{};

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
        codigosDeIngreso[party.id] = party.codigo!;
        return party;
    }

    /// Contrato 4.2: entra como oyente con el código de invitación.
    Future<PartyActual> unirse(String codigo, {String? clave}) async {
        final respuesta = await _api.post(Servicio.party, '/parties/unirse', cuerpo: {'codigo': codigo}, idempotente: true, idempotencyKey: clave,);
        final party = PartyActual.desdeJson(_comoMapa(respuesta));
        codigosDeIngreso[party.id] = codigo;

        return party;
    }

    /// Contrato 4.3: la instantánea que se pide al conectar o reconectar el WebSocket.
    Future<PartyActual> consultar(String partyId) async {
        return PartyActual.desdeJson(_comoMapa(await _api.get(Servicio.party, '/parties/$partyId')));
    }

    /// Contrato 4.1.3: si sale el anfitrión, el servidor aplica la sucesión.
    Future<void> salir(String partyId) async {
        await _api.post(Servicio.party, '/parties/$partyId/salir', idempotente: true);
    }

    /// Contrato 4.1.4: solo el anfitrión; todos reciben party.finalizada.
    Future<void> finalizar(String partyId) async {
        await _api.post(Servicio.party, '/parties/$partyId/finalizar', idempotente: true);
    }

    /// Contrato 4.4: solo el anfitrión. Devuelve la nueva versión de la party.
    Future<int> cambiarPermisos(String partyId, String usuarioId, {required bool puedeAportar, required bool puedeModificarCola,
                                required int versionEsperada}) async {
        final respuesta = _comoMapa(await _api.put(Servicio.party, '/parties/$partyId/miembros/$usuarioId/permisos',
                                                   cuerpo: {'puede_aportar': puedeAportar, 'puede_modificar_cola': puedeModificarCola,
                                                            'version_esperada': versionEsperada}, idempotente: true));
        return (respuesta['version'] as num).toInt();
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