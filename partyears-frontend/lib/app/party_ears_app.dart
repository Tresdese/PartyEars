import 'package:flutter/material.dart';

import '../core/network/red.dart';
import '../core/theme/app_theme.dart';
import '../features/auth/presentation/login_screen.dart';
import 'navigation/main_shell.dart';

class PartyEarsApp extends StatelessWidget {
  const PartyEarsApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'PartyEars',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark,
      // Straight in when tokens are saved: Android may kill the app in the middle of a party.
      home: FutureBuilder<bool>(
        future: Red.instancia.api.haySesion(),
        builder: (context, sesion) => switch (sesion.data) {
          null => const Scaffold(),
          true => const MainShell(),
          false => const LoginScreen(),
        },
      ),
    );
  }
}
