import uuid

from datetime import datetime, timezone
from channels.layers import get_channel_layer

async def publicar(party_id, tipo, datos, version=None, evento_id=None):
    # Contract 7.3 requires a trailing 'Z'; isoformat() emits '+00:00' for UTC.
    ahora = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    mensaje = {
        'tipo': tipo,
        # The outbox row's id when there is one instead of a new UUID: a resend must carry
        # the same id so clients can drop the duplicate (contract 7.3).
        'evento_id': str(evento_id or uuid.uuid4()),
        'datos': datos,
        'version': version,
        'enviado_en': ahora,
    }

    await get_channel_layer().group_send(f'party_{party_id}',
                                         {'type': 'evento', 'mensaje': mensaje})
