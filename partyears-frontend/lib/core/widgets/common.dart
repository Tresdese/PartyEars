import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../theme/app_theme.dart';

bool isCompact(BuildContext context) => MediaQuery.sizeOf(context).width < 700;

void copyPartyCode(BuildContext context, String code) {
  Clipboard.setData(ClipboardData(text: code));
  ScaffoldMessenger.of(context).showSnackBar(
    const SnackBar(content: Text('Código copiado')),
  );
}

class AppLogo extends StatelessWidget {
  const AppLogo({super.key});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(
            gradient: AppColors.primaryGradient,
            borderRadius: BorderRadius.circular(10),
          ),
          child: const Icon(Icons.headphones, size: 20, color: Colors.white),
        ),
        const SizedBox(width: 10),
        const Flexible(
          child: Text.rich(
            TextSpan(
              children: [
                TextSpan(text: 'Party'),
                TextSpan(
                  text: 'Ears',
                  style: TextStyle(color: AppColors.primaryLight),
                ),
              ],
            ),
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w800,
              letterSpacing: -0.5,
            ),
          ),
        ),
      ],
    );
  }
}

class PageHeader extends StatelessWidget {
  const PageHeader({
    super.key,
    required this.eyebrow,
    required this.title,
    required this.subtitle,
  });

  final String eyebrow;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          eyebrow.toUpperCase(),
          style: const TextStyle(
            color: AppColors.primaryLight,
            fontSize: 11,
            fontWeight: FontWeight.w700,
            letterSpacing: 3,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          title,
          style: const TextStyle(
            fontSize: 30,
            fontWeight: FontWeight.w800,
            letterSpacing: -0.5,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          subtitle,
          style: const TextStyle(color: AppColors.muted, fontSize: 14),
        ),
      ],
    );
  }
}

class AlbumCover extends StatelessWidget {
  const AlbumCover({super.key, required this.color, this.size = 44});

  final Color color;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(8),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [color, Color.lerp(color, Colors.black, 0.5)!],
        ),
      ),
      child: Icon(
        Icons.album_outlined,
        size: size * 0.35,
        color: Colors.white70,
      ),
    );
  }
}

class WaveBars extends StatelessWidget {
  const WaveBars({super.key, this.barWidth = 6, this.maxHeight = 84});

  final double barWidth;
  final double maxHeight;

  static const _heights = [
    0.15, 0.6, 1.0, 0.5, 0.2, 0.55, 0.95, 0.85, 0.3, 0.25, 0.9, 0.95, 0.5,
    0.2, 0.8, 1.0, 0.5, 0.15, 0.5, 1.0, 0.7, 0.2, 0.55, 0.95, 0.8, 0.3,
    0.25, 0.9, 0.95,
  ];

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (final h in _heights)
          Container(
            width: barWidth,
            height: maxHeight * h,
            margin: EdgeInsets.symmetric(horizontal: barWidth * 0.6),
            decoration: BoxDecoration(
              gradient: AppColors.waveGradient,
              borderRadius: BorderRadius.circular(barWidth),
            ),
          ),
      ],
    );
  }
}

class StatusBadge extends StatelessWidget {
  const StatusBadge({super.key, required this.label, this.icon});

  final String label;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.success.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 14, color: AppColors.success),
            const SizedBox(width: 6),
          ],
          Text(
            label.toUpperCase(),
            style: const TextStyle(
              color: AppColors.success,
              fontSize: 11,
              fontWeight: FontWeight.w700,
              letterSpacing: 1,
            ),
          ),
        ],
      ),
    );
  }
}

class StatusDot extends StatelessWidget {
  const StatusDot({super.key, this.color = AppColors.success});

  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 7,
      height: 7,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
    );
  }
}
