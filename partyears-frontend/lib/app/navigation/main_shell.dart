import 'dart:async';

import 'package:flutter/material.dart';

import '../../core/demo_data.dart';
import '../../core/network/api_exception.dart';
import '../../core/network/red.dart';
import '../../core/theme/app_theme.dart';
import '../../core/widgets/common.dart';
import '../../features/auth/presentation/login_screen.dart';
import '../../features/home/presentation/home_screen.dart';
import '../../features/music/presentation/music_screen.dart';
import '../../features/party/data/party_models.dart';
import '../../features/party/data/party_service.dart';
import '../../features/party/presentation/party_screen.dart';
import '../../features/profile/presentation/profile_screen.dart';

class MainShell extends StatefulWidget {
    const MainShell({super.key});

    @override
    State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
    int _selectedIndex = 0;

    PartyActual? _party;

    // Members get no code from the server (contract 4); the screens that only show the code
    // keep using it, and "in a party" is decided by _party.
    String? get _partyCode => _party?.codigo;

    late final PartyService _partyService = PartyService.fabrica();

    StreamSubscription<void>? _expirada;

    @override
    void initState() {
        super.initState();
        // Back to login instead of failing every call: the saved refresh token stopped working.
        _expirada = Red.instancia.api.sesionExpirada.listen((_) {
            if (mounted) unawaited(_logout());
        });
        _restaurarParty();
    }

    @override
    void dispose() {
        _expirada?.cancel();
        super.dispose();
    }

    Future<void> _restaurarParty() async {
        try {
            var party = await _partyService.actual();
            // The server already closed the participation (app killed for more than 15 s):
            // come back with the saved code, as after any detected disconnection.
            final codigo = party == null ? await PartyService.codigoRecordado() : null;
            if (codigo != null) {
                try {
                    party = await _partyService.unirse(codigo);
                } on ApiException catch (e) {
                    // Expelled, ended or full: the saved code no longer leads anywhere.
                    if (!e.esDeRed) await PartyService.olvidar();
                }
            }

            if (!mounted || party == null) return;

            setState(() => _party = party);
        } on ApiException {
        // Sin sesión o sin conexión: se queda en "sin party".
        }
    }

    Future<void> _crearParty(String nombre, {String? clave}) async {
        final party = await _partyService.crear(nombre, clave: clave);

        if (!mounted) return;

        setState(() => _party = party);
    }

    Future<void> _unirseParty(String codigo, {String? clave}) async {
        final party = await _partyService.unirse(codigo, clave: clave);

        if (!mounted) return;

        setState(() => _party = party);
    }

    // CU-15 step 6 and CU-16 step 8: back to the main screen, with the message if there is one.
    void _salirDeParty(String? mensaje) {
        unawaited(PartyService.olvidar());
        setState(() {
            _party = null;
            _selectedIndex = 0;
        });
        if (mensaje != null) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(mensaje)));
    }

    static const List<({String? section, String label, IconData icon})> _items = [
        (section: 'Descubrir', label: 'Inicio', icon: Icons.home_outlined),
        (section: null, label: 'Música', icon: Icons.music_note_outlined),
        (section: 'Tu experiencia', label: 'Party', icon: Icons.group_outlined),
        (section: 'Cuenta', label: 'Perfil', icon: Icons.person_outline),
    ];

    void _go(int index) => setState(() => _selectedIndex = index);

    // CU-03: revoking on the server instead of only changing screens, or the refresh token
    // would stay valid for 7 days on this device.
    Future<void> _logout() async {
        await PartyService.olvidar();
        await Red.instancia.api.cerrarSesion();
        if (!mounted) return;
        Navigator.of(context).pushAndRemoveUntil(
            MaterialPageRoute<void>(builder: (_) => const LoginScreen()),
            (_) => false,
        );
    }

    @override
    Widget build(BuildContext context) {
        final compact = isCompact(context);

        final content = Column(
            children: [
                _TopBar(
                    title: _items[_selectedIndex].label,
                    partyCode: _partyCode,
                    onLogout: _logout,
                ),
                Expanded(
                    child: IndexedStack(
                        index: _selectedIndex,
                        children: [
                            HomeScreen(
                                partyCode: _partyCode,
                                onOpenParty: () => _go(2),
                                onExploreMusic: () => _go(1),
                            ),
                            MusicScreen(inParty: _party != null),
                            PartyScreen(
                                partyCode: _partyCode,
                                party: _party,
                                onCreate: _crearParty,
                                onJoin: _unirseParty,
                                onLeave: _salirDeParty,
                            ),
                            const ProfileScreen(),
                        ],
                    ),
                ),
                const _MiniPlayer(),
            ],
        );

        if (compact) {
            return Scaffold(
                body: SafeArea(child: content),
                bottomNavigationBar: NavigationBar(
                    selectedIndex: _selectedIndex,
                    onDestinationSelected: _go,
                    destinations: [
                        for (final item in _items)
                        NavigationDestination(icon: Icon(item.icon), label: item.label),
                    ],
                ),
            );
        }

        return Scaffold(
            body: Row(
                children: [
                    _Sidebar(
                        items: _items,
                        selectedIndex: _selectedIndex,
                        onSelect: _go,
                        onLogout: _logout,
                    ),
                    Expanded(child: content),
                ],
            ),
        );
    }
}

