class MiembroParty {
    const MiembroParty({
        required this.usuarioId,
        required this.puedeAportar,
        required this.puedeModificarCola,
        required this.conectado,
        this.nombreUsuario,
    });

    factory MiembroParty.desdeJson(Map<String, dynamic> json) => MiembroParty(
        usuarioId: json['usuario_id'] as String,
        nombreUsuario: json['nombre_usuario'] as String?,
        puedeAportar: json['puede_aportar'] as bool? ?? false,
        puedeModificarCola: json['puede_modificar_cola'] as bool? ?? false,
        conectado: json['conectado'] as bool? ?? false,
    );

    final String usuarioId;
    final String? nombreUsuario;
    final bool puedeAportar;
    final bool puedeModificarCola;
    final bool conectado;

    String get nombreVisible => nombreUsuario ?? 'Usuario ${usuarioId.substring(0, usuarioId.length.clamp(0, 8))}';
}

class PartyActual {
    const PartyActual({
        required this.id,
        required this.nombre,
        required this.codigo,
        required this.version,
        required this.anfitrionId,
        this.finalizadaEn,
        this.miembros = const [],
    });

    factory PartyActual.desdeJson(Map<String, dynamic> json) => PartyActual(
        id: json['id'] as String,
        nombre: json['nombre'] as String,
        codigo: json['codigo'] as String?,
        version: (json['version'] as num).toInt(),
        anfitrionId: json['anfitrion_id'] as String,
        finalizadaEn: json['finalizada_en'] as String?,
        miembros: [
            for (final m in (json['miembros'] as List<dynamic>? ?? const []))
                MiembroParty.desdeJson(Map<String, dynamic>.from(m as Map)),
        ],
    );

    final String id;
    final String nombre;
    final String? codigo;
    final int version;
    final String anfitrionId;
    final String? finalizadaEn;
    final List<MiembroParty> miembros;

    MiembroParty? miembro(String? usuarioId) {
        for (final m in miembros) {
            if (m.usuarioId == usuarioId) return m;
        }
        return null;
    }
}
