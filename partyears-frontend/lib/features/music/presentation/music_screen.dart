import 'package:flutter/material.dart';

import '../../queue/presentation/queue_screen.dart';

class MusicScreen extends StatefulWidget {
  const MusicScreen({super.key});

  @override
  State<MusicScreen> createState() => _MusicScreenState();
}

class _MusicScreenState extends State<MusicScreen> {
  bool _isHost = true;
  double _progress = 102;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Wrap(
          alignment: WrapAlignment.spaceBetween,
          crossAxisAlignment: WrapCrossAlignment.center,
          spacing: 12,
          runSpacing: 12,
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('SONIDO SINCRONIZADO', style: textTheme.labelMedium),
                const SizedBox(height: 4),
                Text('Reproductor', style: textTheme.headlineMedium),
                const SizedBox(height: 8),
                const Text(
                  'La reproducción se sincroniza entre todos los miembros de la Party.',
                ),
              ],
            ),
            Chip(
              avatar: const Icon(Icons.verified_user_outlined, size: 18),
              label: Text(_isHost ? 'ERES ANFITRIÓN' : 'PARTICIPANTE'),
            ),
          ],
        ),
        const SizedBox(height: 24),

        
        Card(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Chip(label: Text('REPRODUCIENDO · Noche electrónica')),
                    const Chip(
                      avatar: Icon(Icons.people_outline, size: 16),
                      label: Text('4 escuchando'),
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                const Icon(Icons.album, size: 96),
                const SizedBox(height: 16),
                Text(
                  'AHORA SUENA',
                  textAlign: TextAlign.center,
                  style: textTheme.labelMedium,
                ),
                const SizedBox(height: 4),
                Text(
                  'Midnight City',
                  textAlign: TextAlign.center,
                  style: textTheme.headlineSmall,
                ),
                Text(
                  'M83',
                  textAlign: TextAlign.center,
                  style: textTheme.titleMedium,
                ),
                const SizedBox(height: 16),
                Slider(
                  value: _progress,
                  max: 243,
                  onChanged: _isHost
                      ? (val) => setState(() => _progress = val)
                      : null,
                ),
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 16),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('1:42'),
                      Text('4:03'),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    IconButton(
                      onPressed: _isHost ? () {} : null,
                      icon: const Icon(Icons.skip_previous),
                    ),
                    const SizedBox(width: 16),
                    FilledButton(
                      onPressed: _isHost ? () {} : null,
                      style: FilledButton.styleFrom(
                        shape: const CircleBorder(),
                        padding: const EdgeInsets.all(16),
                      ),
                      child: const Icon(Icons.pause),
                    ),
                    const SizedBox(width: 16),
                    IconButton(
                      onPressed: _isHost ? () {} : null,
                      icon: const Icon(Icons.skip_next),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Text(
                  _isHost
                      ? 'Como anfitrión, puedes controlar la reproducción.'
                      : 'Solo el anfitrión puede pausar o cambiar la pista.',
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),

       
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('Siguiente en la cola', style: textTheme.titleMedium),
                    TextButton.icon(
                      onPressed: () => Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) => const QueueScreen(),
                        ),
                      ),
                      icon: const Icon(Icons.arrow_forward, size: 16),
                      label: const Text('Ver cola'),
                    ),
                  ],
                ),
                const ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: CircleAvatar(child: Icon(Icons.music_note)),
                  title: Text('Blinding Lights'),
                  subtitle: Text('The Weeknd · 3:20'),
                  trailing: Icon(Icons.add),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),

    
        Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Permisos de reproducción', style: textTheme.titleMedium),
                const SizedBox(height: 8),
                const Text(
                  'El anfitrión controla reproducir, pausar y cambiar de canción. Los participantes pueden consultar la pista y votar saltos.',
                ),
                const SizedBox(height: 16),
                OutlinedButton.icon(
                  onPressed: () => setState(() => _isHost = !_isHost),
                  icon: const Icon(Icons.swap_horiz),
                  label: Text(
                    _isHost
                        ? 'Demo: cambiar a participante'
                        : 'Demo: cambiar a anfitrión ',
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}