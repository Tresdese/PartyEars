import 'dart:convert';

import 'red.dart';

/// Quién inició sesión, leído del token de acceso (contrato 1.3) sin verificar la firma: solo
/// sirve para mostrarlo, el servidor decide todo lo demás.
class UsuarioSesion {
    const UsuarioSesion({required this.id, required this.nombreUsuario});

    final String id;
    final String nombreUsuario;

    String get iniciales {
        final letras = nombreUsuario.replaceAll(RegExp(r'[^A-Za-z0-9]'), '');
        if (letras.isEmpty) return '?';
        return letras.substring(0, letras.length < 2 ? letras.length : 2).toUpperCase();
    }

    static UsuarioSesion? desdeToken(String token) {
        final partes = token.split('.');
        if (partes.length != 3) return null;
        try {
            final datos = jsonDecode(utf8.decode(base64Url.decode(base64Url.normalize(partes[1]))));
            if (datos is! Map || datos['sub'] is! String) return null;
            return UsuarioSesion(id: datos['sub'] as String, nombreUsuario: datos['nombre_usuario'] as String? ?? 'Usuario');
        } on FormatException {
            return null;
        }
    }

    static Future<UsuarioSesion?> actual() async {
        try {
            return desdeToken((await Red.instancia.api.tokensVigentes()).tokenAcceso);
        } on Exception {
            return null;
        }
    }
}
