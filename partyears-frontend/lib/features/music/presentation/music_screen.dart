import 'package:flutter/material.dart';

import '../../../core/demo_data.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/common.dart';
import '../../queue/presentation/queue_screen.dart';

class MusicScreen extends StatefulWidget {
  const MusicScreen({super.key, required this.inParty});

  final bool inParty;

  @override
  State<MusicScreen> createState() => _MusicScreenState();
}

class _MusicScreenState extends State<MusicScreen> {
  static const _allGenres = 'Todos';
  static const _genres = [
    _allGenres,
    'Electrónica',
    'Pop',
    'Indie',
    'Alternativa',
  ];

  String _genre = _allGenres;
  String _query = '';

  @override
  Widget build(BuildContext context) {
    final query = _query.trim().toLowerCase();
    final songs = demoSongs
        .where(
          (s) =>
              (_genre == _allGenres || s.genre == _genre) &&
              (s.title.toLowerCase().contains(query) ||
                  s.artist.toLowerCase().contains(query)),
        )
        .toList();

    final gap = isCompact(context) ? 20.0 : 40.0;
    return ListView(
      padding: EdgeInsets.fromLTRB(gap, gap, gap, 32),
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            const Expanded(
              child: PageHeader(
                eyebrow: 'Explora y descubre',
                title: 'Catálogo musical',
                subtitle:
                    'Busca canciones, descubre artistas y agrega música '
                    'a tu Party.',
              ),
            ),
            if (widget.inParty)
              FilledButton.icon(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(builder: (_) => const QueueScreen()),
                ),
                icon: const Icon(Icons.queue_music, size: 18),
                label: const Text('Ver cola ($demoQueueCount)'),
              ),
          ],
        ),
        const SizedBox(height: 24),
        TextField(
          onChanged: (value) => setState(() => _query = value),
          decoration: const InputDecoration(
            prefixIcon: Icon(Icons.search, color: AppColors.muted),
            hintText: 'Buscar por canción o artista...',
          ),
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final genre in _genres)
              ChoiceChip(
                label: Text(genre),
                selected: genre == _genre,
                onSelected: (_) => setState(() => _genre = genre),
                showCheckmark: false,
                backgroundColor: AppColors.surface,
                selectedColor: AppColors.primary.withValues(alpha: 0.3),
                side: BorderSide(
                  color: genre == _genre
                      ? AppColors.primaryLight
                      : AppColors.border,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
                labelStyle: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
          ],
        ),
        const SizedBox(height: 36),
        Row(
          children: [
            const Expanded(
              child: Text(
                'Canciones populares',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
              ),
            ),
            Text(
              '${songs.length} ${songs.length == 1 ? 'resultado' : 'resultados'}',
              style: const TextStyle(color: AppColors.muted, fontSize: 12),
            ),
          ],
        ),
        const SizedBox(height: 16),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            color: AppColors.surface,
            border: Border.all(color: AppColors.border),
            borderRadius: BorderRadius.circular(16),
          ),
          child: songs.isEmpty
              ? const Padding(
                  padding: EdgeInsets.all(24),
                  child: Text(
                    'No hay canciones que coincidan.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: AppColors.muted),
                  ),
                )
              : Column(
                  children: [
                    for (var i = 0; i < songs.length; i++) ...[
                      if (i > 0) const Divider(height: 1),
                      _SongRow(song: songs[i]),
                    ],
                  ],
                ),
        ),
      ],
    );
  }
}

class _SongRow extends StatelessWidget {
  const _SongRow({required this.song});

  final Song song;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
      child: Row(
        children: [
          AlbumCover(color: song.color),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  song.title,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  song.artist,
                  style: const TextStyle(color: AppColors.muted, fontSize: 11),
                ),
              ],
            ),
          ),
          Text(
            song.duration,
            style: const TextStyle(color: AppColors.muted, fontSize: 12),
          ),
          const SizedBox(width: 14),
          IconButton(
            tooltip: 'Agregar a la cola',
            onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(
                  'Agregar "${song.title}" a la cola requiere el backend',
                ),
              ),
            ),
            style: IconButton.styleFrom(
              backgroundColor: const Color(0xFF2A2440),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
            icon: const Icon(Icons.add, size: 18),
          ),
        ],
      ),
    );
  }
}
