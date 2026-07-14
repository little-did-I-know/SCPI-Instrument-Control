"""Tests for the SCPI dialect field on model capabilities."""

from scpi_control.models import MODEL_REGISTRY, detect_model_from_idn


class TestDialectField:
    def test_hd_series_is_modern(self):
        assert MODEL_REGISTRY["SDS824X HD"].dialect == "modern"
        assert MODEL_REGISTRY["SDS804X HD"].dialect == "modern"

    def test_x_e_series_is_legacy(self):
        for model in ("SDS1104X-E", "SDS1204X-E", "SDS1202X-E", "SDS1102X-E"):
            assert MODEL_REGISTRY[model].dialect == "legacy"

    def test_plus_and_5000x_are_modern(self):
        for model in ("SDS2104X Plus", "SDS2204X Plus", "SDS2354X Plus", "SDS5104X", "SDS5054X"):
            assert MODEL_REGISTRY[model].dialect == "modern"

    def test_detection_from_idn_carries_dialect(self):
        legacy = detect_model_from_idn("Siglent Technologies,SDS1104X-E,SN1,1.0")
        modern = detect_model_from_idn("Siglent Technologies,SDS824X HD,SN2,3.8")
        assert legacy.dialect == "legacy"
        assert modern.dialect == "modern"

    def test_unknown_model_falls_back_to_legacy(self):
        cap = detect_model_from_idn("Siglent Technologies,SDS9999Z,SN3,1.0")
        assert cap.dialect == "legacy"

    def test_unknown_hd_model_infers_modern(self):
        cap = detect_model_from_idn("Siglent Technologies,SDS3054X HD,SN4,1.0")
        assert cap.dialect == "modern"
