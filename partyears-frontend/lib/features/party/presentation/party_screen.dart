import 'package:flutter/material.dart';

import '../../../core/widgets/common.dart';
import '../../queue/presentation/queue_screen.dart';
import '../../voice/presentation/voice_screen.dart';

class PartyScreen extends StatefulWidget {
  const PartyScreen({
    super.key,
    required this.partyCode,
    required this.onCreate,
    required this.onLeave,
  });

  final String? partyCode;
  final VoidCallback onCreate;
  final VoidCallback onLeave;

  @override
  State<PartyScreen> createState() => _PartyScreenState();
}

class _PartyScreenState extends State<PartyScreen> {
  static final _codeFormat = RegExp(r'^[A-Z0-9]{6}$');

  final _codeController = TextEditingController();

  @override
  void dispose() {
    _codeController.dispose();
    super.dispose();
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  void _join() {
    final code = _codeController.text.trim().toUpperCase();
    _showMessage(_codeFormat.hasMatch(code)
        ? 'Unirse requiere el backend'
        : 'Ingresa un código válido de seis caracteres');
  }

  @override
  Widget build(BuildContext context) {
    final code = widget.partyCode;
    return ListView(
      padding: const EdgeInsets.all(24),
      children: code == null ? _noParty() : _inParty(code),
    );
  }

  List<Widget> _noParty() => [
        Text('Tus parties', style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: widget.onCreate,
          icon: const Icon(Icons.add),
          label: const Text('Crear Party (demo)'),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _codeController,
          maxLength: 6,
          textCapitalization: TextCapitalization.characters,
          decoration: const InputDecoration(
            labelText: 'Código de invitación',
            hintText: 'ABC123',
          ),
          onSubmitted: (_) => _join(),
        ),
        OutlinedButton(
          onPressed: _join,
          child: const Text('Unirse a una Party (demo)'),
        ),
      ];

  List<Widget> _inParty(String code) => [
        Text('Tu party', style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: 16),
        ListTile(
          leading: const Icon(Icons.vpn_key_outlined),
          title: const Text('Código de invitación'),
          subtitle: Text(code),
          trailing: IconButton(
            tooltip: 'Copiar código',
            onPressed: () => copyPartyCode(context, code),
            icon: const Icon(Icons.copy_outlined),
          ),
        ),
        ListTile(
          leading: const Icon(Icons.queue_music),
          title: const Text('Cola de reproducción'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute<void>(builder: (_) => const QueueScreen()),
          ),
        ),
        ListTile(
          leading: const Icon(Icons.mic_none),
          title: const Text('Sala de voz'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute<void>(builder: (_) => const VoiceScreen()),
          ),
        ),
        const Divider(height: 40),
        OutlinedButton.icon(
          onPressed: widget.onLeave,
          icon: const Icon(Icons.exit_to_app),
          label: const Text('Salir de la party (demo)'),
        ),
      ];
}
