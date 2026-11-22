class ElementoCola {
    const ElementoCola({required this.id, required this.recursoAudioId, required this.estado});

    factory ElementoCola.desdeJson(Map<String, dynamic> json) => ElementoCola(
        id: json['id'] as String,
        recursoAudioId: json['recurso_audio_id'] as String,
        estado: json['estado'] as String,
    );

    final String id;
    final String recursoAudioId;
    final String estado;
}

/// Contrato 5.3. Sin canción actual, [estado] es 'detenida' y los ids son null.
class EstadoReproduccion {
    const EstadoReproduccion({
        required this.version,
        required this.estado,
        required this.posicionBaseMs,
        this.elementoId,
        this.recursoAudioId,
        this.referenciaEn,
    });

    factory EstadoReproduccion.desdeJson(Map<String, dynamic> json) {
        final referencia = json['referencia_en'] as String?;
        return EstadoReproduccion(
            version: (json['version'] as num).toInt(),
            estado: json['estado'] as String,
            posicionBaseMs: (json['posicion_base_ms'] as num? ?? 0).toInt(),
            elementoId: json['elemento_id'] as String?,
            recursoAudioId: json['recurso_audio_id'] as String?,
            referenciaEn: referencia == null ? null : DateTime.parse(referencia).toUtc(),
        );
    }

    static const detenida = EstadoReproduccion(version: -1, estado: 'detenida', posicionBaseMs: 0);

    final int version;
    final String estado;
    final int posicionBaseMs;
    final String? elementoId;
    final String? recursoAudioId;
    final DateTime? referenciaEn;

    bool get sonando => estado == 'reproduciendo';
}

/// Contrato 5: estado de la cola compartida.
class EstadoCola {
    const EstadoCola({required this.version, required this.pendientes, this.actual, this.reproduccion});

    factory EstadoCola.desdeJson(Map<String, dynamic> json) {
        final actual = json['actual'] as Map<String, dynamic>?;
        final reproduccion = actual?['reproduccion'] as Map<String, dynamic>?;
        return EstadoCola(
            version: (json['version'] as num).toInt(),
            actual: actual == null ? null : ElementoCola.desdeJson(Map<String, dynamic>.from(actual['elemento'] as Map)),
            reproduccion: reproduccion == null ? null : EstadoReproduccion.desdeJson(reproduccion),
            pendientes: [
                for (final e in (json['pendientes'] as List<dynamic>? ?? const []))
                    ElementoCola.desdeJson(Map<String, dynamic>.from(e as Map)),
            ],
        );
    }

    static const vacia = EstadoCola(version: -1, pendientes: []);

    final int version;
    final ElementoCola? actual;
    final EstadoReproduccion? reproduccion;
    final List<ElementoCola> pendientes;
}
