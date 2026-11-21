class ApiException implements Exception {
    const ApiException({
        required this.codigo,
        required this.mensaje,
        this.detalles,
        this.estadoHttp,
        this.idempotencyKey,
    });

    factory ApiException.desdeRespuesta(int estadoHttp, Object? cuerpo) {
        if (cuerpo is Map && cuerpo['codigo'] is String && cuerpo['mensaje'] is String) {
            final detalles = cuerpo['detalles'];

            return ApiException(
                codigo: cuerpo['codigo'] as String,
                mensaje: cuerpo['mensaje'] as String,
                detalles: detalles is Map ? Map<String, dynamic>.from(detalles) : null,
                estadoHttp: estadoHttp,
            );
        }
        
        if (estadoHttp == 503) {
            return ApiException(
                codigo: 'SERVICIO_NO_DISPONIBLE',
                mensaje: 'El servicio no está disponible. Intenta de nuevo en un momento.',
                estadoHttp: estadoHttp,
            );
        }
        
        return ApiException(
            codigo: respuestaInvalida,
            mensaje: 'El servidor respondió con un error inesperado ($estadoHttp).',
            estadoHttp: estadoHttp,
        );
    }

    static const sinConexion = 'SIN_CONEXION';
    static const tiempoAgotado = 'TIEMPO_AGOTADO';
    static const respuestaInvalida = 'RESPUESTA_INVALIDA';
    static const sesionExpirada = 'SESION_EXPIRADA';

    final String codigo;
    final String mensaje;
    final Map<String, dynamic>? detalles;
    final int? estadoHttp;
    final String? idempotencyKey;

    bool get esDeRed => codigo == sinConexion || codigo == tiempoAgotado;
    bool get esVersionObsoleta => codigo == 'VERSION_OBSOLETA';

    int? get versionActual => (detalles?['version_actual'] as num?)?.toInt();

    List<String>? erroresDe(String campo) {
        final valor = detalles?[campo];
        return valor is List ? valor.map((e) => e.toString()).toList() : null;
    }

    ApiException conClave(String clave) => ApiException(
        codigo: codigo,
        mensaje: mensaje,
        detalles: detalles,
        estadoHttp: estadoHttp,
        idempotencyKey: clave,
    );

    @override
    String toString() => 'ApiException($codigo, http $estadoHttp): $mensaje';
}