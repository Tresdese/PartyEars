import 'package:flutter/material.dart';

import '../../../app/navigation/main_shell.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/network/red.dart';
import 'login_screen.dart';

class RegisterScreen extends StatefulWidget {
    const RegisterScreen({super.key});

    @override
    State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
    final _campos = {
        for (final c in ['nombre_usuario', 'correo', 'contrasena', 'confirmacion']) c: TextEditingController(),
    };
    Map<String, dynamic> _errores = {};
    bool _enviando = false;

    @override
    void dispose() {
        for (final c in _campos.values) {
            c.dispose();
        }
        super.dispose();
    }

    // CU-01, then CU-02 with the same data: asking to log in right after signing up is a step
    // the person would always take.
    Future<void> _registrar() async {
        setState(() {
            _enviando = true;
            _errores = {};
        });
        try {
            await Red.instancia.api.post(Servicio.auth, '/registro', autenticado: false, cuerpo: {
                for (final e in _campos.entries) e.key: e.value.text,
            });
            await iniciarSesion(_campos['correo']!.text, _campos['contrasena']!.text);
            if (!mounted) return;
            Navigator.of(context).pushAndRemoveUntil(
                MaterialPageRoute<void>(builder: (_) => const MainShell()),
                (_) => false,
            );
        } on ApiException catch (e) {
            if (!mounted) return;
            setState(() => _errores = e.detalles ?? {});
            if (e.detalles == null) {
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.mensaje)));
            }
        } finally {
            if (mounted) setState(() => _enviando = false);
        }
    }

    // Field errors come as {"campo": ["mensaje", ...]} (contract 1.4).
    String? _error(String campo) {
        final mensajes = _errores[campo];
        return mensajes is List && mensajes.isNotEmpty ? mensajes.join(' ') : null;
    }

    Widget _campo(String campo, String etiqueta, {bool oculto = false, TextInputType? teclado}) {
        return Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: TextField(
                controller: _campos[campo],
                obscureText: oculto,
                keyboardType: teclado,
                decoration: InputDecoration(labelText: etiqueta, errorText: _error(campo)),
            ),
        );
    }

    @override
    Widget build(BuildContext context) {
        return Scaffold(
            appBar: AppBar(title: const Text('Crear cuenta')),
            body: Center(
                child: SingleChildScrollView(
                    padding: const EdgeInsets.all(24),
                    child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 420),
                        child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                                _campo('nombre_usuario', 'Nombre de usuario'),
                                _campo('correo', 'Correo electrónico', teclado: TextInputType.emailAddress),
                                _campo('contrasena', 'Contraseña (mínimo 10 caracteres)', oculto: true),
                                _campo('confirmacion', 'Confirmar contraseña', oculto: true),
                                const SizedBox(height: 8),
                                FilledButton(
                                    onPressed: _enviando ? null : _registrar,
                                    child: const Text('Registrarse'),
                                ),
                            ],
                        ),
                    ),
                ),
            ),
        );
    }
}
