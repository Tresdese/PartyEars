import 'package:flutter/material.dart';

import '../../features/auth/presentation/login_screen.dart';
import '../../features/home/presentation/home_screen.dart';
import '../../features/music/presentation/music_screen.dart';
import '../../features/party/presentation/party_screen.dart';
import '../../features/profile/presentation/profile_screen.dart';

class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _selectedIndex = 0;

  static const _titles = ['Inicio', 'Música', 'Parties', 'Perfil'];
  static const _screens = [
    HomeScreen(),
    MusicScreen(),
    PartyScreen(),
    ProfileScreen(),
  ];

  static const _destinations = [
    NavigationDestination(icon: Icon(Icons.home_outlined), label: 'Inicio'),
    NavigationDestination(icon: Icon(Icons.library_music_outlined), label: 'Música'),
    NavigationDestination(icon: Icon(Icons.groups_outlined), label: 'Parties'),
    NavigationDestination(icon: Icon(Icons.person_outline), label: 'Perfil'),
  ];

  void _logout() {
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute<void>(builder: (_) => const LoginScreen()),
      (_) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final isDesktop = constraints.maxWidth >= 700;
        return Scaffold(
          appBar: AppBar(
            title: Text('PartyEars · ${_titles[_selectedIndex]}'),
            actions: [
              IconButton(
                tooltip: 'Salir de la demostración',
                onPressed: _logout,
                icon: const Icon(Icons.logout),
              ),
            ],
          ),
          body: Row(
            children: [
              if (isDesktop)
                NavigationRail(
                  selectedIndex: _selectedIndex,
                  onDestinationSelected: (index) =>
                      setState(() => _selectedIndex = index),
                  labelType: NavigationRailLabelType.all,
                  destinations: const [
                    NavigationRailDestination(
                      icon: Icon(Icons.home_outlined),
                      label: Text('Inicio'),
                    ),
                    NavigationRailDestination(
                      icon: Icon(Icons.library_music_outlined),
                      label: Text('Música'),
                    ),
                    NavigationRailDestination(
                      icon: Icon(Icons.groups_outlined),
                      label: Text('Parties'),
                    ),
                    NavigationRailDestination(
                      icon: Icon(Icons.person_outline),
                      label: Text('Perfil'),
                    ),
                  ],
                ),
              Expanded(
                child: IndexedStack(
                  index: _selectedIndex,
                  children: _screens,
                ),
              ),
            ],
          ),
          bottomNavigationBar: isDesktop
              ? null
              : NavigationBar(
                  selectedIndex: _selectedIndex,
                  onDestinationSelected: (index) =>
                      setState(() => _selectedIndex = index),
                  destinations: _destinations,
                ),
        );
      },
    );
  }
}