class _Sidebar extends StatelessWidget {
    const _Sidebar({
        required this.items,
        required this.selectedIndex,
        required this.onSelect,
        required this.onLogout,
    });

    final List<({String? section, String label, IconData icon})> items;
    final int selectedIndex;
    final ValueChanged<int> onSelect;
    final VoidCallback onLogout;

    @override
    Widget build(BuildContext context) {
        return Container(
            width: 240,
            padding: const EdgeInsets.fromLTRB(12, 28, 12, 12),
            decoration: const BoxDecoration(
                color: AppColors.sidebar,
                border: Border(right: BorderSide(color: AppColors.border)),
            ),
            child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 12),
                    child: AppLogo(),
                ),
                const SizedBox(height: 16),
                for (var i = 0; i < items.length; i++) ...[
                    if (items[i].section != null)
                    Padding(
                        padding: const EdgeInsets.fromLTRB(16, 24, 16, 10),
                        child: Text(
                            items[i].section!.toUpperCase(),
                            style: const TextStyle(
                                color: AppColors.muted,
                                fontSize: 11,
                                fontWeight: FontWeight.w700,
                                letterSpacing: 2,
                            ),
                        ),
                    ),
                    _NavTile(
                    label: items[i].label,
                    icon: items[i].icon,
                    selected: i == selectedIndex,
                    onTap: () => onSelect(i),
                    ),
                ],
                const Spacer(),
                _UserCard(onLogout: onLogout),
                ],
            ),
        );
    }
}

class _NavTile extends StatelessWidget {
    const _NavTile({
        required this.label,
        required this.icon,
        required this.selected,
        required this.onTap,
    });

    final String label;
    final IconData icon;
    final bool selected;
    final VoidCallback onTap;

    @override
    Widget build(BuildContext context) {
        final color = selected ? Colors.white : const Color(0xFFD0D0E0);
        return Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Material(
                color: selected ? AppColors.primary.withValues(alpha: 0.18) : Colors.transparent,
                borderRadius: BorderRadius.circular(10),
                child: InkWell(
                    borderRadius: BorderRadius.circular(10),
                    onTap: onTap,
                    child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                        child: Row(
                            children: [
                                Icon(icon, size: 20, color: color),
                                const SizedBox(width: 12),
                                Expanded(
                                    child: Text(
                                        label,
                                        style: TextStyle(color: color, fontWeight: FontWeight.w500),
                                    ),
                                ),
                            ],
                        ),
                    ),
                ),
            ),
        );
    }
}

class _UserCard extends StatelessWidget {
    const _UserCard({required this.onLogout});

    final VoidCallback onLogout;

    @override
    Widget build(BuildContext context) {
        return Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
                color: AppColors.surface,
                border: Border.all(color: AppColors.border),
                borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
                children: [
                    const _Avatar(),
                    const SizedBox(width: 10),
                    const Expanded(
                        child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisSize: MainAxisSize.min,
                            children: [
                                Text(
                                    demoUserName,
                                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                                ),
                                SizedBox(height: 2),
                                Row(
                                    children: [
                                        StatusDot(),
                                        SizedBox(width: 6),
                                        Flexible(
                                            child: Text(
                                                'Conectado',
                                                style: TextStyle(color: AppColors.muted, fontSize: 11),
                                            ),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ),
                    IconButton(
                        tooltip: 'Cerrar sesión',
                        onPressed: onLogout,
                        icon: const Icon(Icons.logout, size: 20, color: AppColors.muted),
                    ),
                ],
            ),
        );
    }
}

class _Avatar extends StatelessWidget {
    const _Avatar();

    @override
    Widget build(BuildContext context) {
        return const CircleAvatar(
            radius: 16,
            backgroundColor: AppColors.primary,
            child: Text(
                demoUserInitials,
                style: TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                ),
            ),
        );
    }
}

class _TopBar extends StatelessWidget {
    const _TopBar({
        required this.title,
        required this.partyCode,
        required this.onLogout,
    });

    final String title;
    final String? partyCode;
    final VoidCallback onLogout;

