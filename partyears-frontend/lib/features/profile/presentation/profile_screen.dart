import 'package:flutter/material.dart';

import '../../../core/demo_data.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/common.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  static const _email = '$demoUserName@ejemplo.com';

  bool _notifications = true;
  bool _autoplay = true;
  bool _highQuality = false;

  void _showMessage(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
    );
  }

  void _updatePreference(VoidCallback change) {
    setState(change);
    _showMessage('Preferencia actualizada en la demo');
  }

  BoxDecoration get _panelDecoration => BoxDecoration(
        color: AppColors.surface,
        border: Border.all(color: AppColors.border),
        borderRadius: BorderRadius.circular(16),
      );

  @override
  Widget build(BuildContext context) {
    final compact = isCompact(context);
    final gap = compact ? 20.0 : 40.0;
    final account = _buildAccountPanel();
    final preferences = _buildPreferencesPanel();

    return ListView(
      padding: EdgeInsets.fromLTRB(gap, gap, gap, 32),
      children: [
        const PageHeader(
          eyebrow: 'Tu cuenta',
          title: 'Perfil y preferencias',
          subtitle: 'Gestiona la información de tu cuenta y personaliza '
              'PartyEars.',
        ),
        const SizedBox(height: 24),
        if (compact) ...[
          account,
          const SizedBox(height: 20),
          preferences,
        ] else
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(width: 330, child: account),
              const SizedBox(width: 20),
              Expanded(child: preferences),
            ],
          ),
      ],
    );
  }

  Widget _buildAccountPanel() {
    return Container(
      padding: const EdgeInsets.all(28),
      decoration: _panelDecoration,
      child: Column(
        children: [
          Container(
            width: 78,
            height: 78,
            alignment: Alignment.center,
            decoration: const BoxDecoration(
              shape: BoxShape.circle,
              gradient: AppColors.primaryGradient,
            ),
            child: const Text(
              demoUserInitials,
              style: TextStyle(
                color: Colors.white,
                fontSize: 29,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          const SizedBox(height: 14),
          const Text(
            demoUserName,
            style: TextStyle(fontSize: 19, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 2),
          const Text(
            _email,
            style: TextStyle(color: AppColors.muted, fontSize: 12),
          ),
          const SizedBox(height: 12),
          const StatusBadge(label: 'Cuenta activa'),
          const SizedBox(height: 20),
          const Divider(height: 1),
          const _InfoRow(label: 'Miembro desde', value: 'Octubre 2026'),
          const _InfoRow(label: 'Parties creadas', value: '05'),
          const _InfoRow(label: 'Rol actual', value: 'Anfitrión', last: true),
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: () => _showMessage(
                'La edición de perfil requiere la API de autenticación',
              ),
              style: OutlinedButton.styleFrom(
                foregroundColor: AppColors.primaryLight,
                side: const BorderSide(color: Color(0xFF4A4167)),
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
              ),
              icon: const Icon(Icons.person_outline, size: 18),
              label: const Text('Editar perfil'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPreferencesPanel() {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: _panelDecoration,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Preferencias generales',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 2),
          const Text(
            'Ajustes locales de interfaz y reproducción.',
            style: TextStyle(color: AppColors.muted, fontSize: 12),
          ),
          const SizedBox(height: 8),
          _SettingRow(
            title: 'Notificaciones',
            description: 'Avisarme cuando alguien se una a mi Party.',
            trailing: _PrefSwitch(
              value: _notifications,
              onChanged: (v) => _updatePreference(() => _notifications = v),
            ),
          ),
          _SettingRow(
            title: 'Reproducción automática',
            description: 'Continuar con la siguiente canción disponible.',
            trailing: _PrefSwitch(
              value: _autoplay,
              onChanged: (v) => _updatePreference(() => _autoplay = v),
            ),
          ),
          _SettingRow(
            title: 'Audio en alta calidad',
            description: 'Preferir calidad alta cuando la conexión lo permita.',
            trailing: _PrefSwitch(
              value: _highQuality,
              onChanged: (v) => _updatePreference(() => _highQuality = v),
            ),
          ),
          const _SettingRow(
            title: 'Idioma',
            description: 'Idioma principal de la aplicación',
            trailing: _ValuePill(value: 'Español', icon: Icons.language),
          ),
          const _SettingRow(
            title: 'Apariencia',
            description: 'Tema de la interfaz',
            trailing: _ValuePill(value: 'Oscuro'),
            last: true,
          ),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({
    required this.label,
    required this.value,
    this.last = false,
  });

  final String label;
  final String value;
  final bool last;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 14),
      decoration: BoxDecoration(
        border: last
            ? null
            : const Border(bottom: BorderSide(color: AppColors.border)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: const TextStyle(color: AppColors.muted, fontSize: 12),
          ),
          Text(
            value,
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
          ),
        ],
      ),
    );
  }
}

class _SettingRow extends StatelessWidget {
  const _SettingRow({
    required this.title,
    required this.description,
    required this.trailing,
    this.last = false,
  });

  final String title;
  final String description;
  final Widget trailing;
  final bool last;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 12),
      decoration: BoxDecoration(
        border: last
            ? null
            : const Border(bottom: BorderSide(color: AppColors.border)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  description,
                  style: const TextStyle(
                    color: AppColors.muted,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 16),
          trailing,
        ],
      ),
    );
  }
}

class _PrefSwitch extends StatelessWidget {
  const _PrefSwitch({required this.value, required this.onChanged});

  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    return Switch(
      value: value,
      onChanged: onChanged,
      activeThumbColor: Colors.white,
      activeTrackColor: AppColors.primary,
      inactiveThumbColor: Colors.white,
      inactiveTrackColor: const Color(0xFF3B3B52),
      trackOutlineColor: WidgetStateProperty.all(Colors.transparent),
    );
  }
}

class _ValuePill extends StatelessWidget {
  const _ValuePill({required this.value, this.icon});

  final String value;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.background,
        border: Border.all(color: AppColors.border),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(value, style: const TextStyle(fontSize: 12)),
          if (icon != null) ...[
            const SizedBox(width: 6),
            Icon(icon, size: 16, color: AppColors.muted),
          ],
        ],
      ),
    );
  }
}