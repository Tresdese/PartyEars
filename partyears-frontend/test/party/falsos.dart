import 'dart:async';

import 'package:partyears_frontend/core/network/simulado.dart';
import 'package:partyears_frontend/features/party/data/cola_models.dart';
import 'package:partyears_frontend/features/party/data/cola_service.dart';
import 'package:partyears_frontend/features/party/data/party_models.dart';
import 'package:partyears_frontend/features/party/data/party_service.dart';
import 'package:partyears_frontend/features/party/sesion_party.dart';
import 'package:partyears_frontend/features/player/reproductor.dart';

class ReproductorFalso implements Reproductor {
    final llamadas = <String>[];
    final erroresCtrl = StreamController<String>.broadcast();
    final terminadoCtrl = StreamController<void>.broadcast();
    Duration posicionActual = Duration.zero;
    bool cerrado = false;

    @override
    Stream<bool> get reproduciendo => const Stream.empty();
    @override
    Stream<void> get terminado => terminadoCtrl.stream;
    @override
    Stream<String> get errores => erroresCtrl.stream;
    @override
    Duration get posicion => posicionActual;
    @override
    Duration get duracion => const Duration(minutes: 3);

    @override
    Future<void> abrir(Uri url, {Map<String, String> cabeceras = const {}, Duration desde = Duration.zero}) async => llamadas.add('abrir');
    @override
    Future<void> reproducir() async => llamadas.add('reproducir');
    @override
    Future<void> pausar() async => llamadas.add('pausar');
    @override
    Future<void> irA(Duration posicion) async {
        llamadas.add('irA ${posicion.inMilliseconds}');
        posicionActual = posicion;
    }
    @override
    Future<void> volumen(double valor) async {}
    @override
    Future<void> reintentar() async => llamadas.add('reintentar');
    @override
    Future<void> cerrar() async => cerrado = true;
}

class PartyServiceFalso implements PartyService {
    PartyServiceFalso(this.party);

    PartyActual party;
    int consultas = 0;

    @override
    Future<PartyActual?> actual() async => null;
    @override
    Future<PartyActual> crear(String nombre, {String? clave}) async => party;
    @override
    Future<PartyActual> unirse(String codigo, {String? clave}) async => party;
    @override
    Future<PartyActual> consultar(String partyId) async {
        consultas++;
        return party;
    }
}

class ColaServiceFalsa implements ColaService {
    EstadoCola cola = EstadoCola.vacia;
    final acciones = <String>[];
    final terminadas = <String>[];

    @override
    Future<EstadoCola> consultar(String partyId) async => cola;
    @override
    Future<EstadoReproduccion> reproduccion(String partyId, String accion, {String? elementoId, int? posicionMs}) async {
        acciones.add(accion);
        return EstadoReproduccion.detenida;
    }
    @override
    Future<void> terminada(String partyId, String elementoId) async => terminadas.add(elementoId);
}

/// WebSocket que no conecta: las pruebas de pantallas no necesitan eventos.
class WsQuieto extends WsSimulado {
    @override
    Future<void> conectar() async {}
}

const partyDePrueba = PartyActual(id: 'p1', nombre: 'Viernes', codigo: 'K7Q2ZP', version: 1, anfitrionId: 'u1');

/// Sesión con red y reproductor falsos, para pruebas de pantallas.
SesionParty sesionFalsa(PartyActual party) => SesionParty(
    party: party,
    partyService: PartyServiceFalso(party),
    colaService: ColaServiceFalsa(),
    ws: WsQuieto(),
    reproductor: ReproductorFalso(),
    abrirAudio: (_, _) async {},
);
