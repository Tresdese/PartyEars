import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

enum Servicio {
    auth('auth', 8001),
    music('music', 8002),
    party('party', 8003),
    queue('queue', 8004),
    streaming('streaming', 8005);

    const Servicio(this.nombre, this.puertoDesarrollo);

    final String nombre;

    final int puertoDesarrollo;
}

class ApiConfig {
    ApiConfig(Map<Servicio, String> urls) : _urls = Map.unmodifiable(urls);

    factory ApiConfig.desdeHost(String host, {bool seguro = false}) {
        return ApiConfig({for (final s in Servicio.values) s: seguro ? 'https://$host' : 'http://$host:${s.puertoDesarrollo}',});
    }

    static const _clave = 'partyears.urls';
    static const _hostPorDefecto = String.fromEnvironment('PARTYEARS_HOST', defaultValue: 'localhost');

    final Map<Servicio, String> _urls;

    String urlBase(Servicio s) => _urls[s]!;

    Uri rest(Servicio s, String ruta, [Map<String, String>? query]) {
        final uri = Uri.parse('${_sinBarraFinal(urlBase(s))}/api/v1/${s.nombre}$ruta');
        
        return (query == null || query.isEmpty) ? uri : uri.replace(queryParameters: query);
    }

    Uri ws(Servicio s, String ruta) {
        final base = Uri.parse(_sinBarraFinal(urlBase(s)));
        
        return base.replace(scheme: base.scheme == 'https' ? 'wss' : 'ws', path: '/ws/v1/${s.nombre}$ruta',);
    }

    static String _sinBarraFinal(String url) => url.endsWith('/') ? url.substring(0, url.length - 1) : url;

    static Future<ApiConfig> cargar() async {
        final porDefecto = ApiConfig.desdeHost(_hostPorDefecto);

        try {
            final prefs = await SharedPreferences.getInstance();
            final texto = prefs.getString(_clave);
            
            if (texto == null) return porDefecto;
            
            final guardado = jsonDecode(texto) as Map<String, dynamic>;
            
            return ApiConfig({for (final s in Servicio.values) s: (guardado[s.nombre] as String?) ?? porDefecto.urlBase(s),});
        } catch (_) {
            return porDefecto;
        }   
    }

    Future<void> guardar() async {
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString(_clave, jsonEncode({for (final s in Servicio.values) s.nombre: _urls[s]}),
    );
  }
}