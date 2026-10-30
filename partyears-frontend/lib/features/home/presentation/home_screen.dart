import 'package:flutter/material.dart';

import '../../../core/demo_data.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/common.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({
    super.key,
    required this.partyCode,
    required this.onOpenParty,
    required this.onExploreMusic,
  });

  final String? partyCode;
  final VoidCallback onOpenParty;
  final VoidCallback onExploreMusic;

  @override
  Widget build(BuildContext context) {
    final compact = isCompact(context);
    final inParty = partyCode != null;
    final gap = compact ? 20.0 : 40.0;
    return ListView(
      padding: EdgeInsets.fromLTRB(gap, gap, gap, 32),
      children: [
        const PageHeader(
          eyebrow: 'Tu espacio musical',
          title: 'Bienvenido a PartyEars',
          subtitle: 'Tu música, tu gente y una sola experiencia compartida.',
        ),
        const SizedBox(height: 28),
        _HeroBanner(
          inParty: inParty,
          onOpenParty: onOpenParty,
          onExploreMusic: onExploreMusic,
        ),
        if (inParty) ...[
          const SizedBox(height: 40),
          const Text('Un vistazo rápido', style: _sectionStyle),
          const SizedBox(height: 16),
          _Stats(compact: compact),
          const SizedBox(height: 40),
          Row(
            children: [
              const Expanded(
                child: Text('Continúa escuchando', style: _sectionStyle),
              ),
              TextButton(
                onPressed: onOpenParty,
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text('Ver Party'),
                    SizedBox(width: 6),
                    Icon(Icons.arrow_forward, size: 18),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _NowPlayingCard(song: demoSongs.first),
        ],
      ],
    );
  }
}

const _sectionStyle = TextStyle(fontSize: 18, fontWeight: FontWeight.w700);

final _cardDecoration = BoxDecoration(
  color: AppColors.surface,
  border: Border.all(color: AppColors.border),
  borderRadius: BorderRadius.circular(14),
);

class _HeroBanner extends StatelessWidget {
  const _HeroBanner({
    required this.inParty,
    required this.onOpenParty,
    required this.onExploreMusic,
  });

  final bool inParty;
  final VoidCallback onOpenParty;
  final VoidCallback onExploreMusic;

  @override
  Widget build(BuildContext context) {
    final compact = isCompact(context);
    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.primary.withValues(alpha: 0.4)),
        gradient: const LinearGradient(
          colors: [Color(0xFF241B42), Color(0xFF3B2C6B)],
        ),
      ),
      child: Stack(
        children: [
          Positioned(
            right: -40,
            top: -60,
            child: Container(
              width: 420,
              height: 420,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.white.withValues(alpha: 0.04),
              ),
            ),
          ),
          if (!compact)
            Positioned(
              right: 70,
              top: 0,
              bottom: 0,
              child: Center(
                child: Transform.rotate(
                  angle: -0.3,
                  child: const WaveBars(barWidth: 5, maxHeight: 110),
                ),
              ),
            ),
          Padding(
            padding: EdgeInsets.all(compact ? 24 : 40),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (inParty) ...[
                  const StatusBadge(
                    label: 'Sala activa',
                    icon: Icons.volume_up_outlined,
                  ),
                  const SizedBox(height: 16),
                ],
                ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 500),
                  child: Text(
                    inParty
                        ? 'La música suena mejor cuando es compartida.'
                        : 'Crea o únete a una Party',
                    style: const TextStyle(
                      fontSize: 30,
                      fontWeight: FontWeight.w800,
                      letterSpacing: -0.5,
                      height: 1.15,
                    ),
                  ),
                ),
                const SizedBox(height: 14),
                ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 440),
                  child: Text(
                    inParty
                        ? 'Crea una party, invita a tus amigos y escuchen las '
                            'mismas canciones en tiempo real.'
                        : 'Crea una sala e invita a tus amigos con un código, '
                            'o ingresa con el código que te compartieron.',
                    style:
                        const TextStyle(color: Color(0xFFD0CDE0), height: 1.4),
                  ),
                ),
                const SizedBox(height: 24),
                Wrap(
                  spacing: 12,
                  runSpacing: 8,
                  children: [
                    FilledButton(
                      onPressed: onOpenParty,
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(inParty ? 'Ir a mi Party' : 'Crear o unirse'),
                          const SizedBox(width: 8),
                          const Icon(Icons.arrow_forward, size: 18),
                        ],
                      ),
                    ),
                    TextButton(
                      onPressed: onExploreMusic,
                      style: TextButton.styleFrom(
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(
                            horizontal: 16, vertical: 18),
                      ),
                      child: const Text('Explorar música'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Stats extends StatelessWidget {
  const _Stats({required this.compact});

  final bool compact;

  @override
  Widget build(BuildContext context) {
    const cards = [
      _StatCard(
        icon: Icons.group_outlined,
        value: demoParticipants,
        label: 'Participantes en tu sala',
      ),
      _StatCard(
        icon: Icons.queue_music,
        value: demoQueueCount,
        label: 'Canciones en cola',
      ),
      _StatCard(
        icon: Icons.mic_none,
        value: demoVoiceMembers,
        label: 'Miembros conectados a voz',
      ),
    ];
    if (compact) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (final card in cards)
            Padding(padding: const EdgeInsets.only(bottom: 12), child: card),
        ],
      );
    }
    return Row(
      children: [
        for (var i = 0; i < cards.length; i++) ...[
          if (i > 0) const SizedBox(width: 18),
          Expanded(child: cards[i]),
        ],
      ],
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({
    required this.icon,
    required this.value,
    required this.label,
  });

  final IconData icon;
  final int value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: _cardDecoration,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 20),
          const SizedBox(height: 12),
          Text(
            value.toString().padLeft(2, '0'),
            style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 6),
          Text(
            label,
            style: const TextStyle(color: AppColors.muted, fontSize: 12),
          ),
        ],
      ),
    );
  }
}

class _NowPlayingCard extends StatelessWidget {
  const _NowPlayingCard({required this.song});

  final Song song;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: _cardDecoration,
      child: Row(
        children: [
          AlbumCover(color: song.color, size: 56),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const StatusBadge(label: 'En curso'),
                const SizedBox(height: 8),
                Text(
                  song.title,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
                Text(
                  song.artist,
                  style: const TextStyle(color: AppColors.muted, fontSize: 12),
                ),
              ],
            ),
          ),
          Text(song.duration, style: const TextStyle(color: AppColors.muted)),
        ],
      ),
    );
  }
}
