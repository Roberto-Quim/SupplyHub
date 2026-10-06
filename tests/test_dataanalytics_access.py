from django.test import SimpleTestCase, override_settings

from supplyhub.services.dataanalytics_access_service import authorize_and_log


class DataAnalyticsAccessTests(SimpleTestCase):
    @override_settings(DATAANALYTICS_ENABLED=False)
    def test_dataanalytics_desactivado_es_passthrough_para_desarrollo(self):
        allowed, id_usuario, id_perfil = authorize_and_log(
            1,
            no_nomina="demo",
            metodo_acceso=3,
        )
        self.assertTrue(allowed)
        self.assertEqual(id_usuario, 0)
        self.assertEqual(id_perfil, 0)
