import 'package:flutter/material.dart';

import '../../../core/network/ws_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/common.dart';
import '../../voice/presentation/voice_screen.dart';
import '../data/party_models.dart';
import '../sesion_party.dart';

/// Pantalla de una party en curso (T-55): canción, cola, participantes y conexión.
class PartyEnCurso extends StatefulWidget {
    const PartyEnCurso({super.key, required this.party, required this.onLeave});

    final PartyActual party;
    final VoidCallback onLeave;

    @override
    State<PartyEnCurso> createState() => _PartyEnCursoState();
}

class _PartyEnCursoState extends State<PartyEnCurso> {
    late final SesionParty _sesion = SesionParty.fabrica(widget.party);

    @override
    void initState() {
        super.initState();
        _sesion.iniciar();
    }

    @override
    void dispose() {
        _sesion.dispose();
        super.dispose();
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
                    Text('Siguen en la cola', style: Theme.of(context).textTheme.titleMedium),
                    if (_sesion.cola.pendientes.isEmpty)
                        const ListTile(title: Text('La cola está vacía.')),
                    for (final (i, e) in _sesion.cola.pendientes.indexed)
                        ListTile(leading: Text('${i + 1}'), title: Text(nombreCancion(e.recursoAudioId))),
                    const Divider(height: 32),
                    Text('Participantes', style: Theme.of(context).textTheme.titleMedium),
                    for (final m in _sesion.party.miembros) _Participante(miembro: m, esAnfitrion: m.usuarioId == _sesion.party.anfitrionId),
                    const Divider(height: 32),
                    ListTile(
                        leading: const Icon(Icons.mic_none),
                        title: const Text('Sala de voz'),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const VoiceScreen())),
                    ),
                    const SizedBox(height: 16),
                    OutlinedButton.icon(
                        onPressed: widget.onLeave,
                        icon: const Icon(Icons.exit_to_app),
                        label: const Text('Salir de la party (demo)'),
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
                _ => ('Sin conexión, reintentando…', Colors.orangeAccent),
            },
        };
        return Row(children: [StatusDot(color: color), const SizedBox(width: 8), Text(texto, style: TextStyle(color: color))]);
    }
}

class _Participante extends StatelessWidget {
    const _Participante({required this.miembro, required this.esAnfitrion});

    final MiembroParty miembro;
    final bool esAnfitrion;

    @override
    Widget build(BuildContext context) {
        final nombre = miembro.nombreUsuario ?? 'Usuario ${miembro.usuarioId.substring(0, miembro.usuarioId.length.clamp(0, 8))}';
        return ListTile(
            leading: StatusDot(color: miembro.conectado ? AppColors.success : AppColors.muted),
            title: Text(esAnfitrion ? '$nombre (anfitrión)' : nombre),
            subtitle: Text(miembro.conectado ? 'Conectado' : 'Desconectado'),
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

