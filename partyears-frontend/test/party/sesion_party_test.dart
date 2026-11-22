import 'package:flutter_test/flutter_test.dart';
import 'package:partyears_frontend/core/network/simulado.dart';
import 'package:partyears_frontend/core/network/ws_client.dart';
import 'package:partyears_frontend/features/party/data/cola_models.dart';
import 'package:partyears_frontend/features/party/data/party_models.dart';
import 'package:partyears_frontend/features/party/sesion_party.dart';

import 'falsos.dart';

Map<String, dynamic> reproduccionJson(int version, {String estado = 'pausada', String elemento = 'e1'}) => {
    'cola_id': 'c1', 'version': version, 'elemento_id': elemento, 'recurso_audio_id': 'r-$elemento', 'estado': estado,
    'posicion_base_ms': 0, 'referencia_en': DateTime.now().toUtc().toIso8601String(), 'duracion_ms': null,
};

Map<String, dynamic> colaJson(int version, int pendientes) => {
    'id': 'c1', 'modalidad': 'compartida', 'version': version, 'actual': null,
    'pendientes': [for (var i = 0; i < pendientes; i++) {'id': 'e$i', 'recurso_audio_id': 'r$i', 'estado': 'pendiente'}],
};

void main() {
    late WsSimulado ws;
    late PartyServiceFalso partyService;
    late ColaServiceFalsa colaService;
    late ReproductorFalso reproductor;
    late List<String> abiertos;
    late SesionParty sesion;

    SesionParty crear(PartyActual party, {String? usuarioId}) => SesionParty(
        party: party, partyService: partyService, colaService: colaService, ws: ws, reproductor: reproductor,
        abrirAudio: (recurso, _) async => abiertos.add(recurso), usuarioId: usuarioId,
    );

    Future<void> procesar() => Future<void>.delayed(const Duration(milliseconds: 50));

    setUp(() async {
        ws = WsSimulado();
        partyService = PartyServiceFalso(partyDePrueba);
        colaService = ColaServiceFalsa();
        reproductor = ReproductorFalso();
        abiertos = [];
        colaService.cola = EstadoCola.desdeJson({
            ...colaJson(4, 1),
            'actual': {'elemento': {'id': 'e9', 'recurso_audio_id': 'r-e9', 'estado': 'pausada'},
                       'reproduccion': reproduccionJson(4, elemento: 'e9')},
        });
        sesion = crear(partyDePrueba);
        await sesion.iniciar();
        // The clock waits up to 2 s for a pong that WsSimulado never sends.
        await Future<void>.delayed(const Duration(milliseconds: 2300));
    });

    tearDown(() => sesion.cerrar());

    test('al conectar pide las instantáneas y abre la canción actual (quien llega tarde)', () {
        expect(partyService.consultas, 1);
        expect(sesion.cola.version, 4);
        expect(abiertos, ['r-e9']);
        expect(sesion.conectada, isTrue);
    });

    test('aplica cola.actualizada y reproduccion.estado aunque traigan la misma versión', () async {
        ws.emitir('reproduccion.estado', datos: reproduccionJson(5, estado: 'reproduciendo', elemento: 'e1'));
        ws.emitir('cola.actualizada', datos: colaJson(5, 3));
        await procesar();
        expect(sesion.reproduccion.version, 5);
        expect(sesion.cola.pendientes.length, 3);
        expect(abiertos.last, 'r-e1');
    });

    test('descarta un estado más viejo que el que ya tiene', () async {
        ws.emitir('cola.actualizada', datos: colaJson(3, 7));
        await procesar();
        expect(sesion.cola.pendientes.length, 1);
    });

    test('un cambio de miembros vuelve a pedir la party', () async {
        ws.emitir('miembro.permisos', datos: {'usuario_id': 'u2', 'puede_aportar': true, 'puede_modificar_cola': false});
        await procesar();
        expect(partyService.consultas, 2);
    });

    test('el anfitrión avisa el fin de la canción', () async {
        reproductor.terminadoCtrl.add(null);
        await procesar();
        expect(colaService.terminadas, ['e9']);
    });

    test('un oyente no avisa el fin de la canción', () async {
        await sesion.cerrar();
        ws = WsSimulado();
        reproductor = ReproductorFalso();
        const oyente = PartyActual(id: 'p1', nombre: 'Viernes', codigo: null, version: 1, anfitrionId: 'u1');
        partyService = PartyServiceFalso(oyente);
        sesion = crear(oyente, usuarioId: 'u2');
        await sesion.iniciar();
        await procesar();
        reproductor.terminadoCtrl.add(null);
        await procesar();
        expect(colaService.terminadas, isEmpty);
        expect(sesion.esAnfitrion, isFalse);
    });

    test('con permiso de modificar puede saltar aunque no sea anfitrión', () {
        const party = PartyActual(id: 'p1', nombre: 'x', codigo: null, version: 1, anfitrionId: 'u1', miembros: [
            MiembroParty(usuarioId: 'u2', puedeAportar: false, puedeModificarCola: true, conectado: true),
        ]);
        final otra = crear(party, usuarioId: 'u2');
        expect((otra.esAnfitrion, otra.puedeSaltar), (false, true));
    });

    test('party finalizada cierra la sesión y el audio', () async {
        ws.emitir('party.finalizada', datos: {'motivo': 'anfitrion'});
        await procesar();
        expect(sesion.cierre, WsMotivoCierre.partyFinalizada);
        expect(reproductor.cerrado, isTrue);
    });

    test('lee el usuario del token', () {
        const token = 'x.eyJzdWIiOiJ1LTQyIn0.y';
        expect(usuarioDelToken(token), 'u-42');
        expect(usuarioDelToken('simulado.123'), isNull);
    });
}
