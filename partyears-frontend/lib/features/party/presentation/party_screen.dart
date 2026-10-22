import 'package:flutter/material.dart';

import '../../queue/presentation/queue_screen.dart';
import '../../voice/presentation/voice_screen.dart';

class PartyScreen extends StatelessWidget {
  const PartyScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Text('Tus parties', style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Crear Party requiere el backend')),
          ),
          icon: const Icon(Icons.add),
          label: const Text('Crear Party (demo)'),
        ),
        const SizedBox(height: 12),
        const TextField(
          maxLength: 6,
          textCapitalization: TextCapitalization.characters,
          decoration: InputDecoration(
            labelText: 'Código de invitación',
            hintText: 'ABC123',
          ),
        ),
        OutlinedButton(
          onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Unirse requiere el backend')),
          ),
          child: const Text('Unirse a una Party (demo)'),
        ),
        const Divider(height: 40),
        const Text('Vistas internas de una Party (solo prototipos)'),
        const SizedBox(height: 12),
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
      ],
    );
  }
}
