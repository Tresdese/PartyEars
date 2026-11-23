import 'package:flutter/material.dart';

import '../../../core/network/ws_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/common.dart';
import '../../voice/presentation/voice_screen.dart';
import '../data/party_models.dart';
import '../sesion_party.dart';
import 'agregar_cancion_screen.dart';

/// Pantalla de una party en curso (T-55): canción, cola, participantes y conexión.
class PartyEnCurso extends StatefulWidget {
    const PartyEnCurso({super.key, required this.party, required this.onLeave});

    final PartyActual party;

    /// Se llama al terminar la party para este usuario, con el mensaje que hay que mostrar.
    final void Function(String? mensaje) onLeave;

    @override
    State<PartyEnCurso> createState() => _PartyEnCursoState();
}

class _PartyEnCursoState extends State<PartyEnCurso> {
    late final SesionParty _sesion = SesionParty.fabrica(widget.party);

    bool _saliendo = false;

    @override
    void initState() {
        super.initState();
        _sesion.addListener(_alCambiar);
        _sesion.iniciar();
    }

    // CU-16 step 7-8 and the WebSocket close codes: whoever the party ended for goes back to
    // the main screen with a message instead of staying on a dead screen.
    void _alCambiar() {
        final mensaje = switch (_sesion.cierre) {
            WsMotivoCierre.partyFinalizada => 'La party ha finalizado',
            WsMotivoCierre.sinAcceso => 'Ya no estás en esta party',
            WsMotivoCierre.partyNoExiste => 'Esta party no existe',
            _ => null,
        };
        if (mensaje != null && !_saliendo) {
            _saliendo = true;
            WidgetsBinding.instance.addPostFrameCallback((_) => widget.onLeave(mensaje));
        }
    }

    bool get _esMovil => Theme.of(context).platform == TargetPlatform.android;

    Future<bool> _confirmar(String texto, String accion) async {
        final si = await showDialog<bool>(
            context: context,
            builder: (contexto) => AlertDialog(
                content: Text(texto),
                actions: [
                    TextButton(onPressed: () => Navigator.of(contexto).pop(false), child: const Text('Cancelar')),
                    FilledButton(onPressed: () => Navigator.of(contexto).pop(true), child: Text(accion)),
                ],
            ),
        );
        return si ?? false;
    }

    Future<void> _salir() async {
        if (!await _confirmar('¿Deseas salir de la party?', _esMovil ? 'Salir' : 'Confirmar salida')) return;
        _saliendo = true;
        final mensaje = await _sesion.salir();
        widget.onLeave(mensaje);
    }

    Future<void> _finalizar() async {
        const texto = '¿Deseas finalizar la party? La reproducción compartida terminará para todos los participantes';
        if (!await _confirmar(texto, _esMovil ? 'Finalizar' : 'Finalizar para todos')) return;
        _saliendo = true;
        final mensaje = await _sesion.finalizar();
        if (_sesion.cierre == WsMotivoCierre.partyFinalizada) {
            widget.onLeave(mensaje);
        } else {
            _saliendo = false;
            _mostrar(mensaje);
        }
    }

    @override
    void dispose() {
        _sesion.removeListener(_alCambiar);
        _sesion.dispose();
        super.dispose();
    }

