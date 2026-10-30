import 'package:flutter/material.dart';

import '../../../core/demo_data.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/common.dart';

class VoiceScreen extends StatefulWidget {
  const VoiceScreen({super.key});

  @override
  State<VoiceScreen> createState() => _VoiceScreenState();
}

class _VoiceMember {
  const _VoiceMember({
    required this.initials,
    required this.name,
    required this.role,
    required this.speaking,
    this.isSelf = false,
  });

  final String initials;
  final String name;
  final String role;
  final bool speaking;
  final bool isSelf;
}

class _VoiceScreenState extends State<VoiceScreen> {
  static const _roomName = 'Noche electrónica';

  bool _micOn = false;

  List<_VoiceMember> get _members => [
        _VoiceMember(
          initials: demoUserInitials,
          name: demoUserName,
          role: 'Anfitrión',
          speaking: _micOn,
          isSelf: true,
        ),
        const _VoiceMember(
          initials: 'AM',
          name: 'Ana M.',
          role: 'Participante',
          speaking: true,
        ),
        const _VoiceMember(
          initials: 'LC',
          name: 'Luis C.',
          role: 'Participante',
          speaking: false,
        ),
        const _VoiceMember(
          initials: 'JP',
          name: 'José P.',
          role: 'Participante',
          speaking: true,
        ),
      ];

  void _toggleMic() {
    setState(() => _micOn = !_micOn);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          _micOn ? 'Micrófono activado (demo)' : 'Micrófono silenciado (demo)',
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final members = _members;
    final gap = isCompact(context) ? 20.0 : 40.0;

    return Scaffold(
      appBar: AppBar(title: const Text('Sala de voz')),
      body: ListView(
        padding: EdgeInsets.fromLTRB(gap, gap, gap, 32),
        children: [
          Wrap(
            alignment: WrapAlignment.spaceBetween,
            crossAxisAlignment: WrapCrossAlignment.end,
            spacing: 16,
            runSpacing: 12,
            children: [
              const PageHeader(
                eyebrow: 'Conexión por audio',
                title: 'Sala de voz',
                subtitle:
                    'Habla con los miembros de tu Party en tiempo real, sin cámara.',
              ),
              StatusBadge(
                label: '${members.length} en sala',
                icon: Icons.groups_outlined,
              ),
            ],
          ),
          const SizedBox(height: 24),
          Container(
            padding: const EdgeInsets.all(24),
            decoration: _panelDecoration,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildRoomHeader(),
                const SizedBox(height: 22),
                _buildMembersGrid(members),
                const SizedBox(height: 22),
                _buildMicBar(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  BoxDecoration get _panelDecoration => BoxDecoration(
        color: AppColors.surface,
        border: Border.all(color: AppColors.border),
        borderRadius: BorderRadius.circular(16),
      );

  Widget _buildRoomHeader() {
    return Wrap(
      alignment: WrapAlignment.spaceBetween,
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 12,
      runSpacing: 12,
      children: [
        const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              _roomName,
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
            ),
            SizedBox(height: 2),
            Text(
              'Canal de voz · Código $demoPartyCode',
              style: TextStyle(color: AppColors.muted, fontSize: 12),
            ),
          ],
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: AppColors.background,
            border: Border.all(color: AppColors.border),
            borderRadius: BorderRadius.circular(8),
          ),
          child: const Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              StatusDot(),
              SizedBox(width: 8),
              Text(
                'Canal conectado (demo)',
                style: TextStyle(color: AppColors.success, fontSize: 12),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildMembersGrid(List<_VoiceMember> members) {
    return LayoutBuilder(
      builder: (context, constraints) {
        const spacing = 16.0;
        final columns = constraints.maxWidth >= 640 ? 3 : 2;
        final itemWidth =
            (constraints.maxWidth - spacing * (columns - 1)) / columns;
        return Wrap(
          spacing: spacing,
          runSpacing: spacing,
          children: [
            for (final member in members)
              SizedBox(
                width: itemWidth,
                child: _MemberCard(member: member),
              ),
          ],
        );
      },
    );
  }

  Widget _buildMicBar() {
    return Wrap(
      alignment: WrapAlignment.spaceBetween,
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 16,
      runSpacing: 12,
      children: [
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              _micOn
                  ? 'Tu micrófono está activo'
                  : 'Tu micrófono está silenciado',
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 2),
            Text(
              _micOn
                  ? 'Los demás participantes pueden escucharte.'
                  : 'Actívalo cuando quieras hablar.',
              style: const TextStyle(color: AppColors.muted, fontSize: 12),
            ),
          ],
        ),
        FilledButton.icon(
          onPressed: _toggleMic,
          style: _micOn
              ? FilledButton.styleFrom(
                  backgroundColor: const Color(0xFF4B2B3F),
                  foregroundColor: const Color(0xFFFFBDCA),
                )
              : null,
          icon: Icon(_micOn ? Icons.mic_off_outlined : Icons.mic_none),
          label: Text(_micOn ? 'Silenciar micrófono' : 'Activar micrófono'),
        ),
      ],
    );
  }
}

class _MemberCard extends StatelessWidget {
  const _MemberCard({required this.member});

  final _VoiceMember member;

  @override
  Widget build(BuildContext context) {
    final speaking = member.speaking;

    return Container(
      padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 16),
      decoration: BoxDecoration(
        color: AppColors.background.withValues(alpha: 0.6),
        border: Border.all(
          color: speaking ? AppColors.teal : AppColors.border,
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 62,
            height: 62,
            alignment: Alignment.center,
            decoration: const BoxDecoration(
              shape: BoxShape.circle,
              gradient: AppColors.primaryGradient,
            ),
            child: Text(
              member.initials,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          const SizedBox(height: 10),
          Text(
            member.isSelf ? '${member.name} (Tú)' : member.name,
            textAlign: TextAlign.center,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 4),
          Text(
            member.role,
            style: const TextStyle(color: AppColors.muted, fontSize: 11),
          ),
          const SizedBox(height: 10),
          if (speaking)
            const _SpeakingBars()
          else
            const Icon(
              Icons.mic_off_outlined,
              size: 20,
              color: AppColors.muted,
            ),
        ],
      ),
    );
  }
}

class _SpeakingBars extends StatelessWidget {
  const _SpeakingBars();

  static const _heights = [8.0, 15.0, 11.0, 18.0, 9.0, 13.0, 6.0];

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 20,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          for (final h in _heights)
            Container(
              width: 3,
              height: h,
              margin: const EdgeInsets.symmetric(horizontal: 1.5),
              decoration: BoxDecoration(
                color: AppColors.teal,
                borderRadius: BorderRadius.circular(3),
              ),
            ),
        ],
      ),
    );
  }
}