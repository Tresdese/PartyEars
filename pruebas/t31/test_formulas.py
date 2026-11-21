import unittest

from cliente_sincronizacion import desfase_de_reloj, iso_a_ms, posicion_esperada


class FormulasTests(unittest.TestCase):

    def test_reproduciendo_avanza_desde_la_referencia(self):
        estado = {'estado': 'reproduciendo', 'posicion_base_ms': 45000,
                  'referencia_en': '2026-11-10T18:30:00.000Z'}
        referencia = iso_a_ms(estado['referencia_en'])
        self.assertEqual(posicion_esperada(estado, referencia + 2500), 47500)
        self.assertEqual(posicion_esperada(estado, referencia - 1000), 44000)

    def test_pausada_no_avanza(self):
        estado = {'estado': 'pausada', 'posicion_base_ms': 45000,
                  'referencia_en': '2026-11-10T18:30:00.000Z'}
        self.assertEqual(posicion_esperada(estado, iso_a_ms(estado['referencia_en']) + 9999), 45000)

    def test_desfase_con_ida_y_vuelta_simetrica(self):
        # Server clock 300 ms ahead; 40 ms each way.
        self.assertEqual(desfase_de_reloj(t_cliente=1000, t_servidor=1340, t_recibido=1080), 300)

    def test_iso_con_milisegundos(self):
        self.assertEqual(iso_a_ms('1970-01-01T00:00:01.250Z'), 1250)


if __name__ == '__main__':
    unittest.main()
