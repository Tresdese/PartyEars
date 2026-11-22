import '../../core/network/api_config.dart';
import '../../core/network/red.dart';
import 'reproductor.dart';

/// Abre en el reproductor el audio de un recurso del catálogo (contrato 3.3).
Future<void> abrirRecurso(Reproductor reproductor, String recursoAudioId, {Duration desde = Duration.zero}) async {
    final red = Red.instancia;
    final tokens = await red.api.tokensVigentes();
    final url = red.config.rest(Servicio.music, '/recursos/$recursoAudioId/audio');

    // TODO(T-16): the token goes in a header instead of a signed URL (contract 3.3); a token
    // that expires mid-song breaks the next seek until the song is reopened with a new one.
    await reproductor.abrir(url, cabeceras: {'Authorization': 'Bearer ${tokens.tokenAcceso}'}, desde: desde);
}
