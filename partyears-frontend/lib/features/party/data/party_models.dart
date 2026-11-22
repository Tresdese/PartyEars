class PartyActual {
    const PartyActual({
        required this.id, 
        required this.nombre, 
        required this.codigo, 
        required this.version, 
        required this.anfitrionId, 
        this.finalizadaEn,
    });

    factory PartyActual.desdeJson(Map<String, dynamic> json) => PartyActual(
        id: json['id'] as String,
        nombre: json['nombre'] as String,
        codigo: json['codigo'] as String?,
        version: (json['version'] as num).toInt(),
        anfitrionId: json['anfitrion_id'] as String,
        finalizadaEn: json['finalizada_en'] as String?,
    );

    final String id;
    final String nombre;
    final String? codigo;
    final int version;
    final String anfitrionId;
    final String? finalizadaEn;
}
