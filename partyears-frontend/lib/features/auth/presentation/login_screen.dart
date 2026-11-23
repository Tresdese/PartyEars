import 'package:flutter/material.dart';

import '../../../app/navigation/main_shell.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/network/red.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/common.dart';
import '../../party/data/party_service.dart';
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
                  child: FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.centerLeft,
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 6,
                          ),
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
                        const Text('Escucha la música.', style: _headlineStyle),
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

class _LoginForm extends StatefulWidget {
  const _LoginForm();

  @override
  State<_LoginForm> createState() => _LoginFormState();
}

class _LoginFormState extends State<_LoginForm> {
  final _correo = TextEditingController();
  final _contrasena = TextEditingController();
  bool _enviando = false;

  @override
  void dispose() {
    _correo.dispose();
    _contrasena.dispose();
    super.dispose();
  }

  void _showPending(BuildContext context, String message) {
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _cambiarServidor() async {
    final campo = TextEditingController(text: Red.instancia.host);
    final host = await showDialog<String>(
      context: context,
      builder: (contexto) => AlertDialog(
        title: const Text('Servidor de PartyEars'),
        content: TextField(
          controller: campo,
          autofocus: true,
          keyboardType: TextInputType.url,
          decoration: const InputDecoration(
            labelText: 'IP de la máquina con el backend',
            hintText: '10.8.0.6',
          ),
          onSubmitted: (texto) => Navigator.of(contexto).pop(texto),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(contexto).pop(),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(contexto).pop(campo.text),
            child: const Text('Guardar'),
          ),
        ],
      ),
    );
    campo.dispose();
    final limpio = host == null ? '' : hostDeTexto(host);
    if (limpio.isEmpty) return;
    // The saved party code belongs to the old backend's database session.
    await PartyService.olvidar();
    await Red.instancia.cambiarServidor(limpio);
    if (mounted) setState(() {});
  }

  // CU-02: api_client keeps the tokens of a successful /login, so here only navigate.
  Future<void> _entrar() async {
    setState(() => _enviando = true);
    try {
      await iniciarSesion(_correo.text, _contrasena.text);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(builder: (_) => const MainShell()),
      );
    } on ApiException catch (e) {
      if (!mounted) return;
      _showPending(context, e.mensaje);
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    const labelStyle = TextStyle(fontSize: 12, fontWeight: FontWeight.w600);
    return AutofillGroup(
      child: Column(
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
          TextField(
            controller: _correo,
            keyboardType: TextInputType.emailAddress,
            autofillHints: const [AutofillHints.email],
            textInputAction: TextInputAction.next,
            decoration: const InputDecoration(hintText: 'tu@correo.com'),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              const Expanded(child: Text('Contraseña', style: labelStyle)),
              TextButton(
                onPressed: () => _showPending(
                  context,
                  'Recuperar contraseña todavía no está disponible',
                ),
                child: const Text(
                  '¿La olvidaste?',
                  style: TextStyle(fontSize: 12),
                ),
              ),
            ],
          ),
          TextField(
            controller: _contrasena,
            obscureText: true,
            autofillHints: const [AutofillHints.password],
            onSubmitted: (_) => _enviando ? null : _entrar(),
            decoration: const InputDecoration(hintText: '••••••••'),
          ),
          const SizedBox(height: 24),
          FilledButton(
            onPressed: _enviando ? null : _entrar,
            child: const Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Flexible(child: Text('Entrar a PartyEars')),
                SizedBox(width: 8),
                Icon(Icons.arrow_forward, size: 18),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Wrap(
            alignment: WrapAlignment.center,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(
                'Servidor: ${Red.instancia.host}',
                style: const TextStyle(color: AppColors.muted, fontSize: 12),
              ),
              TextButton(
                onPressed: _enviando ? null : _cambiarServidor,
                child: const Text('Cambiar', style: TextStyle(fontSize: 12)),
              ),
            ],
          ),
          const SizedBox(height: 8),
          const Divider(),
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
                  MaterialPageRoute<void>(builder: (_) => const RegisterScreen()),
                ),
                child: const Text('Crear una cuenta'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// Lo que la persona escribe como servidor, reducido al host: acepta "http://10.8.0.6:8001/".
String hostDeTexto(String texto) {
  var host = texto.trim();
  final esquema = host.indexOf('://');
  if (esquema >= 0) host = host.substring(esquema + 3);
  host = host.split('/').first.split(':').first;
  return host.contains(' ') ? '' : host;
}

/// CU-02. Lanza ApiException con el mensaje del servidor si el correo o la contraseña fallan.
Future<void> iniciarSesion(String correo, String contrasena) async {
  await Red.instancia.api.post(
    Servicio.auth,
    '/login',
    cuerpo: {'correo': correo.trim(), 'contrasena': contrasena},
    autenticado: false,
  );
}
