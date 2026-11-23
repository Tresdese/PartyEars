import 'package:flutter_test/flutter_test.dart';
import 'package:partyears_frontend/core/network/ws_client.dart';
import 'package:partyears_frontend/features/party/sesion_party.dart';

import 'falsos.dart';

void main() {
    late WsConectado ws;

    Future<SesionParty> iniciada() async {
        ws = WsConectado();
        final s = SesionParty(party: partyDePrueba, partyService: PartyServiceFalso(partyDePrueba), colaService: ColaServiceFalsa(),
                              ws: ws, reproductor: ReproductorFalso(), abrirAudio: (_, _) async {}, usuarioId: 'u2');
        addTearDown(s.cerrar);
        await s.iniciar();
        return s;
    }

    test('party.finalizada sin conectados guarda el motivo (CU-16, cierre automático)', () async {
        final s = await iniciada();
        ws.emitir('party.finalizada', {'motivo': 'sin_conectados'});
        await Future<void>.delayed(Duration.zero);
        expect(s.cierre, WsMotivoCierre.partyFinalizada);
        expect(s.motivoFinalizacion, 'sin_conectados');
    });

    test('party.finalizada del anfitrión guarda su motivo', () async {
        final s = await iniciada();
        ws.emitir('party.finalizada', {'motivo': 'anfitrion'});
        await Future<void>.delayed(Duration.zero);
        expect(s.motivoFinalizacion, 'anfitrion');
    });

    test('si el servidor no dice el motivo, queda sin motivo', () async {
        final s = await iniciada();
        ws.emitir('party.finalizada');
        await Future<void>.delayed(Duration.zero);
        expect(s.cierre, WsMotivoCierre.partyFinalizada);
        expect(s.motivoFinalizacion, isNull);
    });
}