    void _mostrar(String mensaje) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(mensaje)));
    }

    void _abrirCatalogo() {
        Navigator.of(context).push(MaterialPageRoute<void>(
            builder: (_) => AgregarCancionScreen(buscar: _sesion.buscarCanciones!, agregar: _sesion.agregar),
        ));
    }

    Future<void> _cambiarPermisos(MiembroParty miembro, bool aportar, bool modificar) async {
        _mostrar(await _sesion.cambiarPermisos(miembro, puedeAportar: aportar, puedeModificarCola: modificar));
    }

    @override
    Widget build(BuildContext context) {
        return ListenableBuilder(
            listenable: _sesion,
            builder: (context, _) => ListView(
                padding: const EdgeInsets.all(24),
                children: [
                    Text(_sesion.party.nombre, style: Theme.of(context).textTheme.headlineMedium),
                    const SizedBox(height: 8),
                    _Conexion(estado: _sesion.conexion, cierre: _sesion.cierre),
                    if (_sesion.cambioAnfitrion case final cambio?) ...[
                        const SizedBox(height: 8),
                        _AvisoAnfitrion(nuevo: cambio.nuevo, anteriorDesconectado: cambio.anteriorDesconectado, movil: _esMovil),
                    ],
                    const SizedBox(height: 16),
                    if (_sesion.party.codigo != null)
                        ListTile(
                            leading: const Icon(Icons.vpn_key_outlined),
                            title: const Text('Código de invitación'),
                            subtitle: Text(_sesion.party.codigo!),
                            trailing: IconButton(
                                tooltip: 'Copiar código',
                                onPressed: () => copyPartyCode(context, _sesion.party.codigo!),
                                icon: const Icon(Icons.copy_outlined),
                            ),
                        ),
                    if (_sesion.aviso != null) _Aviso(texto: _sesion.aviso!),
                    if (_sesion.errorAudio != null)
                        _Aviso(texto: _sesion.errorAudio!, accion: 'Reintentar', alPresionar: _sesion.reintentarAudio),
                    _Sonando(sesion: _sesion),
                    const Divider(height: 32),
                    Row(
                        children: [
                            Expanded(child: Text('Siguen en la cola', style: Theme.of(context).textTheme.titleMedium)),
                            // Hidden instead of disabled without permission (T-56: hide controls by permission).
                            if (_sesion.puedeAportar && _sesion.buscarCanciones != null)
                                TextButton.icon(
                                    onPressed: _sesion.conectada ? _abrirCatalogo : null,
                                    icon: const Icon(Icons.add),
                                    label: const Text('Agregar canción'),
                                ),
                        ],
                    ),
                    if (_sesion.cola.pendientes.isEmpty)
                        const ListTile(title: Text('La cola está vacía.')),
                    for (final (i, e) in _sesion.cola.pendientes.indexed)
                        ListTile(leading: Text('${i + 1}'), title: Text(nombreCancion(e.recursoAudioId))),
                    const Divider(height: 32),
                    Text('Participantes', style: Theme.of(context).textTheme.titleMedium),
                    for (final m in _sesion.party.miembros)
                        _Participante(
                            miembro: m,
                            esAnfitrion: m.usuarioId == _sesion.party.anfitrionId,
                            // P-07 only for the host, and never on the host's own row (contract 4.4).
                            permisos: _sesion.esAnfitrion && m.usuarioId != _sesion.party.anfitrionId && _sesion.conectada
                                ? (aportar, modificar) => _cambiarPermisos(m, aportar, modificar)
                                : null,
                        ),
                    const Divider(height: 32),
                    ListTile(
                        leading: const Icon(Icons.mic_none),
                        title: const Text('Sala de voz'),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const VoiceScreen())),
                    ),
                    const SizedBox(height: 16),
                    Wrap(
                        spacing: 12,
                        runSpacing: 12,
                        children: [
                            OutlinedButton.icon(
                                onPressed: _salir,
                                icon: const Icon(Icons.exit_to_app),
                                label: const Text('Salir de la party'),
                            ),
                            if (_sesion.esAnfitrion)
                                OutlinedButton.icon(
                                    onPressed: _finalizar,
                                    icon: const Icon(Icons.stop_circle_outlined),
                                    label: const Text('Finalizar party'),
                                ),
                        ],
                    ),
                ],
            ),
        );
    }
}

/// TODO(T-14): the song title comes from music (contract 3.2); until then a short id.
String nombreCancion(String recursoAudioId) => 'Canción ${recursoAudioId.substring(0, recursoAudioId.length.clamp(0, 8))}';

class _Sonando extends StatelessWidget {
    const _Sonando({required this.sesion});

    final SesionParty sesion;

    @override
    Widget build(BuildContext context) {
        final reproduccion = sesion.reproduccion;
        final hayActual = reproduccion.recursoAudioId != null;
        final habilitado = sesion.conectada;
        final estado = switch (reproduccion.estado) {
            'reproduciendo' => 'Sonando',
            'pausada' => 'En pausa',
            _ => 'Nada sonando',
        };

        return Card(
            child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                        Text(estado, style: const TextStyle(color: AppColors.muted)),
                        const SizedBox(height: 4),
                        Text(hayActual ? nombreCancion(reproduccion.recursoAudioId!) : '—',
                             style: Theme.of(context).textTheme.titleLarge),
                        const SizedBox(height: 12),
                        Wrap(
                            spacing: 8,
                            children: [
                                if (sesion.esAnfitrion && !hayActual)
                                    FilledButton.icon(
                                        onPressed: habilitado && sesion.cola.pendientes.isNotEmpty ? () => sesion.controlar('iniciar') : null,
                                        icon: const Icon(Icons.play_arrow),
                                        label: const Text('Iniciar'),
                                    ),
                                if (sesion.esAnfitrion && reproduccion.sonando)
                                    FilledButton.icon(
                                        onPressed: habilitado ? () => sesion.controlar('pausar') : null,
                                        icon: const Icon(Icons.pause),
                                        label: const Text('Pausar'),
                                    ),
                                if (sesion.esAnfitrion && reproduccion.estado == 'pausada')
                                    FilledButton.icon(
                                        onPressed: habilitado ? () => sesion.controlar('reanudar') : null,
                                        icon: const Icon(Icons.play_arrow),
                                        label: const Text('Reanudar'),
                                    ),
                                if (sesion.puedeSaltar && hayActual)
                                    OutlinedButton.icon(
                                        onPressed: habilitado ? () => sesion.controlar('saltar') : null,
                                        icon: const Icon(Icons.skip_next),
                                        label: const Text('Saltar'),
                                    ),
                            ],
                        ),
                    ],
                ),
            ),
        );
    }
}

