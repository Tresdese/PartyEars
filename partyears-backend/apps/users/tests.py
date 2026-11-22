import uuid
from datetime import timedelta

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.users.models import Sesion, Usuario


def _generar_par_claves():
    privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    privada_pem = privada.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode('utf-8')
    publica_pem = privada.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode('utf-8')
    return privada_pem, publica_pem


CLAVE_PRIVADA_TEST, CLAVE_PUBLICA_TEST = _generar_par_claves()


@override_settings(JWT_CLAVE_PRIVADA=CLAVE_PRIVADA_TEST, JWT_CLAVE_PUBLICA=CLAVE_PUBLICA_TEST)
class AuthEndpointsTests(TestCase):
    URL_REGISTRO = '/api/v1/auth/registro'
    URL_LOGIN = '/api/v1/auth/login'
    URL_RENOVAR = '/api/v1/auth/renovar'
    URL_LOGOUT = '/api/v1/auth/logout'
    URL_USUARIOS = '/api/v1/auth/usuarios'

    def setUp(self):
        self.cliente = APIClient()
        self.datos_validos = {
            'nombre_usuario': 'axel_dev',
            'correo': 'axel@partyears.test',
            'contrasena': 'segura12345',
            'confirmacion': 'segura12345',
        }

    def test_registro_exitoso_guarda_hash_django_y_responde_201(self):
        respuesta = self.cliente.post(self.URL_REGISTRO, self.datos_validos, format='json')
        self.assertEqual(respuesta.status_code, 201)

        cuerpo = respuesta.json()
        uuid.UUID(cuerpo['id'])
        self.assertEqual(cuerpo['nombre_usuario'], 'axel_dev')
        self.assertEqual(cuerpo['correo'], 'axel@partyears.test')
        self.assertTrue(cuerpo['creado_en'].endswith('Z'))

        usuario = Usuario.objects.get(id=cuerpo['id'])
        self.assertNotEqual(usuario.contrasena_hash, 'segura12345')
        self.assertTrue(usuario.verificar_contrasena('segura12345'))

    def test_registro_rechaza_contrasena_menor_a_10_caracteres(self):
        datos = {**self.datos_validos, 'contrasena': 'corta1234', 'confirmacion': 'corta1234'}
        respuesta = self.cliente.post(self.URL_REGISTRO, datos, format='json')
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()['codigo'], 'DATOS_INVALIDOS')
        self.assertIn('contrasena', respuesta.json()['detalles'])

    def test_registro_rechaza_confirmacion_distinta(self):
        datos = {**self.datos_validos, 'confirmacion': 'otra_clave123'}
        respuesta = self.cliente.post(self.URL_REGISTRO, datos, format='json')
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()['codigo'], 'DATOS_INVALIDOS')
        self.assertIn('confirmacion', respuesta.json()['detalles'])

    def test_registro_rechaza_correo_y_nombre_duplicados(self):
        self.cliente.post(self.URL_REGISTRO, self.datos_validos, format='json')

        # Correo duplicado (insensible a mayúsculas)
        dup_correo = {
            'nombre_usuario': 'otro_usuario',
            'correo': 'AXEL@PARTYEARS.TEST',
            'contrasena': 'segura12345',
            'confirmacion': 'segura12345',
        }
        r_correo = self.cliente.post(self.URL_REGISTRO, dup_correo, format='json')
        self.assertEqual(r_correo.status_code, 409)
        self.assertEqual(r_correo.json()['codigo'], 'DUPLICADO')
        self.assertIn('correo', r_correo.json()['detalles'])

        # Nombre de usuario duplicado (insensible a mayúsculas)
        dup_nombre = {
            'nombre_usuario': 'AXEL_DEV',
            'correo': 'nuevo@partyears.test',
            'contrasena': 'segura12345',
            'confirmacion': 'segura12345',
        }
        r_nombre = self.cliente.post(self.URL_REGISTRO, dup_nombre, format='json')
        self.assertEqual(r_nombre.status_code, 409)
        self.assertEqual(r_nombre.json()['codigo'], 'DUPLICADO')
        self.assertIn('nombre_usuario', r_nombre.json()['detalles'])

    def test_login_exitoso_emite_jwt_rs256_con_claims_esperados(self):
        reg = self.cliente.post(self.URL_REGISTRO, self.datos_validos, format='json').json()

        respuesta = self.cliente.post(
            self.URL_LOGIN,
            {'correo': 'axel@partyears.test', 'contrasena': 'segura12345'},
            format='json',
        )
        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertIn('token_acceso', cuerpo)
        self.assertIn('token_renovacion', cuerpo)
        self.assertTrue(cuerpo['expira_en'].endswith('Z'))
        self.assertEqual(cuerpo['usuario']['id'], reg['id'])
        self.assertEqual(cuerpo['usuario']['nombre_usuario'], 'axel_dev')

        claims = jwt.decode(cuerpo['token_acceso'], CLAVE_PUBLICA_TEST, algorithms=['RS256'])
        self.assertEqual(claims['sub'], reg['id'])
        self.assertEqual(claims['nombre_usuario'], 'axel_dev')
        uuid.UUID(claims['sid'])

    def test_login_contrasena_incorrecta_y_correo_inexistente(self):
        self.cliente.post(self.URL_REGISTRO, self.datos_validos, format='json')

        r_pass = self.cliente.post(
            self.URL_LOGIN,
            {'correo': 'axel@partyears.test', 'contrasena': 'incorrecta123'},
            format='json',
        )
        self.assertEqual(r_pass.status_code, 401)
        self.assertEqual(r_pass.json()['codigo'], 'CREDENCIALES_INVALIDAS')

        r_mail = self.cliente.post(
            self.URL_LOGIN,
            {'correo': 'noexiste@partyears.test', 'contrasena': 'segura12345'},
            format='json',
        )
        self.assertEqual(r_mail.status_code, 401)
        self.assertEqual(r_mail.json()['codigo'], 'CREDENCIALES_INVALIDAS')

    def test_login_cuenta_inactiva_responde_403(self):
        reg = self.cliente.post(self.URL_REGISTRO, self.datos_validos, format='json').json()
        Usuario.objects.filter(id=reg['id']).update(activo=False)

        respuesta = self.cliente.post(
            self.URL_LOGIN,
            {'correo': 'axel@partyears.test', 'contrasena': 'segura12345'},
            format='json',
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()['codigo'], 'CUENTA_INACTIVA')

    def test_renovar_rota_token_e_invalida_el_anterior(self):
        self.cliente.post(self.URL_REGISTRO, self.datos_validos, format='json')
        login = self.cliente.post(
            self.URL_LOGIN,
            {'correo': 'axel@partyears.test', 'contrasena': 'segura12345'},
            format='json',
        ).json()

        r_renovar = self.cliente.post(
            self.URL_RENOVAR,
            {'token_renovacion': login['token_renovacion']},
            format='json',
        )
        self.assertEqual(r_renovar.status_code, 200)
        nuevo = r_renovar.json()
        self.assertNotEqual(nuevo['token_renovacion'], login['token_renovacion'])

        # Reutilizar el token anterior debe fallar con 401
        r_reuso = self.cliente.post(
            self.URL_RENOVAR,
            {'token_renovacion': login['token_renovacion']},
            format='json',
        )
        self.assertEqual(r_reuso.status_code, 401)
        self.assertEqual(r_reuso.json()['codigo'], 'TOKEN_INVALIDO')

    def test_logout_revoca_sesion_y_bloquea_operaciones_posteriores(self):
        self.cliente.post(self.URL_REGISTRO, self.datos_validos, format='json')
        login = self.cliente.post(
            self.URL_LOGIN,
            {'correo': 'axel@partyears.test', 'contrasena': 'segura12345'},
            format='json',
        ).json()

        self.cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {login['token_acceso']}")
        r_logout = self.cliente.post(
            self.URL_LOGOUT,
            {'token_renovacion': login['token_renovacion']},
            format='json',
        )
        self.assertEqual(r_logout.status_code, 204)

        # Intentar renovar después de logout falla
        r_renovar = self.cliente.post(
            self.URL_RENOVAR,
            {'token_renovacion': login['token_renovacion']},
            format='json',
        )
        self.assertEqual(r_renovar.status_code, 401)

        # Intentar usar el token de acceso revocado falla
        r_usuarios = self.cliente.get(self.URL_USUARIOS)
        self.assertEqual(r_usuarios.status_code, 401)
        self.assertEqual(r_usuarios.json()['codigo'], 'TOKEN_INVALIDO')

    def test_consultar_usuarios_devuelve_nombres_publicos_sin_correos(self):
        u1 = self.cliente.post(self.URL_REGISTRO, self.datos_validos, format='json').json()
        u2 = self.cliente.post(
            self.URL_REGISTRO,
            {
                'nombre_usuario': 'america_dev',
                'correo': 'america@partyears.test',
                'contrasena': 'segura12345',
                'confirmacion': 'segura12345',
            },
            format='json',
        ).json()

        login = self.cliente.post(
            self.URL_LOGIN,
            {'correo': 'axel@partyears.test', 'contrasena': 'segura12345'},
            format='json',
        ).json()

        self.cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {login['token_acceso']}")
        r_lista = self.cliente.get(f"{self.URL_USUARIOS}?ids={u1['id']},{u2['id']}")
        self.assertEqual(r_lista.status_code, 200)

        resultados = r_lista.json()['resultados']
        self.assertEqual(len(resultados), 2)
        for item in resultados:
            self.assertNotIn('correo', item)
            self.assertIn('id', item)
            self.assertIn('nombre_usuario', item)
