import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class TokensGuardados {
    const TokensGuardados({
        required this.tokenAcceso,
        required this.tokenRenovacion,
        required this.expiraEn,
    });

    factory TokensGuardados.desdeJson(Map<String, dynamic> json) {
        return TokensGuardados(
            tokenAcceso: json['token_acceso'] as String,
            tokenRenovacion: json['token_renovacion'] as String,
            expiraEn: DateTime.parse(json['expira_en'] as String).toUtc(),
        );
    }

    final String tokenAcceso;
    final String tokenRenovacion;
    final DateTime expiraEn;

    Duration get tiempoRestante => expiraEn.difference(DateTime.now().toUtc());
}

abstract class TokenStore {
    Future<TokensGuardados?> leer();
    Future<void> guardar(TokensGuardados tokens);
    Future<void> borrar();
}

class TokenStoreSeguro implements TokenStore {
    TokenStoreSeguro([FlutterSecureStorage? almacen]) : _almacen = almacen ?? const FlutterSecureStorage();

    final FlutterSecureStorage _almacen;

    static const _kAcceso = 'token_acceso';
    static const _kRenovacion = 'token_renovacion';
    static const _kExpira = 'expira_en';

    @override
    Future<TokensGuardados?> leer() async {
        try {
            final acceso = await _almacen.read(key: _kAcceso);
            final renovacion = await _almacen.read(key: _kRenovacion);
            final expira = DateTime.tryParse(await _almacen.read(key: _kExpira) ?? '');
      
            if (acceso == null || renovacion == null || expira == null) return null;
            
            return TokensGuardados(
                tokenAcceso: acceso,
                tokenRenovacion: renovacion,
                expiraEn: expira.toUtc(),
            );
        } catch (_) {
            await borrar();
            return null;
        }
    }

    @override
    Future<void> guardar(TokensGuardados tokens) async {
        await _almacen.write(key: _kAcceso, value: tokens.tokenAcceso);
        await _almacen.write(key: _kRenovacion, value: tokens.tokenRenovacion);
        await _almacen.write(key: _kExpira, value: tokens.expiraEn.toUtc().toIso8601String(),);
    }

    @override
    Future<void> borrar() async {
        try {
            await _almacen.delete(key: _kAcceso);
            await _almacen.delete(key: _kRenovacion);
            await _almacen.delete(key: _kExpira);
        } catch (_) {}
    }
}

class TokenStoreMemoria implements TokenStore {
    TokensGuardados? _tokens;

    @override
    Future<TokensGuardados?> leer() async => _tokens;

    @override
    Future<void> guardar(TokensGuardados tokens) async => _tokens = tokens;

    @override
    Future<void> borrar() async => _tokens = null;
}