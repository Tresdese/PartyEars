import secrets

ALFABETO = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
LONGITUD = 6

def generar_codigo():
    return ''.join(secrets.choice(ALFABETO) for _ in range(LONGITUD))