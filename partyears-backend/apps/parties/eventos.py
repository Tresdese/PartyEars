import uuid

from datetime import datetime, timezone
from channels.layers import get_channel_layer

async def publicar(party_id, tipo, datos, version=None):
    # Contract 7.3 requires a trailing 'Z'; isoformat() emits '+00:00' for UTC.
    ahora = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    mensaje = {
        'tipo': tipo,
        'evento_id': str(uuid.uuid4()),
        'datos': datos,
        'version': version,
        'enviado_en': ahora,
    }

    await get_channel_layer().group_send(f'party_{party_id}', {'type': 'evento', 'mensaje': mensaje})