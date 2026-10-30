import 'package:flutter/material.dart';

import '../../../app/navigation/main_shell.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/common.dart';
import 'register_screen.dart';

class LoginScreen extends StatelessWidget {
  const LoginScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final compact = isCompact(context);
    return Scaffold(
      body: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (!compact) const Expanded(flex: 8, child: _BrandPanel()),
          Expanded(
            flex: 7,
            child: Center(
              child: SingleChildScrollView(
                padding: EdgeInsets.all(compact ? 24 : 40),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 410),
                  child: const _LoginForm(),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _BrandPanel extends StatelessWidget {
  const _BrandPanel();

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: RadialGradient(
          center: Alignment(-0.1, 0),
          radius: 1.0,
          colors: [Color(0xFF34265E), Color(0xFF15122A)],
        ),
      ),
      child: Stack(
        children: [
          for (final size in [760.0, 600.0, 460.0])
            OverflowBox(
              alignment: const Alignment(-0.1, -0.05),
              maxWidth: double.infinity,
              maxHeight: double.infinity,
              child: Container(
                width: size,
                height: size,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: Colors.white.withValues(alpha: 0.03),
                ),
              ),
            ),
          Padding(
            padding: const EdgeInsets.fromLTRB(64, 40, 64, 40),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const AppLogo(),
                Expanded(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.06),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: const Text(
                          'MÚSICA · AMIGOS · VOZ',
                          style: TextStyle(
                            color: Color(0xFFD8CCFF),
                            fontSize: 11,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                      const SizedBox(height: 20),
                      const Text(
                        'Escucha la música.',
                        style: _headlineStyle,
                      ),
                      Text(
                        'Vive el momento.',
                        style: _headlineStyle.copyWith(
                          color: AppColors.primaryLight,
                        ),
                      ),
                      const SizedBox(height: 20),
                      ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 380),
                        child: const Text(
                          'Tu espacio para escuchar canciones, crear salas y '
                          'conectar por voz con quienes más disfrutas.',
                          style: TextStyle(
                            color: Color(0xFFC4C0D8),
                            fontSize: 15,
                            height: 1.5,
                          ),
                        ),
                      ),
                      const SizedBox(height: 40),
                      const WaveBars(),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  static const _headlineStyle = TextStyle(
    fontSize: 52,
    fontWeight: FontWeight.w800,
    letterSpacing: -1.5,
    height: 1.05,
  );
}

class _LoginForm extends StatelessWidget {
  const _LoginForm();

  void _showPending(BuildContext context, String message) {
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    const labelStyle = TextStyle(fontSize: 12, fontWeight: FontWeight.w600);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (isCompact(context)) ...[
          const AppLogo(),
          const SizedBox(height: 32),
        ],
        const PageHeader(
          eyebrow: 'Bienvenido a PartyEars',
          title: 'Inicia sesión',
          subtitle: 'Ingresa para volver a tu música y tus Parties.',
        ),
        const SizedBox(height: 32),
        const Text('Correo electrónico', style: labelStyle),
        const SizedBox(height: 8),
        const TextField(
          keyboardType: TextInputType.emailAddress,
          decoration: InputDecoration(hintText: 'tu@correo.com'),
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            const Text('Contraseña', style: labelStyle),
            const Spacer(),
            TextButton(
              onPressed: () => _showPending(
                  context, 'Recuperar contraseña requiere el backend'),
              child: const Text('¿La olvidaste?',
                  style: TextStyle(fontSize: 12)),
            ),
          ],
        ),
        const TextField(
          obscureText: true,
          decoration: InputDecoration(hintText: '••••••••'),
        ),
        const SizedBox(height: 24),
        FilledButton(
          onPressed: () {
            Navigator.of(context).pushReplacement(
              MaterialPageRoute<void>(builder: (_) => const MainShell()),
            );
          },
          child: const Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('Entrar a PartyEars'),
              SizedBox(width: 8),
              Icon(Icons.arrow_forward, size: 18),
            ],
          ),
        ),
        const SizedBox(height: 24),
        Stack(
          alignment: Alignment.center,
          children: [
            const Divider(),
            Container(
              color: AppColors.background,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: const Text(
                'Acceso de demostración · sin backend',
                textAlign: TextAlign.center,
                style: TextStyle(color: AppColors.muted, fontSize: 11),
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),
        Wrap(
          alignment: WrapAlignment.center,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            const Text(
              '¿Aún no tienes cuenta?',
              style: TextStyle(color: AppColors.muted, fontSize: 13),
            ),
            TextButton(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => const RegisterScreen(),
                ),
              ),
              child: const Text('Crear una cuenta'),
            ),
          ],
        ),
      ],
    );
  }
}