class _Conexion extends StatelessWidget {
    const _Conexion({required this.estado, required this.cierre});

    final WsEstado estado;
    final WsMotivoCierre? cierre;

    @override
    Widget build(BuildContext context) {
        final (texto, color) = switch (cierre) {
            WsMotivoCierre.partyFinalizada => ('La party terminó', AppColors.muted),
            WsMotivoCierre.sinAcceso => ('Ya no estás en esta party', Colors.redAccent),
            WsMotivoCierre.partyNoExiste => ('Esta party no existe', Colors.redAccent),
            WsMotivoCierre.sesionInvalida => ('Tu sesión terminó', Colors.redAccent),
            null => switch (estado) {
                WsEstado.conectado => ('Conectado', AppColors.success),
                WsEstado.conectando => ('Conectando…', Colors.orangeAccent),
                _ => ('Sin conexión, modificaciones deshabilitadas', Colors.orangeAccent),
            },
        };
        return Row(children: [StatusDot(color: color), const SizedBox(width: 8), Text(texto, style: TextStyle(color: color))]);
    }
}

class _Participante extends StatelessWidget {
    const _Participante({required this.miembro, required this.esAnfitrion, this.permisos});

    final MiembroParty miembro;
    final bool esAnfitrion;

    /// Solo para el anfitrión (P-07): recibe los dos permisos nuevos.
    final void Function(bool puedeAportar, bool puedeModificarCola)? permisos;

    @override
    Widget build(BuildContext context) {
        final nombre = miembro.nombreVisible;
        return ListTile(
            leading: StatusDot(color: miembro.conectado ? AppColors.success : AppColors.muted),
            title: Text(esAnfitrion ? '$nombre (anfitrión)' : nombre),
            // Chips under the name instead of as trailing: two chips overflow a 360 px phone row.
            subtitle: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                    Text(miembro.conectado ? 'Conectado' : 'Desconectado'),
                    if (permisos != null)
                        Wrap(
                            spacing: 8,
                            children: [
                                // Granting needs the member connected (CU-13); taking away does not (CU-14).
                                FilterChip(
                                    label: const Text('Agregar canciones'),
                                    selected: miembro.puedeAportar,
                                    onSelected: miembro.conectado || miembro.puedeAportar
                                        ? (valor) => permisos!(valor, miembro.puedeModificarCola) : null,
                                ),
                                FilterChip(
                                    label: const Text('Modificar la cola'),
                                    selected: miembro.puedeModificarCola,
                                    onSelected: miembro.conectado || miembro.puedeModificarCola
                                        ? (valor) => permisos!(miembro.puedeAportar, valor) : null,
                                ),
                            ],
                        ),
                ],
            ),
        );
    }
}

class _Aviso extends StatelessWidget {
    const _Aviso({required this.texto, this.accion, this.alPresionar});

    final String texto;
    final String? accion;
    final VoidCallback? alPresionar;

    @override
    Widget build(BuildContext context) {
        return Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Row(
                children: [
                    Expanded(child: Text(texto, style: TextStyle(color: Theme.of(context).colorScheme.error))),
                    if (accion != null) TextButton(onPressed: alPresionar, child: Text(accion!)),
                ],
            ),
        );
    }
}

class _AvisoAnfitrion extends StatelessWidget {
    const _AvisoAnfitrion({required this.nuevo, required this.anteriorDesconectado, required this.movil});

    final String nuevo;
    final bool anteriorDesconectado;
    final bool movil;

    @override
    Widget build(BuildContext context) {
        final texto = anteriorDesconectado && !movil
            ? 'Anfitrión desconectado: $nuevo es el sucesor por orden de ingreso'
            : 'Nuevo anfitrión: $nuevo';
        return Row(children: [
            const Icon(Icons.info_outline, size: 18, color: AppColors.muted),
            const SizedBox(width: 8),
            Expanded(child: Text(texto)),
        ]);
    }
}
