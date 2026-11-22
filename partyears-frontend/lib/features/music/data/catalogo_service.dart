import '../../../core/network/api_client.dart';
import '../../../core/network/api_config.dart';

class VarianteAudio {
    const VarianteAudio({required this.recursoAudioId, required this.tipo, required this.disponible});

    final String recursoAudioId;
    final String tipo;
    final bool disponible;
}

class CancionCatalogo {
    const CancionCatalogo({required this.titulo, required this.artistas, required this.duracionMs, required this.variantes});

    factory CancionCatalogo.desdeJson(Map<String, dynamic> json) => CancionCatalogo(
        titulo: json['titulo'] as String,
        artistas: [for (final a in (json['artistas'] as List<dynamic>? ?? const [])) (a as Map)['nombre'] as String],
        duracionMs: (json['duracion_ms'] as num? ?? 0).toInt(),
        variantes: [
            for (final v in (json['variantes'] as List<dynamic>? ?? const []))
                VarianteAudio(recursoAudioId: (v as Map)['recurso_audio_id'] as String, tipo: v['tipo'] as String,
                              disponible: v['disponible'] as bool? ?? false),
        ],
    );

    final String titulo;
    final List<String> artistas;
    final int duracionMs;
    final List<VarianteAudio> variantes;
}

/// Búsqueda del catálogo (contrato 3.1).
class CatalogoService {
    CatalogoService(this._api);

    final ApiClient _api;

    // TODO(T-52): only the first page; P-06 shows up to 20 results until search pages exist.
    Future<List<CancionCatalogo>> buscar(String texto) async {
        final respuesta = await _api.get(Servicio.music, '/canciones', query: {'q': texto, 'pagina': '1'});
        final resultados = respuesta is Map ? respuesta['resultados'] : null;
        return [for (final c in (resultados as List<dynamic>? ?? const [])) CancionCatalogo.desdeJson(Map<String, dynamic>.from(c as Map))];
    }
}
