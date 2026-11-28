import '../../../core/network/api_client.dart';
import '../../../core/network/api_config.dart';

class VarianteAudio {
    const VarianteAudio({required this.recursoAudioId, required this.tipo, required this.disponible});

    final String recursoAudioId;
    final String tipo;
    final bool disponible;

    bool get esInstrumental => tipo == 'instrumental';
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

    String get nombreArtistas => artistas.join(', ');

    /// RF-25: solo se ofrece la instrumental si el catálogo la tiene.
    VarianteAudio? get original => _variante('original');
    VarianteAudio? get instrumental => _variante('instrumental');

    VarianteAudio? _variante(String tipo) {
        for (final v in variantes) {
            if (v.tipo == tipo && v.disponible) return v;
        }
        return null;
    }
}

/// Una página de la búsqueda (contrato 1.5).
class PaginaCatalogo {
    const PaginaCatalogo({required this.resultados, required this.pagina, required this.totalPaginas, required this.total});

    factory PaginaCatalogo.desdeJson(Map<String, dynamic> json) => PaginaCatalogo(
        resultados: [
            for (final c in (json['resultados'] as List<dynamic>? ?? const []))
                CancionCatalogo.desdeJson(Map<String, dynamic>.from(c as Map)),
        ],
        pagina: (json['pagina'] as num? ?? 1).toInt(),
        totalPaginas: (json['total_paginas'] as num? ?? 0).toInt(),
        total: (json['total'] as num? ?? 0).toInt(),
    );

    final List<CancionCatalogo> resultados;
    final int pagina;
    final int totalPaginas;
    final int total;

    bool get hayMas => pagina < totalPaginas;
}

/// Lo que se muestra de un elemento de cola: la canción y la variante (contrato 3.2).
class DetalleRecurso {
    const DetalleRecurso({required this.recursoAudioId, required this.tipo, required this.titulo, required this.artistas,
                          required this.duracionMs});

    factory DetalleRecurso.desdeJson(Map<String, dynamic> json) {
        final cancion = Map<String, dynamic>.from(json['cancion'] as Map);
        return DetalleRecurso(
            recursoAudioId: json['recurso_audio_id'] as String,
            tipo: json['tipo'] as String,
            titulo: cancion['titulo'] as String,
            artistas: [for (final a in (cancion['artistas'] as List<dynamic>? ?? const [])) (a as Map)['nombre'] as String],
            duracionMs: (cancion['duracion_ms'] as num? ?? 0).toInt(),
        );
    }

    final String recursoAudioId;
    final String tipo;
    final String titulo;
    final List<String> artistas;
    final int duracionMs;

    String get tituloConVariante => tipo == 'instrumental' ? '$titulo (instrumental)' : titulo;
    String get nombreArtistas => artistas.join(', ');
}

/// Búsqueda del catálogo (contrato 3.1) y metadatos de recursos (3.2).
class CatalogoService {
    CatalogoService(this._api);

    final ApiClient _api;

    Future<PaginaCatalogo> buscarPagina(String texto, {int pagina = 1}) async {
        final respuesta = await _api.get(Servicio.music, '/canciones', query: {'q': texto, 'pagina': '$pagina'});
        return PaginaCatalogo.desdeJson(respuesta is Map<String, dynamic> ? respuesta : const {});
    }

    // TODO(T-56): P-06 shows only the first page; switch it to buscarPagina with "Cargar más"
    // like the music screen.
    Future<List<CancionCatalogo>> buscar(String texto) async => (await buscarPagina(texto)).resultados;

    Future<DetalleRecurso> detalle(String recursoAudioId) async {
        final respuesta = await _api.get(Servicio.music, '/recursos/$recursoAudioId');
        return DetalleRecurso.desdeJson(Map<String, dynamic>.from(respuesta as Map));
    }
}