    @override
    Widget build(BuildContext context) {
        final compact = isCompact(context);
        final code = partyCode;
        return Container(
            height: compact ? 64 : 80,
            padding: EdgeInsets.symmetric(horizontal: compact ? 16 : 36),
            decoration: const BoxDecoration(
                border: Border(bottom: BorderSide(color: AppColors.border)),
            ),
            child: Row(
                children: [
                    if (!compact) ...[
                        const Text('PartyEars', style: TextStyle(color: AppColors.muted)),
                        const Padding(
                            padding: EdgeInsets.symmetric(horizontal: 10),
                            child: Icon(Icons.chevron_right, size: 18, color: AppColors.muted),
                        ),
                    ],
                    Expanded(
                        child: Text(
                            title,
                            style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                    ),
                    if (code != null) ...[
                        _Pill(
                            onTap: () => copyPartyCode(context, code),
                            child: Row(
                                children: [
                                    const Icon(Icons.copy_outlined, size: 16),
                                    const SizedBox(width: 8),
                                    Text(code, style: const TextStyle(fontSize: 12)),
                                ],
                            ),
                        ),
                        const SizedBox(width: 12),
                    ],
                    if (compact)
                        IconButton(
                            tooltip: 'Cerrar sesión',
                            onPressed: onLogout,
                            icon: const Icon(Icons.logout, size: 20, color: AppColors.muted),
                        )
                    else ...[
                        _Pill(
                            color: AppColors.success.withValues(alpha: 0.08),
                            child: const Row(
                                children: [
                                    StatusDot(),
                                    SizedBox(width: 8),
                                    Text(
                                        'Servicios conectados',
                                        style: TextStyle(color: AppColors.success, fontSize: 12),
                                    ),
                                ],
                            ),
                        ),
                        const SizedBox(width: 12),
                        IconButton(
                            tooltip: 'Notificaciones',
                            onPressed: () {},
                            style: IconButton.styleFrom(
                                side: const BorderSide(color: AppColors.border),
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10),),
                            ),
                            icon: const Icon(Icons.notifications_none, size: 20),
                        ),
                        const SizedBox(width: 12),
                        const _Avatar(),
                    ],
                ],
            ),
        );
    }
}

class _Pill extends StatelessWidget {
    const _Pill({required this.child, this.color = AppColors.surface, this.onTap});

    final Widget child;
    final Color color;
    final VoidCallback? onTap;

    @override
    Widget build(BuildContext context) {
        return Material(
            color: color,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
                side: const BorderSide(color: AppColors.border),
            ),
            child: InkWell(
                onTap: onTap,
                borderRadius: BorderRadius.circular(10),
                child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    child: child,
                ),
            ),
        );
    }
}

class _MiniPlayer extends StatelessWidget {
    const _MiniPlayer();

    @override
    Widget build(BuildContext context) {
        final song = demoSongs.first;
        final compact = isCompact(context);
        return Container(
            height: 68,
            padding: EdgeInsets.symmetric(horizontal: compact ? 16 : 24),
            decoration: const BoxDecoration(
                color: AppColors.sidebar,
                border: Border(top: BorderSide(color: AppColors.border)),
            ),
            child: Row(
                children: [
                    Expanded(
                        child: Row(
                            children: [
                                AlbumCover(color: song.color),
                                const SizedBox(width: 14),
                                Flexible(
                                    child: Column(
                                        mainAxisAlignment: MainAxisAlignment.center,
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                            Text(
                                                song.title,
                                                maxLines: 1,
                                                overflow: TextOverflow.ellipsis,
                                                style: const TextStyle(
                                                    fontSize: 13,
                                                    fontWeight: FontWeight.w600,
                                                ),
                                            ),
                                            Text(
                                                song.artist,
                                                maxLines: 1,
                                                overflow: TextOverflow.ellipsis,
                                                style: const TextStyle(
                                                    color: AppColors.muted,
                                                    fontSize: 11,
                                                ),
                                            ),
                                        ],
                                    ),
                                ),
                            ],
                        ),
                    ),
                    const Icon(Icons.skip_previous_outlined),
                    const SizedBox(width: 16),
                    Container(
                        width: 34,
                        height: 34,
                        decoration: const BoxDecoration(
                        color: AppColors.primary,
                        shape: BoxShape.circle,
                        ),
                        child: const Icon(Icons.pause, size: 18),
                    ),
                    const SizedBox(width: 16),
                    const Icon(Icons.skip_next_outlined),
                    if (!compact) ...[
                        const SizedBox(width: 40),
                        SizedBox(
                        width: 300,
                        child: LinearProgressIndicator(
                            value: 0.42,
                            minHeight: 4,
                            color: AppColors.primaryLight,
                            backgroundColor: AppColors.border,
                            borderRadius: BorderRadius.circular(2),
                        ),
                        ),
                    ],
                    const Expanded(
                        child: Align(
                        alignment: Alignment.centerRight,
                        child: Icon(Icons.volume_up_outlined, color: AppColors.muted),
                        ),
                    ),
                ],
            ),
        );
    }
}
